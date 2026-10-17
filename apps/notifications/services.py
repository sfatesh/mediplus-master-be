from django.utils import timezone
from django.db.models import Q
from .models import Notification
from apps.accounts.models import Role


def send_notification(
    title: str,
    message: str,
    notification_type: str = Notification.NotificationType.OPERATIONAL,
    recipient=None,
    target_role=None,
    link: str = None,
    severity: str = Notification.Severity.INFO,
    metadata: dict = None
) -> Notification:
    """
    Creates and records a notification addressed to an individual user or broadcast to a role.
    """
    return Notification.objects.create(
        recipient=recipient,
        target_role=target_role,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
        severity=severity,
        delivery_status=Notification.DeliveryStatus.SENT,
        metadata=metadata or {}
    )


def get_user_notifications(user):
    """
    Returns notifications for the user: direct recipient OR role-targeted broadcast.
    """
    if not user or not user.is_authenticated:
        return Notification.objects.none()

    role = getattr(user, 'role', None)
    return Notification.objects.filter(
        Q(recipient=user) | Q(recipient__isnull=True, target_role=role)
    ).order_by('-created_at')


def mark_notification_as_read(notification_id: int, user) -> bool:
    """
    Marks a notification as read if it belongs to the user or is targeted to their role.
    """
    qs = get_user_notifications(user).filter(id=notification_id)
    notif = qs.first()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save(update_fields=['is_read', 'read_at', 'updated_at'])
        return True
    return False


def mark_all_notifications_as_read(user) -> int:
    """
    Marks all notifications for this user as read.
    """
    qs = get_user_notifications(user).filter(is_read=False)
    now = timezone.now()
    count = qs.update(is_read=True, read_at=now, updated_at=now)
    return count
