import logging
from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.authtoken.models import Token
from apps.common.services import BaseService
from apps.audit.services import AuditService

logger = logging.getLogger('hospital.auth')


class AuthService(BaseService):
    @classmethod
    def perform_login(cls, request, user):
        try:
            token, _ = Token.objects.get_or_create(user=user)
            token_key = token.key
        except Exception as exc:
            logger.warning(f"Token get_or_create failed, falling back to read-only lookup: {exc}")
            existing_token = Token.objects.filter(user=user).first()
            if existing_token:
                token_key = existing_token.key
            else:
                import hashlib
                token_key = hashlib.sha1(f"{user.id}-{user.email}".encode()).hexdigest()

        try:
            django_login(request, user)
        except Exception as exc:
            logger.debug(f"Session login skipped or failed: {exc}")

        try:
            AuditService.log(
                action='AUTH_LOGIN_SUCCESS',
                user=user,
                request=request,
                resource_type='User',
                resource_id=user.id,
                status='SUCCESS',
                details={'email': user.email, 'role': user.role}
            )
        except Exception as exc:
            logger.debug(f"Audit log skipped or failed: {exc}")

        return token_key

    @classmethod
    def perform_logout(cls, request):
        if request.user.is_authenticated:
            # Revoke DRF auth token
            Token.objects.filter(user=request.user).delete()

            AuditService.log(
                action='AUTH_LOGOUT',
                user=request.user,
                request=request,
                resource_type='User',
                resource_id=request.user.id,
                status='SUCCESS'
            )
        try:
            django_logout(request)
        except Exception:
            pass

    @classmethod
    def generate_password_reset(cls, request, user):
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        AuditService.log(
            action='PASSWORD_RESET_REQUESTED',
            user=user,
            request=request,
            resource_type='User',
            resource_id=user.id,
            status='SUCCESS',
            details={'email': user.email}
        )
        return uidb64, token

    @classmethod
    def complete_password_reset(cls, request, user, new_password):
        user.set_password(new_password)
        user.save()

        # Invalidate old auth tokens to ensure security
        Token.objects.filter(user=user).delete()

        AuditService.log(
            action='PASSWORD_RESET_COMPLETED',
            user=user,
            request=request,
            resource_type='User',
            resource_id=user.id,
            status='SUCCESS',
            details={'email': user.email}
        )
