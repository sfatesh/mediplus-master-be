from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EncounterViewSet, ClinicalNoteViewSet, PrescriptionViewSet

router = DefaultRouter()
router.register(r'clinical/encounters', EncounterViewSet, basename='encounter')
router.register(r'clinical/notes', ClinicalNoteViewSet, basename='clinical-note')
router.register(r'clinical/prescriptions', PrescriptionViewSet, basename='prescription')

urlpatterns = [
    path('', include(router.urls)),
]
