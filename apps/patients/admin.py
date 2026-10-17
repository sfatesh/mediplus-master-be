from django.contrib import admin
from .models import Patient, PatientConsent


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('id', 'medical_record_number', 'first_name', 'last_name', 'gender', 'phone', 'is_active', 'created_at')
    list_filter = ('gender', 'is_active', 'blood_group')
    search_fields = ('medical_record_number', 'first_name', 'last_name', 'phone', 'email')


@admin.register(PatientConsent)
class PatientConsentAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'consent_type', 'status', 'granted_at', 'signed_by')
    list_filter = ('consent_type', 'status')
    search_fields = ('patient__medical_record_number', 'signed_by')

