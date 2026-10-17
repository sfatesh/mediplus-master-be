from django.contrib import admin
from .models import Appointment, DoctorSchedule, DoctorLeave, QueueEntry


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference_number', 'first_name', 'last_name', 'doctor', 'appointment_date', 'appointment_time', 'status')
    list_filter = ('status', 'appointment_date', 'doctor')
    search_fields = ('reference_number', 'first_name', 'last_name', 'phone')


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'doctor', 'day_of_week', 'start_time', 'end_time', 'slot_duration_minutes', 'is_active')
    list_filter = ('doctor', 'day_of_week', 'is_active')


@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):
    list_display = ('id', 'doctor', 'start_date', 'end_date', 'reason', 'is_approved')
    list_filter = ('is_approved', 'doctor')


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'token_number', 'patient_name', 'doctor', 'queue_date', 'queue_type', 'status', 'check_in_time')
    list_filter = ('status', 'queue_type', 'queue_date', 'doctor')
    search_fields = ('token_number', 'patient_name', 'patient_phone')

