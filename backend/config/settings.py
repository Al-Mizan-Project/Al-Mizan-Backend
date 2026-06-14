import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent
SERVICES_DIR = BASE_DIR / "services"

for path in (BASE_DIR, SERVICES_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def env_str(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def env_float(name, default=0.0):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value.strip())


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DJANGO_ENV = env_str("DJANGO_ENV", "development").lower()
DEBUG = env_bool("DEBUG", DJANGO_ENV != "production")
SECRET_KEY = env_str("SECRET_KEY", "unsafe-dev-secret")
PORT = env_str("PORT", "8000")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,backend,nginx,*")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "django_filters",
    "auth_service",
    "acteurs_service",
    "appels_service",
    "contractant_service",
    "contrats_service",
    "documents_service",
    "evaluations_service",
    "ia_service",
    "notifications_service",
    "soumissions_app",
    "apps.common",
    "apps.documents",
    "apps.integrations",
    "apps.recours",
    "common.apps.AuditCommonConfig",
    "ledger",
    "readstore",
    "integrity",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _build_database(default_name):
    database_url = env_str("DATABASE_URL", "")
    conn_max_age = env_int("CONN_MAX_AGE", 120)
    if database_url:
        database = dj_database_url.parse(
            database_url,
            conn_max_age=conn_max_age,
            ssl_require=env_bool("DB_SSL_REQUIRE", False),
        )
    else:
        database = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", default_name),
            "USER": env_str("DB_USER", "almizan_user"),
            "PASSWORD": env_str("DB_PASSWORD", "almizan_password"),
            "HOST": env_str("DB_HOST", "postgres"),
            "PORT": env_str("DB_PORT", "5432"),
            "CONN_MAX_AGE": conn_max_age,
        }
    database["CONN_MAX_AGE"] = conn_max_age
    database["CONN_HEALTH_CHECKS"] = env_bool("DB_CONN_HEALTH_CHECKS", True)
    database["DISABLE_SERVER_SIDE_CURSORS"] = True
    return database


def _clone_database(base, name, user, password, host, port):
    cloned = dict(base)
    cloned["NAME"] = name
    cloned["USER"] = user
    cloned["PASSWORD"] = password
    cloned["HOST"] = host
    cloned["PORT"] = port
    return cloned


DEFAULT_DB_NAME = env_str("DB_NAME", "almizan_db")
default_db = _build_database(DEFAULT_DB_NAME)

DATABASES = {
    "default": default_db,
    "ledger": _clone_database(
        default_db,
        env_str("DB_LEDGER_NAME", DEFAULT_DB_NAME),
        env_str("DB_LEDGER_USER", env_str("DB_USER", "almizan_user")),
        env_str("DB_LEDGER_PASSWORD", env_str("DB_PASSWORD", "almizan_password")),
        env_str("DB_LEDGER_HOST", env_str("DB_HOST", "postgres")),
        env_str("DB_LEDGER_PORT", env_str("DB_PORT", "5432")),
    ),
    "read": _clone_database(
        default_db,
        env_str("DB_READ_NAME", DEFAULT_DB_NAME),
        env_str("DB_READ_USER", env_str("DB_USER", "almizan_user")),
        env_str("DB_READ_PASSWORD", env_str("DB_PASSWORD", "almizan_password")),
        env_str("DB_READ_HOST", env_str("DB_HOST", "postgres")),
        env_str("DB_READ_PORT", env_str("DB_PORT", "5432")),
    ),
}

