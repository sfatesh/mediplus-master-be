import os

env = os.getenv('DJANGO_ENV', '').lower()
if not env:
    # Auto-detect Vercel or cloud production environments
    if os.getenv('VERCEL') == '1' or os.getenv('ENVIRONMENT') == 'production':
        env = 'production'
    else:
        env = 'development'

if env == 'production':
    from .production import *
elif env == 'testing':
    from .testing import *
else:
    from .development import *

