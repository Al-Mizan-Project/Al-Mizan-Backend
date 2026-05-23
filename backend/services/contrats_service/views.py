"""
contrats_service/views.py

All validation/contract logic now uses the Attribution model (soumissions_app).

Endpoints kept at same URLs:
  GET  /validations/                          → list attributions provisoires by commission
  GET  /validations/<id>/                     → attribution detail (all info)
  POST /validations/<id>/affecter/            → assign validated_by member
  POST /validations/<id>/valider/             → set statut = definitive
  GET  /contrats/                             → list attributions definitives (= contrats)
  GET  /contrats/<id>/                        → attribution definitive detail
  GET  /soumissions/<soumission_id>/contrat   → get definitive attribution for a soumission
"""

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
from soumissions_app.models import Attribution, Soumission

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
# VALIDATION  →  attributions de statut "provisoire"
# ---------------------------------------------------------------------------

class ValidationListCreateView(ProtectedAPIView):
    """
    GET /validations/
    Retourne les attributions provisoires pour une commission donnée.

    Query params:
      - commission_id  (obligatoire ou optionnel selon le rôle)
      - validation_level  (optionnel : interne | externe_wilaya | ...)
      - service_contractant_id (optionnel)
    """

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


class ValidationRetrieveUpdateDeleteView(ProtectedAPIView):
    """
    GET  /validations/<attribution_id>/
    Retourne les détails complets d'une attribution (provisoire ou definitive).
    On enrichit avec les données de soumission et d'appel depuis les autres services.
    """

    def get(self, request, validation_id):
        attribution = Attribution.objects.filter(pk=validation_id).first()
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

        # Enrich: commission details (interne or externe)
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
# AFFECTER  →  assigner un membre (validated_by)
# ---------------------------------------------------------------------------

