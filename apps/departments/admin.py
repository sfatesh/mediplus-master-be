from django.contrib import admin
from .models import Department, Doctor


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'department', 'position', 'qualification', 'is_active')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'position', 'qualification')
    prepopulated_fields = {'slug': ('name',)}

