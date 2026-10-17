from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LabTestCatalogueViewSet,
    LabOrderViewSet,
    LabSpecimenViewSet,
    LabResultViewSet,
)

router = DefaultRouter()
router.register(r'laboratory/tests', LabTestCatalogueViewSet, basename='lab-test')
router.register(r'laboratory/orders', LabOrderViewSet, basename='lab-order')
router.register(r'laboratory/specimens', LabSpecimenViewSet, basename='lab-specimen')
router.register(r'laboratory/results', LabResultViewSet, basename='lab-result')

urlpatterns = [
    path('', include(router.urls)),
]
