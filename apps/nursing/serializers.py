from rest_framework import serializers
from .models import (
    NursePatientAssignment,
    VitalObservation,
    NursingCareNote,
    NursingTask,
    MedicationAdministrationRecord,
    ShiftHandover,
)


class NursePatientAssignmentSerializer(serializers.ModelSerializer):
    nurse_name = serializers.CharField(source='nurse.full_name', read_only=True)
    patient_name = serializers.CharField(source='admission.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='admission.patient.medical_record_number', read_only=True)
    bed_number = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()

    class Meta:
        model = NursePatientAssignment
        fields = [
            'id',
            'nurse',
            'nurse_name',
            'admission',
            'patient_name',
            'patient_mrn',
            'bed_number',
            'ward_name',
            'shift',
            'assignment_date',
            'is_active',
            'notes',
            'created_at',
        ]

    def get_bed_number(self, obj):
        assignment = obj.admission.current_bed_assignment
        return assignment.bed.bed_number if assignment and assignment.bed else 'Unassigned'

    def get_ward_name(self, obj):
        assignment = obj.admission.current_bed_assignment
        return assignment.bed.room.ward.name if assignment and assignment.bed else 'Unassigned'


class VitalObservationSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    patient_name = serializers.CharField(source='admission.patient.full_name', read_only=True)

    class Meta:
        model = VitalObservation
        fields = [
            'id',
            'admission',
            'patient_name',
            'recorded_by',
            'recorded_by_name',
            'recorded_at',
            'temperature_c',
            'pulse_rate',
            'blood_pressure_systolic',
            'blood_pressure_diastolic',
            'respiratory_rate',
            'spo2_percent',
            'pain_score',
            'gcs_score',
            'fluid_intake_ml',
            'fluid_output_ml',
            'is_critical',
            'critical_alert_reasons',
            'action_taken',
            'created_at',
        ]


class NursingCareNoteSerializer(serializers.ModelSerializer):
    nurse_name = serializers.CharField(source='nurse.full_name', read_only=True)

    class Meta:
        model = NursingCareNote
        fields = [
            'id',
            'admission',
            'nurse',
            'nurse_name',
            'shift',
            'note_type',
            'content',
            'tasks_performed',
            'is_signed',
            'signed_at',
            'created_at',
        ]


class NursingTaskSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)

    class Meta:
        model = NursingTask
        fields = [
            'id',
            'admission',
            'title',
            'description',
            'due_time',
            'status',
            'priority',
            'completed_at',
            'completed_by',
            'completed_by_name',
            'notes',
            'created_at',
        ]


class MedicationAdministrationRecordSerializer(serializers.ModelSerializer):
    administered_by_name = serializers.CharField(source='administered_by.full_name', read_only=True)
    patient_name = serializers.CharField(source='admission.patient.full_name', read_only=True)

    class Meta:
        model = MedicationAdministrationRecord
        fields = [
            'id',
            'admission',
            'patient_name',
            'prescription_item',
            'medication_name',
            'dose',
            'route',
            'scheduled_time',
            'administered_time',
            'status',
            'administered_by',
            'administered_by_name',
            'remarks',
            'created_at',
        ]


class ShiftHandoverSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    outgoing_nurse_name = serializers.CharField(source='outgoing_nurse.full_name', read_only=True)
    incoming_nurse_name = serializers.CharField(source='incoming_nurse.full_name', read_only=True)

    class Meta:
        model = ShiftHandover
        fields = [
            'id',
            'ward',
            'ward_name',
            'shift',
            'handover_date',
            'outgoing_nurse',
            'outgoing_nurse_name',
            'incoming_nurse',
            'incoming_nurse_name',
            'general_ward_summary',
            'patient_summaries',
            'is_acknowledged',
            'acknowledged_at',
            'created_at',
        ]
