import os

env = os.getenv('DJANGO_ENV', 'development').lower()

if env == 'production':
    from .production import *
elif env == 'testing':
    from .testing import *
else:
    from .development import *

