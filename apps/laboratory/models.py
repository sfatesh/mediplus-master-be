import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import TimeStampedModel


def generate_lab_order_number() -> str:
    return f"LAB-ORD-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def generate_specimen_barcode() -> str:
    return f"SPEC-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class LabTestCatalogue(TimeStampedModel):
    CATEGORY_CHOICES = [
        ('HEMATOLOGY', 'Hematology'),
        ('BIOCHEMISTRY', 'Clinical Biochemistry'),
        ('MICROBIOLOGY', 'Microbiology & Serology'),
        ('IMMUNOLOGY', 'Immunology'),
        ('PATHOLOGY', 'Histopathology / Cytology'),
        ('URINALYSIS', 'Urinalysis & Body Fluids'),
        ('RADIOLOGY', 'Diagnostic Imaging / Radiology'),
        ('CARDIOLOGY', 'Cardiology Diagnostics (ECG/Echo)'),
        ('OTHER', 'General Diagnostics'),
    ]

    SPECIMEN_TYPE_CHOICES = [
        ('WHOLE_BLOOD', 'Whole Blood'),
        ('SERUM', 'Serum'),
        ('PLASMA', 'Plasma'),
        ('URINE', 'Urine Sample'),
        ('STOOL', 'Stool Sample'),
        ('SPUTUM', 'Sputum'),
        ('CSF', 'Cerebrospinal Fluid (CSF)'),
        ('SWAB', 'Swab (Nasal/Throat/Wound)'),
        ('BIOPSY', 'Biopsy / Tissue Specimen'),
        ('NONE', 'No Specimen Required (e.g. Imaging)'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, db_index=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='HEMATOLOGY', db_index=True)
    specimen_type = models.CharField(max_length=50, choices=SPECIMEN_TYPE_CHOICES, default='WHOLE_BLOOD')
    container_type = models.CharField(max_length=100, blank=True, help_text="e.g. Lavender (EDTA), Gold (SST)")
    specimen_volume_required = models.CharField(max_length=50, blank=True, help_text="e.g. 3 mL, 10 mL")
    turnaround_time_hours = models.PositiveIntegerField(default=4)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'laboratory_test_catalogue'
        verbose_name = 'Lab Test Catalogue Item'
        verbose_name_plural = 'Lab Test Catalogue'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} [{self.code}] ({self.category})"


class LabTestParameter(models.Model):
    lab_test = models.ForeignKey(LabTestCatalogue, on_delete=models.CASCADE, related_name='parameters')
    name = models.CharField(max_length=100, help_text="e.g. Hemoglobin, WBC, Potassium, Glucose")
    unit = models.CharField(max_length=50, blank=True, help_text="e.g. g/dL, x10^3/uL, mmol/L")
    reference_range_min = models.FloatField(null=True, blank=True)
    reference_range_max = models.FloatField(null=True, blank=True)
    reference_range_text = models.CharField(max_length=100, blank=True, help_text="e.g. 13.5 - 17.5, Negative")
    critical_low = models.FloatField(null=True, blank=True, help_text="Panic low threshold")
    critical_high = models.FloatField(null=True, blank=True, help_text="Panic high threshold")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'laboratory_test_parameter'
        verbose_name = 'Lab Test Parameter'
        verbose_name_plural = 'Lab Test Parameters'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.lab_test.code} -> {self.name} ({self.unit or 'text'})"


class LabOrder(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('STAT', 'STAT (Emergency)'),
    ]

    STATUS_CHOICES = [
        ('ORDERED', 'Ordered'),
        ('COLLECTED', 'Sample Collected'),
        ('IN_PROGRESS', 'Processing / In Lab'),
        ('COMPLETED', 'Completed & Released'),
        ('CANCELLED', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=50, unique=True, default=generate_lab_order_number, db_index=True)
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='lab_orders')
    ordering_doctor = models.ForeignKey(
        'departments.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordered_labs'
    )
    encounter = models.ForeignKey(
        'clinical.Encounter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_orders'
    )
    admission = models.ForeignKey(
        'admissions.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_orders'
    )
    clinical_indication = models.TextField(blank=True, help_text="Working diagnosis or clinical symptoms")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='ROUTINE', db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ORDERED', db_index=True)
    ordered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'laboratory_order'
        verbose_name = 'Lab Order'
        verbose_name_plural = 'Lab Orders'
        ordering = ['-ordered_at']

    def __str__(self):
        return f"{self.order_number} for {self.patient.full_name} ({self.priority} - {self.status})"


