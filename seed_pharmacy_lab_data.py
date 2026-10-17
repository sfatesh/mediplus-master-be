import os
import django
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.pharmacy.models import Supplier, MedicineCatalogue, StockBatch, StockMovementLedger
from apps.laboratory.models import LabTestCatalogue, LabTestParameter
from apps.accounts.models import User, Role


def seed():
    admin = User.objects.filter(role=Role.ADMIN).first()
    today = date.today()

    # 1. Seed Pharmacy Suppliers
    s1, _ = Supplier.objects.get_or_create(
        code='SUP-001',
        defaults={
            'name': 'Apex Pharma Distributors',
            'contact_person': 'Robert Vance',
            'phone': '+1 (555) 234-8900',
            'email': 'orders@apexpharma.com',
            'address': '450 Industrial Parkway, BioTech Hub, CA',
            'license_number': 'WHL-CA-88912',
            'tax_id': 'TX-992140',
        }
    )

    s2, _ = Supplier.objects.get_or_create(
        code='SUP-002',
        defaults={
            'name': 'MedGlobal Solutions Ltd',
            'contact_person': 'Sarah Jenkins',
            'phone': '+1 (555) 345-6712',
            'email': 'supply@medglobal.com',
            'address': '12 Healthcare Way, Medical District, NY',
            'license_number': 'WHL-NY-11029',
            'tax_id': 'TX-441209',
        }
    )

    # 2. Seed Medicine Catalogue
    meds_data = [
        {
            'code': 'MED-AMOX-500',
            'name': 'Amoxicillin 500mg',
            'generic_name': 'Amoxicillin Trihydrate',
            'category': 'Antibiotics',
            'dosage_form': 'CAPSULE',
            'strength': '500 mg',
            'unit_of_measure': 'STRIP',
            'reorder_level': 30,
            'unit_price': Decimal('8.50'),
            'is_prescription_required': True,
        },
        {
            'code': 'MED-PARA-500',
            'name': 'Paracetamol 500mg',
            'generic_name': 'Acetaminophen',
            'category': 'Analgesics / Antipyretic',
            'dosage_form': 'TABLET',
            'strength': '500 mg',
            'unit_of_measure': 'STRIP',
            'reorder_level': 50,
            'unit_price': Decimal('3.00'),
            'is_prescription_required': False,
        },
        {
            'code': 'MED-METF-500',
            'name': 'Metformin HCl 500mg',
            'generic_name': 'Metformin Hydrochloride',
            'category': 'Antidiabetic',
            'dosage_form': 'TABLET',
            'strength': '500 mg',
            'unit_of_measure': 'STRIP',
            'reorder_level': 25,
            'unit_price': Decimal('6.25'),
            'is_prescription_required': True,
        },
        {
            'code': 'MED-ATOR-20',
            'name': 'Atorvastatin 20mg',
            'generic_name': 'Atorvastatin Calcium',
            'category': 'Cardiovascular',
            'dosage_form': 'TABLET',
            'strength': '20 mg',
            'unit_of_measure': 'STRIP',
            'reorder_level': 20,
            'unit_price': Decimal('14.00'),
            'is_prescription_required': True,
        },
        {
            'code': 'MED-CEFT-1G',
            'name': 'Ceftriaxone 1g Injection',
            'generic_name': 'Ceftriaxone Sodium',
            'category': 'Antibiotics (IV)',
            'dosage_form': 'INJECTION',
            'strength': '1000 mg',
            'unit_of_measure': 'VIAL',
            'reorder_level': 15,
            'unit_price': Decimal('22.50'),
            'is_prescription_required': True,
        },
        {
            'code': 'MED-SALB-100',
            'name': 'Salbutamol Inhaler 100mcg',
            'generic_name': 'Albuterol / Salbutamol',
            'category': 'Respiratory',
            'dosage_form': 'INHALER',
            'strength': '100 mcg/dose',
            'unit_of_measure': 'PIECE',
            'reorder_level': 10,
            'unit_price': Decimal('18.00'),
            'is_prescription_required': True,
        },
    ]

    for m in meds_data:
        med, created = MedicineCatalogue.objects.get_or_create(
            code=m['code'],
            defaults=m
        )

        # Seed Active Stock Batches for each
        b1_no = f"BTH-{med.code}-01"
        b1, b1_created = StockBatch.objects.get_or_create(
            medication=med,
            batch_number=b1_no,
            defaults={
                'manufacture_date': today - timedelta(days=90),
                'expiry_date': today + timedelta(days=365),
                'quantity_on_hand': 120,
                'unit_cost': med.unit_price * Decimal('0.60'),
                'unit_sale_price': med.unit_price,
                'status': 'ACTIVE',
            }
        )
        if b1_created and admin:
            StockMovementLedger.objects.create(
                medication=med,
                batch=b1,
                movement_type='PURCHASE_RECEIPT',
                quantity=120,
                balance_after=120,
                reference_type='INITIAL_STOCK_SEED',
                reference_id='SEED-001',
                unit_cost=b1.unit_cost,
                notes='Initial inventory opening balance',
                created_by=admin
            )

    # 3. Seed Laboratory Catalogue with Standard Diagnostic Panels & Reference Ranges
    # Panel 1: Complete Blood Count (CBC)
    cbc, _ = LabTestCatalogue.objects.get_or_create(
        code='LAB-CBC',
        defaults={
            'name': 'Complete Blood Count (CBC) with Differential',
            'category': 'HEMATOLOGY',
            'specimen_type': 'WHOLE_BLOOD',
            'container_type': 'Lavender Top (K2 EDTA)',
            'specimen_volume_required': '3.0 mL',
            'turnaround_time_hours': 2,
            'price': Decimal('45.00'),
            'description': 'Automated complete blood cell count including WBC, RBC, Hemoglobin, Hematocrit, and Platelets.'
        }
    )
    cbc_params = [
        {'name': 'White Blood Cells (WBC)', 'unit': '10^3/µL', 'reference_range_min': 4.5, 'reference_range_max': 11.0, 'critical_low': 2.0, 'critical_high': 25.0, 'sort_order': 1},
        {'name': 'Hemoglobin (Hb)', 'unit': 'g/dL', 'reference_range_min': 13.5, 'reference_range_max': 17.5, 'critical_low': 7.0, 'critical_high': 20.0, 'sort_order': 2},
        {'name': 'Hematocrit (Hct)', 'unit': '%', 'reference_range_min': 41.0, 'reference_range_max': 50.0, 'critical_low': 20.0, 'critical_high': 60.0, 'sort_order': 3},
        {'name': 'Platelet Count', 'unit': '10^3/µL', 'reference_range_min': 150.0, 'reference_range_max': 450.0, 'critical_low': 50.0, 'critical_high': 999.0, 'sort_order': 4},
    ]
    for p in cbc_params:
        LabTestParameter.objects.get_or_create(lab_test=cbc, name=p['name'], defaults=p)

    # Panel 2: Basic Metabolic Panel (BMP)
    bmp, _ = LabTestCatalogue.objects.get_or_create(
        code='LAB-BMP',
        defaults={
            'name': 'Basic Metabolic Panel (BMP)',
            'category': 'BIOCHEMISTRY',
            'specimen_type': 'SERUM',
            'container_type': 'Gold Top (SST with Gel)',
            'specimen_volume_required': '5.0 mL',
            'turnaround_time_hours': 3,
            'price': Decimal('55.00'),
            'description': 'Assesses renal function, glucose metabolism, and electrolyte balance.'
        }
    )
    bmp_params = [
        {'name': 'Sodium (Na)', 'unit': 'mmol/L', 'reference_range_min': 135.0, 'reference_range_max': 145.0, 'critical_low': 120.0, 'critical_high': 160.0, 'sort_order': 1},
        {'name': 'Potassium (K)', 'unit': 'mmol/L', 'reference_range_min': 3.5, 'reference_range_max': 5.1, 'critical_low': 2.8, 'critical_high': 6.2, 'sort_order': 2},
        {'name': 'Chloride (Cl)', 'unit': 'mmol/L', 'reference_range_min': 98.0, 'reference_range_max': 107.0, 'critical_low': 80.0, 'critical_high': 125.0, 'sort_order': 3},
        {'name': 'Blood Urea Nitrogen (BUN)', 'unit': 'mg/dL', 'reference_range_min': 7.0, 'reference_range_max': 20.0, 'critical_low': 2.0, 'critical_high': 80.0, 'sort_order': 4},
        {'name': 'Serum Creatinine', 'unit': 'mg/dL', 'reference_range_min': 0.7, 'reference_range_max': 1.3, 'critical_low': 0.2, 'critical_high': 4.0, 'sort_order': 5},
        {'name': 'Fasting Blood Glucose', 'unit': 'mg/dL', 'reference_range_min': 70.0, 'reference_range_max': 99.0, 'critical_low': 50.0, 'critical_high': 400.0, 'sort_order': 6},
    ]
    for p in bmp_params:
        LabTestParameter.objects.get_or_create(lab_test=bmp, name=p['name'], defaults=p)

    # Panel 3: Routine Urinalysis
    uri, _ = LabTestCatalogue.objects.get_or_create(
        code='LAB-URINE',
        defaults={
            'name': 'Urinalysis Complete Routine',
            'category': 'URINALYSIS',
            'specimen_type': 'URINE',
            'container_type': 'Sterile Urine Collection Cup',
            'specimen_volume_required': '15 mL',
            'turnaround_time_hours': 1,
            'price': Decimal('25.00'),
            'description': 'Chemical analysis and microscopic sediment evaluation of urine.'
        }
    )
    uri_params = [
        {'name': 'Urine pH', 'unit': '', 'reference_range_min': 4.5, 'reference_range_max': 8.0, 'sort_order': 1},
        {'name': 'Protein', 'unit': '', 'reference_range_text': 'Negative', 'sort_order': 2},
        {'name': 'Glucose', 'unit': '', 'reference_range_text': 'Negative', 'sort_order': 3},
        {'name': 'Leukocyte Esterase', 'unit': '', 'reference_range_text': 'Negative', 'sort_order': 4},
    ]
    for p in uri_params:
        LabTestParameter.objects.get_or_create(lab_test=uri, name=p['name'], defaults=p)

    print("Successfully seeded Pharmacy and Laboratory foundation catalog and test panels.")


if __name__ == '__main__':
    seed()

