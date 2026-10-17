import re
from datetime import date
from django.core.exceptions import ValidationError


def validate_phone_number(value):
    """Validates international or standard phone number formats."""
    pattern = r'^\+?1?\d{9,15}$'
    clean = re.sub(r'[\s\-\(\)]', '', value)
    if not re.match(pattern, clean):
        raise ValidationError('Enter a valid phone number with 9-15 digits.')


def validate_future_date(value):
    """Validates that a date is not in the past."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValidationError('Invalid date format. Expected YYYY-MM-DD.')
    if value < date.today():
        raise ValidationError('Appointment date cannot be in the past.')

