import json
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone
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
    affect_validator_to_appel,
)
from .services.health import check_readiness
from .services.validation_interne import get_commission_interne_dashboard_data
from .services.validation_externe import get_commission_externe_dashboard_data
from .services.commission_unified import CommissionAppelsService


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
        validated_by = self.request.query_params.get("validated_by")
        try:
            service_id = int(service_id_raw) if service_id_raw not in (None, "") else None
        except ValueError:
            service_id = None

        queryset = appels_offres_queryset(
            statut=statut,
            service_id=service_id,
            search=search,
            request=self.request,
        )

        if validated_by is not None and validated_by != "":
            queryset = queryset.filter(validated_by=str(validated_by).strip())

        return queryset

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


class AppelOffresAffectValidatorView(APIView):
    """
    Endpoint pour affecter un validateur à un appel d'offres et créer une entrée de suivi.
    
    Opérations effectuées:
    1. Met à jour le champ validated_by de la table appels_offres
    2. Crée une entrée de suivi dans appels_offres_suivis pour le validateur
    
    Request body:
    {
        "validator_id": <id de l'utilisateur validateur>
    }
    """
    def post(self, request, appel_id):
        validator_id = request.data.get("validator_id")
        
        appel, suivi, notification = affect_validator_to_appel(
            appel_id=appel_id,
            validator_id=validator_id,
        )
        bump_cache_version()
        
        return Response({
            "appel": AppelOffresSerializer(appel).data,
            "suivi": AppelOffresSuiviSerializer(suivi).data if suivi else None,
            "notification": {
                "id": notification.id,
                "utilisateur_id": notification.utilisateur_id,
                "type_notification": notification.type_notification,
                "titre": notification.titre,
                "message": notification.message,
                "categorie": notification.categorie,
                "entite_liee_type": notification.entite_liee_type,
                "entite_liee_id": notification.entite_liee_id,
                "statut": notification.statut,
                "sent_at": notification.sent_at,
            },
        })


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


def _commission_response_file_path():
    if hasattr(settings, 'COMMISSION_RESPONSE_PATH'):
        return Path(settings.COMMISSION_RESPONSE_PATH).resolve()
    if hasattr(settings, 'BASE_DIR'):
        return Path(settings.BASE_DIR).resolve() / "commission-endpoints-response.json"
    return Path(__file__).resolve().parents[2] / "commission-endpoints-response.json"


def _write_commission_response(endpoint_key, payload, status_code):
    logger = logging.getLogger(__name__)
    try:
        file_path = _commission_response_file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if file_path.exists():
            try:
                existing = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
        existing.setdefault("responses", {})[endpoint_key] = {
            "updatedAt": timezone.now().isoformat(),
            "status": status_code,
            "body": payload,
        }
        existing["lastUpdated"] = timezone.now().isoformat()
        existing["lastEndpoint"] = endpoint_key
        file_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.exception("Unable to write commission endpoint response snapshot: %s", exc)


def _commission_response(endpoint_key, payload, status_code=status.HTTP_200_OK):
    _write_commission_response(endpoint_key, payload, status_code)
    return Response(payload, status=status_code)


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

# ── Tableau de Bord Commission Interne ────────────────────────────────

class CommissionInterneDossiersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Debug: log user info
        import logging
        logger = logging.getLogger(__name__)
        # Log user info and raw Authorization header for troubleshooting 401s
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        try:
            auth_preview = auth_header[:80] + '...' if auth_header and len(auth_header) > 80 else (auth_header or 'MISSING')
        except Exception:
            auth_preview = 'UNRETRIEVABLE'
        logger.info(f"User: {request.user}, Authenticated: {request.user.is_authenticated}, Authorization: {auth_preview}")
        
        membre_id = None
        user_id = getattr(request.user, 'id_utilisateur', None)
        user_email = getattr(request.user, 'email', None)

        if request.user.is_authenticated:
            membre_id = getattr(request.user, 'id_membre', None)
            if not membre_id:
                membre_id = user_id

        if not membre_id:
            # Allow passing user id explicitly as query param as a fast fallback
            user_id_param = request.query_params.get('user_id') if hasattr(request, 'query_params') else request.GET.get('user_id')
            if user_id_param:
                # Try to interpret user_id_param as id_utilisateur (int) and lookup id_membre from utilisateurs table
                try:
                    from auth_service.models import Utilisateur
                    user_id_int = int(user_id_param)
                    user_obj = Utilisateur.objects.filter(id_utilisateur=user_id_int).first()
                    if user_obj and user_obj.id_membre:
                        membre_id = str(user_obj.id_membre)
                    else:
                        # fallback: if user_id_param is numeric, use as id_utilisateur fallback
                        membre_id = user_id_int
                except (ValueError, Exception):
                    # If not numeric, treat as id_membre directly
                    membre_id = user_id_param

        if not membre_id:
            # Tentative : essayer de décoder le JWT manuellement au cas où
            # l'authentification DRF n'a pas peuplé `request.user`.
            from django.conf import settings
            from rest_framework_simplejwt.backends import TokenBackend

            auth_header = request.META.get('HTTP_AUTHORIZATION') or request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                raw_token = auth_header.split(' ', 1)[1]
                try:
                    tb = TokenBackend(
                        algorithm=settings.SIMPLE_JWT.get('ALGORITHM', 'HS256'),
                        signing_key=settings.SIMPLE_JWT.get('SIGNING_KEY'),
                    )
                    payload = tb.decode(raw_token, verify=True)
                    logger.info(f"Decoded token payload keys: {list(payload.keys())}")
                    membre_id = payload.get('id_membre') or payload.get('id_utilisateur') or payload.get('user_id')
                    if not membre_id and payload.get('email') == user_email:
                        membre_id = user_id
                except Exception as e:
                    logger.info(f"Token decode fallback failed: {e}")

        if not membre_id and user_id is not None:
            from contractant_service.models import MembresCommissionInterne

            # Adapt the user_id to the model field type to avoid SQL type mismatch (uuid vs integer)
            try:
                field = MembresCommissionInterne._meta.get_field('id_membre')
                ftype = field.get_internal_type()
            except Exception:
                ftype = None

            query_val = user_id
            if ftype in ('IntegerField', 'AutoField', 'BigIntegerField', 'SmallIntegerField'):
                # if user_id looks like a UUID string, convert last hex segment to int
                if isinstance(user_id, str) and '-' in user_id:
                    try:
                        query_val = int(user_id.split('-')[-1], 16)
                    except Exception:
                        query_val = user_id
            elif ftype == 'UUIDField':
                # if user_id is a UUID-like string, try to cast
                if isinstance(user_id, str) and '-' in user_id:
                    try:
                        from uuid import UUID
                        query_val = UUID(user_id)
                    except Exception:
                        query_val = user_id

            membre_data = MembresCommissionInterne.objects.filter(
                id_membre=query_val
            ).first()
            if membre_data:
                membre_id = user_id
        
        if not membre_id:
            logger.error(f"No id_membre found for user {request.user}")
            payload = {"detail": "Identifiant membre introuvable."}
            return _commission_response("commission-interne", payload, status.HTTP_400_BAD_REQUEST)
            
        try:
            data = get_commission_interne_dashboard_data(membre_id)
            return _commission_response("commission-interne", data, status.HTTP_200_OK)
        except PermissionDenied as e:
            empty_stats = {"enAttente": 0, "enCours": 0, "enRetard": 0, "pret": 0, "enAttentePct": 0, "enCoursPct": 0, "enRetardPct": 0, "pretPct": 0}
            payload = {"stats": empty_stats, "appels": [], "detail": str(e)}
            return _commission_response("commission-interne", payload, status.HTTP_200_OK)
        except Exception as e:
            payload = {"detail": str(e)}
            return _commission_response("commission-interne", payload, status.HTTP_500_INTERNAL_SERVER_ERROR)


class CommissionExterneDossiersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        membre_id = None
        user_id = getattr(request.user, 'id_utilisateur', None)
        user_email = getattr(request.user, 'email', None)

        if request.user.is_authenticated:
            membre_id = getattr(request.user, 'id_membre', None)
            if not membre_id:
                membre_id = user_id

        if not membre_id:
            # Allow passing user id explicitly as query param as a fast fallback
            user_id_param = request.query_params.get('user_id') if hasattr(request, 'query_params') else request.GET.get('user_id')
            if user_id_param:
                # Try to interpret user_id_param as id_utilisateur (int) and lookup id_membre from utilisateurs table
                try:
                    from auth_service.models import Utilisateur
                    user_id_int = int(user_id_param)
                    user_obj = Utilisateur.objects.filter(id_utilisateur=user_id_int).first()
                    if user_obj and user_obj.id_membre:
                        membre_id = str(user_obj.id_membre)
                    else:
                        # fallback: if user_id_param is numeric, use as id_utilisateur fallback
                        membre_id = user_id_int
                except (ValueError, Exception):
                    # If not numeric, treat as id_membre directly
                    membre_id = user_id_param

        if not membre_id:
            # Try to decode token as fallback (same logic as interne)
            from django.conf import settings
            from rest_framework_simplejwt.backends import TokenBackend

            auth_header = request.META.get('HTTP_AUTHORIZATION') or request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                raw_token = auth_header.split(' ', 1)[1]
                try:
                    tb = TokenBackend(
                        algorithm=settings.SIMPLE_JWT.get('ALGORITHM', 'HS256'),
                        signing_key=settings.SIMPLE_JWT.get('SIGNING_KEY'),
                    )
                    payload = tb.decode(raw_token, verify=True)
                    membre_id = payload.get('id_membre') or payload.get('id_utilisateur') or payload.get('user_id')
                    if not membre_id and payload.get('email') == user_email:
                        membre_id = user_id
                except Exception:
                    pass

        if not membre_id and user_id is not None:
            from contractant_service.models import MembresCommissionExterne

            try:
                field = MembresCommissionExterne._meta.get_field('id_membre')
                ftype = field.get_internal_type()
            except Exception:
                ftype = None

            query_val = user_id
            if ftype in ('IntegerField', 'AutoField', 'BigIntegerField', 'SmallIntegerField'):
                if isinstance(user_id, str) and '-' in user_id:
                    try:
                        query_val = int(user_id.split('-')[-1], 16)
                    except Exception:
                        query_val = user_id
            elif ftype == 'UUIDField':
                if isinstance(user_id, str) and '-' in user_id:
                    try:
                        from uuid import UUID
                        query_val = UUID(user_id)
                    except Exception:
                        query_val = user_id

            membre_data = MembresCommissionExterne.objects.filter(id_membre=query_val).first()
            if membre_data:
                membre_id = user_id

        if not membre_id:
            payload = {"detail": "Identifiant membre introuvable."}
            return _commission_response("commission-externe", payload, status.HTTP_400_BAD_REQUEST)

        try:
            data = get_commission_externe_dashboard_data(membre_id)
            return _commission_response("commission-externe", data, status.HTTP_200_OK)
        except PermissionDenied as e:
            empty_stats = {"enAttente": 0, "enCours": 0, "enRetard": 0, "pret": 0, "enAttentePct": 0, "enCoursPct": 0, "enRetardPct": 0, "pretPct": 0}
            payload = {"stats": empty_stats, "appels": [], "detail": str(e)}
            return _commission_response("commission-externe", payload, status.HTTP_200_OK)
        except Exception as e:
            payload = {"detail": str(e)}
            return _commission_response("commission-externe", payload, status.HTTP_500_INTERNAL_SERVER_ERROR)


