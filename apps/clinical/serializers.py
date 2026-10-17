from rest_framework import serializers
from .models import Encounter, ClinicalNote, Prescription, PrescriptionItem


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = [
            'id',
            'medication_name',
            'dosage',
            'frequency',
            'duration',
            'route',
            'quantity',
            'instructions'
        ]


class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, required=False)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    prescriber_name = serializers.CharField(source='prescriber.full_name', read_only=True)

    class Meta:
        model = Prescription
        fields = [
            'id',
            'prescription_number',
            'encounter',
            'patient',
            'patient_name',
            'prescriber',
            'prescriber_name',
            'status',
            'authorized_at',
            'clinical_instructions',
            'items',
            'created_at'
        ]
        read_only_fields = ['id', 'prescription_number', 'authorized_at', 'created_at']
        extra_kwargs = {
            'encounter': {'required': False},
            'patient': {'required': False},
            'prescriber': {'required': False}
        }

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        prescription = Prescription.objects.create(**validated_data)
        for item_data in items_data:
            PrescriptionItem.objects.create(prescription=prescription, **item_data)
        return prescription


class ClinicalNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    signed_by_name = serializers.CharField(source='signed_by.full_name', read_only=True)

    class Meta:
        model = ClinicalNote
        fields = [
            'id',
            'encounter',
            'author',
            'author_name',
            'subjective',
            'objective',
            'assessment',
            'plan',
            'diagnoses',
            'follow_up_instructions',
            'follow_up_date',
            'is_signed',
            'signed_at',
            'signed_by',
            'signed_by_name',
            'version',
            'amendment_reason',
            'previous_version',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'author', 'is_signed', 'signed_at', 'signed_by',
            'version', 'previous_version', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'encounter': {'required': False},
            'author': {'required': False}
        }


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    token_number = serializers.CharField(source='queue_entry.token_number', read_only=True)
    clinical_notes = ClinicalNoteSerializer(many=True, read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = [
            'id',
            'encounter_number',
            'patient',
            'patient_name',
            'patient_mrn',
            'doctor',
            'doctor_name',
            'attending_user',
            'appointment',
            'queue_entry',
            'token_number',
            'encounter_type',
            'status',
            'started_at',
            'completed_at',
            'chief_complaint',
            'vitals',
            'clinical_notes',
            'prescriptions',
            'created_at'
        ]
        read_only_fields = ['id', 'encounter_number', 'started_at', 'completed_at', 'created_at']


class StartEncounterSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    doctor_id = serializers.IntegerField()
    appointment_id = serializers.IntegerField(required=False, allow_null=True)
    queue_entry_id = serializers.IntegerField(required=False, allow_null=True)
    encounter_type = serializers.ChoiceField(choices=Encounter.ENCOUNTER_TYPE_CHOICES, default='OUTPATIENT')
    chief_complaint = serializers.CharField(required=False, allow_blank=True)
    vitals = serializers.JSONField(required=False, default=dict)


class AmendNoteSerializer(serializers.Serializer):
    amendment_reason = serializers.CharField(required=True)
    subjective = serializers.CharField(required=True)
    objective = serializers.CharField(required=True)
    assessment = serializers.CharField(required=True)
    plan = serializers.CharField(required=True)
    diagnoses = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    follow_up_instructions = serializers.CharField(required=False, allow_blank=True)
    follow_up_date = serializers.DateField(required=False, allow_null=True)
