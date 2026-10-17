from apps.common.services import BaseService
from .models import Department, Doctor


class DepartmentService(BaseService):
    @classmethod
    def get_active_departments(cls):
        return Department.objects.filter(is_active=True).prefetch_related('doctors').order_by('name')

    @classmethod
    def get_active_doctors(cls, department_id=None):
        queryset = Doctor.objects.filter(is_active=True).select_related('department').order_by('name')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset

