from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.patients.models import Patient, PatientConsent
from apps.audit.models import AuditLog


class PatientAuthorizationAndIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Doctor user
        self.doctor_user = User.objects.create_user(
            email='dr.test@mediplus.com',
            password='DoctorPassword123!',
            full_name='Dr. Gregory House',
            role=Role.DOCTOR
        )

        # Nurse user
        self.nurse_user = User.objects.create_user(
            email='nurse.test@mediplus.com',
            password='NursePassword123!',
            full_name='Nurse Jackie',
            role=Role.NURSE
        )

        # Receptionist user
        self.receptionist_user = User.objects.create_user(
            email='receptionist.test@mediplus.com',
            password='ReceptionPassword123!',
            full_name='Receptionist Pam',
            role=Role.RECEPTIONIST
        )

        # Patient A
        self.patient_a_user = User.objects.create_user(
            email='patient_a@mediplus.com',
            password='Password123!',
            full_name='Arthur Dent',
            role=Role.PATIENT
        )
        self.patient_a = Patient.objects.create(
            user=self.patient_a_user,
            medical_record_number='MED-2026-0001',
            first_name='Arthur',
            last_name='Dent',
            date_of_birth='1985-03-11',
            phone='+1 555-1111',
            email='patient_a@mediplus.com',
            blood_group='O+',
            city='London',
            emergency_contact_name='Trillian Astra',
            emergency_contact_phone='+1 555-9876',
            guardian_name='Slartibartfast',
            guardian_relationship='Uncle',
            guardian_phone='+1 555-5432',
            is_active=True
        )

        # Patient B
        self.patient_b_user = User.objects.create_user(
            email='patient_b@mediplus.com',
            password='Password123!',
            full_name='Ford Prefect',
            role=Role.PATIENT
        )
        self.patient_b = Patient.objects.create(
            user=self.patient_b_user,
            medical_record_number='MED-2026-0002',
            first_name='Ford',
            last_name='Prefect',
            date_of_birth='1982-07-20',
            phone='+1 555-2222',
            email='patient_b@mediplus.com',
            blood_group='AB-',
            city='Betelgeuse',
            is_active=True
        )

    def test_unauthenticated_request_rejected(self):
        response = self.client.get('/api/v1/patients/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_list_isolated_to_own_record(self):
        """A patient querying the patients list should ONLY see their own record."""
        self.client.force_authenticate(user=self.patient_a_user)
        response = self.client.get('/api/v1/patients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['medical_record_number'], 'MED-2026-0001')

    def test_patient_cannot_view_other_patient_data(self):
        """Patient A must NOT be able to access Patient B's record."""
        self.client.force_authenticate(user=self.patient_a_user)
        response = self.client.get(f'/api/v1/patients/{self.patient_b.id}/')
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_patient_can_view_own_record(self):
        self.client.force_authenticate(user=self.patient_a_user)
        response = self.client.get(f'/api/v1/patients/{self.patient_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['medical_record_number'], 'MED-2026-0001')
        self.assertEqual(response.json()['guardian_name'], 'Slartibartfast')

    def test_patient_my_profile_endpoint(self):
        self.client.force_authenticate(user=self.patient_a_user)
        response = self.client.get('/api/v1/patients/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['first_name'], 'Arthur')

    def test_staff_can_view_all_patients(self):
        """Doctors, nurses and receptionists must have access to all patient records."""
        for staff_user in [self.doctor_user, self.nurse_user, self.receptionist_user]:
            self.client.force_authenticate(user=staff_user)
            response = self.client.get('/api/v1/patients/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['count'], 2)

    def test_staff_patient_search_and_filtering(self):
        """Verify search by MRN and filtering by blood group/city."""
        self.client.force_authenticate(user=self.doctor_user)
        # Search by MRN
        search_resp = self.client.get('/api/v1/patients/?search=MED-2026-0001')
        self.assertEqual(search_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(search_resp.json()['count'], 1)

        # Filter by blood group
        filter_resp = self.client.get('/api/v1/patients/?blood_group=AB-')
        self.assertEqual(filter_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(filter_resp.json()['count'], 1)
        self.assertEqual(filter_resp.json()['results'][0]['last_name'], 'Prefect')

    def test_duplicate_detection_rejects_duplicate_patient(self):
        """Creating a patient with matching email or name+DOB is rejected with duplicate validation error."""
        self.client.force_authenticate(user=self.receptionist_user)
        payload = {
            'first_name': 'Arthur',
            'last_name': 'Dent',
            'date_of_birth': '1985-03-11',
            'phone': '+1 555-9999',
            'email': 'different_email@example.com'
        }
        response = self.client.post('/api/v1/patients/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duplicate', str(response.json()).lower())

    def test_check_duplicate_api_action(self):
        """Real-time duplicate check returns matching records."""
        self.client.force_authenticate(user=self.receptionist_user)
        payload = {
            'first_name': 'Arthur',
            'last_name': 'Dent',
            'date_of_birth': '1985-03-11'
        }
        response = self.client.post('/api/v1/patients/check-duplicate/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['is_duplicate'])
        self.assertGreaterEqual(data['match_count'], 1)

    def test_auditable_demographic_change_logging(self):
        """Updating demographics creates audit log diff and audit log retrieval endpoint works."""
        self.client.force_authenticate(user=self.receptionist_user)
        patch_payload = {
            'city': 'Cambridge',
            'phone': '+1 555-8888',
            'guardian_phone': '+1 555-7777'
        }
        response = self.client.patch(f'/api/v1/patients/{self.patient_a.id}/', patch_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check audit log endpoint
        audit_resp = self.client.get(f'/api/v1/patients/{self.patient_a.id}/audit-logs/')
        self.assertEqual(audit_resp.status_code, status.HTTP_200_OK)
        logs = audit_resp.json()
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]['action'], 'PATIENT_RECORD_UPDATED')

    def test_patient_consent_recording_and_retrieval(self):
        """Consent can be recorded and verified."""
        self.client.force_authenticate(user=self.doctor_user)
        payload = {
            'consent_type': 'DATA_SHARING',
            'status': 'GRANTED',
            'signed_by': 'Arthur Dent',
            'notes': 'Patient consented to sharing lab data with cardiology specialist.'
        }
        response = self.client.post(
            f'/api/v1/patients/{self.patient_a.id}/consents/',
            payload,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify consent is linked to patient
        self.client.force_authenticate(user=self.patient_a_user)
        view_resp = self.client.get(f'/api/v1/patients/{self.patient_a.id}/')
        self.assertEqual(view_resp.status_code, status.HTTP_200_OK)
        consents = view_resp.json().get('consents', [])
        self.assertEqual(len(consents), 1)
        self.assertEqual(consents[0]['consent_type'], 'DATA_SHARING')
