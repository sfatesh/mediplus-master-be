from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import Role, AppPermission, RolePermission


PERMISSIONS_CATALOG = [
    # patients
    {'codename': 'patients.view', 'name': 'View Patients', 'module': 'patients', 'description': 'View patient demographic records and list'},
    {'codename': 'patients.create', 'name': 'Register Patient', 'module': 'patients', 'description': 'Create and register new patient profile'},
    {'codename': 'patients.edit', 'name': 'Edit Patient', 'module': 'patients', 'description': 'Update patient contact and demographic details'},
    {'codename': 'patients.delete', 'name': 'Deactivate Patient', 'module': 'patients', 'description': 'Deactivate or archive patient registration'},

    # appointments
    {'codename': 'appointments.view', 'name': 'View Appointments', 'module': 'appointments', 'description': 'View doctor appointment schedules and queues'},
    {'codename': 'appointments.create', 'name': 'Book Appointment', 'module': 'appointments', 'description': 'Schedule new OPD appointments'},
    {'codename': 'appointments.reschedule', 'name': 'Reschedule Appointment', 'module': 'appointments', 'description': 'Modify appointment times and doctor slots'},
    {'codename': 'appointments.cancel', 'name': 'Cancel Appointment', 'module': 'appointments', 'description': 'Cancel booked appointments'},
    {'codename': 'appointments.checkin', 'name': 'Check-in Patient', 'module': 'appointments', 'description': 'Mark patient as arrived and queue for consultation'},

    # clinical
    {'codename': 'clinical.consultation_view', 'name': 'View Consultations', 'module': 'clinical', 'description': 'View medical history and clinical encounter notes'},
    {'codename': 'clinical.consultation_create', 'name': 'Conduct Consultation', 'module': 'clinical', 'description': 'Create diagnoses and record consultation notes'},
    {'codename': 'clinical.consultation_sign', 'name': 'Sign Clinical Notes', 'module': 'clinical', 'description': 'Electronically sign and lock medical record notes'},
    {'codename': 'clinical.prescription_create', 'name': 'Authorize Prescription', 'module': 'clinical', 'description': 'Prescribe medications with dosage and frequency'},

    # admissions
    {'codename': 'admissions.view', 'name': 'View Inpatients', 'module': 'admissions', 'description': 'View ward occupancy, beds, and admission lists'},
    {'codename': 'admissions.admit', 'name': 'Admit Inpatient', 'module': 'admissions', 'description': 'Allocate bed and admit patient to hospital ward'},
    {'codename': 'admissions.transfer', 'name': 'Transfer Bed', 'module': 'admissions', 'description': 'Transfer inpatient between beds or departments'},
    {'codename': 'admissions.discharge', 'name': 'Discharge Inpatient', 'module': 'admissions', 'description': 'Process clinical discharge summary and release bed'},

    # nursing
    {'codename': 'nursing.station_view', 'name': 'View Nursing Station', 'module': 'nursing', 'description': 'Access nursing station dashboard and task lists'},
    {'codename': 'nursing.vitals_record', 'name': 'Record Vital Signs', 'module': 'nursing', 'description': 'Record temperature, BP, pulse, SpO2, and respiratory rate'},
    {'codename': 'nursing.notes_record', 'name': 'Add Nursing Notes', 'module': 'nursing', 'description': 'Record bedside nursing progress notes'},
    {'codename': 'nursing.medication_administer', 'name': 'Administer Medication', 'module': 'nursing', 'description': 'Log medication administration (MAR) with timestamp'},
    {'codename': 'nursing.tasks_manage', 'name': 'Manage Care Tasks', 'module': 'nursing', 'description': 'Update nursing orders and care task status'},

    # pharmacy
    {'codename': 'pharmacy.inventory_view', 'name': 'View Inventory', 'module': 'pharmacy', 'description': 'Inspect medication inventory, stock levels, and batches'},
    {'codename': 'pharmacy.stock_update', 'name': 'Update Stock', 'module': 'pharmacy', 'description': 'Add purchase receipts, batch adjustments, and restocks'},
    {'codename': 'pharmacy.dispense', 'name': 'Dispense Medication', 'module': 'pharmacy', 'description': 'Fulfill prescriptions and decrement pharmaceutical stock'},

    # laboratory
    {'codename': 'laboratory.orders_view', 'name': 'View Lab Orders', 'module': 'laboratory', 'description': 'Access laboratory worklist and requested diagnostic tests'},
    {'codename': 'laboratory.order_create', 'name': 'Order Lab Tests', 'module': 'laboratory', 'description': 'Request laboratory investigations for patient'},
    {'codename': 'laboratory.sample_collect', 'name': 'Accession Specimen', 'module': 'laboratory', 'description': 'Collect, barcode, and log laboratory samples'},
    {'codename': 'laboratory.result_entry', 'name': 'Enter Test Results', 'module': 'laboratory', 'description': 'Enter numerical and qualitative diagnostic test results'},
    {'codename': 'laboratory.results_approve', 'name': 'Verify & Release Results', 'module': 'laboratory', 'description': 'Verify accuracy and release diagnostic reports to patient'},

    # billing
    {'codename': 'billing.invoice_view', 'name': 'View Invoices', 'module': 'billing', 'description': 'View itemized patient billing statements and accounts'},
    {'codename': 'billing.invoice_create', 'name': 'Create Invoice', 'module': 'billing', 'description': 'Generate itemized billing statements for services'},
    {'codename': 'billing.payment_record', 'name': 'Collect Payment', 'module': 'billing', 'description': 'Process and record patient payments and issue receipts'},
    {'codename': 'billing.refund_request', 'name': 'Request Refund', 'module': 'billing', 'description': 'Initiate billing refund request with clinical reason'},
    {'codename': 'billing.refund_approve', 'name': 'Approve Refund', 'module': 'billing', 'description': 'Authorize financial refunds and process balance adjustments'},
    {'codename': 'billing.financial_reports', 'name': 'Financial Reporting', 'module': 'billing', 'description': 'View daily collections, revenue summaries, and reconciliations'},

    # reports
    {'codename': 'reports.view_operational', 'name': 'Operational Reports', 'module': 'reports', 'description': 'View occupancy, appointment volume, and turnaround metrics'},
    {'codename': 'reports.view_clinical', 'name': 'Clinical Reports', 'module': 'reports', 'description': 'Access clinical workload and department statistics'},
    {'codename': 'reports.view_financial', 'name': 'Financial Analytics', 'module': 'reports', 'description': 'Access revenue, billing breakdowns, and department receipts'},

    # users & administration
    {'codename': 'users.view', 'name': 'View User Accounts', 'module': 'users', 'description': 'View staff directory, roles, and user profiles'},
    {'codename': 'users.manage_roles', 'name': 'Manage User Roles', 'module': 'users', 'description': 'Assign, modify, or revoke user roles'},
    {'codename': 'users.activate_deactivate', 'name': 'Toggle Account Status', 'module': 'users', 'description': 'Enable or disable user login credentials'},
    {'codename': 'audit.view', 'name': 'View Audit Logs', 'module': 'audit', 'description': 'Review electronic medical records and financial audit trails'},
]


