from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import StatsSummaryResponse
from services.hospital_service import HospitalService

router = APIRouter(prefix="/stats", tags=["Hospital Statistics"])


@router.get("", response_model=StatsSummaryResponse)
def get_stats(db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_stats_summary()

