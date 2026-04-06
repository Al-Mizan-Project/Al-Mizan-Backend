from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import ActeursServicePermission
from .serializers import (
    MembreSerializer,
    OperateurEconomiqueSerializer,
    OrganisationSerializer,
    ServiceContractantSerializer,
    TutelleSerializer,
)
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.health import check_readiness
from .services.membres import membres_queryset
from .services.operateurs import get_operateur_by_nif_or_404, operateurs_queryset
from .services.organisations import (
    delete_organisation,
    organisation_membres_queryset,
    organisations_queryset,
    service_contractant_membres_queryset,
    service_contractants_queryset,
)
from .services.tutelles import tutelles_queryset


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


class WriteScopedThrottleMixin:
    write_throttle_scope = ""

    def get_throttles(self):
        original_scope = getattr(self, "throttle_scope", None)
        if self.request.method in {"POST", "PUT", "PATCH", "DELETE"} and self.write_throttle_scope:
            self.throttle_scope = self.write_throttle_scope
        else:
            self.throttle_scope = None
        throttles = super().get_throttles()
        self.throttle_scope = original_scope
        return throttles


class CachedListMixin:
    cache_namespace = ""

    def get_list_cache_identifier(self):
        return "list"

    def list(self, request, *args, **kwargs):
        identifier = self.get_list_cache_identifier()
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached(self.cache_namespace, identifier, query_string)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            write_cached(response.data, self.cache_namespace, identifier, query_string)
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


class OrganisationListCreateView(WriteScopedThrottleMixin, CachedListMixin, ListCreateAPIView):
    cache_namespace = "organisations"
    serializer_class = OrganisationSerializer
    write_throttle_scope = "organisations_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("organisations.read",),
        "POST": ("organisations.write",),
    }

    def get_queryset(self):
        return organisations_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class OrganisationRetrieveUpdateDeleteView(WriteScopedThrottleMixin, CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "organisations"
    serializer_class = OrganisationSerializer
    lookup_field = "id_organisation"
    lookup_url_kwarg = "organisation_id"
    write_throttle_scope = "organisations_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("organisations.read",),
        "PATCH": ("organisations.write",),
        "PUT": ("organisations.write",),
        "DELETE": ("organisations.write",),
    }

    def get_queryset(self):
        return organisations_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        delete_organisation(instance.id_organisation)
        bump_cache_version()


class OrganisationMembresView(CachedListMixin, ListAPIView):
    cache_namespace = "organisations-membres"
    serializer_class = MembreSerializer
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("membres.read",),
    }

    def get_queryset(self):
        return organisation_membres_queryset(self.kwargs["organisation_id"])

    def get_list_cache_identifier(self):
        return str(self.kwargs["organisation_id"])


class ServiceContractantListCreateView(WriteScopedThrottleMixin, CachedListMixin, ListCreateAPIView):
    cache_namespace = "services-contractants"
    serializer_class = ServiceContractantSerializer
    write_throttle_scope = "organisations_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("organisations.read",),
        "POST": ("organisations.write",),
    }

    def get_queryset(self):
        return service_contractants_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class ServiceContractantRetrieveUpdateDeleteView(
    WriteScopedThrottleMixin,
    CachedRetrieveMixin,
    RetrieveUpdateDestroyAPIView,
):
    cache_namespace = "services-contractants"
    serializer_class = ServiceContractantSerializer
    lookup_field = "id_organisation"
    lookup_url_kwarg = "service_id"
    write_throttle_scope = "organisations_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("organisations.read",),
        "PATCH": ("organisations.write",),
        "PUT": ("organisations.write",),
        "DELETE": ("organisations.write",),
    }

    def get_queryset(self):
        return service_contractants_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        delete_organisation(instance.id_organisation)
        bump_cache_version()


class ServiceContractantMembresView(CachedListMixin, ListAPIView):
    cache_namespace = "services-contractants-membres"
    serializer_class = MembreSerializer
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("membres.read",),
    }

    def get_queryset(self):
        return service_contractant_membres_queryset(self.kwargs["service_id"])

    def get_list_cache_identifier(self):
        return str(self.kwargs["service_id"])


class OperateurEconomiqueListCreateView(WriteScopedThrottleMixin, CachedListMixin, ListCreateAPIView):
    cache_namespace = "operateurs-economiques"
    serializer_class = OperateurEconomiqueSerializer
    write_throttle_scope = "operateurs_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("operateurs.read",),
        "POST": ("operateurs.write",),
    }

    def get_queryset(self):
        return operateurs_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class OperateurEconomiqueRetrieveUpdateDeleteView(
    WriteScopedThrottleMixin,
    CachedRetrieveMixin,
    RetrieveUpdateDestroyAPIView,
):
    cache_namespace = "operateurs-economiques"
    serializer_class = OperateurEconomiqueSerializer
    lookup_field = "id_operateur_economique"
    lookup_url_kwarg = "operateur_id"
    write_throttle_scope = "operateurs_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("operateurs.read",),
        "PATCH": ("operateurs.write",),
        "PUT": ("operateurs.write",),
        "DELETE": ("operateurs.write",),
    }

    def get_queryset(self):
        return operateurs_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class OperateurEconomiqueByNifView(APIView):
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("operateurs.read",),
    }

    def get(self, request, nif):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("operateurs-economiques-by-nif", nif, query_string)
        if cached is not None:
            return Response(cached)
        payload = OperateurEconomiqueSerializer(get_operateur_by_nif_or_404(nif)).data
        write_cached(payload, "operateurs-economiques-by-nif", nif, query_string)
        return Response(payload)


class MembreListCreateView(WriteScopedThrottleMixin, CachedListMixin, ListCreateAPIView):
    cache_namespace = "membres"
    serializer_class = MembreSerializer
    write_throttle_scope = "membres_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("membres.read",),
        "POST": ("membres.write",),
    }

    def get_queryset(self):
        return membres_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class MembreRetrieveUpdateDeleteView(WriteScopedThrottleMixin, CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "membres"
    serializer_class = MembreSerializer
    lookup_field = "id_membre"
    lookup_url_kwarg = "membre_id"
    write_throttle_scope = "membres_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("membres.read",),
        "PATCH": ("membres.write",),
        "PUT": ("membres.write",),
        "DELETE": ("membres.write",),
    }

    def get_queryset(self):
        return membres_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class TutelleListCreateView(WriteScopedThrottleMixin, CachedListMixin, ListCreateAPIView):
    cache_namespace = "tutelles"
    serializer_class = TutelleSerializer
    write_throttle_scope = "tutelles_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("tutelles.read",),
        "POST": ("tutelles.write",),
    }

    def get_queryset(self):
        return tutelles_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class TutelleRetrieveUpdateDeleteView(WriteScopedThrottleMixin, CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "tutelles"
    serializer_class = TutelleSerializer
    lookup_field = "id_tutelle"
    lookup_url_kwarg = "tutelle_id"
    write_throttle_scope = "tutelles_write"
    permission_classes = [ActeursServicePermission]
    required_permissions = {
        "GET": ("tutelles.read",),
        "PATCH": ("tutelles.write",),
        "PUT": ("tutelles.write",),
        "DELETE": ("tutelles.write",),
    }

    def get_queryset(self):
        return tutelles_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()
