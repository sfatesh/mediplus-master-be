from datetime import datetime
from django.db import connection
from django.conf import settings
from rest_framework import serializers, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    version = serializers.CharField()
    timestamp = serializers.CharField()
    environment = serializers.CharField()
    database = serializers.CharField()


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = HealthCheckResponseSerializer

    @extend_schema(
        summary="System health check and database connectivity probe",
        responses={200: HealthCheckResponseSerializer, 503: HealthCheckResponseSerializer}
    )
    def get(self, request):
        db_status = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                if not row or row[0] != 1:
                    db_status = "unexpected_response"
        except Exception as e:
            db_status = f"error: {str(e)}"

        is_healthy = db_status == "ok"
        payload = {
            "status": "healthy" if is_healthy else "degraded",
            "service": "Mediplus Hospital Management API (Django DRF)",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": getattr(settings, 'DJANGO_ENV', 'development'),
            "database": db_status
        }
        return Response(
            payload,
            status=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        )

