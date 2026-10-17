from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WardViewSet, RoomViewSet, BedViewSet, AdmissionViewSet

router = DefaultRouter()
router.register(r'wards', WardViewSet, basename='wards')
router.register(r'rooms', RoomViewSet, basename='rooms')
router.register(r'beds', BedViewSet, basename='beds')
router.register(r'admissions', AdmissionViewSet, basename='admissions')

urlpatterns = [
    path('', include(router.urls)),
]
