from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.admissions.models import Ward, Room, Bed, Admission
from apps.admissions.services import admit_patient
from apps.nursing.models import (
    NursePatientAssignment,
    VitalObservation,
    MedicationAdministrationRecord,
    ShiftHandover,
)
from apps.nursing.services import (
    evaluate_vital_alerts,
    record_vital_observation,
    administer_medication,
)


class NursingWorkflowsTestCase(TestCase):
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
        self.nurse = User.objects.create_user(
            email='florence@hospital.test',
            full_name='Florence Nightingale',
            role=Role.NURSE
        )
        self.incoming_nurse = User.objects.create_user(
            email='clara@hospital.test',
            full_name='Clara Barton',
            role=Role.NURSE
        )
        self.doctor_user = User.objects.create_user(
            email='doctor_nursing@test.com',
            full_name='Dr. Meredith Grey',
            role=Role.DOCTOR
        )

        self.dept = Department.objects.create(name='Surgery', slug='surgery')
        self.doctor = Doctor.objects.create(
            name='Dr. Meredith Grey',
            slug='dr-meredith-grey',
            position='General Surgeon',
            department=self.dept
        )

        self.patient = Patient.objects.create(
            medical_record_number='MED-2026-0003',
            first_name='Leonard',
            last_name='McCoy',
            date_of_birth='1975-01-20',
            gender='M',
            phone='+15559876'
        )

        self.ward = Ward.objects.create(
            name='High Dependency Unit',
            code='HDU-1',
            department=self.dept,
            ward_type='HDU',
            daily_base_rate=Decimal('200.00'),
            total_capacity=5
        )
        self.room = Room.objects.create(ward=self.ward, room_number='HDU-01')
        self.bed = Bed.objects.create(room=self.room, bed_number='HDU-BED-1', status='AVAILABLE')

        self.admission = admit_patient(
            patient_id=self.patient.id,
            admitting_doctor_id=self.doctor.id,
            bed_id=self.bed.id,
            admitting_diagnosis='Post-operative abdominal monitoring',
            primary_nurse_id=self.nurse.id,
            user=self.doctor_user
        )

    def test_evaluate_vital_alerts_normal(self):
        normal_vitals = {
            'temperature_c': Decimal('36.8'),
            'pulse_rate': 72,
            'blood_pressure_systolic': 118,
            'blood_pressure_diastolic': 78,
            'respiratory_rate': 16,
            'spo2_percent': 98,
            'pain_score': 2,
            'gcs_score': 15
        }
        is_critical, alerts = evaluate_vital_alerts(normal_vitals)
        self.assertFalse(is_critical)
        self.assertEqual(len(alerts), 0)

    def test_evaluate_vital_alerts_critical_decompensation(self):
        # SpO2 low, high BP, severe tachycardia
        critical_vitals = {
            'temperature_c': Decimal('39.2'),
            'pulse_rate': 135,
            'blood_pressure_systolic': 195,
            'blood_pressure_diastolic': 115,
            'respiratory_rate': 28,
            'spo2_percent': 88,
            'pain_score': 9,
            'gcs_score': 14
        }
        is_critical, alerts = evaluate_vital_alerts(critical_vitals)
        self.assertTrue(is_critical)
        self.assertTrue(any('Hypoxia Alert' in a for a in alerts))
        self.assertTrue(any('Hypertensive Crisis' in a for a in alerts))
        self.assertTrue(any('Severe Tachycardia' in a for a in alerts))
        self.assertTrue(any('High Grade Pyrexia' in a for a in alerts))

    def test_record_vital_observation_service(self):
        vital = record_vital_observation(
            admission_id=self.admission.id,
            vitals_data={
                'temperature_c': Decimal('39.0'),
                'pulse_rate': 125,
                'blood_pressure_systolic': 185,
                'blood_pressure_diastolic': 110,
                'respiratory_rate': 26,
                'spo2_percent': 89,
                'action_taken': 'Administered 4L O2 via nasal cannula, called on-call physician'
            },
            user=self.nurse
        )

        self.assertTrue(vital.is_critical)
        self.assertGreater(len(vital.critical_alert_reasons), 0)
        self.assertEqual(vital.recorded_by, self.nurse)

    def test_medication_administration_mar(self):
        mar = MedicationAdministrationRecord.objects.create(
            admission=self.admission,
            medication_name='Ceftriaxone IV',
            dose='1 g',
            route='IV Piggyback',
            scheduled_time=timezone.now(),
            status='DUE'
        )

        administered = administer_medication(
            mar_id=mar.id,
            status='GIVEN',
            remarks='Infused over 30 minutes without adverse reaction',
            user=self.nurse
        )

        self.assertEqual(administered.status, 'GIVEN')
        self.assertEqual(administered.administered_by, self.nurse)
        self.assertIsNotNone(administered.administered_time)

    def test_shift_handover_and_acknowledgement(self):
        handover = ShiftHandover.objects.create(
            ward=self.ward,
            shift='MORNING',
            outgoing_nurse=self.nurse,
            general_ward_summary='Ward census 1/5. No codes during morning shift.',
            patient_summaries=[{
                'admission_id': self.admission.id,
                'patient_name': self.patient.full_name,
                'bed_number': 'HDU-BED-1',
                'clinical_summary': 'Stable post-op. Vitals monitored q4h.',
                'pending_orders': 'Dressing change at 18:00',
                'precautions': 'Fall risk'
            }]
        )

        self.assertFalse(handover.is_acknowledged)

        # Incoming nurse acknowledges
        handover.is_acknowledged = True
        handover.incoming_nurse = self.incoming_nurse
        handover.acknowledged_at = timezone.now()
        handover.save()

        handover.refresh_from_db()
        self.assertTrue(handover.is_acknowledged)
        self.assertEqual(handover.incoming_nurse, self.incoming_nurse)
