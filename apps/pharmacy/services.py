from datetime import timedelta
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import Role
from apps.audit.services import log_audit_event
from .models import (
    Supplier,
    MedicineCatalogue,
    StockBatch,
    StockMovementLedger,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem,
    DispenseRecord,
    DispenseItem,
    WastageReturnRecord,
)


def receive_goods_shipment(receipt_data: dict, items_data: list, user) -> GoodsReceipt:
    """
    Receives incoming goods into pharmacy inventory with atomic batch updates and ledger logging.
    """
    with transaction.atomic():
        supplier_id = receipt_data.get('supplier_id') or receipt_data.get('supplier')
        supplier = Supplier.objects.get(id=supplier_id)
        
        po = None
        po_id = receipt_data.get('purchase_order_id') or receipt_data.get('purchase_order')
        if po_id:
            po = PurchaseOrder.objects.filter(id=po_id).first()

        grn = GoodsReceipt.objects.create(
            supplier=supplier,
            purchase_order=po,
            received_date=receipt_data.get('received_date', timezone.now().date()),
            invoice_number=receipt_data.get('invoice_number', ''),
            received_by=user,
            notes=receipt_data.get('notes', '')
        )

        for item in items_data:
            med_id = item.get('medication_id') or item.get('medication')
            medication = MedicineCatalogue.objects.get(id=med_id)
            batch_no = item['batch_number'].strip()
            qty = int(item['quantity_received'])
            unit_cost = Decimal(str(item.get('unit_purchase_cost', 0)))
            unit_sale_price = Decimal(str(item.get('unit_sale_price', medication.unit_price)))
            expiry_date = item['expiry_date']
            mfg_date = item.get('manufacture_date')

            GoodsReceiptItem.objects.create(
                goods_receipt=grn,
                medication=medication,
                batch_number=batch_no,
                manufacture_date=mfg_date,
                expiry_date=expiry_date,
                quantity_received=qty,
                unit_purchase_cost=unit_cost,
                unit_sale_price=unit_sale_price,
            )

            # Update or create StockBatch
            batch, created = StockBatch.objects.select_for_update().get_or_create(
                medication=medication,
                batch_number=batch_no,
                defaults={
                    'expiry_date': expiry_date,
                    'manufacture_date': mfg_date,
                    'quantity_on_hand': qty,
                    'unit_cost': unit_cost,
                    'unit_sale_price': unit_sale_price,
                    'status': 'ACTIVE',
                }
            )

            if not created:
                batch.quantity_on_hand += qty
                batch.unit_cost = unit_cost
                batch.unit_sale_price = unit_sale_price
                if batch.status == 'EXPIRED' and str(batch.expiry_date) >= str(timezone.now().date()):
                    batch.status = 'ACTIVE'
                batch.save()

            # Record in immutable Stock Movement Ledger
            StockMovementLedger.objects.create(
                medication=medication,
                batch=batch,
                movement_type='PURCHASE_RECEIPT',
                quantity=qty,
                balance_after=batch.quantity_on_hand,
                reference_type='GOODS_RECEIPT',
                reference_id=grn.grn_number,
                unit_cost=unit_cost,
                notes=f"Received via GRN {grn.grn_number}",
                created_by=user,
            )

            # Link to PO Item if applicable
            if po:
                po_item = po.items.filter(medication=medication).first()
                if po_item:
                    po_item.quantity_received += qty
                    po_item.save()

        if po:
            # Check if all items in PO are fully received
            all_received = all(i.quantity_received >= i.quantity_ordered for i in po.items.all())
            po.status = 'RECEIVED' if all_received else 'PARTIALLY_RECEIVED'
            po.save()

        log_audit_event(
            action='PHARMACY_GOODS_RECEIVED',
            entity_type='GoodsReceipt',
            entity_id=grn.id,
            user=user,
            details={'grn_number': grn.grn_number, 'supplier': supplier.name, 'items_count': len(items_data)}
        )
        return grn