DATABASE_ROUTERS = ["common.db_router.AuditDatabaseRouter"]
AUTH_USER_MODEL = "auth_service.Utilisateur"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env_str("LANGUAGE_CODE", "en-us")
TIME_ZONE = env_str("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APPEND_SLASH = False

IS_TEST_RUN = "test" in sys.argv or "pytest" in " ".join(sys.argv)
REDIS_URL = env_str("REDIS_URL", "redis://:almizan_redis_password@redis:6379/0")
CACHE_TTL = env_int("CACHE_TTL", 60)

if IS_TEST_RUN:
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
            "TIMEOUT": CACHE_TTL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": env_int("REDIS_MAX_CONNECTIONS", 200),
                    "retry_on_timeout": True,
                },
            },
        }
    }

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = env_bool("CELERY_TASK_EAGER_PROPAGATES", False)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "shared.permissions.AuthenticatedOrInternalServicePermission",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "shared.exceptions.custom_exception_handler",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("THROTTLE_ANON_RATE", "240/minute"),
        "user": env_str("THROTTLE_USER_RATE", "1200/minute"),
        "auth_login": env_str("THROTTLE_AUTH_LOGIN_RATE", "20/minute"),
        "auth_password_reset": env_str("THROTTLE_AUTH_PASSWORD_RESET_RATE", "20/minute"),
        "organisations_write": env_str("THROTTLE_ORGANISATIONS_WRITE_RATE", "120/minute"),
        "operateurs_write": env_str("THROTTLE_OPERATEURS_WRITE_RATE", "120/minute"),
        "membres_write": env_str("THROTTLE_MEMBRES_WRITE_RATE", "120/minute"),
        "tutelles_write": env_str("THROTTLE_TUTELLES_WRITE_RATE", "120/minute"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Al-Mizan Backend API",
    "VERSION": "1.0.0",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("ACCESS_TOKEN_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("REFRESH_TOKEN_DAYS", 7)),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env_str("JWT_SIGNING_KEY", SECRET_KEY),
    "USER_ID_FIELD": "id_utilisateur",
    "USER_ID_CLAIM": "user_id",
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", DJANGO_ENV == "production")
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", DJANGO_ENV == "production")
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_X_FORWARDED_HOST = True
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)

LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
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

INTERNAL_BASE_URL = env_str("INTERNAL_BASE_URL", f"http://127.0.0.1:{PORT}")
FRONTEND_BASE_URL = env_str("FRONTEND_BASE_URL", "http://localhost:3000")
FRONTEND_LOGIN_URL = env_str("FRONTEND_LOGIN_URL", f"{FRONTEND_BASE_URL.rstrip('/')}/login")
FRONTEND_PASSWORD_RESET_URL = env_str(
    "FRONTEND_PASSWORD_RESET_URL",
    f"{FRONTEND_BASE_URL.rstrip('/')}/reset-password",
)
ACCOUNT_ACTIVATION_TTL = env_int("ACCOUNT_ACTIVATION_TTL", 86400)
ACCOUNT_ACTIVATION_URL = env_str("ACCOUNT_ACTIVATION_URL", f"{INTERNAL_BASE_URL.rstrip('/')}/auth/activate")
PASSWORD_RESET_TOKEN_TTL = env_int("PASSWORD_RESET_TOKEN_TTL", 900)
REMOTE_SERVICE_TIMEOUT = env_float("REMOTE_SERVICE_TIMEOUT", 30.0)
INTERNAL_SERVICE_TOKEN = env_str("INTERNAL_SERVICE_TOKEN", "dev-internal-token")

MEMBRES_SERVICE_URL = env_str("MEMBRES_SERVICE_URL", INTERNAL_BASE_URL)
MEMBRES_SERVICE_TIMEOUT = env_float("MEMBRES_SERVICE_TIMEOUT", REMOTE_SERVICE_TIMEOUT)

ACTEURS_SERVICE_URL = env_str("ACTEURS_SERVICE_URL", INTERNAL_BASE_URL)
ACTEURS_SERVICE_TIMEOUT = env_float("ACTEURS_SERVICE_TIMEOUT", REMOTE_SERVICE_TIMEOUT)

CONTRACTANT_SERVICE_URL = env_str("CONTRACTANT_SERVICE_URL", INTERNAL_BASE_URL)
CONTRACTANT_SERVICE_TIMEOUT = env_float("CONTRACTANT_SERVICE_TIMEOUT", REMOTE_SERVICE_TIMEOUT)

APPELS_SERVICE_URL = env_str("APPELS_SERVICE_URL", INTERNAL_BASE_URL)
DOCUMENTS_SERVICE_URL = env_str("DOCUMENTS_SERVICE_URL", INTERNAL_BASE_URL)
DOCUMENTS_SERVICE_TIMEOUT = env_float("DOCUMENTS_SERVICE_TIMEOUT", REMOTE_SERVICE_TIMEOUT)
EVALUATIONS_SERVICE_URL = env_str("EVALUATIONS_SERVICE_URL", INTERNAL_BASE_URL)
SOUMISSIONS_SERVICE_URL = env_str("SOUMISSIONS_SERVICE_URL", INTERNAL_BASE_URL)
CONTRATS_SERVICE_URL = env_str("CONTRATS_SERVICE_URL", INTERNAL_BASE_URL)
AUTH_SERVICE_URL = env_str("AUTH_SERVICE_URL", INTERNAL_BASE_URL)
AUDIT_SERVICE_URL = env_str("AUDIT_SERVICE_URL", INTERNAL_BASE_URL)
NOTIFICATIONS_SERVICE_URL = env_str("NOTIFICATIONS_SERVICE_URL", INTERNAL_BASE_URL)

MINIO_URL = env_str("MINIO_URL", "http://minio:9000")
MINIO_ACCESS_KEY = env_str("MINIO_ACCESS_KEY", "admin_almizan")
MINIO_SECRET_KEY = env_str("MINIO_SECRET_KEY", "SecurePassword123!")
MINIO_BUCKET_NAME = env_str("MINIO_BUCKET_NAME", "almizan-documents")

MAX_OCR_FILE_SIZE = env_int("MAX_OCR_FILE_SIZE", 20 * 1024 * 1024)
OCR_MAX_WORKERS = env_int("OCR_MAX_WORKERS", 4)


GROQ_API_KEY = env_str("GROQ_API_KEY", "")
GROQ_MODEL = env_str("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MAX_TOKENS = env_int("GROQ_MAX_TOKENS", 2000)
GROQ_MAX_RETRIES = env_int("GROQ_MAX_RETRIES", 3)
GROQ_RETRY_BASE_DELAY = env_float("GROQ_RETRY_BASE_DELAY", 5.0)

EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "no-reply@almizan.local")
EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
