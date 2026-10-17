from rest_framework import views, status, permissions, serializers, viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from .serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    AppPermissionSerializer,
    RolePermissionSummarySerializer,
    RolePermissionsUpdateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    UserPermissionOverrideSerializer,
)
from .services import AuthService
from .models import User, Role, AppPermission, RolePermission, UserCustomPermission
from apps.common.permissions import IsAdmin, IsSuperAdmin
from apps.audit.services import AuditService


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    token_type = serializers.CharField(default='token')
    user = UserSerializer()


class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        summary="Register a new patient account",
        request=RegisterSerializer,
        responses={201: UserSerializer}
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token_key = AuthService.perform_login(request, user)
        user_data = UserSerializer(user).data

        return Response({
            'message': 'Account created successfully',
            'token': token_key,
            'token_type': 'Token',
            'user': user_data
        }, status=status.HTTP_201_CREATED)


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(
        summary="Authenticate user and return authorization token",
        request=LoginSerializer,
        responses={200: LoginResponseSerializer}
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        token_key = AuthService.perform_login(request, user)

        return Response({
            'token': token_key,
            'token_type': 'Token',
            'access_token': token_key,  # For backward-compatible clients
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class ProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Retrieve current authenticated user profile and roles",
        responses={200: UserSerializer}
    )
    def get(self, request):
        AuditService.log(
            action='VIEW_PROFILE',
            request=request,
            resource_type='User',
            resource_id=request.user.id
        )
        return Response(UserSerializer(request.user).data)

    @extend_schema(
        summary="Update current authenticated user's profile details",
        request=UserProfileUpdateSerializer,
        responses={200: UserSerializer}
    )
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        AuditService.log(
            action='UPDATE_PROFILE',
            request=request,
            resource_type='User',
            resource_id=request.user.id,
            details={'updated_fields': list(serializer.validated_data.keys())}
        )
        return Response(UserSerializer(request.user).data)


class LogoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageResponseSerializer

    @extend_schema(
        summary="Log out current user and invalidate authorization token",
        responses={200: MessageResponseSerializer}
    )
    def post(self, request):
        AuthService.perform_logout(request)
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)


class PasswordResetRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        summary="Request a password recovery reset token",
        request=PasswordResetRequestSerializer,
        responses={200: MessageResponseSerializer}
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        response_data = {'message': 'If the email exists in our records, password reset instructions have been dispatched.'}

        if user:
            uidb64, token = AuthService.generate_password_reset(request, user)
            # In testing/development, include reset tokens in response for verification
            import sys
            from django.conf import settings
            is_test_env = ('test' in sys.argv) or getattr(settings, 'DEBUG', False) or getattr(settings, 'TESTING', False)
            if is_test_env:
                response_data['uidb64'] = uidb64
                response_data['token'] = token

        return Response(response_data, status=status.HTTP_200_OK)


class PasswordResetConfirmView(views.APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        summary="Confirm password reset with received token and new password",
        request=PasswordResetConfirmSerializer,
        responses={200: MessageResponseSerializer}
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        new_password = serializer.validated_data['new_password']

        AuthService.complete_password_reset(request, user, new_password)
        return Response({'message': 'Password has been reset successfully. Please log in with your new credentials.'}, status=status.HTTP_200_OK)


class ChangePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change current authenticated user password",
        request=ChangePasswordSerializer,
        responses={200: MessageResponseSerializer}
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data['new_password']

        AuthService.complete_password_reset(request, request.user, new_password)
        # Generate fresh token for continuing session
        new_token = AuthService.perform_login(request, request.user)

        return Response({
            'message': 'Password changed successfully',
            'token': new_token
        }, status=status.HTTP_200_OK)


class AdminUserViewSet(viewsets.ModelViewSet):
    """
    Administrative management of hospital users, roles, and status.
    Protected strictly for Hospital Administrators and Super Administrators.
    """
    queryset = User.objects.all().select_related('doctor_profile__department', 'staff_profile__department').prefetch_related('user_custom_permissions__permission')
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'full_name', 'phone']
    ordering_fields = ['created_at', 'full_name', 'email']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Prevent deactivating self
        if 'is_active' in request.data and not request.data['is_active']:
            if instance.id == request.user.id:
                return Response(
                    {'detail': 'Administrators cannot deactivate their own user account.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()

        # If role changed to staff, make sure is_staff is True
        if updated_user.role in [
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.DOCTOR,
            Role.RECEPTIONIST,
            Role.NURSE,
            Role.PHARMACIST,
            Role.LAB_TECHNICIAN,
            Role.BILLING_STAFF,
        ]:
            if not updated_user.is_staff:
                updated_user.is_staff = True
                updated_user.save(update_fields=['is_staff'])

        AuditService.log(
            action='ADMIN_USER_UPDATED',
            request=request,
            resource_type='User',
            resource_id=instance.id,
            details={
                'target_email': instance.email,
                'updates': request.data
            }
        )
        return Response(AdminUserSerializer(updated_user).data)

    @action(detail=True, methods=['post'], url_path='override-permission')
    def override_permission(self, request, pk=None):
        """Assign or revoke an explicit permission override for this user."""
        user = self.get_object()
        serializer = UserPermissionOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        codename = serializer.validated_data['permission_codename']
        is_granted = serializer.validated_data['is_granted']

        permission = AppPermission.objects.filter(codename=codename).first()
        if not permission:
            return Response({'detail': f'Permission "{codename}" not found.'}, status=status.HTTP_404_NOT_FOUND)

        UserCustomPermission.objects.update_or_create(
            user=user,
            permission=permission,
            defaults={'is_granted': is_granted}
        )

        AuditService.log(
            action='USER_PERMISSION_OVERRIDDEN',
            request=request,
            resource_type='User',
            resource_id=user.id,
            details={'target_email': user.email, 'codename': codename, 'is_granted': is_granted}
        )
        return Response(AdminUserSerializer(user).data)

    @action(detail=True, methods=['delete'], url_path='clear-permission-override/(?P<codename>[^/.]+)')
    def clear_permission_override(self, request, pk=None, codename=None):
        """Remove a custom permission override for this user."""
        user = self.get_object()
        override = UserCustomPermission.objects.filter(user=user, permission__codename=codename).first()
        if override:
            override.delete()
            AuditService.log(
                action='USER_PERMISSION_OVERRIDE_CLEARED',
                request=request,
                resource_type='User',
                resource_id=user.id,
                details={'target_email': user.email, 'codename': codename}
            )
        return Response(AdminUserSerializer(user).data)


class RoleManagementViewSet(viewsets.ViewSet):
    """
    Role definitions and permission management.
    Protected for Hospital Administrators and Super Administrators.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def list(self, request):
        roles_data = []
        for role_code, role_label in Role.choices:
            if role_code == Role.SUPER_ADMIN:
                perms = list(AppPermission.objects.values_list('codename', flat=True))
            else:
                perms = list(
                    RolePermission.objects.filter(role=role_code)
                    .values_list('permission__codename', flat=True)
                )
            roles_data.append({
                'role': role_code,
                'role_name': role_label,
                'permissions_count': len(perms),
                'permissions': perms
            })
        return Response(roles_data)

    def retrieve(self, request, pk=None):
        role_code = pk.upper()
        role_dict = dict(Role.choices)
        if role_code not in role_dict:
            return Response({'detail': f'Role "{role_code}" does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        if role_code == Role.SUPER_ADMIN:
            perms = list(AppPermission.objects.values_list('codename', flat=True))
        else:
            perms = list(
                RolePermission.objects.filter(role=role_code)
                .values_list('permission__codename', flat=True)
            )

        return Response({
            'role': role_code,
            'role_name': role_dict[role_code],
            'permissions_count': len(perms),
            'permissions': perms
        })

    @action(detail=True, methods=['post'], url_path='permissions')
    def update_permissions(self, request, pk=None):
        role_code = pk.upper()
        role_dict = dict(Role.choices)
        if role_code not in role_dict:
            return Response({'detail': f'Role "{role_code}" does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        if role_code == Role.SUPER_ADMIN:
            return Response(
                {'detail': 'Permissions for Super Admin cannot be restricted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RolePermissionsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_codenames = set(serializer.validated_data['permissions'])

        RolePermission.objects.filter(role=role_code).delete()
        perms_to_add = AppPermission.objects.filter(codename__in=new_codenames)
        RolePermission.objects.bulk_create([
            RolePermission(role=role_code, permission=p) for p in perms_to_add
        ])

        AuditService.log(
            action='ROLE_PERMISSIONS_UPDATED',
            request=request,
            resource_type='Role',
            details={'role': role_code, 'permissions_count': perms_to_add.count()}
        )

        return Response({
            'role': role_code,
            'role_name': role_dict[role_code],
            'permissions_count': perms_to_add.count(),
            'permissions': list(perms_to_add.values_list('codename', flat=True))
        })


class PermissionCatalogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Catalog of all granular application permissions.
    """
    queryset = AppPermission.objects.all().order_by('module', 'codename')
    serializer_class = AppPermissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['codename', 'name', 'module', 'description']

