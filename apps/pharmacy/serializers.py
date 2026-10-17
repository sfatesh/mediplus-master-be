from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
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


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'code',
            'contact_person',
            'phone',
            'email',
            'address',
            'license_number',
            'tax_id',
            'is_active',
            'created_at',
        ]


class StockBatchSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockBatch
        fields = [
            'id',
            'medication',
            'medication_name',
            'batch_number',
            'manufacture_date',
            'expiry_date',
            'quantity_on_hand',
            'unit_cost',
            'unit_sale_price',
            'status',
            'is_expired',
            'created_at',
        ]


class MedicineCatalogueSerializer(serializers.ModelSerializer):
    total_stock = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    batches = StockBatchSerializer(many=True, read_only=True)

    class Meta:
        model = MedicineCatalogue
        fields = [
            'id',
            'code',
            'name',
            'generic_name',
            'category',
            'dosage_form',
            'strength',
            'unit_of_measure',
            'reorder_level',
            'unit_price',
            'is_prescription_required',
            'is_controlled_substance',
            'description',
            'is_active',
            'total_stock',
            'is_low_stock',
            'batches',
            'created_at',
        ]


class StockMovementLedgerSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = StockMovementLedger
        fields = [
            'id',
            'medication',
            'medication_name',
            'batch',
            'batch_number',
            'movement_type',
            'quantity',
            'balance_after',
            'reference_type',
            'reference_id',
            'unit_cost',
            'notes',
            'created_by',
            'created_by_name',
            'created_at',
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id',
            'medication',
            'medication_name',
            'quantity_ordered',
            'quantity_received',
            'unit_price',
            'total_price',
        ]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'po_number',
            'supplier',
            'supplier_name',
            'order_date',
            'expected_delivery_date',
            'status',
            'total_amount',
            'notes',
            'created_by',
            'created_by_name',
            'items',
            'created_at',
        ]


class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)

    class Meta:
        model = GoodsReceiptItem
        fields = [
            'id',
            'medication',
            'medication_name',
            'batch_number',
            'manufacture_date',
            'expiry_date',
            'quantity_received',
            'unit_purchase_cost',
            'unit_sale_price',
        ]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.full_name', read_only=True)
    items = GoodsReceiptItemSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceipt
        fields = [
            'id',
            'grn_number',
            'purchase_order',
            'supplier',
            'supplier_name',
            'received_date',
            'invoice_number',
            'received_by',
            'received_by_name',
            'notes',
            'items',
            'created_at',
        ]


class DispenseItemSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)

    class Meta:
        model = DispenseItem
        fields = [
            'id',
            'prescription_item',
            'medication',
            'medication_name',
            'batch',
            'batch_number',
            'quantity_prescribed',
            'quantity_dispensed',
            'unit_price',
            'total_price',
            'directions',
        ]


class DispenseRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
    pharmacist_name = serializers.CharField(source='pharmacist.full_name', read_only=True)
    items = DispenseItemSerializer(many=True, read_only=True)

    class Meta:
        model = DispenseRecord
        fields = [
            'id',
            'dispense_number',
            'prescription',
            'patient',
            'patient_name',
            'patient_mrn',
            'pharmacist',
            'pharmacist_name',
            'dispense_date',
            'status',
            'total_amount',
            'notes',
            'items',
            'created_at',
        ]


class WastageReturnRecordSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True)

    class Meta:
        model = WastageReturnRecord
        fields = [
            'id',
            'record_type',
            'reference_number',
            'medication',
            'medication_name',
            'batch',
            'batch_number',
            'quantity',
            'reason',
            'notes',
            'processed_by',
            'processed_by_name',
            'created_at',
        ]
