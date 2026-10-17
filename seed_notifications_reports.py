import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User, Role
from apps.notifications.models import Notification
from apps.notifications.services import send_notification

def seed_notifications():
    admin = User.objects.filter(role=Role.ADMIN).first()
    doctor = User.objects.filter(role=Role.DOCTOR).first()
    nurse = User.objects.filter(role=Role.NURSE).first()

    # Seed broadcast notifications for staff
    send_notification(
        title="Scheduled System Maintenance",
        message="Hospital PACS and EMR will undergo backup maintenance on Sunday 02:00 AM.",
        notification_type=Notification.NotificationType.OPERATIONAL,
        target_role=Role.ADMIN,
        severity=Notification.Severity.INFO
    )

    send_notification(
        title="Critical Vital Signs Alert - ICU Bed 04",
        message="Patient SpO2 dropped below 88%. Immediate nursing assessment required.",
        notification_type=Notification.NotificationType.CRITICAL_ALERT,
        target_role=Role.NURSE,
        link="/nursing",
        severity=Notification.Severity.DANGER
    )

    send_notification(
        title="Pending Prescriptions for Dispensing",
        message="3 new outpatient prescriptions authorized by attending physicians.",
        notification_type=Notification.NotificationType.OPERATIONAL,
        target_role=Role.PHARMACIST,
        link="/pharmacy",
        severity=Notification.Severity.WARNING
    )

    send_notification(
        title="STAT Electrolytes Panel Ordered",
        message="STAT lab order placed for emergency admission. Specimen collection pending.",
        notification_type=Notification.NotificationType.OPERATIONAL,
        target_role=Role.LAB_TECHNICIAN,
        link="/laboratory",
        severity=Notification.Severity.WARNING
    )

    if doctor:
        send_notification(
            title="Diagnostic Pathology Results Ready",
            message="Comprehensive Metabolic Panel verified by pathologist for John Doe.",
            notification_type=Notification.NotificationType.LAB_RESULT_READY,
            recipient=doctor,
            link="/laboratory",
            severity=Notification.Severity.SUCCESS
        )

    if admin:
        send_notification(
            title="Daily Revenue Settlement Summary",
            message="Financial batch reconciliation completed. Net collections: $4,850.00.",
            notification_type=Notification.NotificationType.BILLING_EVENT,
            recipient=admin,
            link="/billing",
            severity=Notification.Severity.SUCCESS
        )

    print("Initial notifications seeded successfully.")

if __name__ == '__main__':
    seed_notifications()

