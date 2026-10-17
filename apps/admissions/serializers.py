from rest_framework import serializers
from apps.patients.serializers import PatientSerializer
from apps.departments.serializers import DoctorSerializer
from .models import Ward, Room, Bed, Admission, BedAssignment, InpatientProgressRecord, InpatientCharge


class BedSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    ward_name = serializers.CharField(source='room.ward.name', read_only=True)
    ward_code = serializers.CharField(source='room.ward.code', read_only=True)

    class Meta:
        model = Bed
        fields = [
            'id',
            'room',
            'room_number',
            'ward_name',
            'ward_code',
            'bed_number',
            'bed_type',
            'status',
            'is_active',
        ]


class RoomSerializer(serializers.ModelSerializer):
    beds = BedSerializer(many=True, read_only=True)
    total_beds = serializers.IntegerField(source='beds.count', read_only=True)

    class Meta:
        model = Room
        fields = [
            'id',
            'ward',
            'room_number',
            'room_type',
            'daily_rate',
            'is_active',
            'beds',
            'total_beds',
        ]


class WardSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)
    occupied_beds_count = serializers.IntegerField(read_only=True)
    total_beds_count = serializers.IntegerField(read_only=True)
    available_beds_count = serializers.IntegerField(read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Ward
        fields = [
            'id',
            'name',
            'code',
            'department',
            'department_name',
            'ward_type',
            'floor',
            'total_capacity',
            'daily_base_rate',
            'is_active',
            'occupied_beds_count',
            'total_beds_count',
            'available_beds_count',
            'occupancy_rate',
            'rooms',
        ]


class BedAssignmentSerializer(serializers.ModelSerializer):
    bed_details = BedSerializer(source='bed', read_only=True)
    transferred_by_name = serializers.CharField(source='transferred_by.full_name', read_only=True)

    class Meta:
        model = BedAssignment
        fields = [
            'id',
            'admission',
            'bed',
            'bed_details',
            'assigned_from',
            'assigned_to',
            'is_active',
            'transfer_reason',
            'transferred_by',
            'transferred_by_name',
        ]


class InpatientChargeSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = InpatientCharge
        fields = [
            'id',
            'admission',
            'charge_type',
            'description',
            'unit_price',
            'quantity',
            'total_amount',
            'charge_date',
            'is_billed',
            'created_by',
            'created_by_name',
        ]


class InpatientProgressRecordSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    signed_by_name = serializers.CharField(source='signed_by.full_name', read_only=True)

    class Meta:
        model = InpatientProgressRecord
        fields = [
            'id',
            'admission',
            'author',
            'author_name',
            'record_date',
            'clinical_findings',
            'assessment',
            'orders_and_plan',
            'is_signed',
            'signed_at',
            'signed_by',
            'signed_by_name',
            'version',
            'amendment_reason',
            'created_at',
        ]


class AdmissionListSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)
    patient_gender = serializers.CharField(source='patient.gender', read_only=True)
    doctor_name = serializers.CharField(source='admitting_doctor.name', read_only=True)
    primary_nurse_name = serializers.CharField(source='primary_nurse.full_name', read_only=True)
    current_bed = serializers.SerializerMethodField()

    class Meta:
        model = Admission
        fields = [
            'id',
            'admission_number',
            'patient',
            'patient_name',
            'patient_mrn',
            'patient_gender',
            'admitting_doctor',
            'doctor_name',
            'primary_nurse',
            'primary_nurse_name',
            'admission_date',
            'admission_type',
            'admitting_diagnosis',
            'status',
            'discharge_date',
            'current_bed',
        ]

    def get_current_bed(self, obj):
        active_assignment = obj.current_bed_assignment
        if active_assignment and active_assignment.bed:
            bed = active_assignment.bed
            return {
                'id': bed.id,
                'bed_number': bed.bed_number,
                'room_number': bed.room.room_number,
                'ward_name': bed.room.ward.name,
                'ward_code': bed.room.ward.code,
            }
        return None


class AdmissionDetailSerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    admitting_doctor = DoctorSerializer(read_only=True)
    primary_nurse_name = serializers.CharField(source='primary_nurse.full_name', read_only=True)
    signed_discharge_by_name = serializers.CharField(source='signed_discharge_by.full_name', read_only=True)
    bed_assignments = BedAssignmentSerializer(many=True, read_only=True)
    progress_records = InpatientProgressRecordSerializer(many=True, read_only=True)
    charges = InpatientChargeSerializer(many=True, read_only=True)
    current_bed = serializers.SerializerMethodField()
    total_charges = serializers.SerializerMethodField()

    class Meta:
        model = Admission
        fields = [
            'id',
            'admission_number',
            'patient',
            'admitting_doctor',
            'primary_nurse',
            'primary_nurse_name',
            'admission_date',
            'admission_type',
            'admitting_diagnosis',
            'chief_complaint',
            'status',
            'discharge_date',
            'discharge_disposition',
            'discharge_summary',
            'discharge_instructions',
            'follow_up_date',
            'is_signed_discharge',
            'signed_discharge_by',
            'signed_discharge_by_name',
            'signed_discharge_at',
            'current_bed',
            'bed_assignments',
            'progress_records',
            'charges',
            'total_charges',
            'created_at',
            'updated_at',
        ]

    def get_current_bed(self, obj):
        active_assignment = obj.current_bed_assignment
        if active_assignment and active_assignment.bed:
            bed = active_assignment.bed
            return {
                'id': bed.id,
                'bed_number': bed.bed_number,
                'room_number': bed.room.room_number,
                'ward_name': bed.room.ward.name,
                'ward_code': bed.room.ward.code,
            }
        return None

    def get_total_charges(self, obj):
        return sum(c.total_amount for c in obj.charges.all())


class AdmissionCreateSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField(required=True)
    admitting_doctor_id = serializers.IntegerField(required=True)
    bed_id = serializers.IntegerField(required=True)
    admission_type = serializers.ChoiceField(choices=Admission.ADMISSION_TYPE_CHOICES, default='ELECTIVE')
    admitting_diagnosis = serializers.CharField(required=True)
    chief_complaint = serializers.CharField(required=False, allow_blank=True, default='')
    primary_nurse_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class BedTransferSerializer(serializers.Serializer):
    target_bed_id = serializers.IntegerField(required=True)
    transfer_reason = serializers.CharField(required=True)


class DischargeSerializer(serializers.Serializer):
    discharge_summary = serializers.CharField(required=True)
    discharge_instructions = serializers.CharField(required=False, allow_blank=True, default='')
    discharge_disposition = serializers.ChoiceField(
        choices=Admission.DISCHARGE_DISPOSITION_CHOICES,
        default='ROUTINE_HOME'
    )
    follow_up_date = serializers.DateField(required=False, allow_null=True, default=None)
