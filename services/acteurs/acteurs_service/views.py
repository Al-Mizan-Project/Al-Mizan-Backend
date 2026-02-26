from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import MembreSerializer
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.health import check_readiness
from .services.membres import membres_queryset


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready, cache_ready = check_readiness("acteurs")
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class MembreCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = MembreSerializer
    throttle_scope = "membres_write"

    def get_queryset(self):
        return membres_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class MembreRetrieveView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = MembreSerializer
    lookup_field = "id_membre"
    lookup_url_kwarg = "membre_id"

    def get_queryset(self):
        return membres_queryset()

    def retrieve(self, request, *args, **kwargs):
        identifier = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field))
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("membres", identifier, query_string)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, "membres", identifier, query_string)
        return response
