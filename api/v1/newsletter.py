from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import NewsletterCreate, NewsletterResponse
from services.hospital_service import HospitalService

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])


@router.post("/subscribe", response_model=NewsletterResponse, status_code=status.HTTP_201_CREATED)
def subscribe(data: NewsletterCreate, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.subscribe_newsletter(data.email)

