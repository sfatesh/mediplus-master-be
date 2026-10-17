import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

# Add backend root to sys.path
sys.path.insert(0, str(BASE_DIR))

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY') or 'django-insecure-hospital-management-key-change-in-production'

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 't')

# ALLOWED_HOSTS Configuration
# Explicitly whitelist production host, Vercel preview domains, and local/test hosts.
default_hosts = [
    'localhost',
    '127.0.0.1',
    '[::1]',
    'testserver',
    'mediplus-master-be.vercel.app',
    '.vercel.app',
]

env_allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS') or os.getenv('ALLOWED_HOSTS')
if env_allowed_hosts:
    parsed_hosts = [host.strip() for host in env_allowed_hosts.split(',') if host.strip()]
    ALLOWED_HOSTS = list(dict.fromkeys(default_hosts + parsed_hosts))
else:
    ALLOWED_HOSTS = default_hosts

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.common.apps.CommonConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.patients.apps.PatientsConfig',
    'apps.departments.apps.DepartmentsConfig',
    'apps.appointments.apps.AppointmentsConfig',
    'apps.clinical.apps.ClinicalConfig',
    'apps.admissions.apps.AdmissionsConfig',
    'apps.nursing.apps.NursingConfig',
    'apps.pharmacy.apps.PharmacyConfig',
    'apps.laboratory.apps.LaboratoryConfig',
    'apps.billing.apps.BillingConfig',
    'apps.emergency.apps.EmergencyConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.reports.apps.ReportsConfig',
    'apps.audit.apps.AuditConfig',
    'apps.content.apps.ContentConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database configuration
env_db_url = os.getenv('DATABASE_URL')
if env_db_url and not env_db_url.startswith('sqlite:///python-backend'):
    DATABASE_URL = env_db_url
else:
    # On serverless (Vercel / AWS Lambda), the deployment filesystem is read-only.
    # Copy hospital.db to /tmp so SQLite write operations succeed.
    source_db = BASE_DIR / 'hospital.db'
    if os.getenv('VERCEL') == '1' and source_db.exists():
        import shutil
        tmp_db = Path('/tmp/hospital.db')
        try:
            if not tmp_db.exists() or tmp_db.stat().st_size == 0:
                shutil.copy2(source_db, tmp_db)
            db_file_path = tmp_db.resolve().as_posix()
        except Exception:
            db_file_path = source_db.resolve().as_posix()
    else:
        db_file_path = source_db.resolve().as_posix()

    DATABASE_URL = f"sqlite:///{db_file_path}"

DATABASES = {
    'default': dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Custom User Model & Authentication
AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/login/'
LOGIN_URL = '/admin/login/'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
}

# OpenAPI / Swagger settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Mediplus Hospital Management API',
    'DESCRIPTION': 'Modular, enterprise-grade multi-speciality hospital management REST API.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'PatientConsentStatusEnum': 'apps.patients.models.PatientConsent.STATUS_CHOICES',
        'AuditStatusEnum': 'apps.audit.models.AuditLog.STATUS_CHOICES',
    },
}

# CORS Configuration
# Whitelist frontend domains (local Angular and deployed Vercel frontend)
default_cors_origins = [
    'http://localhost:4200',
    'http://127.0.0.1:4200',
    'https://mediplus-master.vercel.app',
    'https://mediplus-master-fe.vercel.app',
]
env_cors = os.getenv('CORS_ALLOWED_ORIGINS') or os.getenv('DJANGO_CORS_ALLOWED_ORIGINS')
if env_cors:
    parsed_cors = [origin.strip() for origin in env_cors.split(',') if origin.strip()]
    CORS_ALLOWED_ORIGINS = list(dict.fromkeys(default_cors_origins + parsed_cors))
else:
    CORS_ALLOWED_ORIGINS = default_cors_origins

# Allow Vercel preview deployment URLs matching the mediplus-master project
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://mediplus-master(-[a-z0-9]+)?(-[a-z0-9_-]+)?\.vercel\.app$",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# CSRF Configuration
# Django 4+ requires explicit schemes (https:// or http://) in CSRF_TRUSTED_ORIGINS
default_csrf_origins = [
    'https://mediplus-master-be.vercel.app',
    'https://*.vercel.app',
    'https://mediplus-master.vercel.app',
    'https://mediplus-master-fe.vercel.app',
    'http://localhost:4200',
    'http://127.0.0.1:4200',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
env_csrf = os.getenv('CSRF_TRUSTED_ORIGINS') or os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS')
if env_csrf:
    parsed_csrf = [origin.strip() for origin in env_csrf.split(',') if origin.strip()]
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(default_csrf_origins + parsed_csrf))
else:
    CSRF_TRUSTED_ORIGINS = default_csrf_origins

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
