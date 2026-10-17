import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.common.models import TimeStampedModel


class Role(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Hospital Admin'
    DOCTOR = 'DOCTOR', 'Doctor'
    RECEPTIONIST = 'RECEPTIONIST', 'Receptionist'
    NURSE = 'NURSE', 'Nurse'
    PHARMACIST = 'PHARMACIST', 'Pharmacist'
    LAB_TECHNICIAN = 'LAB_TECHNICIAN', 'Lab Technician'
    BILLING_STAFF = 'BILLING_STAFF', 'Billing Staff / Accountant'
    PATIENT = 'PATIENT', 'Patient'


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name='', role=Role.PATIENT, **extra_fields):
        if not email:
            raise ValueError('An email address is required')
        email = self.normalize_email(email)
        
        # Standardize role
        role_val = str(role).upper()
        valid_roles = [c[0] for c in Role.choices]
        if role_val not in valid_roles:
            role_val = Role.PATIENT

        extra_fields.setdefault('is_active', True)
        # Hospital staff roles are given staff status for internal management
        if role_val in [
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.DOCTOR,
            Role.RECEPTIONIST,
            Role.NURSE,
            Role.PHARMACIST,
            Role.LAB_TECHNICIAN,
            Role.BILLING_STAFF,
        ]:
            extra_fields.setdefault('is_staff', True)
        else:
            extra_fields.setdefault('is_staff', False)

        user = self.model(
            email=email,
            full_name=full_name.strip(),
            role=role_val,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, full_name='Administrator', **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Role.SUPER_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password=password, full_name=full_name, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.PATIENT,
        db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN or self.is_superuser

    @property
    def is_admin(self):
        return self.role in [Role.ADMIN, Role.SUPER_ADMIN] or self.is_superuser

    @property
    def is_doctor(self):
        return self.role == Role.DOCTOR

    @property
    def is_receptionist(self):
        return self.role == Role.RECEPTIONIST

    @property
    def is_nurse(self):
        return self.role == Role.NURSE

    @property
    def is_pharmacist(self):
        return self.role == Role.PHARMACIST

    @property
    def is_lab_technician(self):
        return self.role == Role.LAB_TECHNICIAN

    @property
    def is_billing_staff(self):
        return self.role == Role.BILLING_STAFF

    @property
    def is_patient(self):
        return self.role == Role.PATIENT

    @property
    def is_hospital_staff(self):
        return self.role in [
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.DOCTOR,
            Role.RECEPTIONIST,
            Role.NURSE,
            Role.PHARMACIST,
            Role.LAB_TECHNICIAN,
            Role.BILLING_STAFF,
        ] or self.is_superuser

    @property
    def first_name(self):
        parts = self.full_name.split(' ', 1)
        return parts[0] if parts else ''

    @property
    def last_name(self):
        parts = self.full_name.split(' ', 1)
        return parts[1] if len(parts) > 1 else ''

    def get_all_permissions(self):
        """
        Calculates the effective permissions set for this user:
        1. If superuser or SUPER_ADMIN, returns all system permissions + '*'.
        2. Otherwise, fetches permissions assigned to user's role.
        3. Applies user-specific overrides (grants and revokes).
        """
        if self.is_superuser or self.role == Role.SUPER_ADMIN:
            all_perms = list(AppPermission.objects.values_list('codename', flat=True))
            if '*' not in all_perms:
                all_perms.insert(0, '*')
            return all_perms

        # Get role permissions
        role_perms = set(
            RolePermission.objects.filter(role=self.role)
            .values_list('permission__codename', flat=True)
        )

        # Apply user custom overrides
        custom_overrides = self.user_custom_permissions.select_related('permission').all()
        for override in custom_overrides:
            codename = override.permission.codename
            if override.is_granted:
                role_perms.add(codename)
            else:
                role_perms.discard(codename)

        return sorted(list(role_perms))

    def has_app_permission(self, perm_codename):
        """
        Check if user has a specific permission codename.
        """
        if not self.is_active:
            return False
        if self.is_superuser or self.role == Role.SUPER_ADMIN:
            return True
        effective_perms = self.get_all_permissions()
        return ('*' in effective_perms) or (perm_codename in effective_perms)


class StaffProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_members'
    )
    employee_id = models.CharField(max_length=50, unique=True, db_index=True)
    designation = models.CharField(max_length=100)
    qualification = models.CharField(max_length=255, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    shift = models.CharField(
        max_length=20,
        choices=[
            ('MORNING', 'Morning'),
            ('EVENING', 'Evening'),
            ('NIGHT', 'Night'),
            ('ROTATING', 'Rotating')
        ],
        default='MORNING'
    )
    joining_date = models.DateField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'accounts_staff_profile'
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'

    def __str__(self):
        return f"{self.employee_id} - {self.user.full_name} ({self.designation})"


class DoctorProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doctor_profiles'
    )
    specialization = models.CharField(max_length=150)
    license_number = models.CharField(max_length=100, unique=True, db_index=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    room_number = models.CharField(max_length=50, blank=True, null=True)
    biography = models.TextField(blank=True, null=True)
    available_days = models.CharField(max_length=100, default='Mon,Tue,Wed,Thu,Fri')
    is_available_for_emergency = models.BooleanField(default=True)

    class Meta:
        db_table = 'accounts_doctor_profile'
        verbose_name = 'Doctor Profile'
        verbose_name_plural = 'Doctor Profiles'

    def __str__(self):
        return f"Dr. {self.user.full_name} - {self.specialization} ({self.license_number})"


class AppPermission(TimeStampedModel):
    codename = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=50, db_index=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'accounts_permission'
        verbose_name = 'Application Permission'
        verbose_name_plural = 'Application Permissions'
        ordering = ['module', 'codename']

    def __str__(self):
        return f"{self.module} | {self.name} ({self.codename})"


class RolePermission(TimeStampedModel):
    role = models.CharField(max_length=30, choices=Role.choices, db_index=True)
    permission = models.ForeignKey(AppPermission, on_delete=models.CASCADE, related_name='role_mappings')

    class Meta:
        db_table = 'accounts_role_permission'
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role} -> {self.permission.codename}"


class UserCustomPermission(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_custom_permissions')
    permission = models.ForeignKey(AppPermission, on_delete=models.CASCADE, related_name='user_custom_mappings')
    is_granted = models.BooleanField(default=True)

    class Meta:
        db_table = 'accounts_user_permission'
        verbose_name = 'User Custom Permission'
        verbose_name_plural = 'User Custom Permissions'
        unique_together = ('user', 'permission')

    def __str__(self):
        status_str = "Granted" if self.is_granted else "Revoked"
        return f"{self.user.email} -> {self.permission.codename} ({status_str})"

