from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import TimeStampedModel
from apps.admissions.models import Admission, Ward
from apps.clinical.models import PrescriptionItem


class NursePatientAssignment(TimeStampedModel):
    SHIFT_CHOICES = [
        ('MORNING', 'Morning Shift (07:00 - 15:30)'),
        ('EVENING', 'Evening Shift (15:00 - 23:30)'),
        ('NIGHT', 'Night Shift (23:00 - 07:30)'),
    ]

    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='nurse_patient_assignments'
    )
    admission = models.ForeignKey(
        Admission,
        on_delete=models.CASCADE,
        related_name='nurse_assignments'
    )
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='MORNING')
    assignment_date = models.DateField(default=timezone.localdate, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authorized_nurse_assignments'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'nursing_patient_assignment'
        verbose_name = 'Nurse Patient Assignment'
        verbose_name_plural = 'Nurse Patient Assignments'
        ordering = ['-assignment_date', 'shift']
        unique_together = ('nurse', 'admission', 'shift', 'assignment_date')

    def __str__(self):
        return f"{self.nurse.full_name} -> {self.admission.patient.full_name} ({self.shift} on {self.assignment_date})"


class VitalObservation(TimeStampedModel):
    admission = models.ForeignKey(
        Admission,
        on_delete=models.CASCADE,
        related_name='vital_observations'
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recorded_vitals'
    )
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Core Clinical Vital Parameters
    temperature_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Core temperature in Celsius (Normal: 36.1 - 37.2 °C)"
    )
    pulse_rate = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Heart rate / pulse in beats per minute (Normal: 60 - 100 bpm)"
    )
    blood_pressure_systolic = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Systolic arterial pressure in mmHg (Normal: 90 - 120 mmHg)"
    )
    blood_pressure_diastolic = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Diastolic arterial pressure in mmHg (Normal: 60 - 80 mmHg)"
    )
    respiratory_rate = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Respirations per minute (Normal: 12 - 20 bpm)"
    )
    spo2_percent = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Peripheral capillary oxygen saturation in % (Normal: 95 - 100%)"
    )
    pain_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Visual Analog Scale pain score from 0 (None) to 10 (Worst Possible)"
    )
    gcs_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Glasgow Coma Scale total score (3 - 15)"
    )
    fluid_intake_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Oral / IV fluid intake volume in milliliters"
    )
    fluid_output_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Urine / drain fluid output volume in milliliters"
    )

    # Automated Critical Alert Evaluation
    is_critical = models.BooleanField(default=False, db_index=True)
    critical_alert_reasons = models.JSONField(
        default=list,
        blank=True,
        help_text="Specific threshold violations flagged automatically"
    )
    action_taken = models.TextField(
        blank=True,
        null=True,
        help_text="Immediate nursing actions, physician escalation, or oxygen applied"
    )

    class Meta:
        db_table = 'nursing_vital_observation'
        verbose_name = 'Vital Observation'
        verbose_name_plural = 'Vital Observations'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['admission', 'recorded_at']),
            models.Index(fields=['is_critical', 'recorded_at']),
        ]

    def __str__(self):
        alert_str = " [CRITICAL ALERT]" if self.is_critical else ""
        return f"Vitals for {self.admission.patient.full_name} at {self.recorded_at.strftime('%Y-%m-%d %H:%M')}{alert_str}"


class NursingCareNote(TimeStampedModel):
    NOTE_TYPE_CHOICES = [
        ('GENERAL_NOTE', 'General Shift Nursing Note'),
        ('CARE_PLAN', 'Nursing Care Plan Evaluation'),
        ('WOUND_CARE', 'Wound Assessment & Dressing'),
        ('POST_OP', 'Post-Operative Recovery Note'),
        ('INCIDENT', 'Clinical Incident Report'),
        ('CRITICAL_EVENT', 'Clinical Deterioration / Code Event'),
    ]

    SHIFT_CHOICES = [
        ('MORNING', 'Morning'),
        ('EVENING', 'Evening'),
        ('NIGHT', 'Night'),
    ]

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='nursing_notes')
    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authored_nursing_notes'
    )
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='MORNING')
    note_type = models.CharField(max_length=30, choices=NOTE_TYPE_CHOICES, default='GENERAL_NOTE')
    content = models.TextField(help_text="Detailed narrative of patient nursing care and responses")
    tasks_performed = models.JSONField(default=list, blank=True)
    is_signed = models.BooleanField(default=True, db_index=True)
    signed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'nursing_care_note'
        verbose_name = 'Nursing Care Note'
        verbose_name_plural = 'Nursing Care Notes'
        ordering = ['-signed_at']

    def __str__(self):
        return f"{self.note_type} ({self.shift}) by {self.nurse.full_name} for {self.admission.admission_number}"


class NursingTask(TimeStampedModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('STAT', 'STAT / Immediate'),
    ]

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='nursing_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    due_time = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='ROUTINE', db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_nursing_tasks'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'nursing_task'
        verbose_name = 'Nursing Task'
        verbose_name_plural = 'Nursing Tasks'
        ordering = ['due_time', 'priority']

    def __str__(self):
        return f"[{self.priority}] {self.title} - {self.status}"


class MedicationAdministrationRecord(TimeStampedModel):
    STATUS_CHOICES = [
        ('DUE', 'Due / Scheduled'),
        ('GIVEN', 'Administered / Given'),
        ('MISSED', 'Missed Dose'),
        ('REFUSED', 'Patient Refused'),
        ('HELD', 'Clinically Held / Withheld'),
    ]

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='mar_records')
    prescription_item = models.ForeignKey(
        PrescriptionItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='administrations'
    )
    medication_name = models.CharField(max_length=150)
    dose = models.CharField(max_length=50)
    route = models.CharField(max_length=50, default='Oral')
    scheduled_time = models.DateTimeField(db_index=True)
    administered_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DUE', db_index=True)
    administered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='administered_medications'
    )
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'nursing_mar'
        verbose_name = 'Medication Administration Record'
        verbose_name_plural = 'Medication Administration Records'
        ordering = ['scheduled_time']
        indexes = [
            models.Index(fields=['admission', 'status']),
            models.Index(fields=['scheduled_time']),
        ]

    def __str__(self):
        return f"{self.medication_name} ({self.dose}) for {self.admission.patient.full_name} [{self.status}]"


class ShiftHandover(TimeStampedModel):
    SHIFT_CHOICES = [
        ('MORNING', 'Morning (07:00 - 15:30)'),
        ('EVENING', 'Evening (15:00 - 23:30)'),
        ('NIGHT', 'Night (23:00 - 07:30)'),
    ]

    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='handovers')
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    handover_date = models.DateField(default=timezone.localdate, db_index=True)
    outgoing_nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_handovers'
    )
    incoming_nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_handovers'
    )
    general_ward_summary = models.TextField(
        help_text="Ward census summary: total patients, transfers, critical admissions, bed capacity"
    )
    patient_summaries = models.JSONField(
        default=list,
        help_text="Structured patient notes: admission_id, patient_name, bed_number, clinical_summary, pending_orders, precautions"
    )
    is_acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'nursing_shift_handover'
        verbose_name = 'Shift Handover'
        verbose_name_plural = 'Shift Handovers'
        ordering = ['-handover_date', '-created_at']

    def __str__(self):
        ack_label = "Acknowledged" if self.is_acknowledged else "Pending"
        return f"{self.ward.name} Handover ({self.shift} on {self.handover_date}) [{ack_label}]"
