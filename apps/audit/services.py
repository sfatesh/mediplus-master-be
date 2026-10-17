import logging
from apps.common.services import BaseService
from .models import AuditLog

logger = logging.getLogger('hospital.audit')


class AuditService(BaseService):
    @classmethod
    def log(cls, action, user=None, request=None, resource_type=None, resource_id=None, status='SUCCESS', details=None):
        ip_address = None
        user_agent = None

        if request is not None:
            # Extract client IP safely
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

            if user is None and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user

        try:
            record = AuditLog.objects.create(
                user=user,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                status=status,
                details=details or {}
            )
            return record
        except Exception as exc:
            # Never let audit log failure break the main request
            logger.error(f"Failed to record audit log: {exc}", exc_info=True)
            return None


def log_audit_event(action, entity_type=None, entity_id=None, user=None, details=None, status='SUCCESS'):
    return AuditService.log(
        action=action,
        user=user,
        resource_type=entity_type,
        resource_id=entity_id,
        status=status,
        details=details
    )

