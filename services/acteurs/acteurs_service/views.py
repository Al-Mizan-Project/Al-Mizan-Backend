from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Membre
from .serializers import MembreSerializer


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready = False
        cache_ready = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_ready = cursor.fetchone()[0] == 1
        except Exception:
            db_ready = False
        try:
            probe_key = "acteurs:ready"
            cache.set(probe_key, "1", timeout=5)
            cache_ready = cache.get(probe_key) == "1"
        except Exception:
            cache_ready = False
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response({"status": "not_ready", "database": db_ready, "cache": cache_ready}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class MembreCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    queryset = Membre.objects.all()
    serializer_class = MembreSerializer


class MembreRetrieveView(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Membre.objects.all()
    serializer_class = MembreSerializer
    lookup_field = "id_membre"
    lookup_url_kwarg = "membre_id"
