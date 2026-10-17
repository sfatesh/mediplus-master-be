from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.core.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import User, Role
from apps.patients.models import Patient
from apps.departments.models import Department, Doctor
from apps.clinical.models import Encounter, Prescription, PrescriptionItem
from apps.pharmacy.models import (
    Supplier,
    MedicineCatalogue,
    StockBatch,
    StockMovementLedger,
    DispenseRecord,
    DispenseItem,
    GoodsReceipt,
)
from apps.pharmacy.services import (
    dispense_prescription_items,
    receive_goods_shipment,
    record_wastage_or_return,
    get_inventory_alerts,
)


class PharmacyInventoryTestCase(TestCase):
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

    def setUp(self):
        self.today = date.today()

        # Users
        self.admin = User.objects.create_user(
            email='admin_pharma@test.com',
            full_name='Pharma Admin',
            role=Role.ADMIN
        )
        self.pharmacist = User.objects.create_user(
            email='pharmacist@test.com',
            full_name='Chief Pharmacist',
            role=Role.PHARMACIST
        )
        self.nurse = User.objects.create_user(
            email='nurse_pharma@test.com',
            full_name='Nurse Jackie',
            role=Role.NURSE
        )
        self.patient_user = User.objects.create_user(
            email='patient_pharma@test.com',
            full_name='John Doe',
            role=Role.PATIENT
        )

        self.patient = Patient.objects.create(
            user=self.patient_user,
            first_name='John',
            last_name='Doe',
            date_of_birth='1985-05-15',
            gender='M',
            phone='+15551234567',
            address='123 Main St'
        )

        self.department = Department.objects.create(
            name='Internal Medicine',
            slug='internal-med',
            icon='icon-med',
            description='Dept of Internal Med'
        )
        self.doctor = Doctor.objects.create(
            name='Dr. Allison Cameron',
            slug='dr-cameron',
            department_id=self.department.id,
            position='Consultant',
            qualification='MD'
        )

        self.encounter = Encounter.objects.create(
            encounter_number='ENC-PH-001',
            patient=self.patient,
            doctor=self.doctor,
            encounter_type='OUTPATIENT',
            status='IN_PROGRESS'
        )

        self.prescription = Prescription.objects.create(
            encounter=self.encounter,
            patient=self.patient,
            prescriber=self.admin,
            status='AUTHORIZED'
        )

        self.supplier = Supplier.objects.create(
            name='Apex Pharma',
            code='SUP-TEST-1',
            contact_person='Sales Rep'
        )

        self.med_amox = MedicineCatalogue.objects.create(
            code='MED-TEST-AMOX',
            name='Amoxicillin 500mg',
            generic_name='Amoxicillin',
            category='Antibiotics',
            dosage_form='CAPSULE',
            strength='500 mg',
            reorder_level=20,
            unit_price=Decimal('10.00')
        )

        # Batch 1: Active, valid
        self.active_batch = StockBatch.objects.create(
            medication=self.med_amox,
            batch_number='AMOX-VAL-01',
            expiry_date=self.today + timedelta(days=180),
            quantity_on_hand=50,
            unit_cost=Decimal('5.00'),
            unit_sale_price=Decimal('10.00'),
            status='ACTIVE'
        )

        # Batch 2: Expired
        self.expired_batch = StockBatch.objects.create(
            medication=self.med_amox,
            batch_number='AMOX-EXP-99',
            expiry_date=self.today - timedelta(days=10),
            quantity_on_hand=30,
            unit_cost=Decimal('5.00'),
            unit_sale_price=Decimal('10.00'),
            status='EXPIRED'
        )

        self.presc_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medication_name=self.med_amox.name,
            dosage='500 mg',
            frequency='TDS',
            duration='5 days',
            quantity=15,
            instructions='After meals'
        )

    def test_unauthorized_dispensing_rejected(self):
        """Only pharmacists and admins can dispense prescription items."""
        with self.assertRaises(PermissionDenied):
            dispense_prescription_items(
                prescription_id=self.prescription.id,
                items_to_dispense=[{
                    'medication_id': self.med_amox.id,
                    'batch_id': self.active_batch.id,
                    'quantity': 10,
                    'prescription_item_id': self.presc_item.id
                }],
                user=self.nurse
            )

    def test_expired_stock_dispensing_prevented(self):
        """Prevent expired stock from being dispensed even if requested."""
        with self.assertRaises(ValidationError) as ctx:
            dispense_prescription_items(
                prescription_id=self.prescription.id,
                items_to_dispense=[{
                    'medication_id': self.med_amox.id,
                    'batch_id': self.expired_batch.id,
                    'quantity': 5,
                    'prescription_item_id': self.presc_item.id
                }],
                user=self.pharmacist
            )
        self.assertIn('expired', str(ctx.exception).lower())

    def test_stock_conflict_insufficient_stock(self):
        """Prevents dispensing more quantity than batch has on hand."""
        self.presc_item.quantity = 150
        self.presc_item.save()

        with self.assertRaises(ValidationError) as ctx:
            dispense_prescription_items(
                prescription_id=self.prescription.id,
                items_to_dispense=[{
                    'medication_id': self.med_amox.id,
                    'batch_id': self.active_batch.id,
                    'quantity': 100,  # Batch only has 50
                    'prescription_item_id': self.presc_item.id
                }],
                user=self.pharmacist
            )
        self.assertIn('insufficient stock', str(ctx.exception).lower())

    def test_duplicate_and_over_dispensing_prevention(self):
        """Prevents dispensing more than the prescribed quantity for an item."""
        # Prescribed quantity is 15. First dispense 10 units.
        dispense_prescription_items(
            prescription_id=self.prescription.id,
            items_to_dispense=[{
                'medication_id': self.med_amox.id,
                'batch_id': self.active_batch.id,
                'quantity': 10,
                'prescription_item_id': self.presc_item.id
            }],
            user=self.pharmacist
        )

        # Trying to dispense 10 more (total 20 > 15) must fail!
        with self.assertRaises(ValidationError) as ctx:
            dispense_prescription_items(
                prescription_id=self.prescription.id,
                items_to_dispense=[{
                    'medication_id': self.med_amox.id,
                    'batch_id': self.active_batch.id,
                    'quantity': 10,
                    'prescription_item_id': self.presc_item.id
                }],
                user=self.pharmacist
            )
        self.assertIn('cannot dispense', str(ctx.exception).lower())

    def test_successful_dispense_and_stock_ledger(self):
        """Successful dispense decrements batch stock and writes immutable ledger entry."""
        initial_stock = self.active_batch.quantity_on_hand
        dispense_qty = 15

        rec = dispense_prescription_items(
            prescription_id=self.prescription.id,
            items_to_dispense=[{
                'medication_id': self.med_amox.id,
                'batch_id': self.active_batch.id,
                'quantity': dispense_qty,
                'prescription_item_id': self.presc_item.id
            }],
            user=self.pharmacist
        )

        self.assertEqual(rec.status, 'COMPLETED')
        self.active_batch.refresh_from_db()
        self.assertEqual(self.active_batch.quantity_on_hand, initial_stock - dispense_qty)

        # Check ledger
        ledger = StockMovementLedger.objects.filter(reference_id=rec.dispense_number).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.movement_type, 'DISPENSE')
        self.assertEqual(ledger.quantity, -dispense_qty)
        self.assertEqual(ledger.balance_after, self.active_batch.quantity_on_hand)

    def test_goods_receipt_increases_stock(self):
        """Goods receipt note increases stock batch and records ledger entry."""
        grn = receive_goods_shipment(
            receipt_data={
                'supplier_id': self.supplier.id,
                'received_date': self.today,
                'invoice_number': 'INV-9988'
            },
            items_data=[{
                'medication_id': self.med_amox.id,
                'batch_number': 'AMOX-NEW-02',
                'expiry_date': self.today + timedelta(days=400),
                'quantity_received': 100,
                'unit_purchase_cost': '4.50',
                'unit_sale_price': '10.00'
            }],
            user=self.pharmacist
        )

        new_batch = StockBatch.objects.get(medication=self.med_amox, batch_number='AMOX-NEW-02')
        self.assertEqual(new_batch.quantity_on_hand, 100)

        ledger = StockMovementLedger.objects.filter(reference_id=grn.grn_number).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.movement_type, 'PURCHASE_RECEIPT')
        self.assertEqual(ledger.quantity, 100)

    def test_wastage_record_reduces_stock(self):
        """Wastage disposal reduces stock and updates ledger."""
        initial_stock = self.active_batch.quantity_on_hand
        discard_qty = 5

        record = record_wastage_or_return(
            record_type='WASTAGE',
            medication_id=self.med_amox.id,
            batch_id=self.active_batch.id,
            quantity=discard_qty,
            reason='DAMAGED',
            notes='Vial cracked in storage',
            user=self.pharmacist
        )

        self.active_batch.refresh_from_db()
        self.assertEqual(self.active_batch.quantity_on_hand, initial_stock - discard_qty)

        ledger = StockMovementLedger.objects.filter(reference_id=record.reference_number).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.movement_type, 'WASTAGE')
        self.assertEqual(ledger.quantity, -discard_qty)
