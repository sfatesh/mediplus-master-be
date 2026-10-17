from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============ User & Auth Schemas ============
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: Optional[str] = "patient"


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============ Department Schemas ============
class DepartmentBase(BaseModel):
    name: str
    slug: str
    icon: Optional[str] = "flaticon-stethoscope"
    description: str
    image_url: Optional[str] = None
    is_active: Optional[bool] = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentResponse(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    doctors_count: Optional[int] = 0


# ============ Doctor Schemas ============
class DoctorBase(BaseModel):
    name: str
    slug: str
    department_id: Optional[int] = None
    position: str
    qualification: Optional[str] = "MD, MBBS"
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    google_plus: Optional[str] = None
    instagram: Optional[str] = None
    is_active: Optional[bool] = True


class DoctorCreate(DoctorBase):
    pass


class DoctorResponse(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_name: Optional[str] = None
    created_at: datetime


# ============ Appointment Schemas ============
class AppointmentCreate(BaseModel):
    first_name: str = Field(..., min_length=2)
    last_name: str = Field(..., min_length=2)
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=7)
    department_id: Optional[int] = None
    doctor_id: Optional[int] = None
    appointment_date: str
    appointment_time: str
    message: Optional[str] = None


class AppointmentStatusUpdate(BaseModel):
    status: str


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: str
    department_id: Optional[int] = None
    doctor_id: Optional[int] = None
    department_name: Optional[str] = None
    doctor_name: Optional[str] = None
    appointment_date: str
    appointment_time: str
    message: Optional[str] = None
    status: str
    created_at: datetime


# ============ Blog & Comment Schemas ============
class CommentCreate(BaseModel):
    parent_id: Optional[int] = None
    name: str = Field(..., min_length=2)
    email: EmailStr
    website: Optional[str] = None
    message: str = Field(..., min_length=3)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    blog_id: int
    parent_id: Optional[int] = None
    name: str
    website: Optional[str] = None
    message: str
    created_at: datetime
    replies: Optional[List["CommentResponse"]] = []


class BlogPostBase(BaseModel):
    title: str
    slug: str
    excerpt: str
    content: str
    image_url: Optional[str] = None
    author_name: Optional[str] = "Admin"
    author_bio: Optional[str] = None
    author_avatar: Optional[str] = None
    category: Optional[str] = "Medical"
    tags: Optional[str] = "Health,Care,Hospital"


class BlogPostResponse(BlogPostBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    comment_count: int = 0


class BlogDetailResponse(BlogPostResponse):
    comments: List[CommentResponse] = []


# ============ Contact & Newsletter Schemas ============
class ContactCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    subject: str = Field(..., min_length=2)
    message: str = Field(..., min_length=5)


class ContactResponse(ContactCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_read: bool
    created_at: datetime


class NewsletterCreate(BaseModel):
    email: EmailStr


class NewsletterResponse(BaseModel):
    id: int
    email: str
    subscribed_at: datetime
    message: str = "Subscribed successfully"


# ============ Hospital Stats Schemas ============
class StatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    number_value: int
    suffix: str
    icon: Optional[str] = None
    description: Optional[str] = None


class StatsSummaryResponse(BaseModel):
    stats: List[StatResponse]

