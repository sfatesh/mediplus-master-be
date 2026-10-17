from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReportsViewSet, DashboardOverviewView

router = DefaultRouter()
router.register(r'reports', ReportsViewSet, basename='reports')

urlpatterns = [
    path('dashboard/overview/', DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('', include(router.urls)),
]
