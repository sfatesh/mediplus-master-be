from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.admissions.models import Ward, Room, Bed, Admission, BedAssignment, InpatientCharge
from apps.admissions.services import admit_patient, transfer_bed, discharge_patient


class InpatientAdmissionsTestCase(TestCase):
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
            email='admin_inpatient@test.com',
            full_name='Admin User',
            role=Role.ADMIN
        )
        self.doctor_user = User.objects.create_user(
            email='doc_inpatient@test.com',
            full_name='Dr. Gregory House',
            role=Role.DOCTOR
        )
        self.nurse_user = User.objects.create_user(
            email='nurse_inpatient@test.com',
            full_name='Nurse Jackie',
            role=Role.NURSE
        )

        # Department & Doctor
        self.dept = Department.objects.create(name='Internal Medicine', slug='internal-medicine')
        self.doctor = Doctor.objects.create(
            name='Dr. Gregory House',
            slug='dr-gregory-house',
            position='Chief Diagnostician',
            department=self.dept
        )

        # Patients
        self.patient_1 = Patient.objects.create(
            medical_record_number='MED-2026-0001',
            first_name='Arthur',
            last_name='Dent',
            date_of_birth='1980-05-12',
            gender='M',
            phone='+15551234'
        )
        self.patient_2 = Patient.objects.create(
            medical_record_number='MED-2026-0002',
            first_name='Ford',
            last_name='Prefect',
            date_of_birth='1982-08-20',
            gender='M',
            phone='+15555678'
        )

        # Wards, Rooms, Beds
        self.ward = Ward.objects.create(
            name='Medical Ward Alpha',
            code='MWA',
            department=self.dept,
            ward_type='GENERAL',
            daily_base_rate=Decimal('100.00'),
            total_capacity=4
        )
        self.room = Room.objects.create(
            ward=self.ward,
            room_number='101',
            room_type='GENERAL_WARD',
            daily_rate=Decimal('20.00')
        )
        self.bed_1 = Bed.objects.create(
            room=self.room,
            bed_number='101-A',
            bed_type='STANDARD',
            status='AVAILABLE'
        )
        self.bed_2 = Bed.objects.create(
            room=self.room,
            bed_number='101-B',
            bed_type='STANDARD',
            status='AVAILABLE'
        )

    def test_admit_patient_success(self):
        admission = admit_patient(
            patient_id=self.patient_1.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed_1.id,
            admitting_diagnosis='Severe acute pneumonia',
            admission_type='EMERGENCY',
            primary_nurse_id=self.nurse_user.id,
            user=self.admin
        )

        self.assertEqual(admission.status, 'ADMITTED')
        self.bed_1.refresh_from_db()
        self.assertEqual(self.bed_1.status, 'OCCUPIED')

        # Check BedAssignment
        active_assignment = BedAssignment.objects.filter(admission=admission, is_active=True).first()
        self.assertIsNotNone(active_assignment)
        self.assertEqual(active_assignment.bed, self.bed_1)

        # Check InpatientCharge automatically logged (100 base + 20 room = 120)
        charge = InpatientCharge.objects.filter(admission=admission, charge_type='BED_DAY').first()
        self.assertIsNotNone(charge)
        self.assertEqual(charge.total_amount, Decimal('120.00'))

    def test_prevent_double_booking_same_bed(self):
        # First admission occupies bed_1
        admit_patient(
            patient_id=self.patient_1.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed_1.id,
            admitting_diagnosis='Condition A',
            user=self.admin
        )

        # Second admission attempting to occupy bed_1 should raise ValidationError
        with self.assertRaises(ValidationError):
            admit_patient(
                patient_id=self.patient_2.id,
                admitting_doctor_id=self.doctor.id,
                bed_id=self.bed_1.id,
                admitting_diagnosis='Condition B',
                user=self.admin
            )

    def test_prevent_multiple_active_admissions_for_same_patient(self):
        admit_patient(
            patient_id=self.patient_1.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed_1.id,
            admitting_diagnosis='Initial admission',
            user=self.admin
        )

        with self.assertRaises(ValidationError):
            admit_patient(
                patient_id=self.patient_1.id,
                admitting_doctor_id=self.doctor.id,
                bed_id=self.bed_2.id,
                admitting_diagnosis='Second concurrent admission',
                user=self.admin
            )

    def test_bed_transfer_workflow(self):
        admission = admit_patient(
            patient_id=self.patient_1.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed_1.id,
            admitting_diagnosis='Pneumonia',
            user=self.admin
        )

        # Transfer from bed_1 to bed_2
        new_assignment = transfer_bed(
            admission_id=admission.id,
            target_bed_id=self.bed_2.id,
            transfer_reason='Patient requested window side bed',
            user=self.doctor_user
        )

        self.bed_1.refresh_from_db()
        self.bed_2.refresh_from_db()

        self.assertEqual(self.bed_1.status, 'AVAILABLE')
        self.assertEqual(self.bed_2.status, 'OCCUPIED')
        self.assertTrue(new_assignment.is_active)
        self.assertEqual(new_assignment.bed, self.bed_2)

        # Previous assignment should be inactive
        old_assignment = BedAssignment.objects.filter(admission=admission, bed=self.bed_1).first()
        self.assertFalse(old_assignment.is_active)
        self.assertIsNotNone(old_assignment.assigned_to)

    def test_discharge_patient_releases_bed_and_signs_summary(self):
        admission = admit_patient(
            patient_id=self.patient_1.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed_1.id,
            admitting_diagnosis='Pneumonia',
            user=self.admin
        )

        discharged = discharge_patient(
            admission_id=admission.id,
            discharge_summary='Patient responded well to IV antibiotics and is afebrile.',
            discharge_instructions='Take oral amoxicillin for 5 days. Rest and stay hydrated.',
            discharge_disposition='ROUTINE_HOME',
            follow_up_date=timezone.now().date(),
            user=self.doctor_user
        )

        self.assertEqual(discharged.status, 'DISCHARGED')
        self.assertTrue(discharged.is_signed_discharge)
        self.assertEqual(discharged.signed_discharge_by, self.doctor_user)

        self.bed_1.refresh_from_db()
        self.assertEqual(self.bed_1.status, 'AVAILABLE')

        # Cannot discharge already discharged patient
        with self.assertRaises(ValidationError):
            discharge_patient(
                admission_id=admission.id,
                discharge_summary='Duplicate discharge attempt',
                discharge_instructions='N/A',
                user=self.doctor_user
            )
