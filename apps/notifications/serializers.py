from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source='recipient.full_name', read_only=True)
    recipient_email = serializers.CharField(source='recipient.email', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'recipient_name',
            'recipient_email',
            'target_role',
            'notification_type',
            'title',
            'message',
            'link',
            'severity',
            'is_read',
            'read_at',
            'delivery_status',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'delivery_status', 'created_at']


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'recipient',
            'target_role',
            'notification_type',
            'title',
            'message',
            'link',
            'severity',
            'metadata',
        ]
