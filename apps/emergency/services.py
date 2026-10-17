from apps.common.services import BaseService
from .models import EmergencyRecord


class EmergencyService(BaseService):
    @classmethod
    def get_active_records(cls):
        return EmergencyRecord.objects.filter(is_active=True)
