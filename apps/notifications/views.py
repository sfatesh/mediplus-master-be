from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Notification
from .serializers import NotificationSerializer, NotificationCreateSerializer
from .services import (
    get_user_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    send_notification,
)
from apps.accounts.models import Role


@extend_schema_view(
    list=extend_schema(summary="List notifications for the current authenticated user"),
    retrieve=extend_schema(summary="Retrieve a notification by ID"),
)
class NotificationsViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return get_user_notifications(self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def create(self, request, *args, **kwargs):
        # Only admin or internal staff can manually create notifications
        if request.user.role not in [Role.ADMIN, Role.DOCTOR, Role.RECEPTIONIST, Role.NURSE]:
            return Response(
                {"detail": "Permission denied. Only staff can dispatch notifications."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        notif = send_notification(
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', Notification.NotificationType.OPERATIONAL),
            recipient=data.get('recipient'),
            target_role=data.get('target_role'),
            link=data.get('link'),
            severity=data.get('severity', Notification.Severity.INFO),
            metadata=data.get('metadata')
        )
        return Response(NotificationSerializer(notif).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Returns the number of unread notifications for the active user."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=['post'], url_path='mark-as-read')
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        success = mark_notification_as_read(pk, request.user)
        if success:
            return Response({"detail": "Notification marked as read."})
        return Response({"detail": "Notification not found or already read."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all unread notifications for current user as read."""
        count = mark_all_notifications_as_read(request.user)
        return Response({
            "detail": f"{count} notifications marked as read.",
            "marked_count": count,
            "unread_count": 0
        })
