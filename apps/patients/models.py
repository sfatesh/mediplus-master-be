from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel


class Patient(TimeStampedModel):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_profile'
    )
    medical_record_number = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='OTHER')
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=50, db_index=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=50, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, null=True)

    # Guardian Details (for minors / elderly / dependents)
    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_relationship = models.CharField(max_length=50, blank=True, null=True)
    guardian_phone = models.CharField(max_length=50, blank=True, null=True)

    # Clinical details
    allergies = models.TextField(blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'patients_patient'
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['phone']),
            models.Index(fields=['medical_record_number']),
            models.Index(fields=['date_of_birth']),
        ]

    def __str__(self):
        return f"{self.medical_record_number} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class PatientConsent(TimeStampedModel):
    CONSENT_TYPE_CHOICES = [
        ('GENERAL_TREATMENT', 'General Medical Treatment'),
        ('DATA_SHARING', 'Data Sharing & Privacy'),
        ('SURGERY', 'Surgical Procedures'),
        ('TELEMEDICINE', 'Telemedicine & Remote Care'),
        ('RESEARCH', 'Clinical Research Study'),
    ]

    STATUS_CHOICES = [
        ('GRANTED', 'Granted'),
        ('REVOKED', 'Revoked'),
        ('EXPIRED', 'Expired'),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='consents'
    )
    consent_type = models.CharField(max_length=50, choices=CONSENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GRANTED', db_index=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    signed_by = models.CharField(max_length=100)
    witness_name = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'patients_consent'
        verbose_name = 'Patient Consent'
        verbose_name_plural = 'Patient Consents'
        ordering = ['-granted_at']
        indexes = [
            models.Index(fields=['patient', 'consent_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.patient.medical_record_number} - {self.consent_type} ({self.status})"
