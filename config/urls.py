from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)
from apps.common.health import HealthCheckView

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),

    # API Root Health Probe
    path('', HealthCheckView.as_view(), name='root-health'),

    # Versioned API v1
    path('api/v1/', include('api.v1.urls')),

    # OpenAPI 3 Schema & Interactive Documentation
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

