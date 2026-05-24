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

from .serializers import (
    AttributionSerializer,
    AttributionAffecterSerializer,
    AttributionValiderSerializer,
)

logger = logging.getLogger(__name__)


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
        if commission_id:
            qs = qs.filter(commission_id=commission_id)

        validation_level = request.query_params.get("validation_level")
        if validation_level:
            qs = qs.filter(validation_level=validation_level)

        service_contractant_id = request.query_params.get("service_contractant_id")
        if service_contractant_id:
            qs = qs.filter(service_contractant_id=service_contractant_id)

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



