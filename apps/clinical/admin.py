from django.contrib import admin
from .models import Encounter, ClinicalNote, Prescription, PrescriptionItem


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ('id', 'encounter_number', 'patient', 'doctor', 'encounter_type', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'encounter_type')
    search_fields = ('encounter_number', 'patient__first_name', 'patient__last_name', 'patient__medical_record_number')


@admin.register(ClinicalNote)
class ClinicalNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'encounter', 'author', 'version', 'is_signed', 'signed_at', 'signed_by')
    list_filter = ('is_signed', 'version')
    search_fields = ('encounter__encounter_number', 'assessment', 'plan')


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'prescription_number', 'patient', 'prescriber', 'status', 'authorized_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('prescription_number', 'patient__first_name', 'patient__last_name')
    inlines = [PrescriptionItemInline]