DEFAULT_ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: [p['codename'] for p in PERMISSIONS_CATALOG],
    Role.ADMIN: [
        'patients.view', 'patients.create', 'patients.edit', 'patients.delete',
        'appointments.view', 'appointments.create', 'appointments.reschedule', 'appointments.cancel', 'appointments.checkin',
        'clinical.consultation_view',
        'admissions.view', 'admissions.admit', 'admissions.transfer', 'admissions.discharge',
        'nursing.station_view',
        'pharmacy.inventory_view', 'pharmacy.stock_update', 'pharmacy.dispense',
        'laboratory.orders_view', 'laboratory.order_create', 'laboratory.results_approve',
        'billing.invoice_view', 'billing.invoice_create', 'billing.payment_record', 'billing.refund_request', 'billing.refund_approve', 'billing.financial_reports',
        'reports.view_operational', 'reports.view_clinical', 'reports.view_financial',
        'users.view', 'users.manage_roles', 'users.activate_deactivate',
        'audit.view',
    ],
    Role.DOCTOR: [
        'patients.view',
        'appointments.view', 'appointments.create', 'appointments.reschedule', 'appointments.cancel',
        'clinical.consultation_view', 'clinical.consultation_create', 'clinical.consultation_sign', 'clinical.prescription_create',
        'admissions.view', 'admissions.admit', 'admissions.discharge',
        'laboratory.orders_view', 'laboratory.order_create', 'laboratory.results_approve',
        'reports.view_clinical',
    ],
    Role.NURSE: [
        'patients.view',
        'appointments.view', 'appointments.checkin',
        'clinical.consultation_view',
        'admissions.view', 'admissions.admit', 'admissions.transfer',
        'nursing.station_view', 'nursing.vitals_record', 'nursing.notes_record', 'nursing.medication_administer', 'nursing.tasks_manage',
        'laboratory.orders_view', 'laboratory.sample_collect',
    ],
    Role.RECEPTIONIST: [
        'patients.view', 'patients.create', 'patients.edit',
        'appointments.view', 'appointments.create', 'appointments.reschedule', 'appointments.cancel', 'appointments.checkin',
        'admissions.view',
        'billing.invoice_view',
    ],
    Role.PHARMACIST: [
        'patients.view',
        'pharmacy.inventory_view', 'pharmacy.stock_update', 'pharmacy.dispense',
    ],
    Role.LAB_TECHNICIAN: [
        'patients.view',
        'laboratory.orders_view', 'laboratory.sample_collect', 'laboratory.result_entry',
    ],
    Role.BILLING_STAFF: [
        'patients.view',
        'billing.invoice_view', 'billing.invoice_create', 'billing.payment_record', 'billing.refund_request', 'billing.financial_reports',
        'reports.view_financial',
    ],
    Role.PATIENT: [
        'patients.view',
        'appointments.view', 'appointments.create', 'appointments.reschedule', 'appointments.cancel',
        'clinical.consultation_view',
        'billing.invoice_view',
    ],
}


class Command(BaseCommand):
    help = 'Initialize and seed the application permissions catalog and default role mappings'

    def handle(self, *args, **options):
        self.stdout.write("Initializing application permissions...")

        perm_objects = {}
        with transaction.atomic():
            for item in PERMISSIONS_CATALOG:
                perm, created = AppPermission.objects.update_or_create(
                    codename=item['codename'],
                    defaults={
                        'name': item['name'],
                        'module': item['module'],
                        'description': item['description'],
                    }
                )
                perm_objects[item['codename']] = perm
                if created:
                    self.stdout.write(f"  + Created permission: {perm.codename}")

            self.stdout.write("Mapping default role permissions...")
            for role_code, codenames in DEFAULT_ROLE_PERMISSIONS.items():
                for codename in codenames:
                    perm = perm_objects.get(codename)
                    if perm:
                        RolePermission.objects.get_or_create(
                            role=role_code,
                            permission=perm
                        )
                self.stdout.write(f"  * Configured permissions for role: {role_code} ({len(codenames)} permissions)")

        self.stdout.write(self.style.SUCCESS("RBAC permissions catalog and default role mappings successfully initialized!"))

