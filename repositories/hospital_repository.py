from typing import List, Optional
from sqlalchemy.orm import Session
from models.hospital import (
    User, Department, Doctor, Appointment, BlogPost, Comment,
    ContactMessage, NewsletterSubscriber, HospitalStat
)


class HospitalRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- User operations ---
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # --- Department operations ---
    def get_all_departments(self) -> List[Department]:
        return self.db.query(Department).filter(Department.is_active == True).all()

    def get_department_by_id(self, dept_id: int) -> Optional[Department]:
        return self.db.query(Department).filter(Department.id == dept_id).first()

    def get_department_by_slug(self, slug: str) -> Optional[Department]:
        return self.db.query(Department).filter(Department.slug == slug).first()

    def create_department(self, dept: Department) -> Department:
        self.db.add(dept)
        self.db.commit()
        self.db.refresh(dept)
        return dept

    # --- Doctor operations ---
    def get_all_doctors(self, department_id: Optional[int] = None) -> List[Doctor]:
        query = self.db.query(Doctor).filter(Doctor.is_active == True)
        if department_id:
            query = query.filter(Doctor.department_id == department_id)
        return query.all()

    def get_doctor_by_id(self, doctor_id: int) -> Optional[Doctor]:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def create_doctor(self, doctor: Doctor) -> Doctor:
        self.db.add(doctor)
        self.db.commit()
        self.db.refresh(doctor)
        return doctor

    # --- Appointment operations ---
    def create_appointment(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def get_appointment_by_ref(self, ref_number: str) -> Optional[Appointment]:
        return self.db.query(Appointment).filter(Appointment.reference_number == ref_number).first()

    def get_all_appointments(self, status: Optional[str] = None) -> List[Appointment]:
        query = self.db.query(Appointment)
        if status:
            query = query.filter(Appointment.status == status)
        return query.order_by(Appointment.created_at.desc()).all()

    def update_appointment_status(self, appointment: Appointment, status: str) -> Appointment:
        appointment.status = status
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    # --- Blog & Comment operations ---
    def get_all_blogs(self, category: Optional[str] = None, limit: int = 10, offset: int = 0) -> List[BlogPost]:
        query = self.db.query(BlogPost)
        if category:
            query = query.filter(BlogPost.category.ilike(f"%{category}%"))
        return query.order_by(BlogPost.created_at.desc()).offset(offset).limit(limit).all()

    def get_blog_by_slug(self, slug: str) -> Optional[BlogPost]:
        return self.db.query(BlogPost).filter(BlogPost.slug == slug).first()

    def get_blog_by_id(self, blog_id: int) -> Optional[BlogPost]:
        return self.db.query(BlogPost).filter(BlogPost.id == blog_id).first()

    def get_recent_blogs(self, limit: int = 3) -> List[BlogPost]:
        return self.db.query(BlogPost).order_by(BlogPost.created_at.desc()).limit(limit).all()

    def get_blog_categories(self) -> List[dict]:
        from sqlalchemy import func
        results = self.db.query(BlogPost.category, func.count(BlogPost.id)).group_by(BlogPost.category).all()
        return [{"name": r[0], "count": r[1]} for r in results]

    def create_comment(self, comment: Comment) -> Comment:
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_blog_comments(self, blog_id: int) -> List[Comment]:
        return self.db.query(Comment).filter(Comment.blog_id == blog_id).order_by(Comment.created_at.asc()).all()

    # --- Contact operations ---
    def create_contact_message(self, message: ContactMessage) -> ContactMessage:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    # --- Newsletter operations ---
    def add_newsletter_subscriber(self, email: str) -> NewsletterSubscriber:
        subscriber = self.db.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == email).first()
        if not subscriber:
            subscriber = NewsletterSubscriber(email=email)
            self.db.add(subscriber)
            self.db.commit()
            self.db.refresh(subscriber)
        return subscriber

    # --- Stats operations ---
    def get_all_stats(self) -> List[HospitalStat]:
        return self.db.query(HospitalStat).all()