class ValidationApproveView(ProtectedAPIView):
    """
    POST /validations/<attribution_id>/approuver/
    Affecte l'attribution à un membre de la commission (validated_by).
    Body: { "validated_by": <id_utilisateur> }
    (on garde l'URL /approuver/ pour compatibilité frontend mais le sens change)
    """

    def post(self, request, validation_id):
        attribution = Attribution.objects.filter(pk=validation_id).first()
        if not attribution:
            return Response(
                {"detail": "Attribution non trouvée."},
                status=status.HTTP_404_NOT_FOUND,
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


# ---------------------------------------------------------------------------
# VALIDER  →  passer l'attribution de provisoire à définitive
# ---------------------------------------------------------------------------

class ValidationRejectView(ProtectedAPIView):
    """
    POST /validations/<attribution_id>/rejeter/
    Le membre valide l'attribution → statut passe à 'definitive'.
    Body: { "commentaire": "..." }  (optionnel)
    (on garde l'URL /rejeter/ pour compatibilité mais le sens est maintenant
     "valider/confirmer l'attribution" — vous pouvez renommer côté frontend)
    """

    def post(self, request, validation_id):
        attribution = Attribution.objects.filter(pk=validation_id).first()
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
                {"detail": "Aucun membre affecté à cette attribution. Veuillez d'abord affecter un membre."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attribution.statut = "definitive"
        attribution.save(update_fields=["statut", "updated_at"])

        logger.info("Attribution %d validée → définitive", attribution.pk)
        return Response(AttributionSerializer(attribution).data)


# ---------------------------------------------------------------------------
# AFFECTER (nouvelle URL propre)
# ---------------------------------------------------------------------------

class AffecterAttributionView(ProtectedAPIView):
    """
    POST /validations/<attribution_id>/affecter/
    Assigne un membre de commission pour valider cette attribution.
    Body: { "validated_by": <id_utilisateur> }
    """

    def post(self, request, validation_id):
        attribution = Attribution.objects.filter(pk=validation_id).first()
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
    """
    POST /validations/<attribution_id>/valider/
    Le membre affecté confirme la validation → statut passe à 'definitive'.
    """

    def post(self, request, validation_id):
        attribution = Attribution.objects.filter(pk=validation_id).first()
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
# CONTRATS  →  attributions de statut "definitive"
# ---------------------------------------------------------------------------

class ContratListCreateView(ProtectedAPIView):
    """
    GET /contrats
    Retourne toutes les attributions definitives (= contrats).

    Query params:
      - service_contractant_id
      - commission_id
      - appel_id
    """

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


class ContratRetrieveUpdateDeleteView(ProtectedAPIView):
    """
    GET /contrats/<id>
    Détail d'une attribution définitive (contrat).
    """

    def get(self, request, contrat_id):
        attribution = Attribution.objects.filter(pk=contrat_id, statut="definitive").first()
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


# ---------------------------------------------------------------------------
# Keep legacy URL stubs for backward compat (return 404 gracefully)
# ---------------------------------------------------------------------------

class ContratSignView(ProtectedAPIView):
    """POST /contrats/<id>/signer — no longer applicable, kept for URL compat."""

    def post(self, request, contrat_id):
        return Response(
            {"detail": "Action non applicable. Utilisez POST /validations/<id>/valider/ pour confirmer une attribution."},
            status=status.HTTP_410_GONE,
        )


class ContratDocumentsListView(ProtectedAPIView):
    """GET /contrats/<id>/documents — no longer used."""

    def get(self, request, contrat_id):
        return Response(
            {"detail": "Les documents sont désormais gérés directement sur la soumission."},
            status=status.HTTP_410_GONE,
        )


class ContratDocumentDetailView(ProtectedAPIView):
    def post(self, request, contrat_id, document_id):
        return Response(status=status.HTTP_410_GONE)

    def delete(self, request, contrat_id, document_id):
        return Response(status=status.HTTP_410_GONE)


# ---------------------------------------------------------------------------
# soumissions/<soumission_id>/contrat
# ---------------------------------------------------------------------------

class SoumissionContratView(ProtectedAPIView):
    """
    GET /soumissions/<soumission_id>/contrat
    Retourne l'attribution définitive liée à cette soumission.
    """

    def get(self, request, soumission_id):
        attribution = Attribution.objects.filter(
            soumission__id_soumission=soumission_id,
            statut="definitive",
        ).first()
        if not attribution:
            return Response(
                {"detail": "Aucun contrat (attribution définitive) trouvé pour cette soumission."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AttributionSerializer(attribution).data)


# ---------------------------------------------------------------------------
# Aggregated detail page (used by affectation UI)
# ---------------------------------------------------------------------------

class AffectationDetailView(APIView):
    """
    GET /affectation-details/<soumission_id>/
    Agrège les données nécessaires à la page d'affectation :
      - soumission details
      - service_contractant_id
      - membres de la commission (avec charge)
    """
    permission_classes = [AllowAny]

    def get(self, request, soumission_id):
        auth_header = request.headers.get("Authorization", "")
        user_jwt_headers = {"Authorization": auth_header} if auth_header else {}

        # 1. Soumission
        soum_url = f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}/api/soumissions/{soumission_id}"
        try:
            resp_soum = requests.get(soum_url, headers=internal_service_headers(), timeout=3)
            if resp_soum.status_code != 200:
                # fallback
                soum_url2 = f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}/soumissions/{soumission_id}"
                resp_soum = requests.get(soum_url2, headers=internal_service_headers(), timeout=3)
            if resp_soum.status_code != 200:
                return Response({"error": "Soumission non trouvée"}, status=404)
            soum_data = resp_soum.json()
        except Exception as exc:
            return Response({"error": f"Service soumissions injoignable: {exc}"}, status=503)

        # 2. Attribution provisoire existante pour cette soumission (si elle existe)
        attribution = Attribution.objects.filter(
            soumission__id_soumission=soumission_id
        ).first()

        attribution_data = None
        commission_id = None
        validation_level = None
        service_contractant_id = None

        if attribution:
            attribution_data = AttributionSerializer(attribution).data
            commission_id = attribution.commission_id
            validation_level = attribution.validation_level
            service_contractant_id = attribution.service_contractant_id

        # 3. Membres de la commission
        members_list = []
        if commission_id and validation_level:
            try:
                c_type = "internes" if validation_level == "interne" else "evaluation"
                url_m = (
                    f"{settings.CONTRACTANT_SERVICE_URL.rstrip('/')}"
                    f"/commissions-{c_type}/{commission_id}/membres"
                )
                resp_m = requests.get(url_m, headers=internal_service_headers(), timeout=3)
                if resp_m.status_code == 200:
                    raw_members = resp_m.json()
                    for m in raw_members:
                        uid = m.get("id_membre")
                        if not uid:
                            continue

                        # Charge actuelle = nombre d'attributions provisoires où validated_by = uid
                        workload = Attribution.objects.filter(
                            validated_by=uid, statut="provisoire"
                        ).count()

                        real_name = f"Membre #{uid}"
                        try:
                            hex_id = hex(uid)[2:].zfill(12)
                            member_uuid = f"00000000-0000-0000-0000-{hex_id}"
                            url_actor = (
                                f"{settings.ACTEURS_SERVICE_URL.rstrip('/')}/membres/{member_uuid}"
                            )
                            resp_actor = requests.get(
                                url_actor, headers=internal_service_headers(), timeout=1
                            )
                            if resp_actor.status_code == 200:
                                actor_data = resp_actor.json()
                                real_name = (
                                    f"{actor_data.get('nom', '')} {actor_data.get('prenom', '')}".strip()
                                    or real_name
                                )
                        except Exception:
                            pass

                        members_list.append({
                            "id_membre": uid,
                            "id_utilisateur": uid,
                            "nom": real_name,
                            "charge_actuelle": workload,
                            "disponibilite": "Disponible" if workload < 3 else "Chargé",
                        })
            except Exception as exc:
                logger.error("Error fetching commission members: %s", exc)

        return Response({
            "soumission": soum_data,
            "attribution": attribution_data,
            "commission_id": commission_id,
            "validation_level": validation_level,
            "service_contractant_id": service_contractant_id,
            "membres": members_list,
        })


# ---------------------------------------------------------------------------
# ValidationTransmitView kept for URL compat — now creates an Attribution
# ---------------------------------------------------------------------------

class ValidationTransmitView(APIView):
    """
    POST /transmettre-dossier/
    Crée une Attribution provisoire pour une soumission.
    Body: { "id_soumission": 123 }
    """

    def post(self, request, *args, **kwargs):
        soumission_id = request.data.get("id_soumission")
        if not soumission_id:
            return Response({"error": "id_soumission is required"}, status=400)
        try:
            soumission_id = int(soumission_id)
        except (ValueError, TypeError):
            return Response({"error": "id_soumission must be an integer"}, status=400)

        # Vérification doublon
        if Attribution.objects.filter(
            soumission__id_soumission=soumission_id, statut="provisoire"
        ).exists():
            return Response(
                {"error": "Une attribution provisoire existe déjà pour cette soumission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupérer la soumission
        try:
            soumission = Soumission.objects.get(id_soumission=soumission_id)
        except Soumission.DoesNotExist:
            return Response({"error": "Soumission non trouvée"}, status=404)

        # Récupérer l'appel pour déterminer service_contractant + commission
        appel_id = soumission.id_appel_offre
        service_contractant_id = None
        commission_id = None
        validation_level = "interne"

        try:
            appel_url = (
                f"{settings.APPELS_SERVICE_URL.rstrip('/')}/api/appels-offres/{appel_id}"
            )
            resp_a = requests.get(appel_url, headers=internal_service_headers(), timeout=3)
            if resp_a.status_code == 200:
                ao_data = resp_a.json()
                service_contractant_id = ao_data.get("id_service") or ao_data.get("id_service_contractant")
                commission_id = ao_data.get("commission_id") or ao_data.get("id_commission")
                # Determine validation_level from commission type if present
                validation_level = ao_data.get("validation_level", "interne")
        except Exception as exc:
            logger.warning("Error fetching appel for transmit: %s", exc)

        if not service_contractant_id or not commission_id:
            return Response(
                {"error": "Impossible de déterminer le service contractant ou la commission pour cet appel d'offres."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        attribution = Attribution.objects.create(
            soumission=soumission,
            appel_id=appel_id,
            service_contractant_id=service_contractant_id,
            commission_id=commission_id,
            validation_level=validation_level,
            statut="provisoire",
            validated_by=None,
        )

        logger.info("Attribution provisoire créée : %d pour soumission %d", attribution.pk, soumission_id)
        return Response(AttributionSerializer(attribution).data, status=status.HTTP_201_CREATED)
