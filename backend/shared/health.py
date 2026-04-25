from django.core.cache import cache
from django.db import connections
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _check_database(alias):
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


def _check_cache():
    try:
        key = "__almizan_health__"
        cache.set(key, "ok", timeout=5)
        return cache.get(key) == "ok"
    except Exception:
        return False


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_status = {alias: _check_database(alias) for alias in connections}
        cache_ready = _check_cache()
        ready = all(db_status.values()) and cache_ready
        payload = {
            "status": "ready" if ready else "not_ready",
            "databases": db_status,
            "cache": cache_ready,
        }
        return Response(payload, status=200 if ready else 503)
