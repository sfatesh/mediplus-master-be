from apps.common.services import BaseService
from .models import ClinicalRecord


class ClinicalService(BaseService):
    @classmethod
    def get_active_records(cls):
        return ClinicalRecord.objects.filter(is_active=True)
