import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import TimeStampedModel
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient


def generate_admission_number() -> str:
    return f"ADM-{uuid.uuid4().hex[:8].upper()}"


class Ward(TimeStampedModel):
    WARD_TYPE_CHOICES = [
        ('GENERAL', 'General Ward'),
        ('ICU', 'Intensive Care Unit (ICU)'),
        ('HDU', 'High Dependency Unit (HDU)'),
        ('SURGICAL', 'Surgical Ward'),
        ('PEDIATRIC', 'Pediatric Ward'),
        ('MATERNITY', 'Maternity Ward'),
        ('EMERGENCY', 'Emergency Observation'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wards'
    )
    ward_type = models.CharField(max_length=20, choices=WARD_TYPE_CHOICES, default='GENERAL')
    floor = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. 2nd Floor, Wing B")
    total_capacity = models.PositiveIntegerField(default=10)
    daily_base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))

    class Meta:
        db_table = 'admissions_ward'
        verbose_name = 'Ward'
        verbose_name_plural = 'Wards'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def occupied_beds_count(self) -> int:
        return self.rooms.filter(is_active=True).aggregate(
            occupied=models.Count('beds', filter=models.Q(beds__status='OCCUPIED', beds__is_active=True))
        )['occupied'] or 0

    @property
    def total_beds_count(self) -> int:
        return self.rooms.filter(is_active=True).aggregate(
            total=models.Count('beds', filter=models.Q(beds__is_active=True))
        )['total'] or 0

    @property
    def available_beds_count(self) -> int:
        return self.rooms.filter(is_active=True).aggregate(
            available=models.Count('beds', filter=models.Q(beds__status='AVAILABLE', beds__is_active=True))
        )['available'] or 0

    @property
    def occupancy_rate(self) -> float:
        total = self.total_beds_count
        if total == 0:
            return 0.0
        return round((self.occupied_beds_count / total) * 100.0, 1)


class Room(TimeStampedModel):
    ROOM_TYPE_CHOICES = [
        ('GENERAL_WARD', 'General Ward Room'),
        ('SEMI_PRIVATE', 'Semi-Private Room (2 Beds)'),
        ('PRIVATE', 'Private Room (Single)'),
        ('ISOLATION', 'Isolation Room'),
        ('ICU_SUITE', 'ICU Suite'),
    ]

    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50, db_index=True)
    room_type = models.CharField(max_length=30, choices=ROOM_TYPE_CHOICES, default='GENERAL_WARD')
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'admissions_room'
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'
        unique_together = ('ward', 'room_number')
        ordering = ['ward', 'room_number']

    def __str__(self):
        return f"Room {self.room_number} - {self.ward.name}"


class Bed(TimeStampedModel):
    BED_TYPE_CHOICES = [
        ('STANDARD', 'Standard Hospital Bed'),
        ('ELECTRIC', 'Electric Adjustable Bed'),
        ('ICU_CRITICAL', 'ICU Critical Care Bed'),
        ('PEDIATRIC_CRIB', 'Pediatric Crib'),
        ('ISOLATION', 'Negative Pressure Isolation Bed'),
    ]

    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('OCCUPIED', 'Occupied'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('CLEANING', 'Cleaning / Sanitizing'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=50, db_index=True)
    bed_type = models.CharField(max_length=30, choices=BED_TYPE_CHOICES, default='STANDARD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE', db_index=True)

    class Meta:
        db_table = 'admissions_bed'
        verbose_name = 'Bed'
        verbose_name_plural = 'Beds'
        unique_together = ('room', 'bed_number')
        ordering = ['room', 'bed_number']

    def __str__(self):
        return f"Bed {self.bed_number} ({self.room.room_number}, {self.room.ward.code}) [{self.status}]"


class Admission(TimeStampedModel):
    ADMISSION_TYPE_CHOICES = [
        ('ELECTIVE', 'Elective Admission'),
        ('EMERGENCY', 'Emergency Admission'),
        ('TRANSFER', 'Hospital Transfer'),
        ('URGENT', 'Urgent Outpatient Referral'),
    ]

    STATUS_CHOICES = [
        ('ADMITTED', 'Currently Admitted'),
        ('DISCHARGED', 'Discharged'),
        ('TRANSFERRED', 'Transferred to External Facility'),
        ('CANCELLED', 'Cancelled / Did Not Arrive'),
    ]

    DISCHARGE_DISPOSITION_CHOICES = [
        ('ROUTINE_HOME', 'Discharged to Home Routine'),
        ('TRANSFER_FACILITY', 'Transferred to Specialized Facility'),
        ('AGAINST_MEDICAL_ADVICE', 'Discharged Against Medical Advice (DAMA)'),
        ('REHABILITATION', 'Discharged to Rehabilitation / Skilled Nursing'),
        ('DECEASED', 'Deceased'),
    ]

    admission_number = models.CharField(
        max_length=50,
        unique=True,
        default=generate_admission_number,
        db_index=True
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='admissions')
    admitting_doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='admitted_patients')
    primary_nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_inpatient_cases'
    )
    admission_date = models.DateTimeField(default=timezone.now, db_index=True)
    admission_type = models.CharField(max_length=20, choices=ADMISSION_TYPE_CHOICES, default='ELECTIVE')
    admitting_diagnosis = models.TextField(help_text="Primary diagnosis requiring inpatient hospitalization")
    chief_complaint = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ADMITTED', db_index=True)

    # Discharge Information
    discharge_date = models.DateTimeField(null=True, blank=True)
    discharge_disposition = models.CharField(
        max_length=30,
        choices=DISCHARGE_DISPOSITION_CHOICES,
        null=True,
        blank=True
    )
    discharge_summary = models.TextField(blank=True, null=True)
    discharge_instructions = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(null=True, blank=True)
    is_signed_discharge = models.BooleanField(default=False, db_index=True)
    signed_discharge_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_discharges'
    )
    signed_discharge_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'admissions_admission'
        verbose_name = 'Inpatient Admission'
        verbose_name_plural = 'Inpatient Admissions'
        ordering = ['-admission_date']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['admitting_doctor', 'status']),
            models.Index(fields=['admission_date']),
        ]

    def __str__(self):
        return f"{self.admission_number} - {self.patient.full_name} ({self.status})"

    @property
    def current_bed_assignment(self):
        return self.bed_assignments.filter(is_active=True).select_related('bed__room__ward').first()


