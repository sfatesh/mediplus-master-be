from apps.common.services import BaseService
from .models import Appointment


class AppointmentService(BaseService):
    @classmethod
    def get_by_reference(cls, ref_number: str):
        return Appointment.objects.filter(reference_number__iexact=ref_number).select_related('department', 'doctor').first()

    @classmethod
    def update_status(cls, appointment: Appointment, new_status: str) -> Appointment:
        appointment.status = new_status
        appointment.save(update_fields=['status', 'updated_at'])
        cls.log_action('update_status', {'reference': appointment.reference_number, 'new_status': new_status})
        return appointment

