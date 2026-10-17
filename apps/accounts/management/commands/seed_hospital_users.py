from django.core.management.base import BaseCommand
from apps.accounts.models import User, Role, StaffProfile, DoctorProfile
from apps.patients.models import Patient, PatientConsent
from apps.departments.models import Department


class Command(BaseCommand):
    help = 'Seed foundational hospital users for all 7 required roles'

    def handle(self, *args, **options):
        self.stdout.write("Seeding hospital role accounts...")
        default_dept = Department.objects.first()

        users_data = [
            {
                'email': 'superadmin@mediplus.com',
                'password': 'SuperAdminPass123!',
                'full_name': 'Global Super Administrator',
                'phone': '+1 555-0099',
                'role': Role.SUPER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'email': 'admin@mediplus.com',
                'password': 'AdminPass123!',
                'full_name': 'Hospital Director Administrator',
                'phone': '+1 555-0100',
                'role': Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'email': 'billing@mediplus.com',
                'password': 'BillingPass123!',
                'full_name': 'Victoria Vance',
                'phone': '+1 555-0107',
                'role': Role.BILLING_STAFF,
                'is_staff': True,
            },
            {
                'email': 'doctor@mediplus.com',
                'password': 'DoctorPass123!',
                'full_name': 'Dr. Alexander Bennett',
                'phone': '+1 555-0101',
                'role': Role.DOCTOR,
                'is_staff': True,
            },
            {
                'email': 'receptionist@mediplus.com',
                'password': 'ReceptionPass123!',
                'full_name': 'Sarah Jenkins',
                'phone': '+1 555-0102',
                'role': Role.RECEPTIONIST,
                'is_staff': True,
            },
            {
                'email': 'nurse@mediplus.com',
                'password': 'NursePass123!',
                'full_name': 'Emily Watson',
                'phone': '+1 555-0103',
                'role': Role.NURSE,
                'is_staff': True,
            },
            {
                'email': 'pharmacist@mediplus.com',
                'password': 'PharmaPass123!',
                'full_name': 'Marcus Cole',
                'phone': '+1 555-0104',
                'role': Role.PHARMACIST,
                'is_staff': True,
            },
            {
                'email': 'labtech@mediplus.com',
                'password': 'LabTechPass123!',
                'full_name': 'Rachel Green',
                'phone': '+1 555-0105',
                'role': Role.LAB_TECHNICIAN,
                'is_staff': True,
            },
            {
                'email': 'patient@mediplus.com',
                'password': 'PatientPass123!',
                'full_name': 'John Doe',
                'phone': '+1 555-0106',
                'role': Role.PATIENT,
                'is_staff': False,
            },
        ]

        for item in users_data:
            email = item['email']
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    password=item['password'],
                    full_name=item['full_name'],
                    phone=item['phone'],
                    role=item['role'],
                    is_superuser=item.get('is_superuser', False),
                )
                self.stdout.write(self.style.SUCCESS(f"Created user: {email} ({item['role']})"))
            else:
                user.set_password(item['password'])
                user.role = item['role']
                user.save()
                self.stdout.write(f"Updated password and role for: {email}")

            # Profile creation
            if item['role'] == Role.DOCTOR:
                DoctorProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'department': default_dept,
                        'specialization': 'General Medicine & Cardiology',
                        'license_number': f'MED-DOC-{user.id:04d}',
                        'consultation_fee': 75.00,
                        'room_number': 'Room 302',
                        'biography': 'Senior consulting physician with over 15 years experience in internal medicine.',
                        'available_days': 'Mon,Tue,Wed,Thu,Fri',
                    }
                )
            elif item['role'] in [Role.RECEPTIONIST, Role.NURSE, Role.PHARMACIST, Role.LAB_TECHNICIAN]:
                StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'department': default_dept,
                        'employee_id': f'EMP-{user.id:04d}',
                        'designation': item['role'].title().replace('_', ' '),
                        'shift': 'MORNING',
                    }
                )
            elif item['role'] == Role.PATIENT:
                patient, _ = Patient.objects.get_or_create(
                    user=user,
                    defaults={
                        'medical_record_number': f'MED-2026-{user.id:04d}',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'phone': item['phone'],
                        'email': email,
                        'blood_group': 'O+',
                        'gender': 'MALE',
                    }
                )
                # Seed a default treatment consent
                PatientConsent.objects.get_or_create(
                    patient=patient,
                    consent_type='GENERAL_TREATMENT',
                    defaults={
                        'status': 'GRANTED',
                        'signed_by': 'John Doe',
                        'notes': 'Initial registration general consent.'
                    }
                )

        self.stdout.write(self.style.SUCCESS("Hospital role accounts successfully seeded."))

