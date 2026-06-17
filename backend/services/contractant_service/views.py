from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from django.conf import settings
from django.db import transaction

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
from .models import MembresCommissionEvaluation, MembresCommissionInterne, MembresCommissionExterne, CommissionInterne, CommissionExterne
from auth_service.models import Utilisateur
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

MARCHE_VALIDATOR_ROLE_NAMES = {
    "VALIDATEUR_INTERNE_MARCHE",
    "VALIDATEUR_EXTERNE_MARCHE",
}

CDC_VALIDATOR_ROLE_NAMES = {
    "VALIDATEUR_INTERNE_CDC",
    "VALIDATEUR_EXTERNE_CDC",
}


def commission_member_key(user):
    return getattr(user, "id_utilisateur", None)


def filter_members_by_validator_roles(queryset):
    # Commission-members should only return march validators for AffectationSoumission
    member_ids = queryset.values_list("id_membre", flat=True)
    valid_user_ids = Utilisateur.objects.filter(
        id_utilisateur__in=member_ids,
        id_role__nom_role__in=MARCHE_VALIDATOR_ROLE_NAMES,
    ).values_list("id_utilisateur", flat=True)
    return queryset.filter(id_membre__in=valid_user_ids)


def filter_members_by_cdc_validator_roles(queryset):
    member_ids = queryset.values_list("id_membre", flat=True)
    valid_user_ids = Utilisateur.objects.filter(
        id_utilisateur__in=member_ids,
        id_role__nom_role__in=CDC_VALIDATOR_ROLE_NAMES,
    ).values_list("id_utilisateur", flat=True)
    return queryset.filter(id_membre__in=valid_user_ids)


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

class ServiceContractantMyCommissionMembersView(APIView):
    def get(self, request, service_id):
        user = request.user
        if not user or not hasattr(user, "id_membre") or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)

        role_name = getattr(getattr(user, "id_role", None), "nom_role", "")
        role_name = str(role_name).strip().upper()

        membre_id = user.id_membre
        member_key = commission_member_key(user)
        if membre_id is None:
            return Response({"error": "Invalid member ID"}, status=status.HTTP_400_BAD_REQUEST)

        if role_name == "RESP_CM":
            external_link = MembresCommissionExterne.objects.filter(id_membre=member_key).first()
            if not external_link:
                return Response([], status=status.HTTP_200_OK)

            membres = MembresCommissionExterne.objects.filter(
                id_comission_externe=external_link.id_comission_externe_id
            )
            membres = filter_members_by_validator_roles(membres)
            payload = MembresCommissionExterneSerializer(membres, many=True).data
            return Response(payload)

        if role_name == "RESP_VALID_INTERN":
            internal_link = MembresCommissionInterne.objects.filter(
                id_membre=member_key,
                id_commision_interne__id_service_id=service_id,
            ).first()
            if not internal_link:
                return Response([], status=status.HTTP_200_OK)

            membres = MembresCommissionInterne.objects.filter(id_commision_interne__id_service_id=service_id)
            membres = filter_members_by_validator_roles(membres)
            payload = MembresCommissionInterneSerializer(membres, many=True).data
            return Response(payload)

        return Response({"error": "User role is not supported for this endpoint"}, status=status.HTTP_403_FORBIDDEN)


