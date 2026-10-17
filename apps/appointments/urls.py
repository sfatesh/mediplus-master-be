from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet,
    QueueEntryViewSet,
    DoctorScheduleViewSet,
    DoctorLeaveViewSet
)

router = DefaultRouter()
router.register(r'appointments/queue', QueueEntryViewSet, basename='appointment-queue')
router.register(r'appointments/schedules', DoctorScheduleViewSet, basename='doctor-schedule')
router.register(r'appointments/leaves', DoctorLeaveViewSet, basename='doctor-leave')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]
