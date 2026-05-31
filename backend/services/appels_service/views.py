from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AchatSimpleCreateSerializer,
    AchatSimpleSerializer,
    AchatSimpleUpdateSerializer,
    AppelOffresCreateSerializer,
    AppelOffresSerializer,
    AppelOffresSuiviSerializer,
    AppelOffresUpdateSerializer,
    DocumentsAppelSerializer,
)
from .services.achats_simples import achats_simples_by_service_queryset, achats_simples_queryset
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.appels import (
    appels_offres_queryset,
    get_appel_or_404,
    list_appel_documents,
    add_document_to_appel,
    remove_document_from_appel,
    action_soumettre_validation,
    action_valider,
    action_refuser,
    action_publier,
    action_cloturer_depot,
    action_ouvrir_plis,
    action_annuler,
    appels_by_service_queryset,
    is_appel_watched_by_user,
    list_watched_appels_for_user,
    unwatch_appel_for_user,
    watch_appel_for_user,
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

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        statut = self.request.query_params.get("statut", "").strip() or None
        search = self.request.query_params.get("search", "").strip() or None
        service_id_raw = self.request.query_params.get("service_id")
        try:
            service_id = int(service_id_raw) if service_id_raw not in (None, "") else None
        except ValueError:
            service_id = None
        return appels_offres_queryset(
            statut=statut,
            service_id=service_id,
            search=search,
            request=self.request,
        )

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

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return appels_offres_queryset(request=self.request)

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


# ── Achats Simples ────────────────────────────────────────────────────


class AchatSimpleListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "achats-simples"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        statut = self.request.query_params.get("statut", "").strip() or None
        search = self.request.query_params.get("search", "").strip() or None
        service_id_raw = self.request.query_params.get("service_id")
        try:
            service_id = int(service_id_raw) if service_id_raw not in (None, "") else None
        except ValueError:
            service_id = None
        return achats_simples_queryset(statut=statut, service_id=service_id, search=search)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AchatSimpleCreateSerializer
        return AchatSimpleSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class AchatSimpleRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "achats-simples"
    lookup_field = "id_achat_simple"
    lookup_url_kwarg = "achat_id"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return achats_simples_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AchatSimpleUpdateSerializer
        return AchatSimpleSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


# ── Appel workflow actions ────────────────────────────────────────────
# These always require authentication


class AppelOffresPublierView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        appel = action_publier(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresCloturerDepotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        appel = action_cloturer_depot(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresOuvrirPlisView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        appel = action_ouvrir_plis(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresAnnulerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        appel = action_annuler(appel_id)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


# ── Validation workflow actions ───────────────────────────────────────


def _resolve_validated_by(request):
    membre_id = getattr(request.user, "id_membre", None)
    if membre_id:
        return str(membre_id)
    return request.data.get("validated_by")


class AppelOffresSoumettreValidationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        validated_by = _resolve_validated_by(request)
        appel = action_soumettre_validation(appel_id, validated_by=validated_by)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresValiderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        validated_by = _resolve_validated_by(request)
        appel = action_valider(appel_id, validated_by=validated_by)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


class AppelOffresRefuserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id):
        validated_by = _resolve_validated_by(request)
        appel = action_refuser(appel_id, validated_by=validated_by)
        bump_cache_version()
        return Response(AppelOffresSerializer(appel).data)


# ── Appel documents ───────────────────────────────────────────────────


class AppelOffresDocumentsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

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
    permission_classes = [IsAuthenticated]

    def post(self, request, appel_id, document_id):
        add_document_to_appel(appel_id=appel_id, document_id=document_id)
        bump_cache_version()
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, appel_id, document_id):
        remove_document_from_appel(appel_id=appel_id, document_id=document_id)
        bump_cache_version()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Filter by service contractant ────────────────────────────────────


class ServiceContractantAppelsView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "service-appels"
    serializer_class = AppelOffresSerializer
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

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


class ServiceContractantAchatsSimplesView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "service-achats-simples"
    serializer_class = AchatSimpleSerializer
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return achats_simples_by_service_queryset(self.kwargs["service_id"])

    def list(self, request, *args, **kwargs):
        query_string = request.META.get("QUERY_STRING", "")
        namespace = f"service-achats-simples-{kwargs['service_id']}"
        cached = read_cached(namespace, "list", query_string)
        if cached is not None:
            return Response(cached)
        response = super(CachedListMixin, self).list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, namespace, "list", query_string)
        return response


# ── User watched appels ───────────────────────────────────────────────


def _assert_user_scope(request, user_id):
    auth_user_id = getattr(request.user, "id_utilisateur", None)
    if auth_user_id is not None and int(auth_user_id) != int(user_id):
        raise PermissionDenied("Cannot access another user's watched appels")


class UserWatchedAppelsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        _assert_user_scope(request, user_id)
        watched = list_watched_appels_for_user(user_id)
        payload = AppelOffresSuiviSerializer(watched, many=True).data
        return Response(payload)


class UserWatchedAppelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, appel_id):
        _assert_user_scope(request, user_id)
        watched = is_appel_watched_by_user(appel_id=appel_id, user_id=user_id)
        return Response({"is_watched": watched})

    def post(self, request, user_id, appel_id):
        _assert_user_scope(request, user_id)
        watched_link, created = watch_appel_for_user(appel_id=appel_id, user_id=user_id)
        bump_cache_version()
        payload = AppelOffresSuiviSerializer(watched_link).data
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(payload, status=status_code)

    def delete(self, request, user_id, appel_id):
        _assert_user_scope(request, user_id)
        unwatch_appel_for_user(appel_id=appel_id, user_id=user_id)
        bump_cache_version()
        return Response(status=status.HTTP_204_NO_CONTENT)