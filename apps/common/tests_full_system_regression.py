import uuid
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, Role
from apps.departments.models import Department, Doctor
from apps.patients.models import Patient
from apps.appointments.models import Appointment, QueueEntry, DoctorSchedule
from apps.clinical.models import Encounter, ClinicalNote, Prescription, PrescriptionItem
from apps.pharmacy.models import Supplier, MedicineCatalogue, StockBatch, StockMovementLedger
from apps.laboratory.models import LabTestCatalogue, LabTestParameter, LabOrder, LabOrderItem, LabResult
from apps.billing.models import ServiceCatalogue, Invoice, Payment
from apps.admissions.models import Ward, Room, Bed, Admission, BedAssignment
from apps.nursing.models import NursePatientAssignment, VitalObservation, NursingTask
from apps.notifications.models import Notification


class FullSystemIntegrationAndRegressionPass(TestCase):
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

        # 1. Base Department and Doctor
        cls.dept = Department.objects.create(
            name="General Medicine",
            slug="general-medicine",
            icon="flaticon-stethoscope",
            description="General inpatient and outpatient medicine",
            is_active=True
        )
        cls.doctor = Doctor.objects.create(
            name="Dr. Gregory House",
            slug="dr-gregory-house",
            department=cls.dept,
            position="Chief Diagnostician",
            qualification="MD, Board Certified",
            email="dr.house@mediplus.com",
            is_active=True
        )

        # 2. Users for all 7 hospital roles
        cls.admin_user = User.objects.create_superuser(
            email="admin@mediplus.com",
            password="AdminPassword123!",
            full_name="Hospital Administrator",
            role=Role.ADMIN
        )
        cls.doctor_user = User.objects.create_user(
            email="doctor@mediplus.com",
            password="DoctorPassword123!",
            full_name="Dr. Gregory House",
            role=Role.DOCTOR
        )
        cls.receptionist_user = User.objects.create_user(
            email="receptionist@mediplus.com",
            password="RecepPassword123!",
            full_name="Reception Officer",
            role=Role.RECEPTIONIST
        )
        cls.nurse_user = User.objects.create_user(
            email="nurse@mediplus.com",
            password="NursePassword123!",
            full_name="Head Nurse Florence",
            role=Role.NURSE
        )
        cls.pharmacist_user = User.objects.create_user(
            email="pharmacist@mediplus.com",
            password="PharmPassword123!",
            full_name="Senior Pharmacist Robert",
            role=Role.PHARMACIST
        )
        cls.labtech_user = User.objects.create_user(
            email="labtech@mediplus.com",
            password="LabPassword123!",
            full_name="Lab Technician Lisa",
            role=Role.LAB_TECHNICIAN
        )
        cls.patient_user = User.objects.create_user(
            email="patient@mediplus.com",
            password="PatientPassword123!",
            full_name="John Doe",
            role=Role.PATIENT
        )

        # 3. Patient record linked to patient_user
        cls.patient = Patient.objects.create(
            user=cls.patient_user,
            medical_record_number="MRN-TEST-1001",
            first_name="John",
            last_name="Doe",
            email="patient@mediplus.com",
            phone="+1 555-0100",
            date_of_birth=date(1990, 5, 15),
            gender="MALE",
            blood_group="O+"
        )

        # 4. Doctor Schedule for slot discovery
        for day in range(7):
            DoctorSchedule.objects.create(
                doctor=cls.doctor,
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=30,
                is_active=True
            )

        # 5. Pharmacy Setup
        cls.supplier = Supplier.objects.create(
            name="Apex Pharma",
            code="SUPP-APEX",
            email="contact@apexpharma.com"
        )
        cls.medicine = MedicineCatalogue.objects.create(
            name="Amoxicillin 500mg",
            generic_name="Amoxicillin Trihydrate",
            code="MED-AMOX-500",
            category="Antibiotic",
            dosage_form="CAPSULE",
            unit_price=Decimal("15.00"),
            reorder_level=20
        )
        cls.stock_batch = StockBatch.objects.create(
            medication=cls.medicine,
            batch_number="BATCH-VALID-101",
            expiry_date=date.today() + timedelta(days=365),
            quantity_on_hand=100,
            unit_cost=Decimal("8.00"),
            unit_sale_price=Decimal("15.00"),
            status="ACTIVE"
        )

        # 6. Laboratory Setup
        cls.lab_test = LabTestCatalogue.objects.create(
            name="Complete Blood Count",
            code="LAB-CBC-01",
            category="HEMATOLOGY",
            specimen_type="WHOLE_BLOOD",
            price=Decimal("35.00"),
            turnaround_time_hours=4,
            is_active=True
        )
        cls.param_hb = LabTestParameter.objects.create(
            lab_test=cls.lab_test,
            name="Hemoglobin",
            unit="g/dL",
            reference_range_min=13.5,
            reference_range_max=17.5,
            reference_range_text="13.5 - 17.5",
            critical_low=7.0,
            critical_high=20.0
        )
        cls.param_wbc = LabTestParameter.objects.create(
            lab_test=cls.lab_test,
            name="White Blood Cells",
            unit="10^3/uL",
            reference_range_min=4.5,
            reference_range_max=11.0,
            reference_range_text="4.5 - 11.0",
            critical_low=2.0,
            critical_high=30.0
        )

        # 7. Inpatient Ward, Room, Beds
        cls.ward = Ward.objects.create(
            name="General Medical Ward",
            code="GMW-01",
            ward_type="GENERAL",
            total_capacity=10,
            daily_base_rate=Decimal("100.00"),
            is_active=True
        )
        cls.room = Room.objects.create(
            ward=cls.ward,
            room_number="R-101",
            room_type="SEMI_PRIVATE",
            daily_rate=Decimal("120.00"),
            is_active=True
        )
        cls.bed_1 = Bed.objects.create(
            room=cls.room,
            bed_number="B-101-A",
            bed_type="STANDARD",
            status="AVAILABLE",
            is_active=True
        )
        cls.bed_2 = Bed.objects.create(
            room=cls.room,
            bed_number="B-101-B",
            bed_type="STANDARD",
            status="AVAILABLE",
            is_active=True
        )

        # 8. Billing Service Catalogue
        cls.consultation_service = ServiceCatalogue.objects.create(
            name="Specialist Consultation",
            code="SRV-CONS-01",
            category="CONSULTATION",
            standard_rate=Decimal("50.00"),
            tax_rate_percent=Decimal("0.00"),
            is_active=True
        )

    def setUp(self):
        self.client = APIClient()

    def test_01_all_seven_roles_authentication_and_profiles(self):
        """Task 4 & 5: Verify authentication, session tokens, and profiles for all seven roles."""
        role_credentials = [
            (self.admin_user, "admin@mediplus.com", "AdminPassword123!", Role.ADMIN),
            (self.doctor_user, "doctor@mediplus.com", "DoctorPassword123!", Role.DOCTOR),
            (self.receptionist_user, "receptionist@mediplus.com", "RecepPassword123!", Role.RECEPTIONIST),
            (self.nurse_user, "nurse@mediplus.com", "NursePassword123!", Role.NURSE),
            (self.pharmacist_user, "pharmacist@mediplus.com", "PharmPassword123!", Role.PHARMACIST),
            (self.labtech_user, "labtech@mediplus.com", "LabPassword123!", Role.LAB_TECHNICIAN),
            (self.patient_user, "patient@mediplus.com", "PatientPassword123!", Role.PATIENT),
        ]

        for user_obj, email, password, expected_role in role_credentials:
            # 1. Login
            resp = self.client.post('/api/v1/auth/login/', {
                'email': email,
                'password': password
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"Login failed for {email}")
            token = resp.json().get('token')
            self.assertIsNotNone(token, f"No token returned for {email}")

            # 2. Verify Session & Profile
            auth_client = APIClient()
            auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
            me_resp = auth_client.get('/api/v1/auth/me/')
            self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
            user_data = me_resp.json()
            self.assertEqual(user_data['role'], expected_role)
            self.assertEqual(user_data['email'], email)

            # 3. Test Logout
            logout_resp = auth_client.post('/api/v1/auth/logout/')
            self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

    def test_02_outpatient_end_to_end_lifecycle(self):
        """Task 6: Test patient registration through appointments, consultations, prescriptions, lab processing and billing."""
        # 1. Patient Registration
        recep_client = APIClient()
        recep_client.force_authenticate(user=self.receptionist_user)

        new_patient_resp = recep_client.post('/api/v1/patients/', {
            'first_name': 'Sarah',
            'last_name': 'Connor',
            'email': 'sarah.connor@example.com',
            'phone': '+1 555-0299',
            'date_of_birth': '1985-06-20',
            'gender': 'FEMALE',
            'blood_group': 'A+',
            'address': '404 Cyberdyne Way',
            'emergency_contact_name': 'John Connor',
            'emergency_contact_phone': '+1 555-0300'
        })
        self.assertEqual(new_patient_resp.status_code, status.HTTP_201_CREATED)
        patient_id = new_patient_resp.json()['id']
        mrn = new_patient_resp.json()['medical_record_number']
        self.assertTrue(mrn.startswith('MED-'))

        # 2. Appointment Booking
        target_date = (date.today() + timedelta(days=2)).isoformat()
        apt_resp = recep_client.post('/api/v1/appointments/', {
            'first_name': 'Sarah',
            'last_name': 'Connor',
            'email': 'sarah.connor@example.com',
            'phone': '+1 555-0299',
            'department_id': self.dept.id,
            'doctor_id': self.doctor.id,
            'appointment_date': target_date,
            'appointment_time': '10:00 AM',
            'message': 'Routine medical evaluation'
        })
        self.assertEqual(apt_resp.status_code, status.HTTP_201_CREATED)
        apt_id = apt_resp.json()['id']

        # Confirm appointment
        Appointment.objects.filter(pk=apt_id).update(status='CONFIRMED')

        # 3. Patient Check-In & Queue Token Generation
        checkin_resp = recep_client.post(f'/api/v1/appointments/{apt_id}/check-in/')
        self.assertEqual(checkin_resp.status_code, status.HTTP_200_OK)
        queue_data = checkin_resp.json()['queue_entry']
        queue_id = queue_data['id']
        self.assertEqual(queue_data['status'], 'WAITING')

        # 4. Call Token in OPD Queue
        call_resp = recep_client.post(f'/api/v1/appointments/queue/{queue_id}/call/')
        self.assertEqual(call_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(call_resp.json()['status'], 'CALLED')

        # 5. Doctor Clinical Encounter
        doc_client = APIClient()
        doc_client.force_authenticate(user=self.doctor_user)

        encounter_resp = doc_client.post('/api/v1/clinical/encounters/', {
            'patient': patient_id,
            'doctor': self.doctor.id,
            'encounter_type': 'OUTPATIENT',
            'chief_complaint': 'Recurrent persistent migraine and fatigue',
            'vitals': {
                'blood_pressure': '120/80',
                'pulse_rate': 72,
                'temperature_c': 36.8,
                'spo2_percent': 99
            }
        }, format='json')
        self.assertEqual(encounter_resp.status_code, status.HTTP_201_CREATED)
        encounter_id = encounter_resp.json()['id']

        # 6. Doctor Consultation Notes (SOAP) & Signing
        note_resp = doc_client.post('/api/v1/clinical/notes/', {
            'encounter': encounter_id,
            'subjective': 'Patient reports 4 days of throbbing frontal headache.',
            'objective': 'Alert, oriented, cranial nerves intact. Neurological exam normal.',
            'assessment': 'Migraine without aura (G43.0).',
            'plan': 'Analgesics, hydration, CBC laboratory workup.',
            'diagnoses': [{'code': 'G43.0', 'description': 'Migraine without aura'}],
            'follow_up_instructions': 'Review after 1 week if no improvement.'
        }, format='json')
        self.assertEqual(note_resp.status_code, status.HTTP_201_CREATED)
        note_id = note_resp.json()['id']

        # Sign note
        sign_resp = doc_client.post(f'/api/v1/clinical/notes/{note_id}/sign/')
        self.assertEqual(sign_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(sign_resp.json()['is_signed'])

        # Signed note immutability check: Direct modification rejected
        patch_resp = doc_client.patch(f'/api/v1/clinical/notes/{note_id}/', {
            'subjective': 'Altered subjective notes illegally.'
        })
        self.assertEqual(patch_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 7. Prescription Creation & Authorization
        rx_resp = doc_client.post('/api/v1/clinical/prescriptions/', {
            'encounter': encounter_id,
            'patient': patient_id,
            'clinical_instructions': 'Take after food with water.',
            'items': [
                {
                    'medication_name': 'Amoxicillin 500mg',
                    'dosage': '500 mg',
                    'frequency': 'Three times daily',
                    'duration': '5 days',
                    'quantity': 15
                }
            ]
        }, format='json')
        self.assertEqual(rx_resp.status_code, status.HTTP_201_CREATED)
        rx_id = rx_resp.json()['id']

        auth_rx_resp = doc_client.post(f'/api/v1/clinical/prescriptions/{rx_id}/authorize/')
        self.assertEqual(auth_rx_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_rx_resp.json()['status'], 'AUTHORIZED')

        # 8. Laboratory Order, Specimen Collection & Results Release
        lab_order_resp = doc_client.post('/api/v1/laboratory/orders/', {
            'patient_id': patient_id,
            'test_ids': [self.lab_test.id],
            'doctor_id': self.doctor.id,
            'priority': 'ROUTINE',
            'clinical_indication': 'Evaluate fatigue',
            'encounter_id': encounter_id
        }, format='json')
        self.assertEqual(lab_order_resp.status_code, status.HTTP_201_CREATED)
        order_id = lab_order_resp.json()['id']
        order_item_id = lab_order_resp.json()['items'][0]['id']
        specimen_id = lab_order_resp.json()['specimens'][0]['id']

        # Lab tech collects specimen
        tech_client = APIClient()
        tech_client.force_authenticate(user=self.labtech_user)

        coll_resp = tech_client.post(f'/api/v1/laboratory/specimens/{specimen_id}/collect/', {
            'notes': 'Whole blood sample drawn in EDTA tube.'
        })
        self.assertEqual(coll_resp.status_code, status.HTTP_200_OK)

        # Lab tech enters result values
        record_resp = tech_client.post('/api/v1/laboratory/results/record/', {
            'order_item_id': order_item_id,
            'parameter_values': [
                {'parameter_id': self.param_hb.id, 'value_numeric': 14.5},
                {'parameter_id': self.param_wbc.id, 'value_numeric': 6.8}
            ],
            'summary_notes': 'Parameters within normal physiological range.'
        }, format='json')
        self.assertEqual(record_resp.status_code, status.HTTP_201_CREATED)
        result_id = record_resp.json()['id']

        # Doctor / Pathologist verifies and releases results
        release_resp = doc_client.post(f'/api/v1/laboratory/results/{result_id}/verify-release/', {
            'clinical_remarks': 'Verified by Dr. House. Normal CBC.'
        }, format='json')
        self.assertEqual(release_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(release_resp.json()['status'], 'RELEASED')

        # 9. Pharmacy Dispensing
        pharm_client = APIClient()
        pharm_client.force_authenticate(user=self.pharmacist_user)

        rx_item = PrescriptionItem.objects.filter(prescription_id=rx_id).first()
        dispense_resp = pharm_client.post('/api/v1/pharmacy/dispensations/', {
            'prescription_id': rx_id,
            'items': [
                {
                    'prescription_item_id': rx_item.id if rx_item else None,
                    'medication_id': self.medicine.id,
                    'batch_id': self.stock_batch.id,
                    'quantity': 15
                }
            ],
            'notes': 'Dispensed 15 capsules of Amoxicillin 500mg.'
        }, format='json')
        self.assertEqual(dispense_resp.status_code, status.HTTP_201_CREATED, dispense_resp.json())

        # Verify stock decrement and ledger
        self.stock_batch.refresh_from_db()
        self.assertEqual(self.stock_batch.quantity_on_hand, 85)

        # 10. Billing & Payments
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin_user)

        invoice_resp = admin_client.post('/api/v1/billing/invoices/', {
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'due_date': (date.today() + timedelta(days=14)).isoformat(),
            'items': [
                {
                    'description': 'Outpatient Doctor Consultation',
                    'item_type': 'CONSULTATION',
                    'unit_price': '50.00',
                    'quantity': 1
                },
                {
                    'description': 'Complete Blood Count (CBC)',
                    'item_type': 'LABORATORY',
                    'unit_price': '35.00',
                    'quantity': 1
                },
                {
                    'description': 'Amoxicillin 500mg (15 capsules)',
                    'item_type': 'PHARMACY',
                    'unit_price': '15.00',
                    'quantity': 1
                }
            ]
        }, format='json')
        self.assertEqual(invoice_resp.status_code, status.HTTP_201_CREATED, invoice_resp.json())
        invoice_id = invoice_resp.json()['id']
        self.assertEqual(Decimal(invoice_resp.json()['total_amount']), Decimal('100.00'))
        self.assertEqual(Decimal(invoice_resp.json()['balance_due']), Decimal('100.00'))

        # Partial Payment ($40)
        pay1_resp = admin_client.post(f'/api/v1/billing/invoices/{invoice_id}/record-payment/', {
            'amount': '40.00',
            'payment_method': 'CREDIT_CARD',
            'transaction_reference': f"TX-{uuid.uuid4().hex[:8].upper()}",
            'notes': 'Partial payment via card'
        }, format='json')
        self.assertEqual(pay1_resp.status_code, status.HTTP_201_CREATED, pay1_resp.json())

        inv = Invoice.objects.get(pk=invoice_id)
        self.assertEqual(inv.status, 'PARTIALLY_PAID')
        self.assertEqual(inv.balance_due, Decimal('60.00'))

        # Final Settlement ($60)
        pay2_resp = admin_client.post(f'/api/v1/billing/invoices/{invoice_id}/record-payment/', {
            'amount': '60.00',
            'payment_method': 'CASH',
            'transaction_reference': f"TX-{uuid.uuid4().hex[:8].upper()}",
            'notes': 'Final balance settlement'
        }, format='json')
        self.assertEqual(pay2_resp.status_code, status.HTTP_201_CREATED, pay2_resp.json())

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'PAID')
        self.assertEqual(inv.balance_due, Decimal('0.00'))

    def test_03_inpatient_admissions_nursing_and_discharge(self):
        """Task 7: Test inpatient admissions, bed assignments, nursing records and discharge."""
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin_user)

        # 1. Ward Occupancy Check
        occ_resp = admin_client.get('/api/v1/wards/occupancy_summary/')
        self.assertEqual(occ_resp.status_code, status.HTTP_200_OK)
        self.assertIn('overall_total_beds', occ_resp.json())

        # 2. Admit Patient to Bed 1
        admit_resp = admin_client.post('/api/v1/admissions/', {
            'patient_id': self.patient.id,
            'admitting_doctor_id': self.doctor.id,
            'bed_id': self.bed_1.id,
            'admission_type': 'EMERGENCY',
            'admitting_diagnosis': 'Acute Community Acquired Pneumonia',
            'chief_complaint': 'High fever, productive cough and shortness of breath'
        })
        self.assertEqual(admit_resp.status_code, status.HTTP_201_CREATED)
        admission_id = admit_resp.json()['id']

        self.bed_1.refresh_from_db()
        self.assertEqual(self.bed_1.status, 'OCCUPIED')

        # 3. Conflict Prevention: Cannot assign Bed 1 to a second admission
        conflict_patient = Patient.objects.create(
            medical_record_number="MRN-TEST-9999",
            first_name="Jane",
            last_name="Doe",
            date_of_birth=date(1995, 1, 1),
            gender="FEMALE",
            phone="+1 555-9999"
        )
        conflict_resp = admin_client.post('/api/v1/admissions/', {
            'patient_id': conflict_patient.id,
            'admitting_doctor_id': self.doctor.id,
            'bed_id': self.bed_1.id,
            'admission_type': 'ELECTIVE',
            'admitting_diagnosis': 'Elective Surgery'
        })
        self.assertEqual(conflict_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Nurse Assignment
        nurse_client = APIClient()
        nurse_client.force_authenticate(user=self.nurse_user)

        assign_resp = nurse_client.post('/api/v1/nursing/assignments/', {
            'nurse': self.nurse_user.id,
            'admission': admission_id,
            'shift': 'MORNING',
            'assignment_date': date.today().isoformat()
        })
        self.assertEqual(assign_resp.status_code, status.HTTP_201_CREATED)

        # 5. Nursing Vitals with Critical Trigger
        vitals_resp = nurse_client.post('/api/v1/nursing/vitals/', {
            'admission': admission_id,
            'temperature_c': 39.8,  # Critical fever > 39.0
            'pulse_rate': 125,          # Critical tachycardia > 120
            'blood_pressure_systolic': 85,  # Hypotension < 90
            'blood_pressure_diastolic': 55,
            'respiratory_rate': 26,     # Tachypnea
            'spo2_percent': 88,         # Critical hypoxia < 90
            'action_taken': 'Administered supplemental high flow O2 via non-rebreather mask and notified physician.'
        }, format='json')
        self.assertEqual(vitals_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(vitals_resp.json()['is_critical'])
        self.assertGreater(len(vitals_resp.json()['critical_alert_reasons']), 0)

        # 6. Nursing Care Tasks
        task_resp = nurse_client.post('/api/v1/nursing/tasks/', {
            'admission': admission_id,
            'title': 'Administer IV Ceftriaxone 1g STAT',
            'priority': 'STAT',
            'due_time': timezone.now().isoformat()
        })
        self.assertEqual(task_resp.status_code, status.HTTP_201_CREATED)
        task_id = task_resp.json()['id']

        complete_task_resp = nurse_client.post(f'/api/v1/nursing/tasks/{task_id}/complete/', {
            'notes': 'IV Ceftriaxone 1g given slowly over 30 mins with saline flush.'
        })
        self.assertEqual(complete_task_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_task_resp.json()['status'], 'COMPLETED')

        # 7. Bed Transfer to Bed 2
        transfer_resp = admin_client.post(f'/api/v1/admissions/{admission_id}/transfer/', {
            'target_bed_id': self.bed_2.id,
            'transfer_reason': 'Transferred to step-down bed near nursing monitoring station.'
        }, format='json')
        self.assertEqual(transfer_resp.status_code, status.HTTP_200_OK)

        self.bed_1.refresh_from_db()
        self.bed_2.refresh_from_db()
        self.assertEqual(self.bed_1.status, 'AVAILABLE')
        self.assertEqual(self.bed_2.status, 'OCCUPIED')

        # 8. Discharge Patient
        discharge_resp = admin_client.post(f'/api/v1/admissions/{admission_id}/discharge/', {
            'discharge_summary': 'Pneumonia clinically resolved. Vitals stable on room air. Afebrile for 48 hours.',
            'discharge_instructions': 'Continue oral antibiotics for 5 days. Rest and stay hydrated.',
            'discharge_disposition': 'ROUTINE_HOME'
        }, format='json')
        self.assertEqual(discharge_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(discharge_resp.json()['status'], 'DISCHARGED')

        self.bed_2.refresh_from_db()
        self.assertEqual(self.bed_2.status, 'AVAILABLE')

    def test_04_pharmacy_and_laboratory_integrity(self):
        """Task 8: Test pharmacy stock consistency, expired batch handling, and laboratory result release permissions."""
        # 1. Expired Medicine Dispensing Rejection
        expired_batch = StockBatch.objects.create(
            medication=self.medicine,
            batch_number="BATCH-EXPIRED-99",
            expiry_date=date.today() - timedelta(days=10),
            quantity_on_hand=50,
            unit_cost=Decimal("8.00"),
            unit_sale_price=Decimal("15.00"),
            status="EXPIRED"
        )

        pharm_client = APIClient()
        pharm_client.force_authenticate(user=self.pharmacist_user)

        # Create dummy prescription to attempt dispensing expired batch
        rx = Prescription.objects.create(
            encounter=Encounter.objects.create(patient=self.patient, doctor=self.doctor),
            patient=self.patient,
            status='AUTHORIZED'
        )
        rx_item = PrescriptionItem.objects.create(
            prescription=rx,
            medication_name="Amoxicillin 500mg",
            dosage="500 mg",
            frequency="TDS",
            duration="5 days",
            quantity=10
        )

        dispense_attempt = pharm_client.post('/api/v1/pharmacy/dispensations/', {
            'prescription_id': rx.id,
            'items': [
                {
                    'prescription_item_id': rx_item.id,
                    'medication_id': self.medicine.id,
                    'batch_id': expired_batch.id,
                    'quantity': 10
                }
            ]
        })
        self.assertEqual(dispense_attempt.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Confidentiality: Unreleased Lab Result Hidden from Patient
        order = LabOrder.objects.create(
            patient=self.patient,
            ordering_doctor=self.doctor,
            status='ORDERED'
        )
        order_item = LabOrderItem.objects.create(
            order=order,
            lab_test=self.lab_test,
            status='ORDERED'
        )
        unreleased_result = LabResult.objects.create(
            order_item=order_item,
            status='RECORDED',
            is_released=False,
            recorded_by=self.labtech_user
        )

        # Patient query should NOT include unreleased result
        patient_client = APIClient()
        patient_client.force_authenticate(user=self.patient_user)
        pat_res = patient_client.get('/api/v1/laboratory/results/')
        self.assertEqual(pat_res.status_code, status.HTTP_200_OK)
        result_ids = [r['id'] for r in pat_res.json().get('results', pat_res.json())]
        self.assertNotIn(unreleased_result.id, result_ids)

        # Doctor query CAN see it
        doc_client = APIClient()
        doc_client.force_authenticate(user=self.doctor_user)
        doc_res = doc_client.get('/api/v1/laboratory/results/')
        self.assertEqual(doc_res.status_code, status.HTTP_200_OK)
        doc_ids = [r['id'] for r in doc_res.json().get('results', doc_res.json())]
        self.assertIn(unreleased_result.id, doc_ids)

    def test_05_security_access_control_and_role_boundaries(self):
        """Task 9: Test unauthorized record access and role escalation."""
        patient_client = APIClient()
        patient_client.force_authenticate(user=self.patient_user)

        # 1. Patient cannot write clinical notes
        enc = Encounter.objects.create(patient=self.patient, doctor=self.doctor)
        pat_note_attempt = patient_client.post('/api/v1/clinical/notes/', {
            'encounter': enc.id,
            'subjective': 'Fake note'
        })
        self.assertEqual(pat_note_attempt.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Receptionist cannot authorize prescriptions
        recep_client = APIClient()
        recep_client.force_authenticate(user=self.receptionist_user)

        rx = Prescription.objects.create(encounter=enc, patient=self.patient, status='DRAFT')
        recep_auth_attempt = recep_client.post(f'/api/v1/clinical/prescriptions/{rx.id}/authorize/')
        self.assertEqual(recep_auth_attempt.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Nurse cannot access financial summary reports
        nurse_client = APIClient()
        nurse_client.force_authenticate(user=self.nurse_user)
        fin_report_attempt = nurse_client.get('/api/v1/billing/invoices/financial-report/')
        self.assertEqual(fin_report_attempt.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Pharmacist cannot release laboratory results
        order = LabOrder.objects.create(patient=self.patient, ordering_doctor=self.doctor)
        order_item = LabOrderItem.objects.create(order=order, lab_test=self.lab_test)
        result = LabResult.objects.create(order_item=order_item, status='RECORDED', recorded_by=self.labtech_user)

        pharm_client = APIClient()
        pharm_client.force_authenticate(user=self.pharmacist_user)
        pharm_release_attempt = pharm_client.post(f'/api/v1/laboratory/results/{result.id}/verify-release/')
        self.assertEqual(pharm_release_attempt.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_dashboards_reports_and_notifications(self):
        """Tasks 1, 2, 5 & 12: Verify dashboard payloads for all 7 roles, report permissions and notification workflows."""
        # 1. Dashboard Overview for all 7 roles
        role_users = [
            self.admin_user,
            self.doctor_user,
            self.receptionist_user,
            self.nurse_user,
            self.pharmacist_user,
            self.labtech_user,
            self.patient_user,
        ]

        for user_obj in role_users:
            client = APIClient()
            client.force_authenticate(user=user_obj)
            dash_resp = client.get('/api/v1/dashboard/overview/')
            self.assertEqual(dash_resp.status_code, status.HTTP_200_OK, f"Dashboard failed for {user_obj.email}")
            self.assertEqual(dash_resp.json()['role'], user_obj.role)

        # 2. Operational Reports: Admin allowed, Patient forbidden
        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin_user)
        patient_client = APIClient()
        patient_client.force_authenticate(user=self.patient_user)

        report_endpoints = [
            '/api/v1/reports/appointments/',
            '/api/v1/reports/departments/',
            '/api/v1/reports/admissions/',
            '/api/v1/reports/pharmacy/',
            '/api/v1/reports/laboratory/',
            '/api/v1/reports/revenue/',
            '/api/v1/reports/audit/',
        ]

        for endpoint in report_endpoints:
            # Admin can access
            adm_res = admin_client.get(endpoint)
            self.assertEqual(adm_res.status_code, status.HTTP_200_OK, f"Admin could not access {endpoint}")

            # Patient is forbidden
            pat_res = patient_client.get(endpoint)
            self.assertEqual(pat_res.status_code, status.HTTP_403_FORBIDDEN, f"Patient was not forbidden from {endpoint}")

        # 3. Notification Center Workflows
        Notification.objects.create(
            recipient=self.patient_user,
            notification_type='APPOINTMENT_REMINDER',
            severity='INFO',
            title='Upcoming Appointment Reminder',
            message='Your consultation with Dr. Gregory House is confirmed.'
        )

        notif_resp = patient_client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(notif_resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(notif_resp.json()['unread_count'], 1)

        list_resp = patient_client.get('/api/v1/notifications/')
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        notifications = list_resp.json().get('results', list_resp.json())
        notif_id = notifications[0]['id']

        # Mark single as read
        mark_read_resp = patient_client.post(f'/api/v1/notifications/{notif_id}/mark-as-read/')
        self.assertEqual(mark_read_resp.status_code, status.HTTP_200_OK)

        # Mark all read
        mark_all_resp = patient_client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(mark_all_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(mark_all_resp.json()['unread_count'], 0)
