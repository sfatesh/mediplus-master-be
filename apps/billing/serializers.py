from rest_framework import serializers
from .models import (
    ServiceCatalogue,
    InsurancePolicy,
    Invoice,
    InvoiceItem,
    Payment,
    Refund,
    InsuranceClaim,
    InvoiceAdjustment,
)


class ServiceCatalogueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCatalogue
        fields = [
            'id',
            'code',
            'name',
            'category',
            'standard_rate',
            'tax_rate_percent',
            'description',
            'is_active',
            'created_at',
        ]


class InsurancePolicySerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = InsurancePolicy
        fields = [
            'id',
            'patient',
            'patient_name',
            'provider_name',
            'policy_number',
            'group_number',
            'coverage_percentage',
            'max_coverage_amount',
            'valid_until',
            'is_valid',
            'is_active',
            'created_at',
        ]


class InvoiceItemSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            'id',
            'invoice',
            'item_type',
            'service',
            'service_name',
            'description',
            'quantity',
            'unit_price',
            'discount_amount',
            'tax_amount',
            'total_price',
            'encounter_id',
            'lab_order_item_id',
            'dispense_record_id',
            'inpatient_charge_id',
        ]


class PaymentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    received_by_name = serializers.CharField(source='received_by.full_name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'receipt_number',
            'invoice',
            'invoice_number',
            'patient',
            'patient_name',
            'amount',
            'payment_method',
            'transaction_reference',
            'status',
            'paid_at',
            'received_by',
            'received_by_name',
            'notes',
            'created_at',
        ]


class RefundSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source='payment.receipt_number', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id',
            'refund_number',
            'payment',
            'receipt_number',
            'invoice',
            'invoice_number',
            'amount',
            'reason',
            'status',
            'requested_by',
            'requested_by_name',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'processed_at',
            'created_at',
        ]


class InsuranceClaimSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    provider_name = serializers.CharField(source='policy.provider_name', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            'id',
            'claim_number',
            'invoice',
            'invoice_number',
            'policy',
            'provider_name',
            'policy_number',
            'claimed_amount',
            'approved_amount',
            'status',
            'adjudication_notes',
            'submitted_at',
            'settled_at',
            'created_at',
        ]


class InvoiceAdjustmentSerializer(serializers.ModelSerializer):
    adjusted_by_name = serializers.CharField(source='adjusted_by.full_name', read_only=True)

    class Meta:
        model = InvoiceAdjustment
        fields = [
            'id',
            'invoice',
            'adjustment_type',
            'previous_total',
            'new_total',
            'difference',
            'reason',
            'adjusted_by',
            'adjusted_by_name',
            'adjusted_at',
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    adjustments = InvoiceAdjustmentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'patient',
            'patient_name',
            'patient_mrn',
            'encounter',
            'admission',
            'issue_date',
            'due_date',
            'status',
            'subtotal',
            'discount_amount',
            'discount_reason',
            'tax_amount',
            'total_amount',
            'amount_paid',
            'balance_due',
            'notes',
            'created_by',
            'created_by_name',
            'items',
            'payments',
            'refunds',
            'adjustments',
            'created_at',
        ]
