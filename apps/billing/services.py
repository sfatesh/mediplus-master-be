from decimal import Decimal
from datetime import timedelta
from django.db import transaction, models
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import Role
from apps.audit.services import log_audit_event
from .models import (
    ServiceCatalogue,
    Invoice,
    InvoiceItem,
    Payment,
    Refund,
    InsurancePolicy,
    InsuranceClaim,
    InvoiceAdjustment,
)


def create_invoice(
    patient_id: int,
    items_data: list,
    user,
    due_date=None,
    discount_amount=Decimal('0.00'),
    discount_reason: str = '',
    encounter_id: int = None,
    admission_id: int = None,
    notes: str = ''
) -> Invoice:
    """
    Creates an itemized patient invoice with strict server-side calculation and validation.
    """
    from apps.patients.models import Patient

    if not items_data:
        raise ValidationError("At least one line item is required to generate an invoice.")

    with transaction.atomic():
        patient = Patient.objects.get(id=patient_id)
        
        if not due_date:
            due_date = timezone.now().date() + timedelta(days=30)

        invoice = Invoice.objects.create(
            patient=patient,
            encounter_id=encounter_id,
            admission_id=admission_id,
            due_date=due_date,
            status='ISSUED',
            discount_amount=Decimal(str(discount_amount or 0)),
            discount_reason=discount_reason,
            notes=notes,
            created_by=user
        )

        for item_data in items_data:
            qty = int(item_data.get('quantity', 1))
            unit_price = Decimal(str(item_data['unit_price']))
            disc = Decimal(str(item_data.get('discount_amount', 0)))
            tax = Decimal(str(item_data.get('tax_amount', 0)))

            if qty <= 0:
                raise ValidationError("Quantity must be greater than zero.")
            if unit_price < Decimal('0.00'):
                raise ValidationError("Unit price cannot be negative.")

            srv_id = item_data.get('service_id') or item_data.get('service')
            service = ServiceCatalogue.objects.filter(id=srv_id).first() if srv_id else None

            InvoiceItem.objects.create(
                invoice=invoice,
                item_type=item_data.get('item_type', 'OTHER'),
                service=service,
                description=item_data['description'],
                quantity=qty,
                unit_price=unit_price,
                discount_amount=disc,
                tax_amount=tax,
                encounter_id=item_data.get('encounter_id'),
                lab_order_item_id=item_data.get('lab_order_item_id'),
                dispense_record_id=item_data.get('dispense_record_id'),
                inpatient_charge_id=item_data.get('inpatient_charge_id')
            )

        invoice.recalculate_totals()
        invoice.save()

        log_audit_event(
            action='BILLING_INVOICE_CREATED',
            entity_type='Invoice',
            entity_id=invoice.id,
            user=user,
            details={
                'invoice_number': invoice.invoice_number,
                'patient': patient.full_name,
                'total_amount': str(invoice.total_amount),
                'items_count': len(items_data)
            }
        )
        return invoice


def record_payment(
    invoice_id: int,
    amount: Decimal,
    payment_method: str,
    transaction_reference: str,
    user,
    notes: str = ''
) -> Payment:
    """
    Records a payment against an invoice with:
    - Decimal validation
    - Concurrency lock via select_for_update()
    - Idempotency protection against duplicate retries or webhook callbacks
    - Exact allocation reducing balance_due
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError("Payment amount must be greater than zero.")

    ref = transaction_reference.strip()
    if not ref:
        raise ValidationError("A transaction reference is required for payment tracing.")

    with transaction.atomic():
        # Idempotency check:
        existing = Payment.objects.filter(transaction_reference=ref).first()
        if existing:
            if existing.status == 'COMPLETED':
                return existing
            raise ValidationError(f"Transaction reference '{ref}' is already associated with payment #{existing.receipt_number}.")

        invoice = Invoice.objects.select_for_update().get(id=invoice_id)
        if invoice.status in ['CANCELLED', 'REFUNDED']:
            raise ValidationError(f"Cannot process payment for an invoice with status '{invoice.status}'.")

        if invoice.balance_due <= Decimal('0.00'):
            raise ValidationError(f"Invoice {invoice.invoice_number} is already fully paid.")

        if amount > invoice.balance_due:
            raise ValidationError(
                f"Payment amount (${amount}) exceeds outstanding balance (${invoice.balance_due}) on invoice {invoice.invoice_number}."
            )

        payment = Payment.objects.create(
            invoice=invoice,
            patient=invoice.patient,
            amount=amount,
            payment_method=payment_method,
            transaction_reference=ref,
            status='COMPLETED',
            received_by=user,
            notes=notes
        )

        invoice.amount_paid += amount
        invoice.recalculate_totals()
        invoice.save()

        log_audit_event(
            action='BILLING_PAYMENT_PROCESSED',
            entity_type='Payment',
            entity_id=payment.id,
            user=user,
            details={
                'receipt_number': payment.receipt_number,
                'invoice_number': invoice.invoice_number,
                'amount': str(amount),
                'method': payment_method,
                'balance_due_remaining': str(invoice.balance_due)
            }
        )
        try:
            from apps.notifications.services import send_notification
            from apps.notifications.models import Notification
            send_notification(
                title=f"Payment Recorded: ${payment.amount}",
                message=f"Receipt {payment.receipt_number} issued for Invoice {invoice.invoice_number} ({payment.patient.full_name}).",
                notification_type=Notification.NotificationType.BILLING_EVENT,
                target_role=Role.ADMIN,
                link='/billing',
                severity=Notification.Severity.SUCCESS
            )
        except Exception:
            pass
        return payment


def request_refund(payment_id: int, amount: Decimal, reason: str, user) -> Refund:
    """
    Submits a refund request for an existing payment.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal('0.00'):
        raise ValidationError("Refund amount must be greater than zero.")

    if not reason.strip():
        raise ValidationError("A clear reason is required to request a refund.")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)
        if payment.status != 'COMPLETED':
            raise ValidationError("Refunds can only be requested for completed payments.")

        # Check total previous approved/processed refunds on this payment
        prev_refunds = payment.refunds.filter(status__in=['APPROVED', 'PROCESSED', 'REQUESTED']).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        if prev_refunds + amount > payment.amount:
            raise ValidationError(
                f"Cannot refund ${amount}. Payment total is ${payment.amount}, already refunded/requested: ${prev_refunds}."
            )

        refund = Refund.objects.create(
            payment=payment,
            invoice=payment.invoice,
            amount=amount,
            reason=reason,
            status='REQUESTED',
            requested_by=user
        )

        log_audit_event(
            action='BILLING_REFUND_REQUESTED',
            entity_type='Refund',
            entity_id=refund.id,
            user=user,
            details={
                'refund_number': refund.refund_number,
                'amount': str(amount),
                'receipt_number': payment.receipt_number
            }
        )
        return refund


