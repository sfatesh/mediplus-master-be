import uuid
from django.db import models
from apps.common.models import TimeStampedModel
from apps.departments.models import Department, Doctor


def generate_ref_no() -> str:
    return f"MED-{uuid.uuid4().hex[:8].upper()}"


class DoctorSchedule(TimeStampedModel):
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='working_schedules')
    day_of_week = models.IntegerField(choices=DAY_CHOICES, db_index=True)
    start_time = models.TimeField(default='09:00:00')
    end_time = models.TimeField(default='17:00:00')
    slot_duration_minutes = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'appointments_doctor_schedule'
        verbose_name = 'Doctor Working Schedule'
        verbose_name_plural = 'Doctor Working Schedules'
        unique_together = ('doctor', 'day_of_week')

    def __str__(self):
        return f"{self.doctor.name} - {self.get_day_of_week_display()} ({self.start_time}-{self.end_time})"


class DoctorLeave(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='scheduled_leaves')
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    reason = models.CharField(max_length=255)
    is_approved = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'appointments_doctor_leave'
        verbose_name = 'Doctor Leave'
        verbose_name_plural = 'Doctor Leaves'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.doctor.name} Leave ({self.start_date} to {self.end_date})"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('IN_CONSULTATION', 'In Consultation'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('RESCHEDULED', 'Rescheduled'),
        ('NO_SHOW', 'No Show'),
    ]

    id = models.BigAutoField(primary_key=True)
    reference_number = models.CharField(max_length=50, unique=True, default=generate_ref_no, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=50)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments', db_column='department_id')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments', db_column='doctor_id')
    appointment_date = models.CharField(max_length=50)
    appointment_time = models.CharField(max_length=50)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'appointments'
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference_number} - {self.first_name} {self.last_name} ({self.status})"

    @property
    def patient_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class QueueEntry(TimeStampedModel):
    QUEUE_TYPE_CHOICES = [
        ('SCHEDULED', 'Scheduled Appointment'),
        ('WALK_IN', 'Walk-in Registration'),
        ('EMERGENCY', 'Emergency Evaluation'),
    ]

    STATUS_CHOICES = [
        ('WAITING', 'Waiting in OPD Queue'),
        ('CALLED', 'Called to Doctor Cabin'),
        ('IN_CONSULTATION', 'In Consultation'),
        ('COMPLETED', 'Consultation Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]

    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='queue_entries')
    patient = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='queue_entries')
    patient_name = models.CharField(max_length=150)
    patient_phone = models.CharField(max_length=50, blank=True, null=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='queue_entries')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='queue_entries')
    token_number = models.CharField(max_length=20, db_index=True)
    queue_date = models.DateField(db_index=True)
    queue_type = models.CharField(max_length=20, choices=QUEUE_TYPE_CHOICES, default='SCHEDULED')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='WAITING', db_index=True)
    priority = models.IntegerField(default=1, help_text="1: Regular, 2: Priority/Elderly/Child, 3: Urgent/Trauma")
    check_in_time = models.DateTimeField(auto_now_add=True)
    called_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'appointments_queue_entry'
        verbose_name = 'OPD Queue Entry'
        verbose_name_plural = 'OPD Queue Entries'
        ordering = ['-priority', 'check_in_time']
        indexes = [
            models.Index(fields=['doctor', 'queue_date', 'status']),
            models.Index(fields=['queue_date', 'status']),
        ]
        unique_together = ('doctor', 'queue_date', 'token_number')

    def __str__(self):
        return f"{self.token_number} - {self.patient_name} with {self.doctor.name} ({self.status})"
