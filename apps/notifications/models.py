from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.accounts.models import Role


class Notification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        APPOINTMENT_REMINDER = 'APPOINTMENT_REMINDER', 'Appointment Reminder'
        APPOINTMENT_CHANGE = 'APPOINTMENT_CHANGE', 'Appointment Change'
        LAB_RESULT_READY = 'LAB_RESULT_READY', 'Laboratory Result Ready'
        BILLING_EVENT = 'BILLING_EVENT', 'Billing Event'
        CRITICAL_ALERT = 'CRITICAL_ALERT', 'Critical Observation Alert'
        OPERATIONAL = 'OPERATIONAL', 'Internal Operational Alert'

    class Severity(models.TextChoices):
        INFO = 'INFO', 'Information'
        SUCCESS = 'SUCCESS', 'Success'
        WARNING = 'WARNING', 'Warning'
        DANGER = 'DANGER', 'Critical / Danger'

    class DeliveryStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        db_index=True
    )
    target_role = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=Role.choices,
        db_index=True,
        help_text="If set, all users with this role can see this notification"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.OPERATIONAL,
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True)
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.SENT
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.notification_type}) - {'Read' if self.is_read else 'Unread'}"
