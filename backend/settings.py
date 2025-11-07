# backend/settings.py

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# Update untuk production
# Baca ALLOWED_HOSTS dari environment variable, split by comma dan strip whitespace
ALLOWED_HOSTS_STR = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STR.split(',') if host.strip()]

# Tambahkan backend domain jika ada
BACKEND_DOMAIN = os.environ.get('BACKEND_DOMAIN', '')
if BACKEND_DOMAIN:
    # Extract domain dari URL (remove https:// and trailing slash)
    domain = BACKEND_DOMAIN.replace('https://', '').replace('http://', '').rstrip('/')
    # Tambahkan domain dan juga tanpa port jika ada
    if ':' in domain:
        domain_without_port = domain.split(':')[0]
        if domain_without_port not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(domain_without_port)
    if domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(domain)

# Tambahkan Railway domain jika ada
RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_DOMAIN:
    if RAILWAY_DOMAIN not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    
# Untuk development, allow all jika DEBUG=True
if DEBUG:
    ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Aplikasi Pihak Ketiga
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'cloudinary_storage',  # NEW untuk media files
    'cloudinary',          # NEW untuk media files
    
    # Aplikasi Lokal Anda
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # FIX: Tambah comma
    'corsheaders.middleware.CorsMiddleware',  # CORS middleware harus di atas CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Disable APPEND_SLASH untuk menghindari 301 redirect yang menyebabkan CORS issue
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

# Database - Support SQLite local & PostgreSQL production
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files - Local untuk development, Cloudinary untuk production
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cloudinary Configuration untuk production
# Gunakan Cloudinary jika environment variables sudah di-set (production)
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

# Aktifkan Cloudinary jika semua credentials tersedia (production)
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,
    }
    # Catatan: Cloudinary storage akan otomatis mengembalikan URL absolute
    # Tidak perlu override MEDIA_URL karena Cloudinary menangani URL-nya sendiri

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}

# JWT Token Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),  # Access token berlaku 24 jam
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),   # Refresh token berlaku 7 hari
    'ROTATE_REFRESH_TOKENS': True,                 # Rotate refresh token setiap kali digunakan
    'BLACKLIST_AFTER_ROTATION': True,              # Blacklist token lama setelah rotate
    'UPDATE_LAST_LOGIN': True,                      # Update last login time
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
# --- CORS & CSRF FIXED CONFIG ---
CORS_ALLOW_CREDENTIALS = True

# Get frontend URL from environment or use defaults
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://mainajaa.vercel.app')
LOCAL_FRONTEND = os.environ.get('LOCAL_FRONTEND_URL', 'http://localhost:5173')

# Untuk development, allow all origins jika DEBUG=True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
else:
    CORS_ALLOW_ALL_ORIGINS = False
    
    # Baca CORS_ALLOWED_ORIGINS dari environment variable jika ada
    CORS_ORIGINS_ENV = os.environ.get('CORS_ALLOWED_ORIGINS', '')
    if CORS_ORIGINS_ENV:
        # Split by comma dan strip whitespace
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(',') if origin.strip()]
    else:
        # Fallback ke default
        CORS_ALLOWED_ORIGINS = [
            FRONTEND_URL,
            LOCAL_FRONTEND,
        ]
    
    # Tambahkan origin tambahan dari environment variable jika ada
    ADDITIONAL_CORS_ORIGINS = os.environ.get('ADDITIONAL_CORS_ORIGINS', '')
    if ADDITIONAL_CORS_ORIGINS:
        for origin in ADDITIONAL_CORS_ORIGINS.split(','):
            origin = origin.strip()
            if origin and origin not in CORS_ALLOWED_ORIGINS:
                CORS_ALLOWED_ORIGINS.append(origin)

# Tambahkan ini untuk handle subdomain preview otomatis
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# Allow all methods and headers
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

# Preflight cache duration
CORS_PREFLIGHT_MAX_AGE = 86400

# CSRF Configuration - baca dari environment variable jika ada
CSRF_TRUSTED_ORIGINS_ENV = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_ENV:
    # Split by comma dan strip whitespace
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS_ENV.split(',') if origin.strip()]
    # Jika ada wildcard pattern, tambahkan ke regex
    CSRF_TRUSTED_ORIGIN_REGEXES = []
    for origin in CSRF_TRUSTED_ORIGINS:
        if '*' in origin:
            # Convert wildcard to regex
            regex_pattern = origin.replace('*', '.*').replace('.', r'\.')
            CSRF_TRUSTED_ORIGIN_REGEXES.append(f'^{regex_pattern}$')
    # Tambahkan default regex untuk vercel
    if r"^https://.*\.vercel\.app$" not in CSRF_TRUSTED_ORIGIN_REGEXES:
        CSRF_TRUSTED_ORIGIN_REGEXES.append(r"^https://.*\.vercel\.app$")
else:
    # Fallback ke default
    CSRF_TRUSTED_ORIGINS = [
        FRONTEND_URL,
    ]
    CSRF_TRUSTED_ORIGIN_REGEXES = [
        r"^https://.*\.vercel\.app$",
    ]


# Midtrans
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
MIDTRANS_CLIENT_KEY = os.environ.get('MIDTRANS_CLIENT_KEY')
MIDTRANS_IS_PRODUCTION = os.environ.get('MIDTRANS_IS_PRODUCTION', 'False').lower() in ('true', '1', 't')

# Encryption
FERNET_KEY = os.environ.get('FERNET_KEY')

# Email Configuration
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Security Settings untuk Production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

