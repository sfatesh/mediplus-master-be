import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.billing.models import ServiceCatalogue


def seed():
    services = [
        {
            'code': 'SRV-CONS-GEN',
            'name': 'Outpatient General Consultation',
            'category': 'CONSULTATION',
            'standard_rate': Decimal('40.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Standard physician consultation fee for walk-in or booked outpatient visit.'
        },
        {
            'code': 'SRV-CONS-SPEC',
            'name': 'Specialist Doctor Consultation',
            'category': 'CONSULTATION',
            'standard_rate': Decimal('85.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Senior specialist physician clinical assessment.'
        },
        {
            'code': 'SRV-BED-GEN',
            'name': 'General Ward Inpatient Accommodation',
            'category': 'INPATIENT_BED',
            'standard_rate': Decimal('150.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Daily room and general bed care charge.'
        },
        {
            'code': 'SRV-BED-ICU',
            'name': 'Intensive Care Unit (ICU) Bed Care',
            'category': 'INPATIENT_BED',
            'standard_rate': Decimal('600.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Daily intensive care bed, multi-parameter monitoring, and ventilator infrastructure.'
        },
        {
            'code': 'SRV-EMERG-TRI',
            'name': 'Emergency Department Triage & Resuscitation',
            'category': 'EMERGENCY',
            'standard_rate': Decimal('120.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Acute emergency evaluation and vital stabilization.'
        },
        {
            'code': 'SRV-PROC-DRESS',
            'name': 'Sterile Wound Dressing & Debridement',
            'category': 'PROCEDURE',
            'standard_rate': Decimal('35.00'),
            'tax_rate_percent': Decimal('5.00'),
            'description': 'Minor surgical dressing change.'
        },
        {
            'code': 'SRV-LAB-ROUTINE',
            'name': 'Laboratory Processing & Phlebotomy Fee',
            'category': 'LABORATORY',
            'standard_rate': Decimal('15.00'),
            'tax_rate_percent': Decimal('0.00'),
            'description': 'Specimen collection, barcode accessioning, and bio-hazard handling.'
        },
    ]

    for s in services:
        ServiceCatalogue.objects.get_or_create(code=s['code'], defaults=s)

    print("Successfully seeded Hospital Service Catalogue with standard rates.")


if __name__ == '__main__':
    seed()

