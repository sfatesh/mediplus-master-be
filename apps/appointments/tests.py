from django.test import TestCase
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from .models import Appointment, DoctorSchedule, DoctorLeave, QueueEntry


class AppointmentSchedulingAndQueueTests(TestCase):
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (department_id) REFERENCES departments(id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number VARCHAR(50) UNIQUE NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(50) NOT NULL,
                    department_id INTEGER,
                    doctor_id INTEGER,
                    appointment_date VARCHAR(50) NOT NULL,
                    appointment_time VARCHAR(50) NOT NULL,
                    message TEXT,
                    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (department_id) REFERENCES departments(id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                );
            """)

        cls.dept = Department.objects.create(
            name='Cardiology',
            slug='cardiology',
            icon='flaticon-stethoscope',
            description='Heart care and surgery',
            is_active=True
        )
        cls.doctor = Doctor.objects.create(
            name='Dr. Marcus Vance',
            slug='dr-marcus-vance',
            department=cls.dept,
            position='Chief Cardiologist',
            qualification='MD, FACC',
            is_active=True
        )
        cls.receptionist = User.objects.create_user(
            email='receptionist.opd@mediplus.com',
            password='ReceptionPass123!',
            full_name='Nancy Receptionist',
            role=Role.RECEPTIONIST
        )

        # Working schedule: Monday to Friday 09:00 - 17:00
        for day in range(5):
            DoctorSchedule.objects.create(
                doctor=cls.doctor,
                day_of_week=day,
                start_time='09:00:00',
                end_time='17:00:00',
                slot_duration_minutes=30
            )

    def setUp(self):
        self.client = APIClient()

    def test_book_appointment_and_reference_lookup(self):
        payload = {
            'first_name': 'Victoria',
            'last_name': 'Sterling',
            'email': 'victoria@example.com',
            'phone': '+1 555-8822',
            'department_id': self.dept.id,
            'doctor_id': self.doctor.id,
            'appointment_date': '2026-11-20',
            'appointment_time': '10:00',
            'message': 'Consultation on cardiac checkup.'
        }
        response = self.client.post('/api/v1/appointments/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['first_name'], 'Victoria')
        self.assertTrue(data['reference_number'].startswith('MED-'))
        self.assertEqual(data['status'], 'PENDING')

        # Test lookup by reference number
        ref_no = data['reference_number']
        lookup_resp = self.client.get(f'/api/v1/appointments/{ref_no}/')
        self.assertEqual(lookup_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(lookup_resp.json()['reference_number'], ref_no)

    def test_prevent_double_booking_same_slot(self):
        """Concurrent or duplicate booking for same doctor, date and time must be rejected."""
        payload = {
            'first_name': 'Patient',
            'last_name': 'One',
            'phone': '+1 555-0001',
            'department_id': self.dept.id,
            'doctor_id': self.doctor.id,
            'appointment_date': '2026-11-25',
            'appointment_time': '11:00'
        }
        first_resp = self.client.post('/api/v1/appointments/', payload, format='json')
        self.assertEqual(first_resp.status_code, status.HTTP_201_CREATED)

        # Attempt to book exact same slot
        second_payload = {
            'first_name': 'Patient',
            'last_name': 'Two',
            'phone': '+1 555-0002',
            'department_id': self.dept.id,
            'doctor_id': self.doctor.id,
            'appointment_date': '2026-11-25',
            'appointment_time': '11:00'
        }
        second_resp = self.client.post('/api/v1/appointments/', second_payload, format='json')
        self.assertEqual(second_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already booked', str(second_resp.json()).lower())

    def test_slot_discovery_and_leave_handling(self):
        """Slots discovery lists available slots and flags doctor leave."""
        # Query slots for Monday 2026-11-23
        slots_resp = self.client.get(f'/api/v1/appointments/slots/?doctor_id={self.doctor.id}&date=2026-11-23')
        self.assertEqual(slots_resp.status_code, status.HTTP_200_OK)
        slots_data = slots_resp.json()
        self.assertTrue(slots_data['available'])
        self.assertGreater(slots_data['slot_count'], 5)

        # Schedule doctor leave on 2026-11-24
        DoctorLeave.objects.create(
            doctor=self.doctor,
            start_date='2026-11-24',
            end_date='2026-11-24',
            reason='Annual Cardiology Conference',
            is_approved=True
        )

        leave_slots_resp = self.client.get(f'/api/v1/appointments/slots/?doctor_id={self.doctor.id}&date=2026-11-24')
        self.assertEqual(leave_slots_resp.status_code, status.HTTP_200_OK)
        leave_data = leave_slots_resp.json()
        self.assertFalse(leave_data['available'])
        self.assertIn('leave', leave_data['reason'].lower())

    def test_check_in_and_queue_token_issuance(self):
        """Checking in patient moves appointment to CHECKED_IN and generates OPD token."""
        appointment = Appointment.objects.create(
            first_name='Oliver',
            last_name='Queen',
            phone='+1 555-3344',
            department=self.dept,
            doctor=self.doctor,
            appointment_date='2026-11-20',
            appointment_time='14:00',
            status='CONFIRMED'
        )

        self.client.force_authenticate(user=self.receptionist)
        checkin_resp = self.client.post(f'/api/v1/appointments/{appointment.id}/check-in/')
        self.assertEqual(checkin_resp.status_code, status.HTTP_200_OK)
        data = checkin_resp.json()
        self.assertEqual(data['appointment']['status'], 'CHECKED_IN')
        self.assertTrue(data['queue_entry']['token_number'].startswith('OPD-'))

    def test_reschedule_and_cancellation_workflow(self):
        self.client.force_authenticate(user=self.receptionist)
        appointment = Appointment.objects.create(
            first_name='Barry',
            last_name='Allen',
            phone='+1 555-9988',
            department=self.dept,
            doctor=self.doctor,
            appointment_date='2026-11-20',
            appointment_time='09:30',
            status='CONFIRMED'
        )

        # Reschedule
        reschedule_resp = self.client.post(f'/api/v1/appointments/{appointment.id}/reschedule/', {
            'appointment_date': '2026-11-21',
            'appointment_time': '15:30'
        }, format='json')
        self.assertEqual(reschedule_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(reschedule_resp.json()['appointment_date'], '2026-11-21')

        # Cancel
        cancel_resp = self.client.post(f'/api/v1/appointments/{appointment.id}/cancel/', {
            'cancellation_reason': 'Patient requested cancellation.'
        }, format='json')
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_resp.json()['status'], 'CANCELLED')

    def test_walk_in_registration_and_calling(self):
        """Walk-in patient receives token and doctor calls token."""
        self.client.force_authenticate(user=self.receptionist)
        walk_in_resp = self.client.post('/api/v1/appointments/walk-in/', {
            'doctor_id': self.doctor.id,
            'department_id': self.dept.id,
            'patient_name': 'Bruce Wayne',
            'patient_phone': '+1 555-7766',
            'priority': 2
        }, format='json')
        self.assertEqual(walk_in_resp.status_code, status.HTTP_201_CREATED)
        queue_data = walk_in_resp.json()
        queue_id = queue_data['id']
        self.assertEqual(queue_data['status'], 'WAITING')
        self.assertEqual(queue_data['priority'], 2)

        # Doctor calls patient from queue
        call_resp = self.client.post(f'/api/v1/appointments/queue/{queue_id}/call/')
        self.assertEqual(call_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(call_resp.json()['status'], 'CALLED')
