import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.permissions import (
    AuthenticatedOrInternalServicePermission,
    internal_service_headers,
)
from soumissions_app.models import Attribution
from appels_service.models import AppelOffresSuivi
from datetime import timedelta
from django.utils import timezone
from contractant_service.models import (
    MembresCommissionExterne,
    MembresCommissionInterne,
)

from .serializers import (
    AttributionSerializer,
    AttributionAffecterSerializer,
    AttributionValiderSerializer,
)

logger = logging.getLogger(__name__)


def _normalize_membre_id(membre_id):
    if membre_id is None:
        return None

    try:
        from uuid import UUID
        if isinstance(membre_id, UUID):
            return int(str(membre_id).split('-')[-1], 16)
    except Exception:
        pass

    if isinstance(membre_id, str):
        if '-' in membre_id:
            try:
                from uuid import UUID
                return int(str(UUID(membre_id)).split('-')[-1], 16)
            except Exception:
                pass
        try:
            return int(membre_id)
        except Exception:
            return membre_id

    if isinstance(membre_id, int):
        return membre_id

    return membre_id


def _get_request_membre_id(request):
    membre_id = getattr(getattr(request, 'user', None), 'id_membre', None)
    if membre_id is not None:
        return membre_id
    return request.query_params.get('user_id')


def _get_service_contractant_id_for_membre(request):
    membre_id = _get_request_membre_id(request)
    if membre_id is None:
        return None

    adapted = _normalize_membre_id(membre_id)
    try:
        link = MembresCommissionInterne.objects.filter(id_membre=adapted).first()
    except Exception:
        link = None

    if link:
        return getattr(link, 'id_service_id', None)
    return None


def _get_commission_id_for_membre(request):
    membre_id = _get_request_membre_id(request)
    if membre_id is None:
        return None

    adapted = _normalize_membre_id(membre_id)
    try:
        link = MembresCommissionExterne.objects.filter(id_membre=adapted).first()
    except Exception:
        link = None

    if link:
        return getattr(link, 'id_comission_externe_id', None)
    return None


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------

