from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import DepartmentResponse
from services.hospital_service import HospitalService

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentResponse])
def get_departments(db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.list_departments()


@router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(dept_id: int, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_department_by_id(dept_id)

