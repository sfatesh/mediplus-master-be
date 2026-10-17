from django.test import TestCase
from django.db import connection
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.notifications.models import Notification
from apps.notifications.services import (
    send_notification,
    get_user_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
)


class NotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    icon VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    image_url VARCHAR(255),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doctors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    department_id INTEGER,
                    position VARCHAR(100) NOT NULL,
                    qualification VARCHAR(100) NOT NULL,
                    bio TEXT,
                    photo_url VARCHAR(255),
                    phone VARCHAR(50),
                    email VARCHAR(100),
                    twitter VARCHAR(255),
                    facebook VARCHAR(255),
                    google_plus VARCHAR(255),
                    instagram VARCHAR(255),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        cls.admin_user = User.objects.create_user(
            email='admin@mediplus.com',
            full_name='Hospital Admin',
            role=Role.ADMIN,
            password='AdminPass123!'
        )
        cls.nurse_user = User.objects.create_user(
            email='nurse@mediplus.com',
            full_name='Florence Nurse',
            role=Role.NURSE,
            password='NursePass123!'
        )
        cls.patient_user = User.objects.create_user(
            email='patient@mediplus.com',
            full_name='John Patient',
            role=Role.PATIENT,
            password='PatientPass123!'
        )

    def setUp(self):
        self.client = APIClient()

    def test_send_and_retrieve_direct_notification(self):
        notif = send_notification(
            title="Appointment Reminder",
            message="Your appointment is tomorrow at 10:00 AM.",
            notification_type=Notification.NotificationType.APPOINTMENT_REMINDER,
            recipient=self.patient_user,
            severity=Notification.Severity.INFO
        )
        self.assertEqual(notif.recipient, self.patient_user)
        self.assertFalse(notif.is_read)

        # Retrieve for patient
        patient_notifs = get_user_notifications(self.patient_user)
        self.assertIn(notif, patient_notifs)

        # Should not appear for nurse
        nurse_notifs = get_user_notifications(self.nurse_user)
        self.assertNotIn(notif, nurse_notifs)

    def test_broadcast_role_notification(self):
        # Broadcast to NURSE role
        nurse_alert = send_notification(
            title="Ward Observation Alert",
            message="Critical vitals recorded in ICU Ward.",
            notification_type=Notification.NotificationType.CRITICAL_ALERT,
            target_role=Role.NURSE,
            severity=Notification.Severity.DANGER
        )
        # Nurse sees it
        nurse_notifs = get_user_notifications(self.nurse_user)
        self.assertIn(nurse_alert, nurse_notifs)

        # Patient does not see it
        patient_notifs = get_user_notifications(self.patient_user)
        self.assertNotIn(nurse_alert, patient_notifs)

    def test_mark_as_read_and_unread_count_api(self):
        send_notification(
            title="Test 1",
            message="Message 1",
            recipient=self.nurse_user
        )
        notif2 = send_notification(
            title="Test 2",
            message="Message 2",
            recipient=self.nurse_user
        )

        self.client.force_authenticate(user=self.nurse_user)
        res = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['unread_count'], 2)

        # Mark single as read
        res_mark = self.client.post(f'/api/v1/notifications/{notif2.id}/mark-as-read/')
        self.assertEqual(res_mark.status_code, 200)

        res2 = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(res2.data['unread_count'], 1)

        # Mark all read
        res_all = self.client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(res_all.status_code, 200)

        res3 = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(res3.data['unread_count'], 0)

