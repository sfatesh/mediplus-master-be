from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.patients.models import Patient
from apps.departments.models import Department, Doctor
from apps.laboratory.models import (
    LabTestCatalogue,
    LabTestParameter,
    LabOrder,
    LabOrderItem,
    LabSpecimen,
    LabResult,
)
from apps.laboratory.services import (
    create_lab_order,
    collect_specimen,
    record_test_results,
    verify_and_release_result,
    get_critical_lab_alerts,
)


class LaboratoryModuleTestCase(TestCase):
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

    def setUp(self):
        # Users
        self.admin = User.objects.create_user(
            email='admin_lab@test.com',
            full_name='Lab Director Admin',
            role=Role.ADMIN
        )
        self.lab_tech = User.objects.create_user(
            email='lab_tech@test.com',
            full_name='Senior Lab Tech',
            role=Role.LAB_TECHNICIAN
        )
        self.doctor_user = User.objects.create_user(
            email='doc_lab@test.com',
            full_name='Dr. House',
            role=Role.DOCTOR
        )
        self.patient_user = User.objects.create_user(
            email='patient_lab@test.com',
            full_name='Jane Doe',
            role=Role.PATIENT
        )
        self.other_patient_user = User.objects.create_user(
            email='patient2_lab@test.com',
            full_name='Bob Smith',
            role=Role.PATIENT
        )

        self.patient = Patient.objects.create(
            user=self.patient_user,
            first_name='Jane',
            last_name='Doe',
            date_of_birth='1990-08-20',
            gender='F',
            phone='+15559876543',
            address='456 Elm St'
        )

        self.department = Department.objects.create(
            name='Pathology & Diagnostics',
            slug='pathology-diag',
            icon='icon-lab',
            description='Clinical Pathology Dept'
        )
        self.doctor = Doctor.objects.create(
            name='Dr. Gregory House',
            slug='dr-gregory-house',
            department_id=self.department.id,
            position='Head of Diagnostics',
            qualification='MD'
        )

        # Test Catalogue: BMP Panel
        self.test_bmp = LabTestCatalogue.objects.create(
            code='LAB-TEST-BMP',
            name='Basic Metabolic Panel (BMP)',
            category='BIOCHEMISTRY',
            specimen_type='SERUM',
            turnaround_time_hours=2,
            price=Decimal('50.00')
        )
        self.param_potassium = LabTestParameter.objects.create(
            lab_test=self.test_bmp,
            name='Serum Potassium',
            unit='mmol/L',
            reference_range_min=3.5,
            reference_range_max=5.1,
            critical_low=2.8,
            critical_high=6.2,
            sort_order=1
        )
        self.param_glucose = LabTestParameter.objects.create(
            lab_test=self.test_bmp,
            name='Fasting Glucose',
            unit='mg/dL',
            reference_range_min=70.0,
            reference_range_max=99.0,
            critical_low=50.0,
            critical_high=400.0,
            sort_order=2
        )

    def test_lab_order_creation_and_specimen_tracking(self):
        """Creating an order generates order items and specimen accession barcode."""
        order = create_lab_order(
            patient_id=self.patient.id,
            test_ids=[self.test_bmp.id],
            user=self.doctor_user,
            doctor_id=self.doctor.id,
            priority='URGENT',
            clinical_indication='Suspected electrolyte imbalance'
        )

        self.assertEqual(order.status, 'ORDERED')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.specimens.count(), 1)

        specimen = order.specimens.first()
        self.assertEqual(specimen.specimen_type, 'SERUM')

        # Collect specimen
        collected = collect_specimen(specimen.id, self.lab_tech, notes='Collected via venipuncture')
        self.assertEqual(collected.status, 'COLLECTED')
        self.assertEqual(collected.collected_by, self.lab_tech)

        item = order.items.first()
        item.refresh_from_db()
        self.assertEqual(item.status, 'SAMPLE_COLLECTED')

    def test_record_test_results_with_critical_alert(self):
        """Potassium 6.8 exceeds critical_high (6.2) and sets is_critical=True."""
        order = create_lab_order(
            patient_id=self.patient.id,
            test_ids=[self.test_bmp.id],
            user=self.doctor_user,
            doctor_id=self.doctor.id
        )
        item = order.items.first()

        result = record_test_results(
            order_item_id=item.id,
            parameter_values=[
                {'parameter_id': self.param_potassium.id, 'value': '6.8'}, # Critical High!
                {'parameter_id': self.param_glucose.id, 'value': '95.0'},    # Normal
            ],
            summary_notes='Hyperkalemia alert',
            user=self.lab_tech
        )

        self.assertTrue(result.is_critical)
        self.assertEqual(result.overall_interpretation, 'CRITICAL')
        self.assertEqual(result.status, 'PRELIMINARY')

        # Check parameter flags
        p_val_k = result.parameter_values.get(parameter=self.param_potassium)
        self.assertEqual(p_val_k.flag, 'CRITICAL_HIGH')

        p_val_glu = result.parameter_values.get(parameter=self.param_glucose)
        self.assertEqual(p_val_glu.flag, 'NORMAL')

    def test_prevent_silent_overwrite_of_verified_results(self):
        """Verified results cannot be silently overwritten without a correction reason."""
        order = create_lab_order(
            patient_id=self.patient.id,
            test_ids=[self.test_bmp.id],
            user=self.doctor_user
        )
        item = order.items.first()

        # Step 1: Record preliminary result
        result = record_test_results(
            order_item_id=item.id,
            parameter_values=[
                {'parameter_id': self.param_potassium.id, 'value': '4.2'},
                {'parameter_id': self.param_glucose.id, 'value': '88.0'},
            ],
            summary_notes='Normal baseline',
            user=self.lab_tech
        )

        # Step 2: Verify & Release
        verify_and_release_result(result.id, self.doctor_user, release_to_patient=True)
        result.refresh_from_db()
        self.assertEqual(result.status, 'RELEASED')

        # Step 3: Attempting to silently edit without correction reason must fail!
        with self.assertRaises(ValidationError) as ctx:
            record_test_results(
                order_item_id=item.id,
                parameter_values=[
                    {'parameter_id': self.param_potassium.id, 'value': '4.5'},
                    {'parameter_id': self.param_glucose.id, 'value': '90.0'},
                ],
                summary_notes='Silent change attempt',
                user=self.lab_tech,
                correction_reason='' # Missing!
            )
        self.assertIn('correction reason', str(ctx.exception).lower())

        # Step 4: With correction reason, successfully versions the record
        amended = record_test_results(
            order_item_id=item.id,
            parameter_values=[
                {'parameter_id': self.param_potassium.id, 'value': '4.5'},
                {'parameter_id': self.param_glucose.id, 'value': '90.0'},
            ],
            summary_notes='Amended findings',
            user=self.lab_tech,
            correction_reason='Recalibrated analyzer re-run'
        )
        self.assertEqual(amended.version, 2)
        self.assertTrue(amended.is_corrected)
        self.assertEqual(amended.correction_reason, 'Recalibrated analyzer re-run')

    def test_unreleased_results_inaccessible_to_patients(self):
        """Patients cannot view results until they are officially verified and released."""
        client = APIClient()
        order = create_lab_order(
            patient_id=self.patient.id,
            test_ids=[self.test_bmp.id],
            user=self.doctor_user
        )
        item = order.items.first()

        # Record preliminary result (not released yet)
        res = record_test_results(
            order_item_id=item.id,
            parameter_values=[
                {'parameter_id': self.param_potassium.id, 'value': '4.2'},
                {'parameter_id': self.param_glucose.id, 'value': '85.0'},
            ],
            summary_notes='Draft observation',
            user=self.lab_tech
        )

        # Patient login
        client.force_authenticate(user=self.patient_user)
        response = client.get('/api/v1/laboratory/results/')
        self.assertEqual(response.status_code, 200)
        # Should NOT see the unreleased preliminary result
        results_data = response.data.get('results', response.data)
        self.assertEqual(len(results_data), 0)

        # Now release the result
        verify_and_release_result(res.id, self.doctor_user, release_to_patient=True)

        # Patient query again
        response = client.get('/api/v1/laboratory/results/')
        self.assertEqual(response.status_code, 200)
        results_data = response.data.get('results', response.data)
        self.assertEqual(len(results_data), 1)
        self.assertEqual(results_data[0]['id'], res.id)

        # Another patient cannot view it
        client.force_authenticate(user=self.other_patient_user)
        response = client.get('/api/v1/laboratory/results/')
        results_data = response.data.get('results', response.data)
        self.assertEqual(len(results_data), 0)

