from fastapi import APIRouter

from .auth import router as auth_router
from .departments import router as departments_router
from .doctors import router as doctors_router
from .appointments import router as appointments_router
from .blogs import router as blogs_router
from .contact import router as contact_router
from .newsletter import router as newsletter_router
from .stats import router as stats_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(doctors_router)
api_v1_router.include_router(appointments_router)
api_v1_router.include_router(blogs_router)
api_v1_router.include_router(contact_router)
api_v1_router.include_router(newsletter_router)
api_v1_router.include_router(stats_router)

