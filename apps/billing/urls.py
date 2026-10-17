from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ServiceCatalogueViewSet,
    InsurancePolicyViewSet,
    InsuranceClaimViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    RefundViewSet,
)

router = DefaultRouter()
router.register(r'billing/services', ServiceCatalogueViewSet, basename='billing-service')
router.register(r'billing/insurance-policies', InsurancePolicyViewSet, basename='billing-insurance-policy')
router.register(r'billing/claims', InsuranceClaimViewSet, basename='billing-claim')
router.register(r'billing/invoices', InvoiceViewSet, basename='billing-invoice')
router.register(r'billing/payments', PaymentViewSet, basename='billing-payment')
router.register(r'billing/refunds', RefundViewSet, basename='billing-refund')

urlpatterns = [
    path('', include(router.urls)),
]