class LabOrderItem(TimeStampedModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Sample Collection'),
        ('SAMPLE_COLLECTED', 'Sample Collected'),
        ('PROCESSING', 'Processing in Laboratory'),
        ('PRELIMINARY', 'Preliminary Results Entered'),
        ('VERIFIED', 'Verified by Pathologist'),
        ('RELEASED', 'Released to Patient/Physician'),
        ('CANCELLED', 'Cancelled'),
    ]

    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='items')
    lab_test = models.ForeignKey(LabTestCatalogue, on_delete=models.PROTECT, related_name='order_items')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True)

    class Meta:
        db_table = 'laboratory_order_item'
        verbose_name = 'Lab Order Item'
        verbose_name_plural = 'Lab Order Items'

    def __str__(self):
        return f"{self.order.order_number} -> {self.lab_test.name} ({self.status})"


class LabSpecimen(TimeStampedModel):
    STATUS_CHOICES = [
        ('COLLECTED', 'Collected'),
        ('RECEIVED_IN_LAB', 'Received in Lab'),
        ('PROCESSING', 'In Testing'),
        ('REJECTED', 'Specimen Rejected (Clotted/Hemolyzed)'),
    ]

    accession_number = models.CharField(max_length=50, unique=True, default=generate_specimen_barcode, db_index=True)
    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name='specimens')
    specimen_type = models.CharField(max_length=50)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_specimens'
    )
    collected_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='COLLECTED', db_index=True)
    rejection_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'laboratory_specimen'
        verbose_name = 'Lab Specimen'
        verbose_name_plural = 'Lab Specimens'
        ordering = ['-collected_at']

    def __str__(self):
        return f"{self.accession_number} ({self.specimen_type}) - {self.status}"


class LabResult(TimeStampedModel):
    STATUS_CHOICES = [
        ('PRELIMINARY', 'Preliminary / Draft'),
        ('VERIFIED', 'Verified by Pathologist'),
        ('RELEASED', 'Released'),
    ]

    INTERPRETATION_CHOICES = [
        ('NORMAL', 'Normal'),
        ('ABNORMAL', 'Abnormal'),
        ('CRITICAL', 'Critical Alert / Panic Value'),
    ]

    order_item = models.OneToOneField(LabOrderItem, on_delete=models.CASCADE, related_name='result')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRELIMINARY', db_index=True)
    overall_interpretation = models.CharField(max_length=20, choices=INTERPRETATION_CHOICES, default='NORMAL')
    summary_notes = models.TextField(blank=True)
    
    # Critical Alert Tracking
    is_critical = models.BooleanField(default=False, db_index=True)
    critical_alert_sent = models.BooleanField(default=False)
    critical_acknowledged = models.BooleanField(default=False)
    critical_acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_critical_labs'
    )
    critical_acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Authorship & Signing
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_lab_results'
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_lab_results'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    is_released = models.BooleanField(default=False, db_index=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='released_lab_results'
    )
    released_at = models.DateTimeField(null=True, blank=True)

    # Immutability & Versioning (prevent silent overwrites!)
    version = models.PositiveIntegerField(default=1)
    is_corrected = models.BooleanField(default=False)
    correction_reason = models.TextField(blank=True, null=True, help_text="Required if result amended after verification")
    previous_result = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='corrected_versions'
    )

    class Meta:
        db_table = 'laboratory_result'
        verbose_name = 'Lab Result'
        verbose_name_plural = 'Lab Results'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Result v{self.version} for {self.order_item.lab_test.name} ({self.status} - {self.overall_interpretation})"


class LabResultParameterValue(models.Model):
    FLAG_CHOICES = [
        ('NORMAL', 'Normal'),
        ('LOW', 'Low'),
        ('HIGH', 'High'),
        ('CRITICAL_LOW', 'Critical Low!'),
        ('CRITICAL_HIGH', 'Critical High!'),
        ('ABNORMAL', 'Abnormal'),
    ]

    result = models.ForeignKey(LabResult, on_delete=models.CASCADE, related_name='parameter_values')
    parameter = models.ForeignKey(LabTestParameter, on_delete=models.CASCADE, related_name='recorded_values')
    value = models.CharField(max_length=100, help_text="Value as reported by analyzer or tech")
    numeric_value = models.FloatField(null=True, blank=True)
    flag = models.CharField(max_length=20, choices=FLAG_CHOICES, default='NORMAL')
    reference_range_display = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'laboratory_result_param_val'
        verbose_name = 'Lab Result Parameter Value'
        verbose_name_plural = 'Lab Result Parameter Values'

    def __str__(self):
        return f"{self.parameter.name}: {self.value} {self.parameter.unit} [{self.flag}]"
