import uuid
from datetime import date
from django.db import models
from django.db.models import Sum, Q, UniqueConstraint
from django.conf import settings
from django.utils import timezone
from apps.common.models import TimeStampedModel


def generate_po_number() -> str:
    return f"PO-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_grn_number() -> str:
    return f"GRN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_dispense_number() -> str:
    return f"DISP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_ref_code() -> str:
    return f"ADJ-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=200, db_index=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'pharmacy_supplier'
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class MedicineCatalogue(TimeStampedModel):
    DOSAGE_FORM_CHOICES = [
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('SYRUP', 'Syrup / Oral Liquid'),
        ('INJECTION', 'Injection / Infusion'),
        ('OINTMENT', 'Ointment / Cream'),
        ('DROPS', 'Eye/Ear Drops'),
        ('INHALER', 'Inhaler / Resp'),
        ('OTHER', 'Other Form'),
    ]

    UNIT_CHOICES = [
        ('TABLET', 'Tablet'),
        ('STRIP', 'Strip'),
        ('BOX', 'Box'),
        ('BOTTLE', 'Bottle'),
        ('VIAL', 'Vial'),
        ('AMPOULE', 'Ampoule'),
        ('TUBE', 'Tube'),
        ('PIECE', 'Piece'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, db_index=True)
    generic_name = models.CharField(max_length=200, db_index=True)
    category = models.CharField(max_length=100, db_index=True)
    dosage_form = models.CharField(max_length=50, choices=DOSAGE_FORM_CHOICES, default='TABLET')
    strength = models.CharField(max_length=100, help_text="e.g. 500 mg, 10 mg/ml")
    unit_of_measure = models.CharField(max_length=50, choices=UNIT_CHOICES, default='STRIP')
    reorder_level = models.PositiveIntegerField(default=20)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_prescription_required = models.BooleanField(default=True)
    is_controlled_substance = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'pharmacy_medicine_catalogue'
        verbose_name = 'Medicine Catalogue Item'
        verbose_name_plural = 'Medicine Catalogue'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.generic_name} {self.strength})"

    @property
    def total_stock(self) -> int:
        result = self.batches.filter(
            status='ACTIVE',
            expiry_date__gt=timezone.now().date()
        ).aggregate(total=Sum('quantity_on_hand'))
        return result['total'] or 0

    @property
    def is_low_stock(self) -> bool:
        return self.total_stock <= self.reorder_level


class StockBatch(TimeStampedModel):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active / Available'),
        ('EXPIRED', 'Expired'),
        ('QUARANTINED', 'Quarantined'),
        ('RECALLED', 'Recalled'),
    ]

    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT, related_name='batches')
    batch_number = models.CharField(max_length=100, db_index=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(db_index=True)
    quantity_on_hand = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unit_sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)

    class Meta:
        db_table = 'pharmacy_stock_batch'
        verbose_name = 'Stock Batch'
        verbose_name_plural = 'Stock Batches'
        ordering = ['expiry_date', 'id']
        constraints = [
            UniqueConstraint(fields=['medication', 'batch_number'], name='unique_medication_batch')
        ]

    def __str__(self):
        return f"{self.medication.name} - Batch {self.batch_number} (Qty: {self.quantity_on_hand}, Exp: {self.expiry_date})"

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < timezone.now().date() or self.status == 'EXPIRED'


class StockMovementLedger(models.Model):
    MOVEMENT_TYPES = [
        ('PURCHASE_RECEIPT', 'Purchase Goods Receipt'),
        ('DISPENSE', 'Prescription Dispense'),
        ('RETURN', 'Return to Stock'),
        ('WASTAGE', 'Wastage / Damage / Expired Discard'),
        ('ADJUSTMENT_IN', 'Inventory Audit Adjustment (+)'),
        ('ADJUSTMENT_OUT', 'Inventory Audit Adjustment (-)'),
    ]

    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT, related_name='stock_movements')
    batch = models.ForeignKey(StockBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements')
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPES, db_index=True)
    quantity = models.IntegerField(help_text="Signed quantity change (+ for stock in, - for stock out)")
    balance_after = models.IntegerField(help_text="Snapshot of batch quantity on hand after transaction")
    reference_type = models.CharField(max_length=50, help_text="e.g. GOODS_RECEIPT, DISPENSE, AUDIT")
    reference_id = models.CharField(max_length=100, db_index=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'pharmacy_stock_ledger'
        verbose_name = 'Stock Movement Ledger'
        verbose_name_plural = 'Stock Movement Ledgers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} | {self.medication.name} | {self.movement_type} | Qty: {self.quantity}"


class PurchaseOrder(TimeStampedModel):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted / Placed'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CANCELLED', 'Cancelled'),
    ]

    po_number = models.CharField(max_length=50, unique=True, default=generate_po_number, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    order_date = models.DateField(default=timezone.localdate)
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_orders'
    )

    class Meta:
        db_table = 'pharmacy_purchase_order'
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name} ({self.status})"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT, related_name='po_items')
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'pharmacy_po_item'
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'

    def save(self, *args, **kwargs):
        self.total_price = self.quantity_ordered * self.unit_price
        super().save(*args, **kwargs)


