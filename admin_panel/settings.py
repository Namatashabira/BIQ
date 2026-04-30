import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "corsheaders",
    "channels",
    "django_extensions",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "tenants",  # keep for tenant/account model
    "accounts",
    "users",
    "core",
    "core.orders",
    "product",
    "accounting",
    "enrollment",
    "website_config",
    "customer_reviews.apps.CustomerReviewsConfig",
    "sales",
    "forecast",
    "business_reports",
    'cloudinary',
    'cloudinary_storage',
]

# Add Cloudinary apps only if the package is installed
try:
    import cloudinary  # noqa
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]
except ImportError:
    pass

# --------------------------------------
# BASE DIRECTORY
# --------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------
# SECRET & DEBUG
# --------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",") + [
    "healthcheck.railway.app",
    "web-production-36021.up.railway.app",
]

# --------------------------------------
## INSTALLED_APPS now defined above

# --------------------------------------
# MIDDLEWARE
# --------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # For path-based tenant routing, ensure your tenant middleware runs early (before authentication).
    # Example: 'tenants.middleware.TenantPathMiddleware' (if you have a custom one)
    # Place your tenant path middleware here if you have one, e.g.:
    # "tenants.middleware.TenantPathMiddleware",
    "core.logging_middleware.RequestLoggingMiddleware",
    "core.csrf_middleware.CSRFExemptMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware_access.PageAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# --------------------------------------
# URLS & TEMPLATES
# --------------------------------------
ROOT_URLCONF = "admin_panel.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "admin_panel.wsgi.application"
ASGI_APPLICATION = "admin_panel.asgi.application"

# --------------------------------------
# CORS & CSRF
# --------------------------------------

# Dynamically load CORS_ALLOWED_ORIGINS from the database (AllowedOrigin model)
import sys
if 'runserver' in sys.argv or 'gunicorn' in sys.argv or 'uwsgi' in sys.argv:
    try:
        from website_config.models import AllowedOrigin
        CORS_ALLOWED_ORIGINS = list(AllowedOrigin.objects.values_list('origin', flat=True))
    except Exception:
        # Fallback for migrations/initial setup
        CORS_ALLOWED_ORIGINS = [
            "http://localhost:5176",
            "http://127.0.0.1:5176",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "https://web.railway.internal",
            "https://namatashabira.github.io",
        ]
else:
    CORS_ALLOWED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "https://web.railway.internal",
    "https://namatashabira.github.io",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "https://web.railway.internal",
    "https://namatashabira.github.io",
]
CORS_ALLOW_ALL_ORIGINS = True  # Temporarily allow all origins for testing
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
    'cache-control',
    'pragma',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# Disable CSRF for API endpoints
CSRF_EXEMPT_URLS = [r'^api/.*']

# --------------------------------------
# DATABASE
# --------------------------------------
# Use DATABASE_URL for tenant-aware Postgres; fall back to sqlite for local dev.
db_config = dj_database_url.config(
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
)



DATABASES = {
    "default": db_config
}



# --------------------------------------
# PASSWORD VALIDATION
# --------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------
# INTERNATIONALIZATION
# --------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --------------------------------------
# STATIC & MEDIA FILES
# --------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
os.makedirs(STATIC_ROOT, exist_ok=True)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024))

# --------------------------------------
# CLOUDINARY CONFIGURATION
# --------------------------------------
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET', ''),
}

# Use Cloudinary for media file storage in production
if not DEBUG:
    try:
        import cloudinary_storage  # noqa
        DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    except ImportError:
        pass

try:
    import cloudinary
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', ''),
        api_key=os.getenv('CLOUDINARY_API_KEY', ''),
        api_secret=os.getenv('CLOUDINARY_API_SECRET', ''),
        secure=True,
    )
except ImportError:
    pass

# --------------------------------------
# REST FRAMEWORK
# --------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",  # tightened for multi-tenant
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}

# --------------------------------------
# SIMPLE JWT SETTINGS
# --------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# --------------------------------------
# CHANNELS CONFIG
# --------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# --------------------------------------
# LOGGING CONFIGURATION
# --------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'api': {
            'format': '[API] {asctime} - {levelname} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'api',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'api.log',
            'formatter': 'verbose',
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
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
# --------------------------------------
# STATIC & MEDIA FILES
# --------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# Media settings for product images
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------
# DEFAULTS
# --------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"  # shared custom user for multi-tenant

# --------------------------------------
# EMAIL CONFIGURATION
# --------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development - prints to console
# For production, use SMTP:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'ssematasabira24@gmail.com'  # Replace with your email address 'ssematasabira24@gmail.com'

# --------------------------------------
# FRONTEND URL (for password reset links)
# --------------------------------------
# --------------------------------------
# TENANT PATH-BASED ROUTING
# --------------------------------------
# All tenant URLs use the format: /<tenant-path-slug>/...
# Example: /kata-chemical-1a2b3c4d/dashboard/
# The middleware must set request.tenant based on the path_slug in the URL.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5176")
