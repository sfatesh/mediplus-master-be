from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.audit.models import AuditLog


class AuthenticationAndSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            email='admin.test@mediplus.com',
            password='AdminPassword123!',
            full_name='System Admin'
        )

        # Standard Patient user
        self.patient_user = User.objects.create_user(
            email='patient.test@mediplus.com',
            password='PatientPassword123!',
            full_name='Alice Patient',
            role=Role.PATIENT
        )

        # Inactive / Disabled user
        self.disabled_user = User.objects.create_user(
            email='disabled.test@mediplus.com',
            password='DisabledPassword123!',
            full_name='Disabled User',
            role=Role.PATIENT,
            is_active=False
        )

    def test_successful_registration(self):
        payload = {
            'email': 'new.patient@mediplus.com',
            'password': 'SecurePassword123!',
            'full_name': 'Robert Brown',
            'phone': '+1 555-0999',
            'role': 'PATIENT'
        }
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn('token', data)
        self.assertEqual(data['user']['email'], 'new.patient@mediplus.com')
        self.assertEqual(data['user']['role'], Role.PATIENT)
        self.assertTrue(data['user']['patient_mrn'].startswith('MED-'))

    def test_role_escalation_attempt_on_registration_fails(self):
        """Unauthenticated user trying to register with an elevated role must be rejected."""
        for elevated_role in [Role.ADMIN, Role.DOCTOR, Role.NURSE]:
            payload = {
                'email': f'attacker_{elevated_role.lower()}@mediplus.com',
                'password': 'AttackerPass123!',
                'full_name': 'Malicious User',
                'role': elevated_role
            }
            response = self.client.post('/api/v1/auth/register/', payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            # Verify security audit log recorded the attempt
            self.assertTrue(
                AuditLog.objects.filter(action='ROLE_ESCALATION_ATTEMPT').exists()
            )

    def test_successful_login(self):
        payload = {
            'email': 'patient.test@mediplus.com',
            'password': 'PatientPassword123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('token', data)
        self.assertEqual(data['user']['email'], 'patient.test@mediplus.com')
        self.assertEqual(data['user']['role'], Role.PATIENT)

    def test_login_invalid_password(self):
        payload = {
            'email': 'patient.test@mediplus.com',
            'password': 'WrongPassword123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_email(self):
        payload = {
            'email': 'doesnotexist@mediplus.com',
            'password': 'AnyPassword123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_disabled_account_rejected(self):
        """Disabled accounts must be rejected with 403 Forbidden."""
        payload = {
            'email': 'disabled.test@mediplus.com',
            'password': 'DisabledPassword123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('disabled', str(response.json()).lower())

    def test_unauthorized_profile_request(self):
        """Accessing protected profile without credentials must return 401."""
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_profile_access(self):
        self.client.force_authenticate(user=self.patient_user)
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['email'], self.patient_user.email)

    def test_profile_role_escalation_attempt_fails(self):
        """A user cannot elevate their role by sending PATCH /api/v1/auth/me/ with role=ADMIN."""
        self.client.force_authenticate(user=self.patient_user)
        patch_payload = {'role': Role.ADMIN, 'full_name': 'Alice Patient Updated'}
        response = self.client.patch('/api/v1/auth/me/', patch_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Ensure role remains PATIENT in database
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.role, Role.PATIENT)

    def test_password_reset_and_recovery_flow(self):
        """Test complete password reset lifecycle."""
        # Step 1: Request reset
        request_resp = self.client.post(
            '/api/v1/auth/password-reset/',
            {'email': self.patient_user.email},
            format='json'
        )
        self.assertEqual(request_resp.status_code, status.HTTP_200_OK)
        uidb64 = request_resp.json().get('uidb64')
        token = request_resp.json().get('token')
        self.assertIsNotNone(uidb64)
        self.assertIsNotNone(token)

        # Step 2: Confirm reset with new password
        confirm_resp = self.client.post(
            '/api/v1/auth/password-reset-confirm/',
            {
                'uidb64': uidb64,
                'token': token,
                'new_password': 'BrandNewPassword789!'
            },
            format='json'
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        # Step 3: Login with new password
        login_resp = self.client.post(
            '/api/v1/auth/login/',
            {
                'email': self.patient_user.email,
                'password': 'BrandNewPassword789!'
            },
            format='json'
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

    def test_logout_invalidates_token(self):
        # Login to obtain token
        login_resp = self.client.post(
            '/api/v1/auth/login/',
            {
                'email': 'patient.test@mediplus.com',
                'password': 'PatientPassword123!'
            },
            format='json'
        )
        token_key = login_resp.json()['token']

        # Use token to call logout
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token_key}')
        logout_resp = self.client.post('/api/v1/auth/logout/')
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        # Verify token is invalidated
        profile_resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(profile_resp.status_code, status.HTTP_401_UNAUTHORIZED)