class GoodsReceipt(TimeStampedModel):
    grn_number = models.CharField(max_length=50, unique=True, default=generate_grn_number, db_index=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goods_receipts'
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='goods_receipts')
    received_date = models.DateField(default=timezone.localdate)
    invoice_number = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_goods'
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'pharmacy_goods_receipt'
        verbose_name = 'Goods Receipt Note (GRN)'
        verbose_name_plural = 'Goods Receipt Notes (GRN)'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.grn_number} from {self.supplier.name}"


class GoodsReceiptItem(models.Model):
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=100)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    quantity_received = models.PositiveIntegerField()
    unit_purchase_cost = models.DecimalField(max_digits=10, decimal_places=2)
    unit_sale_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'pharmacy_grn_item'
        verbose_name = 'Goods Receipt Item'
        verbose_name_plural = 'Goods Receipt Items'


class DispenseRecord(TimeStampedModel):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('PARTIAL', 'Partially Dispensed'),
        ('CANCELLED', 'Cancelled'),
    ]

    dispense_number = models.CharField(max_length=50, unique=True, default=generate_dispense_number, db_index=True)
    prescription = models.ForeignKey(
        'clinical.Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensations'
    )
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='medication_dispensations')
    pharmacist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='dispensed_prescriptions'
    )
    dispense_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED', db_index=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'pharmacy_dispense_record'
        verbose_name = 'Dispense Record'
        verbose_name_plural = 'Dispense Records'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.dispense_number} for {self.patient.full_name} ({self.status})"


class DispenseItem(models.Model):
    dispense_record = models.ForeignKey(DispenseRecord, on_delete=models.CASCADE, related_name='items')
    prescription_item = models.ForeignKey(
        'clinical.PrescriptionItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensed_items'
    )
    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT)
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    quantity_prescribed = models.PositiveIntegerField(default=1)
    quantity_dispensed = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    directions = models.TextField(blank=True)

    class Meta:
        db_table = 'pharmacy_dispense_item'
        verbose_name = 'Dispense Item'
        verbose_name_plural = 'Dispense Items'

    def save(self, *args, **kwargs):
        self.total_price = self.quantity_dispensed * self.unit_price
        super().save(*args, **kwargs)


class WastageReturnRecord(TimeStampedModel):
    RECORD_TYPE_CHOICES = [
        ('WASTAGE', 'Wastage / Discard'),
        ('RETURN', 'Stock Return'),
    ]

    REASON_CHOICES = [
        ('EXPIRED', 'Expired Medication'),
        ('DAMAGED', 'Damaged Packaging / Broken'),
        ('PATIENT_RETURN', 'Unused Return from Patient'),
        ('SUPPLIER_RETURN', 'Return to Supplier (Recall/Defect)'),
        ('DISCREPANCY', 'Inventory Audit Discrepancy'),
    ]

    record_type = models.CharField(max_length=20, choices=RECORD_TYPE_CHOICES, db_index=True)
    reference_number = models.CharField(max_length=50, unique=True, default=generate_ref_code, db_index=True)
    medication = models.ForeignKey(MedicineCatalogue, on_delete=models.PROTECT)
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        db_table = 'pharmacy_wastage_return'
        verbose_name = 'Wastage & Return Record'
        verbose_name_plural = 'Wastage & Return Records'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.record_type}: {self.medication.name} (Qty: {self.quantity}) - {self.reason}"
