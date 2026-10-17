from django.test import TestCase
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from .models import Department, Doctor
from apps.accounts.models import User, Role


class DepartmentAPITests(TestCase):
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

        cls.dept = Department.objects.create(
            name='Neurology',
            slug='neurology',
            icon='flaticon-stethoscope',
            description='Brain & nervous system treatments',
            is_active=True
        )
        cls.doctor = Doctor.objects.create(
            name='Dr. Lloyd Wilson',
            slug='dr-lloyd-wilson',
            department=cls.dept,
            position='Neurologist',
            qualification='MD, DM',
            is_active=True
        )
        cls.admin_user = User.objects.create_superuser(
            email='admin.dept@mediplus.com',
            password='AdminPassword123!',
            full_name='Dept Admin'
        )
        cls.patient_user = User.objects.create_user(
            email='patient.dept@mediplus.com',
            password='PatientPassword123!',
            full_name='Dept Patient',
            role=Role.PATIENT
        )

    def setUp(self):
        self.client = APIClient()

    def test_list_departments(self):
        response = self.client.get('/api/v1/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Neurology')

    def test_list_doctors(self):
        response = self.client.get('/api/v1/doctors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Dr. Lloyd Wilson')

    def test_admin_can_create_department(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'name': 'Cardiology & Vascular Surgery',
            'icon': 'flaticon-heart',
            'description': 'Advanced cardiovascular clinical care.'
        }
        response = self.client.post('/api/v1/departments/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['name'], 'Cardiology & Vascular Surgery')
        self.assertIn('cardiology', response.json()['slug'])

    def test_unauthenticated_cannot_create_department(self):
        payload = {'name': 'Unauthorized Dept', 'description': 'Test'}
        response = self.client.post('/api/v1/departments/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_create_department(self):
        self.client.force_authenticate(user=self.patient_user)
        payload = {'name': 'Patient Created Dept', 'description': 'Test'}
        response = self.client.post('/api/v1/departments/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_and_assign_doctor(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'name': 'Dr. Sarah Connor',
            'department': self.dept.id,
            'position': 'Chief Neurosurgeon',
            'qualification': 'FRCS, MBBS',
            'phone': '+1 555-0987',
            'email': 'sarah.connor@mediplus.com',
            'bio': 'Specialist in robotic spinal and neurosurgical interventions.'
        }
        response = self.client.post('/api/v1/doctors/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['department'], self.dept.id)
        self.assertEqual(data['department_name'], 'Neurology')
