import logging

logger = logging.getLogger(__name__)


class BaseService:
    """Base class providing transactional logging and standard execution pattern."""
    @classmethod
    def log_action(cls, action: str, details: dict):
        logger.info(f"[{cls.__name__}] Action: {action} - Details: {details}")

