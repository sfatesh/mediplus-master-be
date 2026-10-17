from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import DoctorResponse
from services.hospital_service import HospitalService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=List[DoctorResponse])
def get_doctors(
    department_id: Optional[int] = Query(None, description="Filter doctors by department ID"),
    db: Session = Depends(get_db)
):
    service = HospitalService(db)
    return service.list_doctors(department_id=department_id)


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_doctor_by_id(doctor_id)

