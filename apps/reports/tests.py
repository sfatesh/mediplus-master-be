from decimal import Decimal
from django.test import TestCase
from django.db import connection
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment
from apps.admissions.models import Ward, Room, Bed
from apps.reports.services import (
    get_role_dashboard,
    get_appointments_and_patients_report,
    get_department_activity_report,
    get_admissions_and_occupancy_report,
    get_pharmacy_and_expiry_report,
    get_laboratory_workload_report,
    get_revenue_report,
    get_audit_report,
)


class ReportsAndDashboardTestCase(TestCase):
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        cls.dept = Department.objects.create(
            name="Cardiology",
            slug="cardiology",
            icon="flaticon-heart",
            description="Heart care"
        )
        cls.doc = Doctor.objects.create(
            name="Dr. Smith",
            slug="dr-smith",
            department=cls.dept,
            position="Chief Cardiologist",
            qualification="MD",
            email="dr.smith@mediplus.com"
        )
        cls.patient = Patient.objects.create(
            first_name="Jane",
            last_name="Doe",
            gender="FEMALE",
            date_of_birth="1990-05-15",
            phone="1234567890",
            email="jane.doe@example.com",
            address="123 Main St",
            city="Metropolis"
        )

        cls.admin_user = User.objects.create_user(
            email='admin@mediplus.com',
            full_name='Admin User',
            role=Role.ADMIN,
            password='Password123!'
        )
        cls.doctor_user = User.objects.create_user(
            email='dr.smith@mediplus.com',
            full_name='Dr. Smith',
            role=Role.DOCTOR,
            password='Password123!'
        )
        cls.nurse_user = User.objects.create_user(
            email='nurse@mediplus.com',
            full_name='Nurse Joy',
            role=Role.NURSE,
            password='Password123!'
        )
        cls.patient_user = User.objects.create_user(
            email='jane.doe@example.com',
            full_name='Jane Doe',
            role=Role.PATIENT,
            password='Password123!'
        )

    def setUp(self):
        self.client = APIClient()

    def test_role_specific_dashboards(self):
        # Admin dashboard
        admin_data = get_role_dashboard(self.admin_user)
        self.assertEqual(admin_data['role'], 'ADMIN')
        self.assertIn('total_patients', admin_data['kpis'])
        self.assertIn('occupancy_rate', admin_data['kpis'])

        # Doctor dashboard
        doc_data = get_role_dashboard(self.doctor_user)
        self.assertEqual(doc_data['role'], 'DOCTOR')
        self.assertIn('today_appointments_count', doc_data['kpis'])

        # Nurse dashboard
        nurse_data = get_role_dashboard(self.nurse_user)
        self.assertEqual(nurse_data['role'], 'NURSE')
        self.assertIn('assigned_patients_count', nurse_data['kpis'])

        # Patient dashboard
        patient_data = get_role_dashboard(self.patient_user)
        self.assertEqual(patient_data['role'], 'PATIENT')
        self.assertIn('upcoming_appointments_count', patient_data['kpis'])

    def test_dashboard_api_endpoint(self):
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get('/api/v1/dashboard/overview/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['role'], 'ADMIN')

        # Admin override role to DOCTOR
        res_override = self.client.get('/api/v1/dashboard/overview/?role=DOCTOR')
        self.assertEqual(res_override.status_code, 200)
        self.assertEqual(res_override.data['role'], 'DOCTOR')

    def test_operational_reports_endpoints(self):
        self.client.force_authenticate(user=self.admin_user)

        res_apts = self.client.get('/api/v1/reports/appointments/')
        self.assertEqual(res_apts.status_code, 200)
        self.assertIn('total_appointments', res_apts.data)

        res_dept = self.client.get('/api/v1/reports/departments/')
        self.assertEqual(res_dept.status_code, 200)
        self.assertIn('departments', res_dept.data)

        res_adm = self.client.get('/api/v1/reports/admissions/')
        self.assertEqual(res_adm.status_code, 200)
        self.assertIn('overall', res_adm.data)

        res_pharm = self.client.get('/api/v1/reports/pharmacy/')
        self.assertEqual(res_pharm.status_code, 200)
        self.assertIn('total_medicines', res_pharm.data)

        res_lab = self.client.get('/api/v1/reports/laboratory/')
        self.assertEqual(res_lab.status_code, 200)
        self.assertIn('total_orders', res_lab.data)

        res_rev = self.client.get('/api/v1/reports/revenue/')
        self.assertEqual(res_rev.status_code, 200)
        self.assertIn('total_invoiced', res_rev.data)

        res_audit = self.client.get('/api/v1/reports/audit/')
        self.assertEqual(res_audit.status_code, 200)
        self.assertIn('recent_logs', res_audit.data)

    def test_patient_permission_restricted_from_reports(self):
        self.client.force_authenticate(user=self.patient_user)

        res = self.client.get('/api/v1/reports/appointments/')
        self.assertEqual(res.status_code, 403)

        res_rev = self.client.get('/api/v1/reports/revenue/')
        self.assertEqual(res_rev.status_code, 403)

