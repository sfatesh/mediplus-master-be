import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import TimeStampedModel


def generate_invoice_number() -> str:
    return f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_receipt_number() -> str:
    return f"REC-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_refund_number() -> str:
    return f"REF-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_claim_number() -> str:
    return f"CLM-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class ServiceCatalogue(TimeStampedModel):
    CATEGORY_CHOICES = [
        ('CONSULTATION', 'Doctor Consultation'),
        ('LABORATORY', 'Laboratory Diagnostic'),
        ('PHARMACY', 'Pharmacy / Medication'),
        ('INPATIENT_BED', 'Inpatient Ward & Bed'),
        ('PROCEDURE', 'Clinical / Surgical Procedure'),
        ('EMERGENCY', 'Emergency Care'),
        ('OTHER', 'General Hospital Service'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, db_index=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='CONSULTATION', db_index=True)
    standard_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Tax percentage, e.g. 5.0 for 5%")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'billing_service_catalogue'
        verbose_name = 'Service Catalogue Item'
        verbose_name_plural = 'Service Catalogue'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} [{self.code}] (${self.standard_rate})"


class InsurancePolicy(TimeStampedModel):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='insurance_policies')
    provider_name = models.CharField(max_length=150, db_index=True)
    policy_number = models.CharField(max_length=100, db_index=True)
    group_number = models.CharField(max_length=100, blank=True)
    coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80.00'), help_text="e.g. 80.0 for 80%")
    max_coverage_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('10000.00'))
    valid_until = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'billing_insurance_policy'
        verbose_name = 'Insurance Policy'
        verbose_name_plural = 'Insurance Policies'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider_name} #{self.policy_number} for {self.patient.full_name}"

    @property
    def is_valid(self) -> bool:
        return self.is_active and self.valid_until >= timezone.now().date()


class Invoice(TimeStampedModel):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued / Pending Payment'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Fully Paid'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, default=generate_invoice_number, db_index=True)
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='invoices')
    encounter = models.ForeignKey(
        'clinical.Encounter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    admission = models.ForeignKey(
        'admissions.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)

    # Monetary amounts (strictly decimal)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=200, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices'
    )

    class Meta:
        db_table = 'billing_invoice'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} - {self.patient.full_name} (${self.total_amount} - {self.status})"

    def recalculate_totals(self):
        items = self.items.all()
        calc_subtotal = Decimal('0.00')
        calc_tax = Decimal('0.00')
        calc_item_discounts = Decimal('0.00')

        for item in items:
            calc_subtotal += (Decimal(str(item.quantity)) * Decimal(str(item.unit_price)))
            calc_tax += Decimal(str(item.tax_amount or 0))
            calc_item_discounts += Decimal(str(item.discount_amount or 0))

        self.subtotal = calc_subtotal
        effective_discount = self.discount_amount if self.discount_amount > 0 else calc_item_discounts
        self.discount_amount = effective_discount
        self.tax_amount = calc_tax

        self.total_amount = max(Decimal('0.00'), (self.subtotal - self.discount_amount) + self.tax_amount)
        self.balance_due = max(Decimal('0.00'), self.total_amount - self.amount_paid)

        if self.status not in ['CANCELLED', 'REFUNDED']:
            if self.balance_due <= Decimal('0.00') and self.total_amount > Decimal('0.00'):
                self.status = 'PAID'
            elif self.amount_paid > Decimal('0.00') and self.balance_due > Decimal('0.00'):
                self.status = 'PARTIALLY_PAID'
            elif self.status == 'DRAFT':
                self.status = 'DRAFT'
            else:
                self.status = 'ISSUED'


class InvoiceItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('CONSULTATION', 'Doctor Consultation'),
        ('LABORATORY', 'Laboratory Test'),
        ('PHARMACY', 'Medication / Dispense'),
        ('INPATIENT_BED', 'Inpatient Ward Bed'),
        ('PROCEDURE', 'Procedure / Surgery'),
        ('OTHER', 'Other Service'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=30, choices=ITEM_TYPE_CHOICES, default='OTHER')
    service = models.ForeignKey(ServiceCatalogue, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    # Cross-module trace references
    encounter_id = models.IntegerField(null=True, blank=True)
    lab_order_item_id = models.IntegerField(null=True, blank=True)
    dispense_record_id = models.IntegerField(null=True, blank=True)
    inpatient_charge_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'billing_invoice_item'
        verbose_name = 'Invoice Item'
        verbose_name_plural = 'Invoice Items'

    def save(self, *args, **kwargs):
        line_base = (Decimal(str(self.quantity)) * Decimal(str(self.unit_price))) - Decimal(str(self.discount_amount or 0))
        self.total_price = max(Decimal('0.00'), line_base + Decimal(str(self.tax_amount or 0)))
        super().save(*args, **kwargs)


class Payment(TimeStampedModel):
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Credit / Debit Card'),
        ('BANK_TRANSFER', 'Bank Wire / ACH'),
        ('MOBILE_MONEY', 'Mobile Money / Digital Wallet'),
        ('INSURANCE', 'Insurance Direct Settlement'),
        ('GATEWAY_ONLINE', 'Online Payment Gateway'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('COMPLETED', 'Completed / Verified'),
        ('FAILED', 'Failed / Declined'),
        ('REFUNDED', 'Refunded'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, default=generate_receipt_number, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='CASH')
    
    # Idempotency & duplicate protection:
    transaction_reference = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Unique external transaction ID, gateway reference, or generated idempotency token"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED', db_index=True)
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_payments'
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'billing_payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-paid_at']

    def __str__(self):
        return f"{self.receipt_number} - ${self.amount} via {self.payment_method} ({self.status})"


class Refund(TimeStampedModel):
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested / Pending Approval'),
        ('APPROVED', 'Approved by Finance Admin'),
        ('PROCESSED', 'Processed & Disbursed'),
        ('REJECTED', 'Rejected'),
    ]

    refund_number = models.CharField(max_length=50, unique=True, default=generate_refund_number, db_index=True)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='refunds')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='refunds')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(help_text="Clinical, administrative or billing discrepancy reason")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED', db_index=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_refunds'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_refunds'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_refund'
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.refund_number} - ${self.amount} ({self.status})"


class InsuranceClaim(TimeStampedModel):
    STATUS_CHOICES = [
        ('SUBMITTED', 'Claim Submitted to Payor'),
        ('UNDER_REVIEW', 'Under Payor Adjudication'),
        ('APPROVED', 'Approved by Insurer'),
        ('REJECTED', 'Denied / Rejected'),
        ('SETTLED', 'Payment Settled'),
    ]

    claim_number = models.CharField(max_length=50, unique=True, default=generate_claim_number, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='claims')
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.PROTECT, related_name='claims')
    claimed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED', db_index=True)
    adjudication_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_insurance_claim'
        verbose_name = 'Insurance Claim'
        verbose_name_plural = 'Insurance Claims'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.claim_number} - {self.policy.provider_name} (${self.claimed_amount}) [{self.status}]"


class InvoiceAdjustment(models.Model):
    ADJUSTMENT_TYPE_CHOICES = [
        ('DISCOUNT_AMENDMENT', 'Authorized Discount Applied'),
        ('CORRECTION', 'Clerical / Clinical Correction'),
        ('WRITE_OFF', 'Bad Debt Write-Off'),
        ('CHARGE_REVERSAL', 'Charge Reversal'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPE_CHOICES)
    previous_total = models.DecimalField(max_digits=12, decimal_places=2)
    new_total = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(help_text="Mandatory audit explanation for financial adjustment")
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    adjusted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'billing_invoice_adjustment'
        verbose_name = 'Invoice Adjustment'
        verbose_name_plural = 'Invoice Adjustments'
        ordering = ['-adjusted_at']

    def __str__(self):
        return f"{self.adjustment_type} on {self.invoice.invoice_number}: ${self.difference}"
