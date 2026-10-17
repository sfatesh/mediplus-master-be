from rest_framework import serializers
from .models import (
    LabTestCatalogue,
    LabTestParameter,
    LabOrder,
    LabOrderItem,
    LabSpecimen,
    LabResult,
    LabResultParameterValue,
)


class LabTestParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTestParameter
        fields = [
            'id',
            'name',
            'unit',
            'reference_range_min',
            'reference_range_max',
            'reference_range_text',
            'critical_low',
            'critical_high',
            'sort_order',
        ]


class LabTestCatalogueSerializer(serializers.ModelSerializer):
    parameters = LabTestParameterSerializer(many=True, read_only=True)

    class Meta:
        model = LabTestCatalogue
        fields = [
            'id',
            'code',
            'name',
            'category',
            'specimen_type',
            'container_type',
            'specimen_volume_required',
            'turnaround_time_hours',
            'price',
            'description',
            'is_active',
            'parameters',
            'created_at',
        ]


class LabSpecimenSerializer(serializers.ModelSerializer):
    collected_by_name = serializers.CharField(source='collected_by.full_name', read_only=True)

    class Meta:
        model = LabSpecimen
        fields = [
            'id',
            'accession_number',
            'order',
            'specimen_type',
            'collected_by',
            'collected_by_name',
            'collected_at',
            'status',
            'rejection_reason',
            'notes',
            'created_at',
        ]


class LabResultParameterValueSerializer(serializers.ModelSerializer):
    parameter_name = serializers.CharField(source='parameter.name', read_only=True)
    unit = serializers.CharField(source='parameter.unit', read_only=True)

    class Meta:
        model = LabResultParameterValue
        fields = [
            'id',
            'parameter',
            'parameter_name',
            'unit',
            'value',
            'numeric_value',
            'flag',
            'reference_range_display',
        ]


class LabResultSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True)
    released_by_name = serializers.CharField(source='released_by.full_name', read_only=True)
    test_name = serializers.CharField(source='order_item.lab_test.name', read_only=True)
    test_code = serializers.CharField(source='order_item.lab_test.code', read_only=True)
    patient_name = serializers.CharField(source='order_item.order.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='order_item.order.patient.medical_record_number', read_only=True)
    parameter_values = LabResultParameterValueSerializer(many=True, read_only=True)

    class Meta:
        model = LabResult
        fields = [
            'id',
            'order_item',
            'test_name',
            'test_code',
            'patient_name',
            'patient_mrn',
            'status',
            'overall_interpretation',
            'summary_notes',
            'is_critical',
            'critical_alert_sent',
            'critical_acknowledged',
            'recorded_by',
            'recorded_by_name',
            'recorded_at',
            'verified_by',
            'verified_by_name',
            'verified_at',
            'is_released',
            'released_by',
            'released_by_name',
            'released_at',
            'version',
            'is_corrected',
            'correction_reason',
            'parameter_values',
            'created_at',
        ]


class LabOrderItemSerializer(serializers.ModelSerializer):
    lab_test_name = serializers.CharField(source='lab_test.name', read_only=True)
    lab_test_code = serializers.CharField(source='lab_test.code', read_only=True)
    category = serializers.CharField(source='lab_test.category', read_only=True)
    specimen_type = serializers.CharField(source='lab_test.specimen_type', read_only=True)
    result = LabResultSerializer(read_only=True)

    class Meta:
        model = LabOrderItem
        fields = [
            'id',
            'order',
            'lab_test',
            'lab_test_name',
            'lab_test_code',
            'category',
            'specimen_type',
            'status',
            'result',
            'created_at',
        ]


class LabOrderSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
    ordering_doctor_name = serializers.CharField(source='ordering_doctor.name', read_only=True)
    items = LabOrderItemSerializer(many=True, read_only=True)
    specimens = LabSpecimenSerializer(many=True, read_only=True)

    class Meta:
        model = LabOrder
        fields = [
            'id',
            'order_number',
            'patient',
            'patient_name',
            'patient_mrn',
            'ordering_doctor',
            'ordering_doctor_name',
            'encounter',
            'admission',
            'clinical_indication',
            'priority',
            'status',
            'ordered_at',
            'items',
            'specimens',
            'created_at',
        ]
