from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema_view, extend_schema
from .models import EmergencyRecord
from .serializers import EmergencyRecordSerializer


@extend_schema_view(
    list=extend_schema(summary="List emergency records"),
    retrieve=extend_schema(summary="Retrieve a emergency record by ID")
)
class EmergencyViewSet(viewsets.ModelViewSet):
    queryset = EmergencyRecord.objects.filter(is_active=True)
    serializer_class = EmergencyRecordSerializer
    permission_classes = [permissions.AllowAny]
