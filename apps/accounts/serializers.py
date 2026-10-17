from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from drf_spectacular.utils import extend_schema_field
from .models import (
    User,
    Role,
    StaffProfile,
    DoctorProfile,
    AppPermission,
    RolePermission,
    UserCustomPermission,
)
from apps.audit.services import AuditService


class StaffProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            'employee_id',
            'department',
            'department_name',
            'designation',
            'qualification',
            'license_number',
            'shift',
            'joining_date',
            'emergency_contact',
        ]


class DoctorProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            'department',
            'department_name',
            'specialization',
            'license_number',
            'consultation_fee',
            'room_number',
            'biography',
            'available_days',
            'is_available_for_emergency',
        ]


class UserSerializer(serializers.ModelSerializer):
    staff_profile = StaffProfileSerializer(read_only=True)
    doctor_profile = DoctorProfileSerializer(read_only=True)
    patient_mrn = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'phone',
            'role',
            'is_active',
            'is_staff',
            'patient_mrn',
            'permissions',
            'staff_profile',
            'doctor_profile',
            'created_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'is_active', 'is_staff', 'created_at']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, obj):
        return obj.get_all_permissions()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_patient_mrn(self, obj):
        if hasattr(obj, 'patient_profile') and obj.patient_profile:
            return obj.patient_profile.medical_record_number
        return None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'phone']

    def validate(self, attrs):
        # Explicitly guard against unauthorized role change attempts
        request = self.context.get('request')
        raw_data = self.initial_data
        if 'role' in raw_data and raw_data['role'] != self.instance.role:
            if not (request and request.user and request.user.is_admin):
                AuditService.log(
                    action='ROLE_ESCALATION_ATTEMPT',
                    request=request,
                    resource_type='User',
                    resource_id=self.instance.id,
                    status='DENIED',
                    details={'attempted_role': raw_data.get('role')}
                )
                raise serializers.ValidationError({"role": "You do not have permission to modify roles."})
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    role = serializers.CharField(max_length=30, required=False, default=Role.PATIENT)

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return normalized

    def validate(self, attrs):
        role_input = attrs.get('role', Role.PATIENT).upper()
        valid_roles = [r[0] for r in Role.choices]
        if role_input not in valid_roles:
            role_input = Role.PATIENT

        request = self.context.get('request')
        is_admin_request = bool(request and request.user and request.user.is_authenticated and request.user.is_admin)

        # ROLE ESCALATION PROTECTION: Non-admins cannot register elevated staff/doctor/admin roles
        if role_input != Role.PATIENT and not is_admin_request:
            AuditService.log(
                action='ROLE_ESCALATION_ATTEMPT',
                request=request,
                resource_type='User',
                status='DENIED',
                details={'attempted_role': role_input, 'email': attrs.get('email')}
            )
            raise serializers.ValidationError({
                "role": "Role escalation prohibited. Only administrators can assign hospital staff or doctor roles."
            })

        attrs['role'] = role_input
        return attrs

    def create(self, validated_data):
        from apps.patients.models import Patient
        email = validated_data['email']
        password = validated_data['password']
        full_name = validated_data['full_name']
        phone = validated_data.get('phone', '')
        role = validated_data.get('role', Role.PATIENT)

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            role=role
        )

        # If user registered as a patient, automatically establish their patient identity record
        if role == Role.PATIENT:
            current_year = timezone.now().year
            mrn = f"MED-{current_year}-{user.id:04d}"
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else 'Patient'

            Patient.objects.create(
                user=user,
                medical_record_number=mrn,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                is_active=True
            )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.db.models import Q
        login_input = attrs.get('email', '').strip().lower()
        password = attrs.get('password', '')

        user = User.objects.filter(
            Q(email__iexact=login_input) |
            Q(email__iexact=f"{login_input}@mediplus.com")
        ).first()

        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        if not user.is_active:
            raise PermissionDenied("Account is disabled. Please contact the hospital administration.")

        if not user.check_password(password):
            raise AuthenticationFailed("Invalid email or password.")

        attrs['user'] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": "Invalid or expired reset link."})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})

        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class AppPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppPermission
        fields = ['id', 'codename', 'name', 'module', 'description']


class RolePermissionSummarySerializer(serializers.Serializer):
    role = serializers.CharField()
    role_name = serializers.CharField()
    permissions_count = serializers.IntegerField()
    permissions = serializers.ListField(child=serializers.CharField())


class RolePermissionsUpdateSerializer(serializers.Serializer):
    permissions = serializers.ListField(child=serializers.CharField())


class UserCustomPermissionSerializer(serializers.ModelSerializer):
    codename = serializers.CharField(source='permission.codename', read_only=True)
    name = serializers.CharField(source='permission.name', read_only=True)
    module = serializers.CharField(source='permission.module', read_only=True)

    class Meta:
        model = UserCustomPermission
        fields = ['id', 'permission', 'codename', 'name', 'module', 'is_granted', 'created_at']


class UserPermissionOverrideSerializer(serializers.Serializer):
    permission_codename = serializers.CharField()
    is_granted = serializers.BooleanField()


class AdminUserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    custom_overrides = UserCustomPermissionSerializer(source='user_custom_permissions', many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'phone',
            'role',
            'is_active',
            'is_staff',
            'is_superuser',
            'department_name',
            'permissions',
            'custom_overrides',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_department_name(self, obj):
        if hasattr(obj, 'doctor_profile') and obj.doctor_profile and obj.doctor_profile.department:
            return obj.doctor_profile.department.name
        if hasattr(obj, 'staff_profile') and obj.staff_profile and obj.staff_profile.department:
            return obj.staff_profile.department.name
        return None

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, obj):
        return obj.get_all_permissions()


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    full_name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['role', 'is_active', 'full_name', 'phone']

    def validate_role(self, value):
        request = self.context.get('request')
        # Only superusers can assign SUPER_ADMIN role
        if value == Role.SUPER_ADMIN and not (request and request.user and request.user.is_super_admin):
            raise serializers.ValidationError("Only Super Administrators can assign the Super Admin role.")
        return value

