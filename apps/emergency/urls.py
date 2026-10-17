from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmergencyViewSet

router = DefaultRouter()
router.register(r'emergency', EmergencyViewSet, basename='emergency')

urlpatterns = [
    path('', include(router.urls)),
]