class CommissionAppelsUnifiedView(APIView):
    """
    Unified endpoint for commission appels d'offres.
    
    Handles both RESP_VALID_INTERN and RESP_CM roles.
    Returns appels classified by dynamic state: En Attente, En Cours, En Retard, Prêt.
    
    Query params:
        user_id: int (optional, fallback to auth token)
        membre_id: UUID|string (optional, fallback to auth token)
        role: str (optional, fallback to auth token)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Extract user_id, membre_id, and role from auth or query params
            user_id = self._extract_user_id(request)
            membre_id = self._extract_membre_id(request)
            role = self._extract_role(request)
            
            if not role or not (user_id or membre_id):
                return Response(
                    {"detail": "role and either user_id or membre_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Call unified service with direct membership when available
            data = CommissionAppelsService.get_appels_for_user(user_id=user_id, role=role, membre_id=membre_id)
            return _commission_response("commission-unified", data, status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in CommissionAppelsUnifiedView: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_user_id(self, request) -> int:
        """Extract user_id from auth token or query params."""
        # Try auth user first
        if request.user.is_authenticated:
            user_id = getattr(request.user, 'id_utilisateur', None)
            if user_id:
                return user_id
        
        # Try query param
        user_id_param = request.query_params.get('user_id')
        if user_id_param:
            try:
                return int(user_id_param)
            except ValueError:
                pass
        
        # Try JWT token
        user_id = self._extract_from_jwt(request, 'user_id')
        if user_id:
            try:
                return int(user_id)
            except (ValueError, TypeError):
                pass
        
        return None
    
    def _extract_role(self, request) -> str:
        """Extract role from auth token or query params."""
        # Try auth user first
        if request.user.is_authenticated:
            role = getattr(request.user, 'role', None)
            if role:
                return str(role).upper()
        
        # Try query param
        role_param = request.query_params.get('role')
        if role_param:
            return str(role_param).upper()
        
        # Try JWT token
        role = self._extract_from_jwt(request, 'role')
        if role:
            return str(role).upper()
        
        return None

    def _extract_membre_id(self, request):
        """Extract membre_id from auth token or query params."""
        if request.user.is_authenticated:
            membre_id = getattr(request.user, 'id_membre', None)
            if membre_id:
                return membre_id

        membre_id_param = request.query_params.get('membre_id')
        if membre_id_param:
            return membre_id_param

        membre_id = self._extract_from_jwt(request, 'id_membre')
        if membre_id:
            return membre_id

        return None
    
    def _extract_from_jwt(self, request, field: str):
        """Manually decode JWT and extract field."""
        auth_header = request.META.get('HTTP_AUTHORIZATION') or request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        try:
            from django.conf import settings
            from rest_framework_simplejwt.backends import TokenBackend
            
            raw_token = auth_header.split(' ', 1)[1]
            tb = TokenBackend(
                algorithm=settings.SIMPLE_JWT.get('ALGORITHM', 'HS256'),
                signing_key=settings.SIMPLE_JWT.get('SIGNING_KEY'),
            )
            payload = tb.decode(raw_token, verify=True)
            return payload.get(field)
        except Exception:
            return None

