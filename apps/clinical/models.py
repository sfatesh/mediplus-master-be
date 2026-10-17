import uuid
from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.departments.models import Doctor, Department
from apps.patients.models import Patient
from apps.appointments.models import Appointment, QueueEntry


def generate_encounter_number() -> str:
    return f"ENC-{uuid.uuid4().hex[:8].upper()}"


def generate_prescription_number() -> str:
    return f"RX-{uuid.uuid4().hex[:8].upper()}"


class Encounter(TimeStampedModel):
    ENCOUNTER_TYPE_CHOICES = [
        ('OUTPATIENT', 'Outpatient Consultation'),
        ('WALK_IN', 'Walk-in Consultation'),
        ('FOLLOW_UP', 'Follow-up Visit'),
        ('EMERGENCY', 'Emergency Evaluation'),
    ]

    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    encounter_number = models.CharField(max_length=50, unique=True, default=generate_encounter_number, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='encounters')
    attending_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clinical_encounters'
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='encounters'
    )
    queue_entry = models.ForeignKey(
        QueueEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='encounters'
    )
    encounter_type = models.CharField(max_length=30, choices=ENCOUNTER_TYPE_CHOICES, default='OUTPATIENT')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='IN_PROGRESS', db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    chief_complaint = models.TextField(blank=True, null=True)

    # Standard clinical vitals recorded during triage / consultation
    vitals = models.JSONField(
        default=dict,
        blank=True,
        help_text="Key-value vitals: blood_pressure, pulse_rate, temperature_c, spo2_percent, weight_kg, height_cm, bmi"
    )

    class Meta:
        db_table = 'clinical_encounter'
        verbose_name = 'Patient Encounter'
        verbose_name_plural = 'Patient Encounters'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"{self.encounter_number} - {self.patient.full_name} with {self.doctor.name} ({self.status})"


class ClinicalNote(TimeStampedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='clinical_notes')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_clinical_notes'
    )

    # SOAP structured clinical documentation
    subjective = models.TextField(help_text="Patient reported symptoms, history of present illness")
    objective = models.TextField(help_text="Doctor physical examination and objective diagnostic observations")
    assessment = models.TextField(help_text="Clinical evaluation, working impressions, and differential diagnosis")
    plan = models.TextField(help_text="Treatment strategy, orders, and diagnostic interventions")

    diagnoses = models.JSONField(
        default=list,
        blank=True,
        help_text="List of clinical diagnoses with ICD/clinical codes"
    )
    follow_up_instructions = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(null=True, blank=True)

    # Note Signing & Immutability / Versioning
    is_signed = models.BooleanField(default=False, db_index=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_clinical_notes'
    )
    version = models.IntegerField(default=1)
    amendment_reason = models.TextField(blank=True, null=True, help_text="Reason required when amending a signed note")
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='amended_notes'
    )

    class Meta:
        db_table = 'clinical_note'
        verbose_name = 'Clinical Consultation Note'
        verbose_name_plural = 'Clinical Consultation Notes'
        ordering = ['-created_at']

    def __str__(self):
        signed_label = "Signed" if self.is_signed else "Draft"
        return f"Note v{self.version} ({signed_label}) for {self.encounter.encounter_number}"


class Prescription(TimeStampedModel):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('AUTHORIZED', 'Authorized / Signed'),
        ('DISPENSED', 'Dispensed'),
        ('CANCELLED', 'Cancelled'),
    ]

    prescription_number = models.CharField(max_length=50, unique=True, default=generate_prescription_number, db_index=True)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='prescriptions')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    prescriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authorized_prescriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    authorized_at = models.DateTimeField(null=True, blank=True)
    clinical_instructions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'clinical_prescription'
        verbose_name = 'Prescription'
        verbose_name_plural = 'Prescriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.prescription_number} for {self.patient.full_name} ({self.status})"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    medication_name = models.CharField(max_length=150)
    dosage = models.CharField(max_length=50, help_text="e.g. 500 mg")
    frequency = models.CharField(max_length=100, help_text="e.g. Twice daily after meals")
    duration = models.CharField(max_length=50, help_text="e.g. 7 days")
    route = models.CharField(max_length=30, default='Oral', help_text="Oral, IV, Topical, Inhalation")
    quantity = models.IntegerField(default=1)
    instructions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'clinical_prescription_item'
        verbose_name = 'Prescription Item'
        verbose_name_plural = 'Prescription Items'

    def __str__(self):
        return f"{self.medication_name} {self.dosage} - {self.frequency} ({self.duration})"
