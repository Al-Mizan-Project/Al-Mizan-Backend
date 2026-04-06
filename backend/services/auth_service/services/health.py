from django.core.cache import cache
from django.db import connection


def check_readiness(prefix):
    db_ready = False
    cache_ready = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_ready = cursor.fetchone()[0] == 1
    except Exception:
        db_ready = False
    try:
        probe_key = f"{prefix}:ready"
        cache.set(probe_key, "1", timeout=5)
        cache_ready = cache.get(probe_key) == "1"
    except Exception:
        cache_ready = False
    return db_ready, cache_ready
