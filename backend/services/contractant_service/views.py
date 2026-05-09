from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    CommissionEvaluationCreateSerializer,
    CommissionEvaluationSerializer,
    CommissionEvaluationUpdateSerializer,
    CommissionExterneSerializer,
    CommissionInterneCreateSerializer,
    CommissionInterneSerializer,
    CommissionInterneUpdateSerializer,
    MembresCommissionEvaluationSerializer,
    MembresCommissionInterneSerializer,
    MembresCommissionExterneSerializer,
    ServiceContractantCreateSerializer,
    ServiceContractantSerializer,
    ServiceContractantUpdateSerializer,
)
from .models import MembresCommissionEvaluation, MembresCommissionInterne, MembresCommissionExterne
from .services.cache import bump_cache_version, read_cached, write_cached
from .services.commissions import (
    add_membre_to_commission_eval,
    add_membre_to_commission_interne,
    commissions_evaluation_queryset,
    commissions_externes_queryset,
    commissions_internes_queryset,
    list_commission_eval_membres,
    list_commission_interne_membres,
    list_service_commissions,
    remove_membre_from_commission_eval,
    remove_membre_from_commission_interne,
)
from .services.health import check_readiness
from .services.services_contractants import (
    list_service_membre_ids,
    services_contractants_queryset,
)


# ── Health / Ready ───────────────────────────────────────────────────


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready, cache_ready = check_readiness("contractant")
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ── Cache mixins ─────────────────────────────────────────────────────


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


# ── Commission Evaluation ────────────────────────────────────────────


class CommissionEvaluationListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "commissions-evaluation"

    def get_queryset(self):
        return commissions_evaluation_queryset()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommissionEvaluationCreateSerializer
        return CommissionEvaluationSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class CommissionEvaluationRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "commissions-evaluation"
    lookup_field = "id_comission"
    lookup_url_kwarg = "commission_id"

    def get_queryset(self):
        return commissions_evaluation_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return CommissionEvaluationUpdateSerializer
        return CommissionEvaluationSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class CommissionEvaluationMembresView(APIView):
    def get(self, request, commission_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("commission-eval-membres", str(commission_id), query_string)
        if cached is not None:
            return Response(cached)
        membres = list_commission_eval_membres(commission_id)
        payload = MembresCommissionEvaluationSerializer(membres, many=True).data
        write_cached(payload, "commission-eval-membres", str(commission_id), query_string)
        return Response(payload)


class CommissionEvaluationMembreDetailView(APIView):
    def post(self, request, commission_id, membre_id):
        add_membre_to_commission_eval(commission_id=commission_id, membre_id=membre_id)
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, commission_id, membre_id):
        remove_membre_from_commission_eval(commission_id=commission_id, membre_id=membre_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Commission Interne ───────────────────────────────────────────────


class CommissionInterneListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "commissions-internes"

    def get_queryset(self):
        return commissions_internes_queryset()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommissionInterneCreateSerializer
        return CommissionInterneSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class CommissionInterneRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "commissions-internes"
    lookup_field = "id_comission_interne"
    lookup_url_kwarg = "commission_interne_id"

    def get_queryset(self):
        return commissions_internes_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return CommissionInterneUpdateSerializer
        return CommissionInterneSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class CommissionInterneMembresView(APIView):
    def get(self, request, commission_interne_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("commission-interne-membres", str(commission_interne_id), query_string)
        if cached is not None:
            return Response(cached)
        membres = list_commission_interne_membres(commission_interne_id)
        payload = MembresCommissionInterneSerializer(membres, many=True).data
        write_cached(payload, "commission-interne-membres", str(commission_interne_id), query_string)
        return Response(payload)


class CommissionInterneMembreDetailView(APIView):
    def post(self, request, commission_interne_id, membre_id):
        add_membre_to_commission_interne(commission_interne_id=commission_interne_id, membre_id=membre_id)
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request, commission_interne_id, membre_id):
        remove_membre_from_commission_interne(commission_interne_id=commission_interne_id, membre_id=membre_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommissionExterneMembresView(APIView):
    def get(self, request, commission_externe_id):
        membres = MembresCommissionExterne.objects.filter(id_comission_externe=commission_externe_id)
        payload = MembresCommissionExterneSerializer(membres, many=True).data
        return Response(payload)


# ── Service Contractant ──────────────────────────────────────────────


class ServiceContractantListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "services-contractants"

    def get_queryset(self):
        return services_contractants_queryset()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ServiceContractantCreateSerializer
        return ServiceContractantSerializer

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class ServiceContractantRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "services-contractants"
    lookup_field = "id_service"
    lookup_url_kwarg = "service_id"

    def get_queryset(self):
        return services_contractants_queryset()

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ServiceContractantUpdateSerializer
        return ServiceContractantSerializer

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class ServiceContractantMembresView(APIView):
    def get(self, request, service_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("service-membres", str(service_id), query_string)
        if cached is not None:
            return Response(cached)
        membre_ids = list_service_membre_ids(service_id)
        payload = [{"id_membre": mid} for mid in membre_ids]
        write_cached(payload, "service-membres", str(service_id), query_string)
        return Response(payload)


class ServiceContractantCommissionsView(APIView):
    def get(self, request, service_id):
        query_string = request.META.get("QUERY_STRING", "")
        cached = read_cached("service-commissions", str(service_id), query_string)
        if cached is not None:
            return Response(cached)
        payload = list_service_commissions(service_id)
        write_cached(payload, "service-commissions", str(service_id), query_string)
        return Response(payload)


# ── Commission Externe ───────────────────────────────────────────────


class CommissionExterneListCreateView(CachedListMixin, ListCreateAPIView):
    cache_namespace = "commissions-externes"
    serializer_class = CommissionExterneSerializer

    def get_queryset(self):
        return commissions_externes_queryset()

    def perform_create(self, serializer):
        serializer.save()
        bump_cache_version()


class CommissionExterneRetrieveUpdateDeleteView(CachedRetrieveMixin, RetrieveUpdateDestroyAPIView):
    cache_namespace = "commissions-externes"
    serializer_class = CommissionExterneSerializer
    lookup_field = "id_comission_externe"
    lookup_url_kwarg = "commission_externe_id"

    def get_queryset(self):
        return commissions_externes_queryset()

    def perform_update(self, serializer):
        serializer.save()
        bump_cache_version()

    def perform_destroy(self, instance):
        instance.delete()
        bump_cache_version()


class CommissionExterneCompetenteView(APIView):
    """
    GET /commissions-externes/competente/<int:appel_id>
    """
    def get(self, request, appel_id):
        from .services.commissions import get_commission_externe_competente
        ce = get_commission_externe_competente(appel_id)
        if ce:
            return Response(CommissionExterneSerializer(ce).data)
        return Response({"id_comission_externe": None}, status=status.HTTP_200_OK)


class MyServiceView(APIView):
    """
    GET /my-service
    Returns the id_service for the currently logged-in user.
    """
    def get(self, request):
        user = request.user

        # --- ADDITION: support internal calls with user_id param ---
        user_id_param = request.query_params.get("user_id")
        if user_id_param and not user.is_authenticated:
            from auth_service.models import Utilisateur
            try:
                user = Utilisateur.objects.get(id_utilisateur=int(user_id_param))
            except (Utilisateur.DoesNotExist, ValueError, TypeError):
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        # --- END ADDITION ---

        if not user or not hasattr(user, 'id_membre') or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert UUID to int (last segment hex)
        try:
            id_membre_int = int(str(user.id_membre).split('-')[-1], 16)
        except (ValueError, IndexError):
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)

        # Look in Evaluation Commissions
        m_eval = MembresCommissionEvaluation.objects.filter(id_membre=id_membre_int).first()
        if m_eval:
            return Response({"id_service": m_eval.id_comission.id_service_id})

        # Look in Internal Commissions
        m_int = MembresCommissionInterne.objects.filter(id_membre=id_membre_int).first()
        if m_int:
            return Response({"id_service": m_int.id_commision_interne.id_service_id})

        return Response({"error": "Service not found for this member"}, status=status.HTTP_404_NOT_FOUND)
