from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import (
    AppointmentCreate, AppointmentResponse, AppointmentStatusUpdate
)
from services.hospital_service import HospitalService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(data: AppointmentCreate, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.create_appointment(data)


@router.get("", response_model=List[AppointmentResponse])
def get_appointments(
    status: Optional[str] = Query(None, description="Filter by status (PENDING, CONFIRMED, etc.)"),
    db: Session = Depends(get_db)
):
    service = HospitalService(db)
    return service.list_appointments(status=status)


@router.get("/{ref_number}", response_model=AppointmentResponse)
def get_appointment_by_ref(ref_number: str, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_appointment(ref_number)


@router.patch("/{ref_number}/status", response_model=AppointmentResponse)
def update_status(ref_number: str, data: AppointmentStatusUpdate, db: Session = Depends(get_db)):
    service = HospitalService(db)
    apt = service.repo.get_appointment_by_ref(ref_number)
    if not apt:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment reference not found")
    service.repo.update_appointment_status(apt, data.status)
    return service.get_appointment(ref_number)

