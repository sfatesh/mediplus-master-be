from django.test import TestCase
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, QueueEntry
from .models import Encounter, ClinicalNote, Prescription, PrescriptionItem


class ClinicalEncounterAndConsultationTests(TestCase):
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
            name='Internal Medicine',
            slug='internal-medicine',
            icon='flaticon-stethoscope',
            description='Comprehensive adult internal clinical care',
            is_active=True
        )
        cls.doctor = Doctor.objects.create(
            name='Dr. Gregory House',
            slug='dr-gregory-house',
            department=cls.dept,
            position='Diagnostic Medicine',
            qualification='MD',
            is_active=True
        )
        cls.doctor_user = User.objects.create_user(
            email='dr.house@mediplus.com',
            password='Password123!',
            full_name='Dr. Gregory House',
            role=Role.DOCTOR
        )

        cls.patient_user = User.objects.create_user(
            email='patient.clinical@mediplus.com',
            password='Password123!',
            full_name='John Clinical',
            role=Role.PATIENT
        )
        cls.patient = Patient.objects.create(
            user=cls.patient_user,
            medical_record_number='MED-2026-7777',
            first_name='John',
            last_name='Clinical',
            phone='+1 555-7777',
            date_of_birth='1988-06-15',
            blood_group='A+',
            is_active=True
        )

        cls.other_patient = Patient.objects.create(
            medical_record_number='MED-2026-8888',
            first_name='Jane',
            last_name='Other',
            phone='+1 555-8888',
            is_active=True
        )

    def setUp(self):
        self.client = APIClient()

    def test_complete_doctor_consultation_workflow(self):
        """Test encounter start, vitals, SOAP note, note signing, amendment, and prescription authorization."""
        self.client.force_authenticate(user=self.doctor_user)

        # 1. Start Encounter
        start_payload = {
            'patient_id': self.patient.id,
            'doctor_id': self.doctor.id,
            'encounter_type': 'OUTPATIENT',
            'chief_complaint': 'Persistent dry cough and mild fever for 4 days',
            'vitals': {
                'blood_pressure': '120/80',
                'pulse_rate': 78,
                'temperature_c': 37.8,
                'spo2_percent': 98,
                'weight_kg': 72.5
            }
        }
        start_resp = self.client.post('/api/v1/clinical/encounters/start/', start_payload, format='json')
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        enc_data = start_resp.json()
        encounter_id = enc_data['id']
        self.assertEqual(enc_data['status'], 'IN_PROGRESS')
        self.assertTrue(enc_data['encounter_number'].startswith('ENC-'))

        # 2. Add Clinical SOAP Note
        note_payload = {
            'subjective': 'Patient reports 4-day history of non-productive cough, low grade fever.',
            'objective': 'Lungs clear to auscultation bilaterally. Pharynx mildly erythematous.',
            'assessment': 'Acute viral upper respiratory tract infection.',
            'plan': 'Rest, hydration, symptomatic antipyretics, review if symptoms worsen.',
            'diagnoses': ['Acute Upper Respiratory Infection (J06.9)'],
            'follow_up_instructions': 'Return in 5 days if fever persists above 38.5C.',
            'follow_up_date': '2026-11-01'
        }
        note_resp = self.client.post(f'/api/v1/clinical/encounters/{encounter_id}/notes/', note_payload, format='json')
        self.assertEqual(note_resp.status_code, status.HTTP_201_CREATED)
        note_id = note_resp.json()['id']
        self.assertFalse(note_resp.json()['is_signed'])

        # 3. Doctor signs clinical note
        sign_resp = self.client.post(f'/api/v1/clinical/notes/{note_id}/sign/')
        self.assertEqual(sign_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(sign_resp.json()['is_signed'])
        self.assertIsNotNone(sign_resp.json()['signed_at'])

        # 4. Attempt to sign again should be rejected
        resign_resp = self.client.post(f'/api/v1/clinical/notes/{note_id}/sign/')
        self.assertEqual(resign_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 5. Doctor creates auditable amendment to signed note
        amend_payload = {
            'amendment_reason': 'Added diagnosis of mild seasonal allergic rhinitis based on nasal examination.',
            'subjective': note_payload['subjective'],
            'objective': 'Nasal turbinates mildly swollen and pale. Lungs clear.',
            'assessment': 'Acute viral URI with allergic rhinitis.',
            'plan': 'Add non-sedating antihistamine to previous plan.',
            'diagnoses': ['Acute URI (J06.9)', 'Allergic Rhinitis (J30.9)']
        }
        amend_resp = self.client.post(f'/api/v1/clinical/notes/{note_id}/amend/', amend_payload, format='json')
        self.assertEqual(amend_resp.status_code, status.HTTP_201_CREATED)
        amended_note = amend_resp.json()
        self.assertEqual(amended_note['version'], 2)
        self.assertEqual(amended_note['previous_version'], note_id)
        self.assertFalse(amended_note['is_signed'])

        # 6. Doctor adds prescription
        rx_payload = {
            'clinical_instructions': 'Take medications with plenty of water after food.',
            'items': [
                {
                    'medication_name': 'Paracetamol',
                    'dosage': '500 mg',
                    'frequency': 'Every 6-8 hours as needed for fever',
                    'duration': '3 days',
                    'route': 'Oral',
                    'quantity': 12,
                    'instructions': 'Do not exceed 4g daily.'
                },
                {
                    'medication_name': 'Cetirizine',
                    'dosage': '10 mg',
                    'frequency': 'Once daily at bedtime',
                    'duration': '7 days',
                    'route': 'Oral',
                    'quantity': 7,
                    'instructions': 'Take before sleep.'
                }
            ]
        }
        rx_resp = self.client.post(f'/api/v1/clinical/encounters/{encounter_id}/prescriptions/', rx_payload, format='json')
        self.assertEqual(rx_resp.status_code, status.HTTP_201_CREATED)
        rx_id = rx_resp.json()['id']
        self.assertEqual(rx_resp.json()['status'], 'DRAFT')
        self.assertEqual(len(rx_resp.json()['items']), 2)

        # 7. Doctor authorizes prescription
        auth_rx_resp = self.client.post(f'/api/v1/clinical/prescriptions/{rx_id}/authorize/')
        self.assertEqual(auth_rx_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_rx_resp.json()['status'], 'AUTHORIZED')

        # 8. Complete encounter
        complete_resp = self.client.post(f'/api/v1/clinical/encounters/{encounter_id}/complete/')
        self.assertEqual(complete_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_resp.json()['status'], 'COMPLETED')
        self.assertIsNotNone(complete_resp.json()['completed_at'])

    def test_patient_encounter_isolation(self):
        """Patient can only access their own encounters."""
        enc = Encounter.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            encounter_type='OUTPATIENT',
            status='COMPLETED'
        )
        other_enc = Encounter.objects.create(
            patient=self.other_patient,
            doctor=self.doctor,
            encounter_type='OUTPATIENT',
            status='COMPLETED'
        )

        self.client.force_authenticate(user=self.patient_user)

        # Listing encounters
        list_resp = self.client.get('/api/v1/clinical/encounters/')
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = list_resp.json().get('results', list_resp.json())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], enc.id)

        # Accessing other patient's encounter directly
        other_resp = self.client.get(f'/api/v1/clinical/encounters/{other_enc.id}/')
        self.assertIn(other_resp.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