def dispense_prescription_items(prescription_id: int, items_to_dispense: list, user, notes: str = '') -> DispenseRecord:
    """
    Dispenses prescribed medications with strict checks:
    - Enforces Pharmacist or Admin permission.
    - Prevents dispensing expired stock.
    - Locks batches under concurrency with select_for_update().
    - Validates against duplicate or over-dispensing for the same prescription.
    - Records immutable StockMovementLedger entries.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if user.role not in [Role.PHARMACIST, Role.ADMIN, Role.SUPER_ADMIN] and not user.is_superuser:
        raise PermissionDenied("Only licensed pharmacists or administrators can dispense prescription medication.")

    from apps.clinical.models import Prescription, PrescriptionItem
    from apps.patients.models import Patient

    with transaction.atomic():
        prescription = Prescription.objects.select_for_update().get(id=prescription_id)
        if prescription.status == 'CANCELLED':
            raise ValidationError("Cannot dispense a cancelled prescription.")

        total_dispense_amount = Decimal('0.00')
        dispense_record = DispenseRecord.objects.create(
            prescription=prescription,
            patient=prescription.patient,
            pharmacist=user,
            status='COMPLETED',
            total_amount=Decimal('0.00'),
            notes=notes
        )

        for req_item in items_to_dispense:
            med_id = req_item.get('medication_id') or req_item.get('medication')
            qty_to_dispense = int(req_item['quantity'])
            if qty_to_dispense <= 0:
                raise ValidationError("Quantity to dispense must be greater than zero.")

            medication = MedicineCatalogue.objects.get(id=med_id)

            # Check prescription item link if supplied
            presc_item_id = req_item.get('prescription_item_id') or req_item.get('prescription_item')
            presc_item = None
            if presc_item_id:
                presc_item = PrescriptionItem.objects.select_for_update().get(id=presc_item_id, prescription=prescription)
                
                # Check previous total dispensed for this prescription item
                prev_dispensed = DispenseItem.objects.filter(
                    prescription_item=presc_item,
                    dispense_record__status__in=['COMPLETED', 'PARTIAL']
                ).aggregate(total=models.Sum('quantity_dispensed'))['total'] or 0

                if prev_dispensed + qty_to_dispense > presc_item.quantity:
                    raise ValidationError(
                        f"Cannot dispense {qty_to_dispense} units of {medication.name}. "
                        f"Prescribed: {presc_item.quantity}, Already dispensed: {prev_dispensed}."
                    )

            # Select target batch (or automatically select earliest non-expired batch via FEFO)
            batch_id = req_item.get('batch_id') or req_item.get('batch')
            if batch_id:
                batch = StockBatch.objects.select_for_update().get(id=batch_id, medication=medication)
            else:
                # FEFO - First Expiry First Out
                batch = StockBatch.objects.select_for_update().filter(
                    medication=medication,
                    status='ACTIVE',
                    expiry_date__gt=timezone.now().date(),
                    quantity_on_hand__gte=qty_to_dispense
                ).order_by('expiry_date').first()

                if not batch:
                    raise ValidationError(
                        f"No non-expired active batch with sufficient stock ({qty_to_dispense}) found for {medication.name}."
                    )

            # Rule: Prevent expired stock from being dispensed!
            if batch.is_expired:
                raise ValidationError(
                    f"Batch {batch.batch_number} for {medication.name} is expired (Expiry: {batch.expiry_date}) and cannot be dispensed."
                )

            # Rule: Stock check
            if batch.quantity_on_hand < qty_to_dispense:
                raise ValidationError(
                    f"Insufficient stock in batch {batch.batch_number} for {medication.name}. "
                    f"Available: {batch.quantity_on_hand}, Requested: {qty_to_dispense}."
                )

            # Deduct stock
            batch.quantity_on_hand -= qty_to_dispense
            batch.save()

            item_unit_price = batch.unit_sale_price or medication.unit_price
            line_total = Decimal(str(qty_to_dispense)) * item_unit_price
            total_dispense_amount += line_total

            DispenseItem.objects.create(
                dispense_record=dispense_record,
                prescription_item=presc_item,
                medication=medication,
                batch=batch,
                quantity_prescribed=presc_item.quantity if presc_item else qty_to_dispense,
                quantity_dispensed=qty_to_dispense,
                unit_price=item_unit_price,
                total_price=line_total,
                directions=(req_item.get('directions') or (presc_item.instructions if presc_item else '') or '')
            )

            # Record in immutable Stock Movement Ledger
            StockMovementLedger.objects.create(
                medication=medication,
                batch=batch,
                movement_type='DISPENSE',
                quantity=-qty_to_dispense,
                balance_after=batch.quantity_on_hand,
                reference_type='PRESCRIPTION_DISPENSE',
                reference_id=dispense_record.dispense_number,
                unit_cost=batch.unit_cost,
                notes=f"Dispensed for Prescription {prescription.prescription_number} ({prescription.patient.full_name})",
                created_by=user,
            )

        dispense_record.total_amount = total_dispense_amount
        dispense_record.save()

        # Update prescription status
        total_prescribed = sum(i.quantity for i in prescription.items.all()) if prescription.items.exists() else 0
        total_dispensed = DispenseItem.objects.filter(
            dispense_record__prescription=prescription
        ).aggregate(total=models.Sum('quantity_dispensed'))['total'] or 0

        if total_prescribed > 0 and total_dispensed < total_prescribed:
            prescription.status = 'PARTIAL' if hasattr(prescription, 'status') else 'AUTHORIZED'
            dispense_record.status = 'PARTIAL'
            dispense_record.save()
        else:
            prescription.status = 'DISPENSED'
        
        prescription.save()

        log_audit_event(
            action='PHARMACY_MEDICATION_DISPENSED',
            entity_type='DispenseRecord',
            entity_id=dispense_record.id,
            user=user,
            details={
                'dispense_number': dispense_record.dispense_number,
                'prescription': prescription.prescription_number,
                'patient': prescription.patient.full_name,
                'total_amount': str(total_dispense_amount)
            }
        )
        return dispense_record


def record_wastage_or_return(record_type: str, medication_id: int, batch_id: int, quantity: int, reason: str, notes: str, user) -> WastageReturnRecord:
    """
    Records stock returns or wastage / expired disposal with ledger updates.
    """
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    with transaction.atomic():
        medication = MedicineCatalogue.objects.get(id=medication_id)
        batch = StockBatch.objects.select_for_update().get(id=batch_id, medication=medication)

        if record_type == 'WASTAGE':
            if batch.quantity_on_hand < quantity:
                raise ValidationError(f"Cannot discard {quantity} units. Batch only has {batch.quantity_on_hand} units available.")
            batch.quantity_on_hand -= quantity
            ledger_qty = -quantity
            movement_type = 'WASTAGE'
        elif record_type == 'RETURN':
            batch.quantity_on_hand += quantity
            ledger_qty = quantity
            movement_type = 'RETURN'
        else:
            raise ValidationError("Invalid record type. Must be 'WASTAGE' or 'RETURN'.")

        batch.save()

        record = WastageReturnRecord.objects.create(
            record_type=record_type,
            medication=medication,
            batch=batch,
            quantity=quantity,
            reason=reason,
            notes=notes,
            processed_by=user
        )

        StockMovementLedger.objects.create(
            medication=medication,
            batch=batch,
            movement_type=movement_type,
            quantity=ledger_qty,
            balance_after=batch.quantity_on_hand,
            reference_type='WASTAGE_RETURN',
            reference_id=record.reference_number,
            unit_cost=batch.unit_cost,
            notes=f"{record_type} ({reason}): {notes}",
            created_by=user,
        )

        log_audit_event(
            action=f'PHARMACY_{record_type}',
            entity_type='WastageReturnRecord',
            entity_id=record.id,
            user=user,
            details={'reference_number': record.reference_number, 'quantity': quantity, 'reason': reason}
        )
        return record


def get_inventory_alerts() -> dict:
    """
    Calculates low-stock items and near-expiry / expired batches across the pharmacy catalogue.
    """
    today = timezone.now().date()
    sixty_days_ahead = today + timedelta(days=60)

    # Low stock medications
    all_meds = MedicineCatalogue.objects.filter(is_active=True).prefetch_related('batches')
    low_stock = []
    for med in all_meds:
        current_qty = med.total_stock
        if current_qty <= med.reorder_level:
            low_stock.append({
                'id': med.id,
                'code': med.code,
                'name': med.name,
                'generic_name': med.generic_name,
                'total_stock': current_qty,
                'reorder_level': med.reorder_level,
                'unit_of_measure': med.unit_of_measure,
            })

    # Expired batches
    expired_batches = StockBatch.objects.filter(
        expiry_date__lt=today,
        quantity_on_hand__gt=0
    ).select_related('medication')

    # Expiring within 60 days
    near_expiry = StockBatch.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=sixty_days_ahead,
        quantity_on_hand__gt=0
    ).select_related('medication')

    return {
        'low_stock_count': len(low_stock),
        'low_stock_items': low_stock,
        'expired_batches_count': expired_batches.count(),
        'expired_batches': [
            {
                'id': b.id,
                'medication_name': b.medication.name,
                'batch_number': b.batch_number,
                'quantity_on_hand': b.quantity_on_hand,
                'expiry_date': b.expiry_date,
            } for b in expired_batches
        ],
        'near_expiry_count': near_expiry.count(),
        'near_expiry_batches': [
            {
                'id': b.id,
                'medication_name': b.medication.name,
                'batch_number': b.batch_number,
                'quantity_on_hand': b.quantity_on_hand,
                'expiry_date': b.expiry_date,
                'days_remaining': (b.expiry_date - today).days,
            } for b in near_expiry
        ]
    }
