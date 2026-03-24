import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_str(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if value == "":
        return default
    return value


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DJANGO_ENV = env_str("DJANGO_ENV", "development").lower()
DEBUG = env_bool("DEBUG", env_bool("DJANGO_DEBUG", DJANGO_ENV != "production"))
SECRET_KEY = env_str("SECRET_KEY", env_str("DJANGO_SECRET_KEY", "unsafe-dev-secret"))
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", env_str("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"))
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", env_str("DJANGO_CSRF_TRUSTED_ORIGINS", ""))
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))
LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
if DJANGO_ENV == "production" and SECRET_KEY == "unsafe-dev-secret":
    raise RuntimeError("SECRET_KEY must be set when DJANGO_ENV=production")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "contrats_service",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — PgBouncer sits between Django and PostgreSQL
# ---------------------------------------------------------------------------
DB_NAME = env_str("DB_NAME", "contrats_db")
DB_USER = env_str("DB_USER", "contrats_user")
DB_PASSWORD = env_str("DB_PASSWORD", "contrats_password")
DB_HOST = env_str("DB_HOST", "pgbouncer_contrats")
DB_PORT = env_str("DB_PORT", "6432")
CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", "120"))
DATABASE_URL = env_str("DATABASE_URL", "")
if DATABASE_URL:
    default_db = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=CONN_MAX_AGE,
        ssl_require=env_bool("DB_SSL_REQUIRE", False),
    )
else:
    default_db = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }
default_db["CONN_MAX_AGE"] = CONN_MAX_AGE
default_db["CONN_HEALTH_CHECKS"] = env_bool("DB_CONN_HEALTH_CHECKS", True)
default_db["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES = {"default": default_db}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Redis / Cache
# ---------------------------------------------------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://redis_contrats:6379/1")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": CACHE_TTL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "200")),
                "retry_on_timeout": True,
            },
        },
    }
}

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("THROTTLE_ANON_RATE", "240/minute"),
        "user": os.getenv("THROTTLE_USER_RATE", "1200/minute"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Al-Mizan Contrats Service API",
    "VERSION": "1.0.0",
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", env_bool("DJANGO_SECURE_SSL_REDIRECT", False))
SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    env_bool("DJANGO_SESSION_COOKIE_SECURE", DJANGO_ENV == "production"),
)
CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    env_bool("DJANGO_CSRF_COOKIE_SECURE", DJANGO_ENV == "production"),
)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0")))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False),
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", env_bool("DJANGO_SECURE_HSTS_PRELOAD", False))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_X_FORWARDED_HOST = True

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}

# ---------------------------------------------------------------------------
# Inter-service communication
# ---------------------------------------------------------------------------
SOUMISSIONS_SERVICE_URL = env_str("SOUMISSIONS_SERVICE_URL", "")
CONTRACTANT_SERVICE_URL = env_str("CONTRACTANT_SERVICE_URL", "")
ACTEURS_SERVICE_URL = env_str("ACTEURS_SERVICE_URL", "")
AUTH_SERVICE_URL = env_str("AUTH_SERVICE_URL", "")
DOCUMENTS_SERVICE_URL = env_str("DOCUMENTS_SERVICE_URL", "")
REMOTE_SERVICE_TIMEOUT = float(os.getenv("REMOTE_SERVICE_TIMEOUT", "3"))
