import os
import sys
import django
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.departments.models import Department
from apps.admissions.models import Ward, Room, Bed


def seed_inpatient_infrastructure():
    print("Seeding Wards, Rooms, and Beds...")

    # Default Wards
    wards_data = [
        {
            'name': 'Intensive Care Unit (ICU)',
            'code': 'ICU-MAIN',
            'ward_type': 'ICU',
            'floor': '3rd Floor, West Wing',
            'total_capacity': 6,
            'daily_base_rate': Decimal('350.00'),
            'rooms': [
                {'room_number': 'ICU-01', 'room_type': 'ICU_SUITE', 'daily_rate': Decimal('100.00'), 'beds': ['ICU-101', 'ICU-102']},
                {'room_number': 'ICU-02', 'room_type': 'ICU_SUITE', 'daily_rate': Decimal('100.00'), 'beds': ['ICU-103', 'ICU-104']},
                {'room_number': 'ICU-ISO', 'room_type': 'ISOLATION', 'daily_rate': Decimal('150.00'), 'beds': ['ICU-ISO-1']},
            ]
        },
        {
            'name': 'General Medical Ward',
            'code': 'GMW-NORTH',
            'ward_type': 'GENERAL',
            'floor': '2nd Floor, North Wing',
            'total_capacity': 12,
            'daily_base_rate': Decimal('60.00'),
            'rooms': [
                {'room_number': '201', 'room_type': 'GENERAL_WARD', 'daily_rate': Decimal('0.00'), 'beds': ['201-A', '201-B', '201-C', '201-D']},
                {'room_number': '202', 'room_type': 'SEMI_PRIVATE', 'daily_rate': Decimal('30.00'), 'beds': ['202-A', '202-B']},
                {'room_number': '203-P', 'room_type': 'PRIVATE', 'daily_rate': Decimal('75.00'), 'beds': ['203-PVT']},
            ]
        },
        {
            'name': 'Surgical Post-Op Ward',
            'code': 'SURG-POST',
            'ward_type': 'SURGICAL',
            'floor': '4th Floor, East Wing',
            'total_capacity': 8,
            'daily_base_rate': Decimal('120.00'),
            'rooms': [
                {'room_number': '401', 'room_type': 'SEMI_PRIVATE', 'daily_rate': Decimal('40.00'), 'beds': ['401-A', '401-B']},
                {'room_number': '402', 'room_type': 'PRIVATE', 'daily_rate': Decimal('90.00'), 'beds': ['402-PVT']},
            ]
        },
        {
            'name': 'Pediatric Care Ward',
            'code': 'PED-SOUTH',
            'ward_type': 'PEDIATRIC',
            'floor': '1st Floor, South Wing',
            'total_capacity': 6,
            'daily_base_rate': Decimal('70.00'),
            'rooms': [
                {'room_number': '101-PED', 'room_type': 'GENERAL_WARD', 'daily_rate': Decimal('0.00'), 'beds': ['CRIB-01', 'CRIB-02', 'CRIB-03']},
                {'room_number': '102-PED', 'room_type': 'SEMI_PRIVATE', 'daily_rate': Decimal('35.00'), 'beds': ['PED-201', 'PED-202']},
            ]
        }
    ]

    for w_info in wards_data:
        ward, created = Ward.objects.get_or_create(
            code=w_info['code'],
            defaults={
                'name': w_info['name'],
                'ward_type': w_info['ward_type'],
                'floor': w_info['floor'],
                'total_capacity': w_info['total_capacity'],
                'daily_base_rate': w_info['daily_base_rate'],
            }
        )
        if created:
            print(f"Created Ward: {ward.name}")

        for r_info in w_info['rooms']:
            room, r_created = Room.objects.get_or_create(
                ward=ward,
                room_number=r_info['room_number'],
                defaults={
                    'room_type': r_info['room_type'],
                    'daily_rate': r_info['daily_rate'],
                }
            )

            for bed_num in r_info['beds']:
                bed_type = 'ICU_CRITICAL' if 'ICU' in bed_num else ('PEDIATRIC_CRIB' if 'CRIB' in bed_num else 'STANDARD')
                bed, b_created = Bed.objects.get_or_create(
                    room=room,
                    bed_number=bed_num,
                    defaults={
                        'bed_type': bed_type,
                        'status': 'AVAILABLE'
                    }
                )
                if b_created:
                    print(f"  Created Bed: {bed.bed_number} in Room {room.room_number}")

    print("Inpatient infrastructure seeded successfully!")


if __name__ == '__main__':
    seed_inpatient_infrastructure()

