# backend/settings.py
from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta

# ======================================================
# BASE & ENV
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.environ.get('SECRET_KEY', 'unsafe-secret-key')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# ======================================================
# HOSTS CONFIG
# ======================================================
ALLOWED_HOSTS_STR = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STR.split(',') if host.strip()]

BACKEND_DOMAIN = os.environ.get('BACKEND_DOMAIN', '')
if BACKEND_DOMAIN:
    domain = BACKEND_DOMAIN.replace('https://', '').replace('http://', '').rstrip('/')
    if ':' in domain:
        domain_without_port = domain.split(':')[0]
        if domain_without_port not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(domain_without_port)
    if domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(domain)

RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_DOMAIN and RAILWAY_DOMAIN not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)

if DEBUG:
    ALLOWED_HOSTS = ['*']

# ======================================================
# DJANGO CORE SETTINGS
# ======================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'cloudinary_storage',
    'cloudinary',

    # Local
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

APPEND_SLASH = False
ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ======================================================
# DATABASE CONFIG
# ======================================================
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

# ======================================================
# PASSWORD VALIDATION
# ======================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================================================
# LANGUAGE & TIMEZONE
# ======================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ======================================================
# STATIC & MEDIA FILES
# ======================================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ======================================================
# CLOUDINARY CONFIG (Production only)
# ======================================================
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

if not DEBUG and CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======================================================
# REST FRAMEWORK & JWT
# ======================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# ======================================================
# CORS & CSRF CONFIG (FINAL FIX)
# ======================================================
# Handle CORS_ALLOW_CREDENTIALS from environment (can be string "True" or boolean)
CORS_ALLOW_CREDENTIALS_ENV = os.environ.get('CORS_ALLOW_CREDENTIALS', 'True')
CORS_ALLOW_CREDENTIALS = CORS_ALLOW_CREDENTIALS_ENV.lower() in ('true', '1', 't') if isinstance(CORS_ALLOW_CREDENTIALS_ENV, str) else CORS_ALLOW_CREDENTIALS_ENV

# Get CORS origins from environment variable or use defaults
CORS_ALLOWED_ORIGINS_STR = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if CORS_ALLOWED_ORIGINS_STR:
    # Parse from environment variable (comma-separated)
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS_STR.split(',') if origin.strip()]
    # Also add backend domain for internal requests
    if BACKEND_DOMAIN:
        backend_origin = BACKEND_DOMAIN.replace('https://', '').replace('http://', '').rstrip('/')
        backend_full = BACKEND_DOMAIN.rstrip('/')
        if backend_full not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(backend_full)
else:
    # Default origins
    CORS_ALLOWED_ORIGINS = [
        "https://mainajaa.vercel.app",
        "https://mainajaa-backend-production.up.railway.app",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

# Add regex patterns for Vercel deployments
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.railway\.app$",
]

# CSRF trusted origins - get from environment or use CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS_STR = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_STR:
    # Parse from environment variable (comma-separated)
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS_STR.split(',') if origin.strip()]
else:
    # Use CORS_ALLOWED_ORIGINS as base
    CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS) + [
        "https://*.vercel.app",
        "https://*.railway.app",
    ]

# Allow all methods
CORS_ALLOW_METHODS = [
    "DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT",
]

# Allow all necessary headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "cache-control",
]

CORS_PREFLIGHT_MAX_AGE = 86400

# For development, allow all origins if DEBUG is True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

# ======================================================
# MIDTRANS & ENCRYPTION
# ======================================================
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY')
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'False').lower() in ('true', '1', 't')
FERNET_KEY = os.environ.get('FERNET_KEY')

# Crypto Payment Wallet Addresses
USDT_WALLET_ADDRESS = os.environ.get('USDT_WALLET_ADDRESS', '')
ETH_WALLET_ADDRESS = os.environ.get('ETH_WALLET_ADDRESS', '')
SOL_WALLET_ADDRESS = os.environ.get('SOL_WALLET_ADDRESS', '')

# Blockchain Explorer API Keys (for automatic verification)
ETHERSCAN_API_KEY = os.environ.get('ETHERSCAN_API_KEY', 'YourApiKeyToken')  # Get free API key from etherscan.io
# Note: TronGrid (USDT) doesn't require API keys for basic queries
# Solana RPC is free but consider using dedicated RPC endpoint for production

# Exchange Rate API (for IDR to USD conversion)
EXCHANGERATE_API_KEY = os.environ.get('EXCHANGERATE_API_KEY', '')  # Optional: for exchangerate-api.com

# ======================================================
# EMAIL CONFIG
# ======================================================
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or 'noreply@mainajaa.com'

# ======================================================
# SECURITY (PRODUCTION)
# ======================================================
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # ⚠️ Railway already handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ======================================================
# DEBUG INFO (optional, remove later)
# ======================================================
print("✅ ALLOWED_HOSTS:", ALLOWED_HOSTS)
print("✅ CORS_ALLOWED_ORIGINS:", CORS_ALLOWED_ORIGINS)
try:
    print("✅ CORS_ALLOW_ALL_ORIGINS:", CORS_ALLOW_ALL_ORIGINS)
except NameError:
    print("✅ CORS_ALLOW_ALL_ORIGINS: Not set")
print("✅ CSRF_TRUSTED_ORIGINS:", CSRF_TRUSTED_ORIGINS)
print("✅ DEBUG:", DEBUG)
print("✅ CORS_ALLOW_CREDENTIALS:", CORS_ALLOW_CREDENTIALS)
