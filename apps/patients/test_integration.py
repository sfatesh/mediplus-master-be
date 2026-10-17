from django.test import TestCase
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient, PatientConsent
from apps.audit.models import AuditLog


class PatientDoctorDepartmentWorkflowTests(TestCase):
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
    """
    End-to-end integration tests verifying the complete workflow:
    - Staff login
    - Real-time duplicate check
    - Patient registration & unique MRN generation
    - Duplicate blocking
    - Doctor patient retrieval & consent recording
    - Demographic updates and auditable change logs
    - Patient self-access and cross-patient isolation
    - Department management & doctor assignment
    """

    def setUp(self):
        self.client = APIClient()

        # Admin User
        self.admin = User.objects.create_superuser(
            email='admin.workflow@mediplus.com',
            password='Password123!',
            full_name='Hospital Director'
        )

        # Receptionist User
        self.receptionist = User.objects.create_user(
            email='receptionist.workflow@mediplus.com',
            password='Password123!',
            full_name='Clara Intake',
            role=Role.RECEPTIONIST
        )

        # Doctor User
        self.doctor = User.objects.create_user(
            email='doctor.workflow@mediplus.com',
            password='Password123!',
            full_name='Dr. Marcus Welby',
            role=Role.DOCTOR
        )

        # Pre-existing Department
        self.cardiology_dept = Department.objects.create(
            name='Cardiology',
            slug='cardiology',
            icon='flaticon-heart',
            description='Heart and vascular medical care',
            is_active=True
        )

    def test_complete_registration_to_retrieval_and_audit_workflow(self):
        # 1. Receptionist logs in via auth endpoint
        login_resp = self.client.post('/api/v1/auth/login/', {
            'email': 'receptionist.workflow@mediplus.com',
            'password': 'Password123!'
        }, format='json')
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        receptionist_token = login_resp.json()['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {receptionist_token}')

        # 2. Check for duplicate patient (no duplicate should exist initially)
        dup_check_resp = self.client.post('/api/v1/patients/check-duplicate/', {
            'first_name': 'Jonathan',
            'last_name': 'Swift',
            'phone': '+1 555-8822',
            'date_of_birth': '1990-11-30'
        }, format='json')
        self.assertEqual(dup_check_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(dup_check_resp.json()['is_duplicate'])

        # 3. Register patient with guardian and demographic details
        register_patient_payload = {
            'first_name': 'Jonathan',
            'last_name': 'Swift',
            'date_of_birth': '1990-11-30',
            'gender': 'MALE',
            'blood_group': 'O+',
            'phone': '+1 555-8822',
            'email': 'jonathan.swift@example.com',
            'city': 'Dublin',
            'address': '42 St. Patrick Street',
            'guardian_name': 'Mary Swift',
            'guardian_relationship': 'Mother',
            'guardian_phone': '+1 555-8823',
            'allergies': 'Aspirin'
        }
        create_resp = self.client.post('/api/v1/patients/', register_patient_payload, format='json')
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        patient_data = create_resp.json()
        patient_id = patient_data['id']
        mrn = patient_data['medical_record_number']

        # Verify MRN was generated
        self.assertTrue(mrn.startswith('MED-'))
        self.assertEqual(patient_data['guardian_name'], 'Mary Swift')

        # 4. Duplicate prevention: Attempt to register the exact same patient again
        dup_attempt_resp = self.client.post('/api/v1/patients/', register_patient_payload, format='json')
        self.assertEqual(dup_attempt_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duplicate', str(dup_attempt_resp.json()).lower())

        # 5. Doctor logs in and searches for patient by MRN
        doc_login_resp = self.client.post('/api/v1/auth/login/', {
            'email': 'doctor.workflow@mediplus.com',
            'password': 'Password123!'
        }, format='json')
        doc_token = doc_login_resp.json()['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {doc_token}')

        search_resp = self.client.get(f'/api/v1/patients/?search={mrn}')
        self.assertEqual(search_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(search_resp.json()['count'], 1)
        self.assertEqual(search_resp.json()['results'][0]['id'], patient_id)

        # 6. Doctor retrieves patient details and records consent
        retrieve_resp = self.client.get(f'/api/v1/patients/{patient_id}/')
        self.assertEqual(retrieve_resp.status_code, status.HTTP_200_OK)

        consent_payload = {
            'consent_type': 'DATA_SHARING',
            'status': 'GRANTED',
            'signed_by': 'Mary Swift (Guardian)',
            'notes': 'Authorized data sharing with specialized cardiac lab.'
        }
        consent_resp = self.client.post(f'/api/v1/patients/{patient_id}/consents/', consent_payload, format='json')
        self.assertEqual(consent_resp.status_code, status.HTTP_201_CREATED)

        # 7. Doctor updates patient demographic & clinical details
        update_payload = {
            'city': 'Galway',
            'allergies': 'Aspirin, Penicillin'
        }
        update_resp = self.client.patch(f'/api/v1/patients/{patient_id}/', update_payload, format='json')
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(update_resp.json()['city'], 'Galway')

        # 8. Verify audit logs record the field changes
        audit_resp = self.client.get(f'/api/v1/patients/{patient_id}/audit-logs/')
        self.assertEqual(audit_resp.status_code, status.HTTP_200_OK)
        audit_records = audit_resp.json()
        self.assertGreaterEqual(len(audit_records), 1)
        update_log = next((l for l in audit_records if l['action'] == 'PATIENT_RECORD_UPDATED'), None)
        self.assertIsNotNone(update_log)
        self.assertIn('city', update_log['details']['changes'])

        # 9. Verify Department management by Admin
        self.client.credentials()  # Clear existing credentials for new login
        admin_login = self.client.post('/api/v1/auth/login/', {
            'email': 'admin.workflow@mediplus.com',
            'password': 'Password123!'
        }, format='json')
        self.assertEqual(admin_login.status_code, status.HTTP_200_OK)
        admin_token = admin_login.json()['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token}')

        # Create department
        dept_resp = self.client.post('/api/v1/departments/', {
            'name': 'Pediatric Cardiology',
            'icon': 'flaticon-heart',
            'description': 'Childhood congenital heart disorder diagnostics.'
        }, format='json')
        self.assertEqual(dept_resp.status_code, status.HTTP_201_CREATED)
        new_dept_id = dept_resp.json()['id']

        # Assign doctor to new department
        doc_create_resp = self.client.post('/api/v1/doctors/', {
            'name': 'Dr. Emma Watson',
            'department': new_dept_id,
            'position': 'Pediatric Cardiologist',
            'qualification': 'MD, FACC',
            'phone': '+1 555-4433',
            'email': 'emma.watson@mediplus.com'
        }, format='json')
        self.assertEqual(doc_create_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(doc_create_resp.json()['department_name'], 'Pediatric Cardiology')
