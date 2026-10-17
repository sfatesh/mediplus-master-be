from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.test import APIClient
from apps.accounts.models import User, Role
from apps.patients.models import Patient
from apps.departments.models import Department, Doctor
from apps.billing.models import (
    ServiceCatalogue,
    Invoice,
    InvoiceItem,
    Payment,
    Refund,
    InsurancePolicy,
    InsuranceClaim,
    InvoiceAdjustment,
)
from apps.billing.services import (
    create_invoice,
    record_payment,
    request_refund,
    approve_and_process_refund,
    adjust_invoice,
    get_financial_summary_report,
)


class HospitalBillingTestCase(TestCase):
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
        # Users
        self.admin = User.objects.create_user(
            email='admin_billing@test.com',
            full_name='Finance Director Admin',
            role=Role.ADMIN
        )
        self.cashier = User.objects.create_user(
            email='cashier@test.com',
            full_name='Billing Cashier',
            role=Role.RECEPTIONIST
        )
        self.patient_user = User.objects.create_user(
            email='patient_billing@test.com',
            full_name='Alice Smith',
            role=Role.PATIENT
        )
        self.other_patient_user = User.objects.create_user(
            email='patient2_billing@test.com',
            full_name='Bob Brown',
            role=Role.PATIENT
        )

        self.patient = Patient.objects.create(
            user=self.patient_user,
            first_name='Alice',
            last_name='Smith',
            date_of_birth='1992-03-10',
            gender='F',
            phone='+15554321098',
            address='789 Oak Ave'
        )

        # Service Catalog
        self.srv_consult = ServiceCatalogue.objects.create(
            code='SRV-TEST-CONS',
            name='Specialist Clinical Consultation',
            category='CONSULTATION',
            standard_rate=Decimal('100.00'),
            tax_rate_percent=Decimal('0.00')
        )
        self.srv_proc = ServiceCatalogue.objects.create(
            code='SRV-TEST-PROC',
            name='Minor Surgical Dressing',
            category='PROCEDURE',
            standard_rate=Decimal('50.00'),
            tax_rate_percent=Decimal('0.00')
        )

    def test_invoice_creation_and_calculation(self):
        """Creates an invoice and verifies subtotal, discount, tax, total, and balance_due."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[
                {
                    'service_id': self.srv_consult.id,
                    'description': 'Consultation with Specialist',
                    'quantity': 1,
                    'unit_price': Decimal('100.00'),
                    'discount_amount': Decimal('10.00'),
                    'tax_amount': Decimal('5.00')
                },
                {
                    'service_id': self.srv_proc.id,
                    'description': 'Procedure fee',
                    'quantity': 2,
                    'unit_price': Decimal('50.00'),
                    'discount_amount': Decimal('0.00'),
                    'tax_amount': Decimal('0.00')
                }
            ],
            discount_amount=Decimal('10.00'),
            discount_reason='Senior citizen discount',
            user=self.cashier
        )

        # Subtotal: (1 * 100) + (2 * 50) = 200.00
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        # Discount: 10.00
        self.assertEqual(invoice.discount_amount, Decimal('10.00'))
        # Tax: 5.00
        self.assertEqual(invoice.tax_amount, Decimal('5.00'))
        # Total: (200 - 10) + 5 = 195.00
        self.assertEqual(invoice.total_amount, Decimal('195.00'))
        # Initial amount_paid: 0, balance_due: 195.00
        self.assertEqual(invoice.amount_paid, Decimal('0.00'))
        self.assertEqual(invoice.balance_due, Decimal('195.00'))
        self.assertEqual(invoice.status, 'ISSUED')

    def test_partial_payment_and_allocation(self):
        """Tests partial payments progressing invoice from ISSUED -> PARTIALLY_PAID -> PAID."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Inpatient Bed Charge',
                'quantity': 1,
                'unit_price': Decimal('300.00')
            }],
            user=self.cashier
        )
        self.assertEqual(invoice.total_amount, Decimal('300.00'))

        # Part 1: Pay $100
        p1 = record_payment(
            invoice_id=invoice.id,
            amount=Decimal('100.00'),
            payment_method='CASH',
            transaction_reference='TXN-PARTIAL-001',
            user=self.cashier
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('100.00'))
        self.assertEqual(invoice.balance_due, Decimal('200.00'))
        self.assertEqual(invoice.status, 'PARTIALLY_PAID')

        # Part 2: Pay remaining $200
        p2 = record_payment(
            invoice_id=invoice.id,
            amount=Decimal('200.00'),
            payment_method='CARD',
            transaction_reference='TXN-PARTIAL-002',
            user=self.cashier
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('300.00'))
        self.assertEqual(invoice.balance_due, Decimal('0.00'))
        self.assertEqual(invoice.status, 'PAID')

    def test_duplicate_payment_idempotency_protection(self):
        """Retrying payment with identical transaction_reference returns existing payment and prevents double deduction."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Emergency visit',
                'quantity': 1,
                'unit_price': Decimal('150.00')
            }],
            user=self.cashier
        )

        txn_ref = 'GATEWAY-REF-IDEMPOTENT-123'
        # First call
        pay1 = record_payment(
            invoice_id=invoice.id,
            amount=Decimal('150.00'),
            payment_method='GATEWAY_ONLINE',
            transaction_reference=txn_ref,
            user=self.cashier
        )

        # Retry callback / duplicate network request
        pay2 = record_payment(
            invoice_id=invoice.id,
            amount=Decimal('150.00'),
            payment_method='GATEWAY_ONLINE',
            transaction_reference=txn_ref,
            user=self.cashier
        )

        # Should return the same completed payment record
        self.assertEqual(pay1.id, pay2.id)
        invoice.refresh_from_db()
        # Amount paid should still be 150.00, NOT 300.00!
        self.assertEqual(invoice.amount_paid, Decimal('150.00'))
        self.assertEqual(invoice.balance_due, Decimal('0.00'))
        self.assertEqual(invoice.payments.count(), 1)

    def test_overpayment_prevention(self):
        """Payment amount exceeding balance_due is rejected."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Lab fee',
                'quantity': 1,
                'unit_price': Decimal('80.00')
            }],
            user=self.cashier
        )

        with self.assertRaises(ValidationError) as ctx:
            record_payment(
                invoice_id=invoice.id,
                amount=Decimal('100.00'), # Exceeds 80.00
                payment_method='CASH',
                transaction_reference='TXN-OVER-001',
                user=self.cashier
            )
        self.assertIn('exceeds outstanding balance', str(ctx.exception).lower())

    def test_refund_request_approval_and_balance_reversal(self):
        """Refund request, approval by admin, and subsequent invoice balance reversal."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Specialist Consultation',
                'quantity': 1,
                'unit_price': Decimal('100.00')
            }],
            user=self.cashier
        )

        payment = record_payment(
            invoice_id=invoice.id,
            amount=Decimal('100.00'),
            payment_method='CARD',
            transaction_reference='TXN-REFUND-001',
            user=self.cashier
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')

        # 1. Non-admin requests refund
        refund = request_refund(
            payment_id=payment.id,
            amount=Decimal('100.00'),
            reason='Physician unavailable, consultation rescheduled',
            user=self.cashier
        )
        self.assertEqual(refund.status, 'REQUESTED')

        # 2. Non-admin cannot approve refund
        with self.assertRaises(PermissionDenied):
            approve_and_process_refund(refund.id, self.cashier)

        # 3. Admin approves and processes refund
        processed = approve_and_process_refund(refund.id, self.admin)
        self.assertEqual(processed.status, 'PROCESSED')
        self.assertEqual(processed.approved_by, self.admin)

        # 4. Check that invoice balance was restored and status updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('0.00'))
        self.assertEqual(invoice.balance_due, Decimal('100.00'))
        self.assertEqual(invoice.status, 'REFUNDED')

    def test_invoice_adjustment_audit_trail(self):
        """Invoice adjustments create an immutable audit record and update total amount."""
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Procedure Fee',
                'quantity': 1,
                'unit_price': Decimal('200.00')
            }],
            user=self.cashier
        )

        adj = adjust_invoice(
            invoice_id=invoice.id,
            adjustment_type='DISCOUNT_AMENDMENT',
            new_discount=Decimal('50.00'),
            reason='Hospital charity concession approved by board',
            user=self.admin
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal('150.00'))
        self.assertEqual(invoice.balance_due, Decimal('150.00'))

        self.assertEqual(adj.difference, Decimal('-50.00'))
        self.assertEqual(adj.adjusted_by, self.admin)

    def test_patient_permission_boundaries(self):
        """Patients can only access their own invoices and cannot see other patients' invoices."""
        client = APIClient()
        invoice = create_invoice(
            patient_id=self.patient.id,
            items_data=[{
                'description': 'Pharmacy Meds',
                'quantity': 1,
                'unit_price': Decimal('45.00')
            }],
            user=self.cashier
        )

        # Patient 1 can view their invoice
        client.force_authenticate(user=self.patient_user)
        response = client.get(f'/api/v1/billing/invoices/{invoice.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['invoice_number'], invoice.invoice_number)

        # Patient 2 cannot access Patient 1's invoice
        client.force_authenticate(user=self.other_patient_user)
        response = client.get(f'/api/v1/billing/invoices/{invoice.id}/')
        self.assertEqual(response.status_code, 404)

        # Non-admin cannot view financial summary report
        response = client.get('/api/v1/billing/invoices/financial-report/')
        self.assertEqual(response.status_code, 403)

        # Admin CAN view financial summary report
        client.force_authenticate(user=self.admin)
        response = client.get('/api/v1/billing/invoices/financial-report/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_invoiced', response.data)

