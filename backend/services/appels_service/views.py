from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AppelOffresCreateSerializer,
    AppelOffresSerializer,
    AppelOffresUpdateSerializer,
    DocumentsAppelSerializer,
)
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.appels import (
    appels_offres_queryset,
    get_appel_or_404,
    list_appel_documents,
    add_document_to_appel,
    remove_document_from_appel,
    action_publier,
    action_cloturer_depot,
    action_ouvrir_plis,
    action_annuler,
    appels_by_service_queryset,
)
from .services.health import check_readiness


# ── Health / Ready ────────────────────────────────────────────────────


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready, cache_ready = check_readiness("appels")
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ── Cache mixins ──────────────────────────────────────────────────────


class CachedListMixin:
    cache_namespace = ""

    def list(self, request, *args, **kwargs):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached(self.cache_namespace, "list", query_string)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, self.cache_namespace, "list", query_string)
        return response


class CachedRetrieveMixin:
    cache_namespace = ""

    def retrieve(self, request, *args, **kwargs):
        identifier = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field))
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached(self.cache_namespace, identifier, query_string)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, self.cache_namespace, identifier, query_string)
        return response


# ── Appels Offres ─────────────────────────────────────────────────────


class AppelOffresListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "appels-offres"

    def get_queryset(self):
        return appels_offres_queryset()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AppelOffresCreateSerializer
        return AppelOffresSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class AppelOffresRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "appels-offres"
    lookup_field = "id_appel_offres"
    lookup_url_kwarg = "appel_id"

    def get_queryset(self):
        return appels_offres_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AppelOffresUpdateSerializer
        return AppelOffresSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


# ── Appel workflow actions ────────────────────────────────────────────


class AppelOffresPublierView(APIView):
    def post(self, request, appel_id):
        appel = action_publier(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresCloturerDepotView(APIView):
    def post(self, request, appel_id):
        appel = action_cloturer_depot(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresOuvrirPlisView(APIView):
    def post(self, request, appel_id):
        appel = action_ouvrir_plis(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresAnnulerView(APIView):
    def post(self, request, appel_id):
        appel = action_annuler(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


# ── Appel documents ───────────────────────────────────────────────────


class AppelOffresDocumentsView(APIView):
    def get(self, request, appel_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("appel-documents", str(appel_id), query_string)
        if cached is not None:
            return Response(cached)
        documents = list_appel_documents(appel_id)
        payload = DocumentsAppelSerializer(documents, many=True).data
        write_cached(payload, "appel-documents", str(appel_id), query_string)
        return Response(payload)


class AppelOffresDocumentDetailView(APIView):
    def post(self, request, appel_id, document_id):
        add_document_to_appel(appel_id=appel_id, document_id=document_id)
        bump_cache_version()
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, appel_id, document_id):
        remove_document_from_appel(appel_id=appel_id, document_id=document_id)
        bump_cache_version()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Filter by service contractant ─────────────────────────────────────


class ServiceContractantAppelsView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "service-appels"
    serializer_class = AppelOffresSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return appels_by_service_queryset(self.kwargs["service_id"])

    def list(self, request, *args, **kwargs):
        query_string = request.META.get("QUERY_STRING", "")
        namespace = f"service-appels-{kwargs['service_id']}"
        cached = read_cached(namespace, "list", query_string)
        if cached is not None:
            return Response(cached)
        response = super(CachedListMixin, self).list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, namespace, "list", query_string)
        return response
