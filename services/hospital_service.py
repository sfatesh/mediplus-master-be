from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.hospital import (
    Department, Doctor, Appointment, BlogPost, Comment,
    ContactMessage, NewsletterSubscriber, HospitalStat
)
from serializers.schemas import (
    DepartmentResponse, DoctorResponse,
    AppointmentCreate, AppointmentResponse,
    BlogPostResponse, BlogDetailResponse, CommentCreate, CommentResponse,
    ContactCreate, ContactResponse, NewsletterResponse,
    StatResponse, StatsSummaryResponse
)
from repositories.hospital_repository import HospitalRepository


class HospitalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = HospitalRepository(db)

    # --- Departments ---
    def list_departments(self) -> List[DepartmentResponse]:
        departments = self.repo.get_all_departments()
        responses = []
        for d in departments:
            doc_count = len(d.doctors) if d.doctors else 0
            responses.append(DepartmentResponse(
                id=d.id,
                name=d.name,
                slug=d.slug,
                icon=d.icon,
                description=d.description,
                image_url=d.image_url,
                is_active=d.is_active,
                created_at=d.created_at,
                doctors_count=doc_count
            ))
        return responses

    def get_department_by_id(self, dept_id: int) -> DepartmentResponse:
        d = self.repo.get_department_by_id(dept_id)
        if not d:
            raise HTTPException(status_code=404, detail="Department not found")
        return DepartmentResponse.model_validate(d)

    # --- Doctors ---
    def list_doctors(self, department_id: Optional[int] = None) -> List[DoctorResponse]:
        doctors = self.repo.get_all_doctors(department_id=department_id)
        responses = []
        for doc in doctors:
            dept_name = doc.department.name if doc.department else None
            responses.append(DoctorResponse(
                id=doc.id,
                name=doc.name,
                slug=doc.slug,
                department_id=doc.department_id,
                department_name=dept_name,
                position=doc.position,
                qualification=doc.qualification,
                bio=doc.bio,
                photo_url=doc.photo_url,
                phone=doc.phone,
                email=doc.email,
                twitter=doc.twitter,
                facebook=doc.facebook,
                google_plus=doc.google_plus,
                instagram=doc.instagram,
                is_active=doc.is_active,
                created_at=doc.created_at
            ))
        return responses

    def get_doctor_by_id(self, doctor_id: int) -> DoctorResponse:
        doc = self.repo.get_doctor_by_id(doctor_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Doctor not found")
        dept_name = doc.department.name if doc.department else None
        return DoctorResponse(
            id=doc.id,
            name=doc.name,
            slug=doc.slug,
            department_id=doc.department_id,
            department_name=dept_name,
            position=doc.position,
            qualification=doc.qualification,
            bio=doc.bio,
            photo_url=doc.photo_url,
            phone=doc.phone,
            email=doc.email,
            twitter=doc.twitter,
            facebook=doc.facebook,
            google_plus=doc.google_plus,
            instagram=doc.instagram,
            is_active=doc.is_active,
            created_at=doc.created_at
        )

    # --- Appointments ---
    def create_appointment(self, data: AppointmentCreate) -> AppointmentResponse:
        # Validate department if provided
        dept_name = None
        if data.department_id:
            dept = self.repo.get_department_by_id(data.department_id)
            if dept:
                dept_name = dept.name

        # Validate doctor if provided
        doctor_name = None
        if data.doctor_id:
            doc = self.repo.get_doctor_by_id(data.doctor_id)
            if doc:
                doctor_name = doc.name

        appointment = Appointment(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            department_id=data.department_id,
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            appointment_time=data.appointment_time,
            message=data.message,
            status="PENDING"
        )
        saved = self.repo.create_appointment(appointment)

        return AppointmentResponse(
            id=saved.id,
            reference_number=saved.reference_number,
            first_name=saved.first_name,
            last_name=saved.last_name,
            email=saved.email,
            phone=saved.phone,
            department_id=saved.department_id,
            doctor_id=saved.doctor_id,
            department_name=dept_name,
            doctor_name=doctor_name,
            appointment_date=saved.appointment_date,
            appointment_time=saved.appointment_time,
            message=saved.message,
            status=saved.status,
            created_at=saved.created_at
        )

    def get_appointment(self, ref_number: str) -> AppointmentResponse:
        a = self.repo.get_appointment_by_ref(ref_number)
        if not a:
            raise HTTPException(status_code=404, detail="Appointment reference not found")
        dept_name = a.department.name if a.department else None
        doc_name = a.doctor.name if a.doctor else None
        return AppointmentResponse(
            id=a.id,
            reference_number=a.reference_number,
            first_name=a.first_name,
            last_name=a.last_name,
            email=a.email,
            phone=a.phone,
            department_id=a.department_id,
            doctor_id=a.doctor_id,
            department_name=dept_name,
            doctor_name=doc_name,
            appointment_date=a.appointment_date,
            appointment_time=a.appointment_time,
            message=a.message,
            status=a.status,
            created_at=a.created_at
        )

    def list_appointments(self, status: Optional[str] = None) -> List[AppointmentResponse]:
        appointments = self.repo.get_all_appointments(status=status)
        responses = []
        for a in appointments:
            dept_name = a.department.name if a.department else None
            doc_name = a.doctor.name if a.doctor else None
            responses.append(AppointmentResponse(
                id=a.id,
                reference_number=a.reference_number,
                first_name=a.first_name,
                last_name=a.last_name,
                email=a.email,
                phone=a.phone,
                department_id=a.department_id,
                doctor_id=a.doctor_id,
                department_name=dept_name,
                doctor_name=doc_name,
                appointment_date=a.appointment_date,
                appointment_time=a.appointment_time,
                message=a.message,
                status=a.status,
                created_at=a.created_at
            ))
        return responses

    # --- Blogs ---
    def list_blogs(self, category: Optional[str] = None, limit: int = 10, offset: int = 0) -> List[BlogPostResponse]:
        blogs = self.repo.get_all_blogs(category=category, limit=limit, offset=offset)
        responses = []
        for b in blogs:
            comment_count = len(b.comments) if b.comments else 0
            responses.append(BlogPostResponse(
                id=b.id,
                title=b.title,
                slug=b.slug,
                excerpt=b.excerpt,
                content=b.content,
                image_url=b.image_url,
                author_name=b.author_name,
                author_bio=b.author_bio,
                author_avatar=b.author_avatar,
                category=b.category,
                tags=b.tags,
                created_at=b.created_at,
                comment_count=comment_count
            ))
        return responses

    def get_blog_detail(self, slug_or_id: str) -> BlogDetailResponse:
        if slug_or_id.isdigit():
            b = self.repo.get_blog_by_id(int(slug_or_id))
        else:
            b = self.repo.get_blog_by_slug(slug_or_id)

        if not b:
            raise HTTPException(status_code=404, detail="Blog post not found")

        # Format comments hierarchically
        all_comments = self.repo.get_blog_comments(b.id)
        comment_map = {}
        root_comments = []

        for c in all_comments:
            c_resp = CommentResponse(
                id=c.id,
                blog_id=c.blog_id,
                parent_id=c.parent_id,
                name=c.name,
                website=c.website,
                message=c.message,
                created_at=c.created_at,
                replies=[]
            )
            comment_map[c.id] = c_resp
            if c.parent_id is None:
                root_comments.append(c_resp)
            else:
                parent = comment_map.get(c.parent_id)
                if parent:
                    parent.replies.append(c_resp)
                else:
                    root_comments.append(c_resp)

        return BlogDetailResponse(
            id=b.id,
            title=b.title,
            slug=b.slug,
            excerpt=b.excerpt,
            content=b.content,
            image_url=b.image_url,
            author_name=b.author_name,
            author_bio=b.author_bio,
            author_avatar=b.author_avatar,
            category=b.category,
            tags=b.tags,
            created_at=b.created_at,
            comment_count=len(all_comments),
            comments=root_comments
        )

    def add_comment(self, blog_id: int, data: CommentCreate) -> CommentResponse:
        blog = self.repo.get_blog_by_id(blog_id)
        if not blog:
            raise HTTPException(status_code=404, detail="Blog post not found")

        comment = Comment(
            blog_id=blog_id,
            parent_id=data.parent_id,
            name=data.name,
            email=data.email,
            website=data.website,
            message=data.message
        )
        saved = self.repo.create_comment(comment)
        return CommentResponse(
            id=saved.id,
            blog_id=saved.blog_id,
            parent_id=saved.parent_id,
            name=saved.name,
            website=saved.website,
            message=saved.message,
            created_at=saved.created_at,
            replies=[]
        )

    def get_blog_categories(self) -> List[dict]:
        return self.repo.get_blog_categories()

    def get_recent_blogs(self, limit: int = 3) -> List[BlogPostResponse]:
        blogs = self.repo.get_recent_blogs(limit=limit)
        return [BlogPostResponse.model_validate(b) for b in blogs]

    # --- Contact ---
    def submit_contact(self, data: ContactCreate) -> ContactResponse:
        message = ContactMessage(
            name=data.name,
            email=data.email,
            subject=data.subject,
            message=data.message
        )
        saved = self.repo.create_contact_message(message)
        return ContactResponse.model_validate(saved)

    # --- Newsletter ---
    def subscribe_newsletter(self, email: str) -> NewsletterResponse:
        saved = self.repo.add_newsletter_subscriber(email)
        return NewsletterResponse(
            id=saved.id,
            email=saved.email,
            subscribed_at=saved.subscribed_at,
            message="Thank you for subscribing to Mediplus updates!"
        )

    # --- Stats ---
    def get_stats_summary(self) -> StatsSummaryResponse:
        stats = self.repo.get_all_stats()
        return StatsSummaryResponse(
            stats=[StatResponse.model_validate(s) for s in stats]
        )

