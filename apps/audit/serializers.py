from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_email',
            'user_role',
            'action',
            'ip_address',
            'user_agent',
            'resource_type',
            'resource_id',
            'status',
            'details',
            'created_at'
        ]
        read_only_fields = fields