class ProtectedAPIView(APIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


# ---------------------------------------------------------------------------
# Health / Ready
# ---------------------------------------------------------------------------

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
            probe_key = "contrats:ready"
            cache.set(probe_key, "1", timeout=5)
            cache_ready = cache.get(probe_key) == "1"
        except Exception:
            cache_ready = False
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ---------------------------------------------------------------------------
# ATTRIBUTIONS PROVISOIRES
# ---------------------------------------------------------------------------

class AttributionProvisoireListView(ProtectedAPIView):

    def get(self, request):
        qs = Attribution.objects.filter(statut="provisoire").order_by("-created_at")

        commission_id = request.query_params.get("commission_id")
        validation_level = request.query_params.get("validation_level")
        service_contractant_id = request.query_params.get("service_contractant_id")
        soumission_id = request.query_params.get("soumission_id")

        if commission_id:
            qs = qs.filter(commission_id=commission_id)

        if validation_level:
            qs = qs.filter(validation_level=validation_level)

        if service_contractant_id:
            qs = qs.filter(service_contractant_id=service_contractant_id)

        if soumission_id:
            qs = qs.filter(soumission_id=soumission_id)

        # When the caller does not specify a commission, service, or soumission filter,
        # attempt to scope results to the current commission member.
        if not commission_id and not service_contractant_id and not soumission_id:
            if validation_level == "interne":
                service_id = _get_service_contractant_id_for_membre(request)
                if service_id is not None:
                    qs = qs.filter(service_contractant_id=service_id)
            elif validation_level and validation_level.startswith("externe"):
                commission_id = _get_commission_id_for_membre(request)
                if commission_id is not None:
                    qs = qs.filter(commission_id=commission_id)
            else:
                service_id = _get_service_contractant_id_for_membre(request)
                if service_id is not None:
                    qs = qs.filter(service_contractant_id=service_id)
                else:
                    commission_id = _get_commission_id_for_membre(request)
                    if commission_id is not None:
                        qs = qs.filter(commission_id=commission_id)

        serializer = AttributionSerializer(qs, many=True)
        return Response(serializer.data)


class AttributionDetailView(ProtectedAPIView):

    def get(self, request, attribution_provisoire_id):
        attribution = Attribution.objects.filter(pk=attribution_provisoire_id).first()
        if not attribution:
            return Response(
                {"detail": "Attribution non trouvée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = AttributionSerializer(attribution).data

        # Enrich: soumission details
        try:
            soumission = attribution.soumission
            soum_url = (
                f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}"
                f"/api/soumissions/{soumission.id_soumission}"
            )
            resp = requests.get(soum_url, headers=internal_service_headers(), timeout=3)
            if resp.status_code == 200:
                data["soumission_details"] = resp.json()
        except Exception as exc:
            logger.warning("Could not enrich soumission details: %s", exc)

        # Enrich: appel details
        try:
            appel_url = (
                f"{settings.APPELS_SERVICE_URL.rstrip('/')}"
                f"/api/appels-offres/{attribution.appel_id}"
            )
            resp_a = requests.get(appel_url, headers=internal_service_headers(), timeout=3)
            if resp_a.status_code == 200:
                data["appel_details"] = resp_a.json()
        except Exception as exc:
            logger.warning("Could not enrich appel details: %s", exc)

        # Enrich: commission details
        try:
            level = attribution.validation_level  # interne | externe_*
            c_type = "internes" if level == "interne" else "evaluation"
            comm_url = (
                f"{settings.CONTRACTANT_SERVICE_URL.rstrip('/')}"
                f"/commissions-{c_type}/{attribution.commission_id}"
            )
            resp_c = requests.get(comm_url, headers=internal_service_headers(), timeout=3)
            if resp_c.status_code == 200:
                data["commission_details"] = resp_c.json()
        except Exception as exc:
            logger.warning("Could not enrich commission details: %s", exc)

        return Response(data)


# ---------------------------------------------------------------------------
# AFFECTER & VALIDER
# ---------------------------------------------------------------------------

class AffecterAttributionView(ProtectedAPIView):

    def post(self, request, attribution_provisoire_id):
        attribution = Attribution.objects.filter(pk=attribution_provisoire_id).first()
        if not attribution:
            return Response(
                {"detail": "Attribution non trouvée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attribution.statut == "definitive":
            return Response(
                {"detail": "Impossible d'affecter un membre : l'attribution est déjà définitive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AttributionAffecterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        attribution.validated_by = serializer.validated_data["validated_by"]
        attribution.save(update_fields=["validated_by", "updated_at"])

        logger.info(
            "Attribution %d affectée au membre %d", attribution.pk, attribution.validated_by
        )
        return Response(AttributionSerializer(attribution).data)


class ValiderAttributionView(ProtectedAPIView):

    def post(self, request, attribution_provisoire_id):
        attribution = Attribution.objects.filter(pk=attribution_provisoire_id).first()
        if not attribution:
            return Response(
                {"detail": "Attribution non trouvée."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attribution.statut == "definitive":
            return Response(
                {"detail": "Cette attribution est déjà définitive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not attribution.validated_by:
            return Response(
                {"detail": "Aucun membre affecté. Veuillez d'abord affecter un membre."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attribution.statut = "definitive"
        attribution.save(update_fields=["statut", "updated_at"])

        logger.info("Attribution %d → définitive par membre %d", attribution.pk, attribution.validated_by)
        return Response(AttributionSerializer(attribution).data)


# ---------------------------------------------------------------------------
# ATTRIBUTIONS DEFINITIVES (CONTRATS)
# ---------------------------------------------------------------------------

class AttributionDefinitiveListView(ProtectedAPIView):

    def get(self, request):
        qs = Attribution.objects.filter(statut="definitive").order_by("-updated_at")

        service_contractant_id = request.query_params.get("service_contractant_id")
        if service_contractant_id:
            qs = qs.filter(service_contractant_id=service_contractant_id)

        commission_id = request.query_params.get("commission_id")
        if commission_id:
            qs = qs.filter(commission_id=commission_id)

        appel_id = request.query_params.get("appel_id")
        if appel_id:
            qs = qs.filter(appel_id=appel_id)

        soumission_id = request.query_params.get("soumission_id")
        if soumission_id:
            qs = qs.filter(soumission_id=soumission_id)

        return Response(AttributionSerializer(qs, many=True).data)


class AttributionDefinitiveDetailView(ProtectedAPIView):

    def get(self, request, attribution_definitive_id):
        attribution = Attribution.objects.filter(pk=attribution_definitive_id, statut="definitive").first()
        if not attribution:
            return Response(
                {"detail": "Contrat (attribution définitive) non trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = AttributionSerializer(attribution).data

        # Enrich: soumission
        try:
            soum_url = (
                f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}"
                f"/api/soumissions/{attribution.soumission.id_soumission}"
            )
            resp = requests.get(soum_url, headers=internal_service_headers(), timeout=3)
            if resp.status_code == 200:
                data["soumission_details"] = resp.json()
        except Exception as exc:
            logger.warning("Could not enrich soumission: %s", exc)

        # Enrich: appel
        try:
            appel_url = (
                f"{settings.APPELS_SERVICE_URL.rstrip('/')}"
                f"/api/appels-offres/{attribution.appel_id}"
            )
            resp_a = requests.get(appel_url, headers=internal_service_headers(), timeout=3)
            if resp_a.status_code == 200:
                data["appel_details"] = resp_a.json()
        except Exception as exc:
            logger.warning("Could not enrich appel: %s", exc)

        return Response(data)





class ValidatorAttributionsView(ProtectedAPIView):
    def get(self, request):
        raw_user_id = request.query_params.get("user_id")
        if not raw_user_id:
            return Response({"detail": "user_id est requis."}, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = _normalize_membre_id(raw_user_id)
        
        try:
            attributions = Attribution.objects.filter(validated_by=user_id, statut="provisoire")
            
            results = []
            for attr in attributions:
                data = AttributionSerializer(attr).data
                suivi = AppelOffresSuivi.objects.filter(id_appel_offres_id=attr.appel_id, id_utilisateur=user_id).first()
                
                base_date = suivi.created_at if suivi else attr.created_at
                
                if not base_date:
                    # Fallback to now if base_date is completely missing
                    base_date = timezone.now()
                    
                deadline = base_date + timedelta(days=7)
                now = timezone.now()
                
                if deadline >= now:
                    etat = "En Cours"
                    delayDays = 0
                else:
                    etat = "En Retard"
                    delayDays = (now - deadline).days
                    
                data["status"] = etat
                data["validationDeadline"] = deadline
                data["delayDays"] = delayDays
                
                try:
                    if attr.soumission:
                        soum_url = f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}/api/soumissions/{attr.soumission.id_soumission}"
                        resp = requests.get(soum_url, headers=internal_service_headers(), timeout=3)
                        if resp.status_code == 200:
                            data["soumission_details"] = resp.json()
                except Exception as exc:
                    logger.warning("Could not enrich soumission details: %s", exc)

                try:
                    if attr.appel_id:
                        appel_url = f"{settings.APPELS_SERVICE_URL.rstrip('/')}/api/appels-offres/{attr.appel_id}"
                        resp_a = requests.get(appel_url, headers=internal_service_headers(), timeout=3)
                        if resp_a.status_code == 200:
                            data["appel_details"] = resp_a.json()
                except Exception as exc:
                    logger.warning("Could not enrich appel details: %s", exc)

                results.append(data)
                
            return Response({"attributions": results})
        except Exception as e:
            import traceback
            return Response({"error": "internal_error", "message": str(e), "trace": traceback.format_exc()}, status=500)

