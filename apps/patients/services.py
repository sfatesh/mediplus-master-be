from apps.common.services import BaseService
from .models import Patient


class PatientService(BaseService):
    @classmethod
    def get_patient_by_mrn(cls, mrn: str):
        return Patient.objects.filter(medical_record_number__iexact=mrn).first()