class UserCommissionView(APIView):
    """
    GET /my-commission
    Returns the commission details for the currently logged-in user.
    Uses id_role to determine which commission table to query (internal or external).
    """
    def get(self, request):
        user = request.user
        
        if not user or not hasattr(user, 'id_membre') or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not hasattr(user, 'id_role') or not user.id_role:
            return Response({"error": "User has no role"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get role name
        role_name = getattr(user.id_role, 'nom_role', '').strip().upper()
        
        id_membre_value = user.id_membre
        member_key = commission_member_key(user)
        if not id_membre_value:
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)
        
        # For internal validators (RESP_VALID_INTERN)
        if role_name == "RESP_VALID_INTERN":
            member_link = MembresCommissionInterne.objects.select_related('id_commision_interne__id_service').filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response(
                    {"error": "User is not linked to any internal commission"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            service = member_link.id_commision_interne.id_service
            commissions = CommissionInterne.objects.filter(id_service=service)
            
            return Response({
                "commission_type": "interne",
                "id_service": service.id_service,
                "commissions": [
                    {
                        "id_commission": c.id_comission_interne,
                        "nom_commission": c.nom_comission,
                        "type_commission": c.type_comission,
                    }
                    for c in commissions
                ]
            })
        
        # For external validators (RESP_CM)
        elif role_name == "RESP_CM":
            member_link = MembresCommissionExterne.objects.select_related('id_comission_externe').filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response(
                    {"error": "User is not linked to any external commission"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            commission = member_link.id_comission_externe
            
            return Response({
                "commission_type": "externe",
                "id_commission_externe": str(commission.id_comission_externe),
                "id_commission": str(commission.id_comission_externe),  # Backward compatibility
                "nom_commission": commission.nom_comission,
                "niveau_competance": commission.niveau_competance,
                "seuils_competence_financiere": commission.seuils_competence_financiere,
            })
        
        return Response(
            {"error": "User role is not supported for this endpoint"},
            status=status.HTTP_403_FORBIDDEN
        )

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
        
        id_membre_value = user.id_membre
        member_key = commission_member_key(user)
        if not id_membre_value:
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"id_membre": str(id_membre_value)}
        member_key = commission_member_key(user)

        # Resolve the organisation from the acteurs Membre record.
        try:
            from acteurs_service.models import Membre
            membre = Membre.objects.filter(id_membre=id_membre_value).select_related("organisation").first()
            if membre and membre.organisation_id:
                payload["id_organisation"] = str(membre.organisation_id)
        except Exception:
            pass

        # Resolve the numeric service id from commission membership.
        m_eval = MembresCommissionEvaluation.objects.filter(id_membre=member_key).first()
        if m_eval:
            payload["id_service"] = m_eval.id_comission.id_service_id
            return Response(payload)

        m_int = MembresCommissionInterne.objects.filter(id_membre=member_key).first()
        if m_int:
            payload["id_service"] = m_int.id_commision_interne.id_service_id

        return Response(payload)


class ValidatorsForCurrentUserView(APIView):
    """
    GET /commission-members
    
    Returns all members/validators for the commission/service of the currently logged-in user.
    Only marche validators are included for this endpoint.
    
    Logic:
    1. Get current user's id_membre and id_role
    2. If role is RESP_CM:
       - Look up in Membres_Commission_Externe using id_membre
       - Get the id_commission_externe
       - Return all marche validator members with the same id_commission_externe
    3. If role is RESP_VALID_INTERN:
       - Look up in Membres_Commission_interne using id_membre
       - Get the id_service
       - Return all marche validator members with the same id_service
    
    Response format:
    {
        "commission_type": "externe" | "interne",
        "members": [
            {
                "id_membre": int,
                "id_commission_externe": int (for externe) | null,
                "id_service": int (for interne) | null
            }
        ]
    }
    """
    
    def get(self, request):
        user = request.user
        
        # Validate user authentication
        if not user or not hasattr(user, 'id_membre') or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not hasattr(user, 'id_role') or not user.id_role:
            return Response({"error": "User has no role"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get role name
        role_name = getattr(user.id_role, 'nom_role', '').strip().upper()
        
        id_membre_value = user.id_membre
        if not id_membre_value:
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)
        
        # RESP_CM: External Commission
        if role_name == "RESP_CM":
            # Find current user's external commission membership
            member_link = MembresCommissionExterne.objects.filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response({
                    "commission_type": "externe",
                    "members": []
                }, status=status.HTTP_200_OK)
            
            # Get all members with the same id_commission_externe
            commission_id = member_link.id_comission_externe_id
            all_members = MembresCommissionExterne.objects.filter(
                id_comission_externe_id=commission_id
            )
            all_members = filter_members_by_validator_roles(all_members)
            
            payload = MembresCommissionExterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "externe",
                "id_commission_externe": commission_id,
                "members": payload
            }, status=status.HTTP_200_OK)
        
        # RESP_VALID_INTERN: Internal Commission
        elif role_name == "RESP_VALID_INTERN":
            # Find current user's internal commission membership
            member_link = MembresCommissionInterne.objects.filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response({
                    "commission_type": "interne",
                    "members": []
                }, status=status.HTTP_200_OK)
            
            service_id = member_link.id_commision_interne.id_service_id
            all_members = MembresCommissionInterne.objects.filter(
                id_commision_interne__id_service_id=service_id
            )
            all_members = filter_members_by_validator_roles(all_members)
            
            payload = MembresCommissionInterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "interne",
                "id_service": service_id,
                "members": payload
            }, status=status.HTTP_200_OK)
        
        return Response({
            "error": f"User role '{role_name}' is not supported for this endpoint"
        }, status=status.HTTP_403_FORBIDDEN)


class ValidatorsForCurrentUserCdcView(APIView):
    """
    GET /commission-members-cdc
    
    Same logic as /commission-members but filters members using CDC validator roles.
    """

    def get(self, request):
        user = request.user

        if not user or not hasattr(user, 'id_membre') or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(user, 'id_role') or not user.id_role:
            return Response({"error": "User has no role"}, status=status.HTTP_400_BAD_REQUEST)

        role_name = getattr(user.id_role, 'nom_role', '').strip().upper()
        id_membre_value = user.id_membre
        member_key = commission_member_key(user)
        if not id_membre_value:
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)

        if role_name == "RESP_CM":
            member_link = MembresCommissionExterne.objects.filter(
                id_membre=member_key
            ).first()

            if not member_link:
                return Response({
                    "commission_type": "externe",
                    "members": []
                }, status=status.HTTP_200_OK)

            commission_id = member_link.id_comission_externe_id
            all_members = MembresCommissionExterne.objects.filter(
                id_comission_externe_id=commission_id
            )
            all_members = filter_members_by_cdc_validator_roles(all_members)

            payload = MembresCommissionExterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "externe",
                "id_commission_externe": commission_id,
                "members": payload
            }, status=status.HTTP_200_OK)

        elif role_name == "RESP_VALID_INTERN":
            member_link = MembresCommissionInterne.objects.filter(
                id_membre=member_key
            ).first()

            if not member_link:
                return Response({
                    "commission_type": "interne",
                    "members": []
                }, status=status.HTTP_200_OK)

            service_id = member_link.id_commision_interne.id_service_id
            all_members = MembresCommissionInterne.objects.filter(
                id_commision_interne__id_service_id=service_id
            )
            all_members = filter_members_by_cdc_validator_roles(all_members)

            payload = MembresCommissionInterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "interne",
                "id_service": service_id,
                "members": payload
            }, status=status.HTTP_200_OK)

        return Response({
            "error": f"User role '{role_name}' is not supported for this endpoint"
        }, status=status.HTTP_403_FORBIDDEN)