def approve_and_process_refund(refund_id: int, user) -> Refund:
    """
    Approves and disburses a refund. Enforces Admin or financial manager permission.
    Updates invoice balance due accordingly.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    if not user.is_admin and not user.has_app_permission('billing.refund_approve'):
        raise PermissionDenied("Only financial administrators can approve and process refunds.")

    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(id=refund_id)
        if refund.status == 'PROCESSED':
            raise ValidationError("This refund has already been processed.")
        if refund.status == 'REJECTED':
            raise ValidationError("Cannot process a rejected refund.")

        invoice = Invoice.objects.select_for_update().get(id=refund.invoice_id)
        payment = refund.payment

        # Update refund status
        now = timezone.now()
        refund.status = 'PROCESSED'
        refund.approved_by = user
        refund.approved_at = now
        refund.processed_at = now
        refund.save()

        # Deduct from invoice amount_paid
        invoice.amount_paid = max(Decimal('0.00'), invoice.amount_paid - refund.amount)
        invoice.recalculate_totals()
        if invoice.amount_paid == Decimal('0.00'):
            invoice.status = 'REFUNDED'
        invoice.save()

        # Check if entire payment is refunded
        total_proc_refunds = payment.refunds.filter(status='PROCESSED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if total_proc_refunds >= payment.amount:
            payment.status = 'REFUNDED'
            payment.save()

        log_audit_event(
            action='BILLING_REFUND_PROCESSED',
            entity_type='Refund',
            entity_id=refund.id,
            user=user,
            details={
                'refund_number': refund.refund_number,
                'amount': str(refund.amount),
                'invoice_number': invoice.invoice_number
            }
        )
        return refund


def adjust_invoice(
    invoice_id: int,
    adjustment_type: str,
    new_discount: Decimal,
    reason: str,
    user
) -> InvoiceAdjustment:
    """
    Auditable invoice adjustment workflow for discounts, clerical fixes, or charge reversals.
    """
    if not reason.strip():
        raise ValidationError("Mandatory explanation reason is required for invoice financial adjustments.")

    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(id=invoice_id)
        prev_total = invoice.total_amount

        invoice.discount_amount = Decimal(str(new_discount))
        invoice.recalculate_totals()
        invoice.save()

        diff = invoice.total_amount - prev_total

        adj = InvoiceAdjustment.objects.create(
            invoice=invoice,
            adjustment_type=adjustment_type,
            previous_total=prev_total,
            new_total=invoice.total_amount,
            difference=diff,
            reason=reason,
            adjusted_by=user
        )

        log_audit_event(
            action='BILLING_INVOICE_ADJUSTED',
            entity_type='InvoiceAdjustment',
            entity_id=adj.id,
            user=user,
            details={
                'invoice_number': invoice.invoice_number,
                'difference': str(diff),
                'reason': reason
            }
        )
        return adj


def get_financial_summary_report(start_date=None, end_date=None) -> dict:
    """
    Aggregates financial analytics and revenue reconciliation.
    """
    invoices = Invoice.objects.all()
    payments = Payment.objects.filter(status='COMPLETED')
    refunds = Refund.objects.filter(status='PROCESSED')

    if start_date:
        invoices = invoices.filter(issue_date__gte=start_date)
        payments = payments.filter(paid_at__date__gte=start_date)
        refunds = refunds.filter(processed_at__date__gte=start_date)

    if end_date:
        invoices = invoices.filter(issue_date__lte=end_date)
        payments = payments.filter(paid_at__date__lte=end_date)
        refunds = refunds.filter(processed_at__date__lte=end_date)

    total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_collected = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_outstanding = invoices.exclude(status__in=['CANCELLED', 'REFUNDED']).aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    total_discounts = invoices.aggregate(total=Sum('discount_amount'))['total'] or Decimal('0.00')
    total_refunded = refunds.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Payment methods breakdown
    pm_stats = payments.values('payment_method').annotate(
        total_amount=Sum('amount'),
        tx_count=Count('id')
    ).order_by('-total_amount')

    # Status count
    status_stats = invoices.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('total_amount')
    )

    return {
        'total_invoiced': total_invoiced,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'total_discounts': total_discounts,
        'total_refunded': total_refunded,
        'net_revenue': total_collected - total_refunded,
        'payment_methods': list(pm_stats),
        'invoice_statuses': list(status_stats)
    }
