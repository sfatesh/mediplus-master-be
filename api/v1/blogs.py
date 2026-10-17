from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from serializers.schemas import (
    BlogPostResponse, BlogDetailResponse, CommentCreate, CommentResponse
)
from services.hospital_service import HospitalService

router = APIRouter(prefix="/blogs", tags=["Blog"])


@router.get("", response_model=List[BlogPostResponse])
def get_blogs(
    category: Optional[str] = Query(None, description="Filter articles by category"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    service = HospitalService(db)
    return service.list_blogs(category=category, limit=limit, offset=offset)


@router.get("/recent", response_model=List[BlogPostResponse])
def get_recent_blogs(limit: int = Query(3, ge=1, le=10), db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_recent_blogs(limit=limit)


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_blog_categories()


@router.get("/{slug_or_id}", response_model=BlogDetailResponse)
def get_blog(slug_or_id: str, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.get_blog_detail(slug_or_id)


@router.post("/{blog_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def post_comment(blog_id: int, data: CommentCreate, db: Session = Depends(get_db)):
    service = HospitalService(db)
    return service.add_comment(blog_id, data)

