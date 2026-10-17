from .base import *

# Ensure DEBUG is disabled by default in production
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 't')

# Trust X-Forwarded-Proto header from Vercel edge reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production security headers
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

