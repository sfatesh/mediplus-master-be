from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Allows authentication using either full email (admin@mediplus.com)
    or username prefix (e.g. 'admin', 'doctor', 'receptionist').
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')

        if not username or not password:
            return None

        username = username.strip()

        # Try exact email match first, then email prefix before @
        user = User.objects.filter(
            Q(email__iexact=username) |
            Q(email__iexact=f"{username}@mediplus.com")
        ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

