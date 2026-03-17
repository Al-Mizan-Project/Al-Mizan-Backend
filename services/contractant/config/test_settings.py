"""
Test-specific settings.
Connects directly to PostgreSQL instead of PgBouncer because Django's
test runner uses SERIALIZABLE transactions that PgBouncer (transaction
pool mode) does not support.

Usage:
    python manage.py test --settings=config.test_settings
"""
from .settings import *  # noqa: F401, F403
import os

# Point directly at Postgres, bypassing PgBouncer
DATABASES["default"].update(  # noqa: F405
    {
        "HOST": os.getenv("TEST_DB_HOST", os.getenv("DB_HOST_DIRECT", "contractant_db")),
        "PORT": os.getenv("TEST_DB_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": False,  # OK for direct Postgres connection
    }
)

# Disable throttling during tests
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405

# Use a separate Redis DB index during tests to avoid polluting prod cache
CACHES["default"]["LOCATION"] = REDIS_URL.replace("/1", "/15") if REDIS_URL.endswith("/1") else REDIS_URL  # noqa: F405, F821
