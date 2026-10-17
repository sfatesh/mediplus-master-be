from rest_framework import serializers
from django.db import transaction
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from .models import Appointment, DoctorSchedule, DoctorLeave, QueueEntry


class DoctorScheduleSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = DoctorSchedule
        fields = [
            'id',
            'doctor',
            'doctor_name',
            'day_of_week',
            'day_name',
            'start_time',
            'end_time',
            'slot_duration_minutes',
            'is_active'
        ]


class DoctorLeaveSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)

    class Meta:
        model = DoctorLeave
        fields = [
            'id',
            'doctor',
            'doctor_name',
            'start_date',
            'end_date',
            'reason',
            'is_approved',
            'created_at'
        ]


class QueueEntrySerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.medical_record_number', read_only=True)

    class Meta:
        model = QueueEntry
        fields = [
            'id',
            'token_number',
            'appointment',
            'patient',
            'patient_name',
            'patient_phone',
            'patient_mrn',
            'doctor',
            'doctor_name',
            'department',
            'department_name',
            'queue_date',
            'queue_type',
            'status',
            'priority',
            'check_in_time',
            'called_time',
            'completed_time'
        ]
        read_only_fields = ['id', 'token_number', 'check_in_time']


class AppointmentSerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department', required=False, allow_null=True
    )
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(), source='doctor', required=False, allow_null=True
    )
    department_name = serializers.CharField(source='department.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'reference_number', 'first_name', 'last_name', 'email', 'phone',
            'department_id', 'department_name', 'doctor_id', 'doctor_name',
            'appointment_date', 'appointment_time', 'message', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'reference_number', 'status', 'created_at']

    def validate(self, attrs):
        doctor = attrs.get('doctor')
        apt_date = attrs.get('appointment_date')
        apt_time = attrs.get('appointment_time')

        if doctor and apt_date and apt_time:
            # 1. Check if doctor is on approved leave
            on_leave = DoctorLeave.objects.filter(
                doctor=doctor,
                start_date__lte=apt_date,
                end_date__gte=apt_date,
                is_approved=True
            ).exists()
            if on_leave:
                raise serializers.ValidationError({
                    "appointment_date": f"Dr. {doctor.name} is on scheduled leave on {apt_date}."
                })

            # 2. Check for duplicate booking at the same date and time
            conflict = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=apt_date,
                appointment_time=apt_time
            ).exclude(status__in=['CANCELLED', 'RESCHEDULED', 'NO_SHOW'])

            if self.instance:
                conflict = conflict.exclude(pk=self.instance.pk)

            if conflict.exists():
                raise serializers.ValidationError({
                    "appointment_time": f"This appointment slot ({apt_time} on {apt_date}) is already booked for Dr. {doctor.name}."
                })

        return attrs


class AppointmentRescheduleSerializer(serializers.Serializer):
    appointment_date = serializers.CharField(required=True)
    appointment_time = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class AppointmentCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(required=False, allow_blank=True)


class WalkInRegistrationSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField(required=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    patient_id = serializers.IntegerField(required=False, allow_null=True)
    patient_name = serializers.CharField(required=True)
    patient_phone = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.IntegerField(default=1)
    chief_complaint = serializers.CharField(required=False, allow_blank=True)
