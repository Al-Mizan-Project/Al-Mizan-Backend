import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

def env_str(name, default=""):
    return os.environ.get(name, default).strip() or default

def env_bool(name, default=False):
    val = os.environ.get(name)
    return default if val is None else val.strip().lower() in {'1', 'true', 'yes', 'on'}

def env_list(name, default=""):
    val = os.environ.get(name, default)
    return [x.strip() for x in val.split(',') if x.strip()]

DJANGO_ENV = env_str("DJANGO_ENV", "development").lower()
DEBUG = env_bool("DEBUG", DJANGO_ENV != "production")
SECRET_KEY = env_str("SECRET_KEY", "unsafe-dev-secret")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,*")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'documents_service',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    'default': dj_database_url.config(
        default=env_str("DATABASE_URL", f"sqlite:///{BASE_DIR}/db.sqlite3"),
        conn_max_age=120,
        ssl_require=env_bool("DB_SSL_REQUIRE", False)
    )
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

import sys

REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/1")

if 'test' in sys.argv:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 60,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {"max_connections": 200, "retry_on_timeout": True},
            },
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "300/minute",
        "user": "1200/minute",
    },
}

SIMPLE_JWT = {
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Al-Mizan Documents Service API",
    "VERSION": "1.0.0",
}

CORS_ALLOW_ALL_ORIGINS = True

MINIO_URL = env_str("MINIO_URL", "http://localhost:9000")
MINIO_ACCESS_KEY = env_str("MINIO_ACCESS_KEY", "admin_almizan")
MINIO_SECRET_KEY = env_str("MINIO_SECRET_KEY", "SecurePassword123!")
MINIO_BUCKET_NAME = env_str("MINIO_BUCKET_NAME", "almizan-documents")
