from rest_framework import permissions
from apps.accounts.models import Role


class IsSuperAdmin(permissions.BasePermission):
    """Allows access only to Super Administrators and Django superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == Role.SUPER_ADMIN or request.user.is_superuser)
        )


class IsAdmin(permissions.BasePermission):
    """Allows access to Hospital Administrators, Super Administrators, and Django superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN] or request.user.is_superuser)
        )


class IsDoctor(permissions.BasePermission):
    """Allows access to medical doctors and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.DOCTOR] or request.user.is_superuser)
        )


class IsReceptionist(permissions.BasePermission):
    """Allows access to hospital receptionists and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.RECEPTIONIST] or request.user.is_superuser)
        )


class IsNurse(permissions.BasePermission):
    """Allows access to nursing staff and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.NURSE] or request.user.is_superuser)
        )


class IsPharmacist(permissions.BasePermission):
    """Allows access to pharmacy staff and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.PHARMACIST] or request.user.is_superuser)
        )


class IsLabTechnician(permissions.BasePermission):
    """Allows access to laboratory technicians and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.LAB_TECHNICIAN] or request.user.is_superuser)
        )


class IsBillingStaff(permissions.BasePermission):
    """Allows access to billing specialists, accountants, and administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN, Role.BILLING_STAFF] or request.user.is_superuser)
        )


class IsStaffMember(permissions.BasePermission):
    """Allows access to any authorized hospital staff member."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(request.user.is_hospital_staff or request.user.is_superuser)


class IsPatient(permissions.BasePermission):
    """Allows access to registered patients."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == Role.PATIENT
        )


class IsPatientOwnerOrStaff(permissions.BasePermission):
    """
    Object-level permission:
    - Hospital staff can access patient records within their operational duties.
    - Patients can ONLY access their own records.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Staff members have access based on healthcare/administrative duties
        if user.is_hospital_staff or user.is_superuser:
            return True

        # Check ownership for patient
        if user.role == Role.PATIENT:
            # Direct Patient model instance
            if hasattr(obj, 'user') and obj.user_id is not None:
                return obj.user_id == user.id
            # Model with 'patient' FK
            if hasattr(obj, 'patient') and getattr(obj.patient, 'user_id', None) is not None:
                return obj.patient.user_id == user.id
            # Appointment or record with 'user_id' reference
            if hasattr(obj, 'user_id') and obj.user_id is not None:
                return obj.user_id == user.id

        return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allows full access to staff/admins, read-only to others."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in [Role.ADMIN, Role.SUPER_ADMIN] or request.user.is_staff or request.user.is_superuser)
        )


class HasPermission(permissions.BasePermission):
    """
    Granular permission check against user's effective permissions.
    Usage on viewset:
        required_permission = 'billing.refund_approve'
        permission_classes = [permissions.IsAuthenticated, HasPermission]
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        perm = getattr(view, 'required_permission', None)
        if not perm:
            return True
        return request.user.has_app_permission(perm)


def require_permission(permission_codename: str):
    """
    Factory function returning a DRF permission class that validates
    a specific granular permission codename.
    """
    class GranularPermissionChecker(permissions.BasePermission):
        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            return request.user.has_app_permission(permission_codename)

    GranularPermissionChecker.__name__ = f"RequirePermission_{permission_codename.replace('.', '_')}"
    return GranularPermissionChecker