class AllCommissionMembersView(APIView):
    """
    GET /commission-members-all
    
    Returns ALL members (without any role filtering) for the commission/service of the currently logged-in user.
    
    Logic:
    1. Get current user's id_membre and id_role
    2. If role is RESP_CM:
       - Look up in Membres_Commission_Externe using id_membre
       - Get the id_commission_externe
       - Return ALL members with the same id_commission_externe (no role filtering)
    3. If role is RESP_VALID_INTERN:
       - Look up in Membres_Commission_interne using id_membre
       - Get the id_service
       - Return ALL members with the same id_service (no role filtering)
    4. Otherwise (for other roles):
       - Return all members from both commission_externe and commission_interne tables
    
    Response format:
    {
        "commission_type": "externe" | "interne" | "all",
        "members": [...]
    }
    """
    
    def get(self, request):
        user = request.user
        
        # Validate user authentication
        if not user or not hasattr(user, 'id_membre') or not user.id_membre:
            return Response({"error": "User has no member ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not hasattr(user, 'id_role') or not user.id_role:
            return Response({"error": "User has no role"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get role name
        role_name = getattr(user.id_role, 'nom_role', '').strip().upper()
        
        id_membre_value = user.id_membre
        member_key = commission_member_key(user)
        if not id_membre_value:
            return Response({"error": "Invalid member ID format"}, status=status.HTTP_400_BAD_REQUEST)
        
        # RESP_CM: External Commission - return ALL members without role filter
        if role_name == "RESP_CM":
            # Find current user's external commission membership
            member_link = MembresCommissionExterne.objects.filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response({
                    "commission_type": "externe",
                    "members": []
                }, status=status.HTTP_200_OK)
            
            # Get ALL members with the same id_commission_externe (NO role filtering)
            commission_id = member_link.id_comission_externe_id
            all_members = MembresCommissionExterne.objects.filter(
                id_comission_externe_id=commission_id
            )
            
            payload = MembresCommissionExterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "externe",
                "id_commission_externe": commission_id,
                "members": payload
            }, status=status.HTTP_200_OK)
        
        # RESP_VALID_INTERN: Internal Commission - return ALL members without role filter
        elif role_name == "RESP_VALID_INTERN":
            # Find current user's internal commission membership
            member_link = MembresCommissionInterne.objects.filter(
                id_membre=member_key
            ).first()
            
            if not member_link:
                return Response({
                    "commission_type": "interne",
                    "members": []
                }, status=status.HTTP_200_OK)
            
            service_id = member_link.id_commision_interne.id_service_id
            all_members = MembresCommissionInterne.objects.filter(
                id_commision_interne__id_service_id=service_id
            )
            
            payload = MembresCommissionInterneSerializer(all_members, many=True).data
            return Response({
                "commission_type": "interne",
                "id_service": service_id,
                "members": payload
            }, status=status.HTTP_200_OK)
        
        else:
            # For other roles: return ALL members from both tables without filtering
            all_externe = MembresCommissionExterne.objects.all()
            all_interne = MembresCommissionInterne.objects.all()
            
            externe_payload = MembresCommissionExterneSerializer(all_externe, many=True).data
            interne_payload = MembresCommissionInterneSerializer(all_interne, many=True).data
            
            combined_members = externe_payload + interne_payload
            
            return Response({
                "commission_type": "all",
                "members": combined_members
            }, status=status.HTTP_200_OK)


def _acteurs_service_base_url():
    """Get Acteurs service base URL"""
    return getattr(
        settings,
        'ACTEURS_SERVICE_URL',
        getattr(settings, 'INTERNAL_BASE_URL', 'http://backend:8000'),
    ).rstrip("/")


def _auth_service_base_url():
    """Get Auth service base URL"""
    return getattr(
        settings,
        'AUTH_SERVICE_URL',
        getattr(settings, 'INTERNAL_BASE_URL', 'http://backend:8000'),
    ).rstrip("/")


def _get_internal_service_token():
    """Get internal service token for inter-service communication"""
    return getattr(settings, 'INTERNAL_SERVICE_TOKEN', '')


class AddMemberToCommissionView(APIView):
    """
    POST /add-member-to-commission
    Creates a new member, user account, and adds them to the external commission of the current user.
    
    Request body:
    {
        "email": "user@example.com",
        "password": "secure_password",
        "nom": "Dupont",
        "prenom": "Jean",
        "telephone": "+212...",
        "fonction": "VALIDATEUR_EXTERNE_MARCHE",
        "role_nom": "VALIDATEUR_EXTERNE_MARCHE"
    }
    
    Response:
    {
        "id_membre": "uuid-of-member",
        "id_utilisateur": 123,
        "message": "Member successfully created and added to commission"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Get required data from request
            email = request.data.get('email', '').strip()
            password = request.data.get('password', '').strip()
            nom = request.data.get('nom', '').strip()
            prenom = request.data.get('prenom', '').strip()
            telephone = request.data.get('telephone', '')
            fonction = request.data.get('fonction', '')
            role_nom = request.data.get('role_nom', '').strip()
            id_commission_externe = request.data.get('id_commission_externe')
            
            # Validate required fields
            if not all([email, password, nom, prenom, role_nom]):
                return Response(
                    {"error": "Missing required fields: email, password, nom, prenom, role_nom"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not hasattr(request.user, 'id_membre') or not request.user.id_membre:
                return Response(
                    {"error": "User has no member ID"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine the current user's external commission if not explicitly provided
            member_key = commission_member_key(request.user)
            if not id_commission_externe:
                user_commission_link = MembresCommissionExterne.objects.filter(
                    id_membre=member_key
                ).first()
                if not user_commission_link:
                    return Response(
                        {"error": "User is not linked to any external commission"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                id_commission_externe = user_commission_link.id_comission_externe_id
            else:
                user_commission_link = MembresCommissionExterne.objects.filter(
                    id_membre=member_key,
                    id_comission_externe=id_commission_externe
                ).first()
                if not user_commission_link:
                    return Response(
                        {"error": "User is not authorized to add members to this commission"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # The external commission identifier is also the organisation id for the Acteurs service.
            organisation_id = str(id_commission_externe)

            # Step 1: Create Membre via Acteurs service
            acteurs_url = _acteurs_service_base_url()
            membre_payload = {
                "nom": nom,
                "prenom": prenom,
                "telephone": telephone or None,
                "fonction": fonction or None,
                "organisation": organisation_id
            }
            
            headers = {}
            token = _get_internal_service_token()
            if token:
                headers["X-Internal-Service-Token"] = token
            
            try:
                membre_response = requests.post(
                    f"{acteurs_url}/membres/",
                    json=membre_payload,
                    headers=headers,
                    timeout=10
                )
            except requests.RequestException as e:
                return Response(
                    {"error": f"Failed to connect to Acteurs service: {str(e)}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            if membre_response.status_code != 201:
                return Response(
                    {"error": f"Failed to create member: {membre_response.text}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            membre_data = membre_response.json()
            id_membre = membre_data.get('id_membre') or membre_data.get('id')
            if not id_membre:
                return Response(
                    {"error": "Member ID not returned from service"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 2: Create Utilisateur (User) via Auth service internal registration endpoint
            auth_url = _auth_service_base_url()
            user_payload = {
                "email": email,
                "password": password,
                "id_membre": str(id_membre),
                "role_nom": role_nom,
            }
            
            try:
                user_response = requests.post(
                    f"{auth_url}/internal/users/register",
                    json=user_payload,
                    headers=headers,
                    timeout=10
                )
            except requests.RequestException as e:
                return Response(
                    {"error": f"Failed to connect to Auth service: {str(e)}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            if user_response.status_code != 201:
                return Response(
                    {"error": f"Failed to create user: {user_response.text}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            user_data = user_response.json()
            id_utilisateur = user_data.get('id_utilisateur') or user_data.get('id')
            
            # Step 4: Create association in MembresCommissionExterne
            try:
                with transaction.atomic():
                    association = MembresCommissionExterne.objects.create(
                        id_membre=int(id_utilisateur),
                        id_comission_externe_id=int(id_commission_externe)
                    )
            except Exception as e:
                return Response(
                    {"error": f"Failed to associate member with commission: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Clear cache
            bump_cache_version()
            
            return Response({
                "id_membre": str(id_membre),
                "id_utilisateur": id_utilisateur,
                "message": "Member successfully created and added to commission"
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
