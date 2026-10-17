from django.urls import path, include
from apps.common.health import HealthCheckView

urlpatterns = [
    # Health Probe
    path('health/', HealthCheckView.as_view(), name='health-check'),

    # Domain Apps
    path('', include('apps.accounts.urls')),
    path('', include('apps.departments.urls')),
    path('', include('apps.appointments.urls')),
    path('', include('apps.patients.urls')),
    path('', include('apps.clinical.urls')),
    path('', include('apps.admissions.urls')),
    path('', include('apps.nursing.urls')),
    path('', include('apps.pharmacy.urls')),
    path('', include('apps.laboratory.urls')),
    path('', include('apps.billing.urls')),
    path('', include('apps.emergency.urls')),
    path('', include('apps.notifications.urls')),
    path('', include('apps.reports.urls')),
    path('', include('apps.audit.urls')),
    path('', include('apps.content.urls')),
]

