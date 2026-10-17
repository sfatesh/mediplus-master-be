from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import (
    User,
    Role,
    AppPermission,
    RolePermission,
    UserCustomPermission,
)
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.billing.models import Invoice, Payment, Refund
from django.db import connection
from apps.clinical.models import Encounter, ClinicalNote
from apps.laboratory.models import LabTestCatalogue, LabOrder, LabOrderItem, LabResult


class RBACBackendIntegrationTestCase(TestCase):
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
            name="General Medicine RBAC",
            slug="general-medicine-rbac",
            icon="flaticon-stethoscope",
            description="General medicine department",
            is_active=True
        )
        cls.doc_entity = Doctor.objects.create(
            name="Dr. Test Bennett",
            slug="dr-test-bennett-rbac",
            department=cls.dept,
            position="Senior Consultant",
            qualification="MD",
            email="doctor_rbac@mediplus.com",
            is_active=True
        )

    def setUp(self):
        self.client = APIClient()

        # Seed roles and permissions
        call_command('init_roles_and_permissions')

        # Create user accounts for each of the 9 roles
        self.superadmin = User.objects.create_user(
            email='superadmin_test@mediplus.com',
            password='TestPassword123!',
            full_name='Super Admin User',
            role=Role.SUPER_ADMIN,
            is_superuser=True
        )

        self.admin = User.objects.create_user(
            email='admin_test@mediplus.com',
            password='TestPassword123!',
            full_name='Hospital Admin User',
            role=Role.ADMIN
        )

        self.doctor = User.objects.create_user(
            email='doctor_test@mediplus.com',
            password='TestPassword123!',
            full_name='Dr. Test Bennett',
            role=Role.DOCTOR
        )

        self.nurse = User.objects.create_user(
            email='nurse_test@mediplus.com',
            password='TestPassword123!',
            full_name='Nurse Test Watson',
            role=Role.NURSE
        )

        self.receptionist = User.objects.create_user(
            email='receptionist_test@mediplus.com',
            password='TestPassword123!',
            full_name='Receptionist Test Sarah',
            role=Role.RECEPTIONIST
        )

        self.pharmacist = User.objects.create_user(
            email='pharmacist_test@mediplus.com',
            password='TestPassword123!',
            full_name='Pharmacist Test Marcus',
            role=Role.PHARMACIST
        )

        self.labtech = User.objects.create_user(
            email='labtech_test@mediplus.com',
            password='TestPassword123!',
            full_name='LabTech Test Rachel',
            role=Role.LAB_TECHNICIAN
        )

        self.billing_staff = User.objects.create_user(
            email='billing_test@mediplus.com',
            password='TestPassword123!',
            full_name='Billing Staff Victoria',
            role=Role.BILLING_STAFF
        )

        self.patient_user1 = User.objects.create_user(
            email='patient1_test@mediplus.com',
            password='TestPassword123!',
            full_name='Patient Alice',
            role=Role.PATIENT
        )

        self.patient_user2 = User.objects.create_user(
            email='patient2_test@mediplus.com',
            password='TestPassword123!',
            full_name='Patient Bob',
            role=Role.PATIENT
        )

        self.patient1 = Patient.objects.create(
            user=self.patient_user1,
            medical_record_number='MED-TEST-0001',
            first_name='Alice',
            last_name='Smith',
            phone='+1 555-001',
            email='patient1_test@mediplus.com',
            is_active=True
        )

        self.patient2 = Patient.objects.create(
            user=self.patient_user2,
            medical_record_number='MED-TEST-0002',
            first_name='Bob',
            last_name='Jones',
            phone='+1 555-002',
            email='patient2_test@mediplus.com',
            is_active=True
        )

    # -------------------------------------------------------------
    # 1. Model & Effective Permissions Tests
    # -------------------------------------------------------------
    def test_superadmin_has_wildcard_permission(self):
        self.assertTrue(self.superadmin.is_super_admin)
        self.assertTrue(self.superadmin.is_admin)
        self.assertTrue(self.superadmin.is_hospital_staff)
        self.assertTrue(self.superadmin.has_app_permission('any.custom.perm'))
        self.assertIn('*', self.superadmin.get_all_permissions())

    def test_role_default_permissions_mapping(self):
        # Doctor permissions check
        self.assertTrue(self.doctor.has_app_permission('clinical.consultation_create'))
        self.assertTrue(self.doctor.has_app_permission('clinical.consultation_sign'))
        self.assertFalse(self.doctor.has_app_permission('billing.refund_approve'))
        self.assertFalse(self.doctor.has_app_permission('pharmacy.dispense'))

        # Nurse permissions check
        self.assertTrue(self.nurse.has_app_permission('nursing.vitals_record'))
        self.assertTrue(self.nurse.has_app_permission('nursing.medication_administer'))
        self.assertFalse(self.nurse.has_app_permission('clinical.consultation_sign'))
        self.assertFalse(self.nurse.has_app_permission('billing.invoice_create'))

        # Receptionist permissions check
        self.assertTrue(self.receptionist.has_app_permission('patients.create'))
        self.assertTrue(self.receptionist.has_app_permission('appointments.create'))
        self.assertFalse(self.receptionist.has_app_permission('clinical.consultation_sign'))

        # Billing staff check
        self.assertTrue(self.billing_staff.has_app_permission('billing.invoice_create'))
        self.assertTrue(self.billing_staff.has_app_permission('billing.payment_record'))
        self.assertFalse(self.billing_staff.has_app_permission('billing.refund_approve'))

    def test_user_custom_permission_override_grant_and_revoke(self):
        # Grant doctor the permission to dispense medication
        dispense_perm = AppPermission.objects.get(codename='pharmacy.dispense')
        UserCustomPermission.objects.create(
            user=self.doctor,
            permission=dispense_perm,
            is_granted=True
        )
        self.assertTrue(self.doctor.has_app_permission('pharmacy.dispense'))

        # Revoke consultation_sign from doctor
        sign_perm = AppPermission.objects.get(codename='clinical.consultation_sign')
        UserCustomPermission.objects.create(
            user=self.doctor,
            permission=sign_perm,
            is_granted=False
        )
        self.assertFalse(self.doctor.has_app_permission('clinical.consultation_sign'))

    # -------------------------------------------------------------
    # 2. Authentication, Login & Profile Endpoints
    # -------------------------------------------------------------
    def test_auth_me_returns_permissions_list(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('permissions', response.data)
        self.assertIn('clinical.consultation_create', response.data['permissions'])

    def test_non_admin_cannot_escalate_role_via_profile(self):
        self.client.force_authenticate(user=self.patient_user1)
        response = self.client.patch('/api/v1/auth/me/', {'role': 'ADMIN'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.patient_user1.refresh_from_db()
        self.assertEqual(self.patient_user1.role, Role.PATIENT)

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get('/api/v1/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------
    # 3. Administrative User & Role Management Endpoints
    # -------------------------------------------------------------
    def test_admin_can_list_users(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify paginated results contain user details
        users_list = response.data.get('results', response.data)
        self.assertTrue(len(users_list) >= 8)

    def test_non_admin_cannot_access_user_management(self):
        for staff_user in [self.doctor, self.nurse, self.pharmacist, self.patient_user1]:
            self.client.force_authenticate(user=staff_user)
            response = self.client.get('/api/v1/admin/users/')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_user_role_and_active_status(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f'/api/v1/admin/users/{self.receptionist.id}/',
            {'role': Role.BILLING_STAFF, 'is_active': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.receptionist.refresh_from_db()
        self.assertEqual(self.receptionist.role, Role.BILLING_STAFF)

    def test_admin_cannot_deactivate_own_account(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f'/api/v1/admin/users/{self.admin.id}/',
            {'is_active': False},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_only_superadmin_can_assign_superadmin_role(self):
        # Hospital Admin attempts to assign SUPER_ADMIN role
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f'/api/v1/admin/users/{self.doctor.id}/',
            {'role': Role.SUPER_ADMIN},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Super Admin assigns SUPER_ADMIN role
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.patch(
            f'/api/v1/admin/users/{self.doctor.id}/',
            {'role': Role.SUPER_ADMIN},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.role, Role.SUPER_ADMIN)

    def test_admin_can_view_permissions_catalog_and_roles(self):
        self.client.force_authenticate(user=self.admin)
        # Catalog
        cat_resp = self.client.get('/api/v1/admin/permissions/')
        self.assertEqual(cat_resp.status_code, status.HTTP_200_OK)

        # Roles
        roles_resp = self.client.get('/api/v1/admin/roles/')
        self.assertEqual(roles_resp.status_code, status.HTTP_200_OK)
        roles = [r['role'] for r in roles_resp.data]
        self.assertIn('DOCTOR', roles)
        self.assertIn('SUPER_ADMIN', roles)

    # -------------------------------------------------------------
    # 4. Domain Layer Authorization & IDOR Protection Tests
    # -------------------------------------------------------------
    def test_patient_cannot_view_another_patient_record(self):
        self.client.force_authenticate(user=self.patient_user1)
        # Attempt to retrieve Patient 2
        response = self.client.get(f'/api/v1/patients/{self.patient2.id}/')
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # But can retrieve own record
        own_resp = self.client.get(f'/api/v1/patients/{self.patient1.id}/')
        self.assertEqual(own_resp.status_code, status.HTTP_200_OK)

    def test_patient_cannot_create_invoice(self):
        self.client.force_authenticate(user=self.patient_user1)
        response = self.client.post('/api/v1/billing/invoices/', {
            'patient_id': self.patient1.id,
            'items': [{'description': 'Consultation', 'quantity': 1, 'unit_price': '50.00'}]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_approve_refund(self):
        invoice = Invoice.objects.create(
            patient=self.patient1,
            invoice_number='INV-TEST-001',
            due_date=timezone.now().date(),
            total_amount=Decimal('100.00'),
            subtotal=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            balance_due=Decimal('0.00'),
            status='PAID',
            created_by=self.admin
        )
        payment = Payment.objects.create(
            invoice=invoice,
            patient=self.patient1,
            receipt_number='REC-TEST-001',
            amount=Decimal('100.00'),
            payment_method='CASH',
            status='COMPLETED',
            transaction_reference='REF-001',
            received_by=self.admin
        )
        refund = Refund.objects.create(
            refund_number='REF-TEST-001',
            payment=payment,
            invoice=invoice,
            amount=Decimal('50.00'),
            reason='Overpayment adjustment',
            status='REQUESTED',
            requested_by=self.billing_staff
        )

        # Doctor attempts to approve refund
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f'/api/v1/billing/refunds/{refund.id}/approve-process/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin approves refund successfully
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/v1/billing/refunds/{refund.id}/approve-process/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nurse_cannot_sign_clinical_note(self):
        encounter = Encounter.objects.create(
            encounter_number='ENC-TEST-001',
            patient=self.patient1,
            doctor=self.doc_entity,
            attending_user=self.doctor,
            status='IN_PROGRESS'
        )
        note = ClinicalNote.objects.create(
            encounter=encounter,
            author=self.doctor,
            subjective='Patient feels feverish.',
            objective='Temp 101F',
            assessment='Viral fever',
            plan='Paracetamol 500mg TDS',
            is_signed=False
        )

        # Nurse attempts to sign note
        self.client.force_authenticate(user=self.nurse)
        response = self.client.post(f'/api/v1/clinical/notes/{note.id}/sign/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Doctor signs note successfully
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f'/api/v1/clinical/notes/{note.id}/sign/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

