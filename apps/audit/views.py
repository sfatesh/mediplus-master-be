from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema_view, extend_schema
from .models import AuditLog
from .serializers import AuditLogSerializer
from apps.common.permissions import IsAdmin


@extend_schema_view(
    list=extend_schema(summary="List hospital security and audit logs (Admin only)"),
    retrieve=extend_schema(summary="Retrieve audit log entry by ID (Admin only)")
)
class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'status', 'resource_type']
    search_fields = ['action', 'user__email', 'resource_id', 'ip_address']
    ordering_fields = ['created_at']
