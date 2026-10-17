from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import ContactCreate, ContactResponse
from services.hospital_service import HospitalService

router = APIRouter(prefix="/contact", tags=["Contact & Support"])


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def submit_contact(data: ContactCreate, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.submit_contact(data)

