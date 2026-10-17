from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NursePatientAssignmentViewSet,
    VitalObservationViewSet,
    NursingCareNoteViewSet,
    NursingTaskViewSet,
    MedicationAdministrationRecordViewSet,
    ShiftHandoverViewSet,
)

router = DefaultRouter()
router.register(r'assignments', NursePatientAssignmentViewSet, basename='nursing-assignments')
router.register(r'vitals', VitalObservationViewSet, basename='nursing-vitals')
router.register(r'notes', NursingCareNoteViewSet, basename='nursing-notes')
router.register(r'tasks', NursingTaskViewSet, basename='nursing-tasks')
router.register(r'mar', MedicationAdministrationRecordViewSet, basename='nursing-mar')
router.register(r'handovers', ShiftHandoverViewSet, basename='nursing-handovers')

urlpatterns = [
    path('nursing/', include(router.urls)),
]
