import logging
from datetime import datetime
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Standardizes error responses across all DRF views to:
    {
        "success": False,
        "status_code": 400,
        "error": "Error details",
        "timestamp": "2026-10-15T..."
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            'success': False,
            'status_code': response.status_code,
            'error': response.data,
            'timestamp': datetime.utcnow().isoformat()
        }
        response.data = custom_data
    else:
        logger.error(f"Unhandled Server Error: {exc}", exc_info=True)
        response = Response(
            {
                'success': False,
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': 'Internal server error occurred. Please contact support.',
                'timestamp': datetime.utcnow().isoformat()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response