class BedAssignment(TimeStampedModel):
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='bed_assignments')
    bed = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='assignments')
    assigned_from = models.DateTimeField(default=timezone.now)
    assigned_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    transfer_reason = models.TextField(blank=True, null=True, help_text="Reason when transferred from another bed")
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authorized_bed_transfers'
    )

    class Meta:
        db_table = 'admissions_bed_assignment'
        verbose_name = 'Bed Assignment'
        verbose_name_plural = 'Bed Assignments'
        ordering = ['-assigned_from']
        constraints = [
            models.UniqueConstraint(
                fields=['bed'],
                condition=models.Q(is_active=True),
                name='unique_active_bed_assignment'
            )
        ]

    def __str__(self):
        active_label = "ACTIVE" if self.is_active else "ENDED"
        return f"{self.bed.bed_number} -> {self.admission.admission_number} [{active_label}]"


class InpatientProgressRecord(TimeStampedModel):
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='progress_records')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inpatient_progress_records'
    )
    record_date = models.DateTimeField(default=timezone.now)
    clinical_findings = models.TextField(help_text="Patient daily clinical condition and progress findings")
    assessment = models.TextField(blank=True, null=True)
    orders_and_plan = models.TextField(help_text="Doctor treatment plan, medication changes, and lab/radiology orders")
    is_signed = models.BooleanField(default=False, db_index=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_inpatient_progress_records'
    )
    version = models.IntegerField(default=1)
    amendment_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'admissions_progress_record'
        verbose_name = 'Inpatient Progress Record'
        verbose_name_plural = 'Inpatient Progress Records'
        ordering = ['-record_date']

    def __str__(self):
        return f"Progress Record v{self.version} for {self.admission.admission_number} at {self.record_date.strftime('%Y-%m-%d')}"


class InpatientCharge(TimeStampedModel):
    CHARGE_TYPE_CHOICES = [
        ('BED_DAY', 'Daily Bed Occupancy Rate'),
        ('NURSING_CARE', 'Inpatient Nursing Service'),
        ('DOCTOR_ROUND', 'Attending Physician Daily Round'),
        ('MEDICATION', 'Inpatient Medication Administration'),
        ('PROCEDURE', 'Bedside Clinical Procedure'),
        ('MISCELLANEOUS', 'Hospital Supply / Consumables'),
    ]

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name='charges')
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES, default='BED_DAY')
    description = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    charge_date = models.DateTimeField(default=timezone.now)
    is_billed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_inpatient_charges'
    )

    class Meta:
        db_table = 'admissions_charge'
        verbose_name = 'Inpatient Charge'
        verbose_name_plural = 'Inpatient Charges'
        ordering = ['-charge_date']

    def save(self, *args, **kwargs):
        self.total_amount = Decimal(self.unit_price) * Decimal(self.quantity)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.charge_type}: {self.description} (${self.total_amount})"
