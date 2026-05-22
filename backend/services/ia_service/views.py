import json

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import logging
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
 
from .serializers import AideRedactionRequestSerializer, AideRedactionResponseSerializer
from .services.integrations import fetch_appel_details, fetch_appel_required_document_ids
from .services.redaction import run_aide_redaction_pipeline
 
logger = logging.getLogger(__name__)
from .models import DetectionAnomalieIA
from .serializers import (
    CdcRedigerInputSerializer,
    CdcReviserInputSerializer,
    DetecterAnomaliesAutoInputSerializer,
    DetecterAnomaliesInputSerializer,
    DetecterSaucissonnageAutoInputSerializer,
    DetecterSaucissonnageInputSerializer,
    StatutExamenPatchSerializer,
    VerifierConformiteAutomatiqueInputSerializer,
    VerifierConformiteInputSerializer,
)
from .services.anomalies import (
    detect_anomalies_appel,
    detect_anomalies_soumission,
    generate_anomaly_summary,
    ANOMALY_POINTS,
    _score_to_niveau,
)
from .services.cdc import generate_cdc_draft, revise_cdc_text
from .services.conformite import (
    build_provided_documents_from_metadata,
    build_required_documents_from_metadata,
    infer_document_type_from_text,
    run_conformite_check,
)
from .services.integrations import (
    fetch_document_binary,
    fetch_appel_details,
    fetch_appel_required_document_ids,
    fetch_appels_by_service_contractant,
    fetch_documents_metadata,
    fetch_soumission_details,
    fetch_soumissions_for_appel,
    patch_document_ia_metadata,
    patch_soumission_conformite,
)
from .services.ocr import extract_document_text, extract_documents_text_parallel
from .services.saucissonnage import detect_saucissonnage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_anomaly(record: DetectionAnomalieIA) -> dict:
    """Serialize a DetectionAnomalieIA record to the documented API shape."""
    return {
        "id_anomalie_ia": record.id_detection_anomalie_ia,
        "id_soumission": record.id_soumission,
        "type_anomalie": record.type_anomalie,
        "niveau_severite": record.niveau_severite,
        "score_confiance": float(record.score_confiance),
        "details": record.details,
        "statut_examen": record.statut_examen,
        "date_detection": record.date_detection.isoformat() if record.date_detection else None,
    }


def _serialize_anomaly_with_appel(record: DetectionAnomalieIA) -> dict:
    """Serialize including id_appel_offre (for list views)."""
    data = _serialize_anomaly(record)
    data["id_appel_offre"] = record.id_appel_offre
    return data


def _create_anomaly_record(id_appel_offre: int, anomaly: dict) -> DetectionAnomalieIA:
    return DetectionAnomalieIA.objects.create(
        id_appel_offre=id_appel_offre,
        id_soumission=anomaly.get("id_soumission"),
        type_anomalie=anomaly["type_anomalie"],
        niveau_severite=anomaly["niveau_severite"],
        score_confiance=anomaly["score_confiance"],
        details=anomaly["details"],
        soumissions_impliquees=anomaly.get("soumissions_impliquees"),
        statut_examen=DetectionAnomalieIA.StatutExamen.EN_ATTENTE,
    )


# ---------------------------------------------------------------------------
# Health & readiness
# ---------------------------------------------------------------------------
class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    def get(self, request):
        checks = {"database": False, "cache": False}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = True
        except Exception:
            checks["database"] = False

        try:
            cache.set("ia_ready_probe", "1", timeout=3)
            checks["cache"] = cache.get("ia_ready_probe") == "1"
        except Exception:
            checks["cache"] = False

        if all(checks.values()):
            return Response({"status": "ready", "checks": checks})
        return Response({"status": "degraded", "checks": checks}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Anomaly Detection — POST /ia/anomalies/detecter
# ---------------------------------------------------------------------------
class DetecterAnomaliesView(APIView):
    """
    POST /ia/anomalies/detecter

    Request:  { "id_soumission": 45, "id_appel_offre": 10 }

    Fetches the soumission and appel data from internal services,
    fetches all sibling soumissions for multi-rule analysis,
    then runs the full detection pipeline.

    Response:
    {
      "id_appel_offre": 10,
      "id_soumission": 45,
      "resume": {
        "total_anomalies": 3,
        "nb_errors": 1,
        "nb_warnings": 2,
        "score_severite_global": 65,
        "niveau_global": "ÉLEVÉ"
      },
      "anomalies": [ { "id_anomalie_ia": ..., "type_anomalie": ..., ... } ]
    }
    """

    def post(self, request):
        serializer = DetecterAnomaliesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_soumission = serializer.validated_data["id_soumission"]
        id_appel_offre = serializer.validated_data["id_appel_offre"]

        # ── Fetch target soumission ──────────────────────────────────────
        soumission_sync = fetch_soumission_details(id_soumission)
        if not soumission_sync.get("ok"):
            return Response(
                {
                    "error": "Impossible de récupérer la soumission depuis le service soumissions",
                    "details": soumission_sync.get("error", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        soumission = soumission_sync.get("soumission", {})

        # ── Fetch appel d'offre ──────────────────────────────────────────
        appel_sync = fetch_appel_details(id_appel_offre)
        if not appel_sync.get("ok"):
            return Response(
                {
                    "error": "Impossible de récupérer l'appel d'offres",
                    "details": appel_sync.get("error", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        appel = appel_sync.get("appel", {})

        # ── Fetch all soumissions for multi-rule analysis ────────────────
        all_sync = fetch_soumissions_for_appel(id_appel_offre)
        all_soumissions = all_sync.get("soumissions", [soumission]) if all_sync.get("ok") else [soumission]

        # ── Run detection ────────────────────────────────────────────────
        result = detect_anomalies_soumission(
            soumission=soumission,
            appel=appel,
            all_soumissions=all_soumissions,
        )

        # ── Persist ─────────────────────────────────────────────────────
        created = [_create_anomaly_record(id_appel_offre, a) for a in result["anomalies"]]

        return Response(
            {
                "id_appel_offre": id_appel_offre,
                "id_soumission": id_soumission,
                "resume": {
                    "total_anomalies": result["nb_errors"] + result["nb_warnings"],
                    "nb_errors": result["nb_errors"],
                    "nb_warnings": result["nb_warnings"],
                    "score_severite_global": result["score_severite_global"],
                    "niveau_global": result["niveau_global"],
                },
                "anomalies": [_serialize_anomaly(r) for r in created],
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Anomaly Detection — POST /ia/anomalies/detecter-auto
# ---------------------------------------------------------------------------
class DetecterAnomaliesAutoView(APIView):
    """
    POST /ia/anomalies/detecter-auto

    Request:  { "id_appel_offre": 10 }

    Fetches all soumissions + appel data automatically, then runs
    detection over the entire appel.

    Response:
    {
      "id_appel_offre": 10,
      "total_soumissions_analysees": 12,
      "resume_global": {
        "total_anomalies": 18,
        "score_severite_global": 78,
        "niveau_global": "CRITIQUE"
      },
      "anomalies": [ { "id_anomalie_ia": ..., "id_soumission": ..., ... } ]
    }
    """

    def post(self, request):
        serializer = DetecterAnomaliesAutoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_appel_offre = serializer.validated_data["id_appel_offre"]

        # ── Fetch all soumissions ────────────────────────────────────────
        soumissions_sync = fetch_soumissions_for_appel(id_appel_offre)
        if not soumissions_sync.get("ok"):
            return Response(
                {
                    "error": "Impossible de récupérer les soumissions depuis le service soumissions",
                    "details": soumissions_sync.get("error", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        soumissions = soumissions_sync.get("soumissions", [])
        if not soumissions:
            return Response(
                {
                    "id_appel_offre": id_appel_offre,
                    "total_soumissions_analysees": 0,
                    "resume_global": {
                        "total_anomalies": 0,
                        "score_severite_global": 0,
                        "niveau_global": "FAIBLE",
                    },
                    "anomalies": [],
                },
                status=status.HTTP_200_OK,
            )

        # ── Fetch appel d'offre ──────────────────────────────────────────
        appel_sync = fetch_appel_details(id_appel_offre)
        appel = appel_sync.get("appel", {}) if appel_sync.get("ok") else {}

        # ── Run detection ────────────────────────────────────────────────
        result = detect_anomalies_appel(soumissions=soumissions, appel=appel)

        # ── Persist ─────────────────────────────────────────────────────
        created = [_create_anomaly_record(id_appel_offre, a) for a in result["anomalies"]]

        return Response(
            {
                "id_appel_offre": id_appel_offre,
                "total_soumissions_analysees": result["total_soumissions_analysees"],
                "resume_global": result["resume_global"],
                "anomalies": [_serialize_anomaly(r) for r in created],
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Saucissonnage Detection — Market Splitting
# ---------------------------------------------------------------------------
class DetecterSaucissonnageView(APIView):
    """
    POST /ia/saucissonnage/detecter
    
    Detect market splitting (saucissonnage) patterns across multiple 
    appels d'offres. Accepts appel data directly in the request body.
    """

    def post(self, request):
        serializer = DetecterSaucissonnageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appels = serializer.validated_data["appels"]
        service_contractant_id = serializer.validated_data.get("id_service_contractant")

        result = detect_saucissonnage(
            appels,
            service_contractant_id=service_contractant_id,
        )

        anomalies = result["anomalies"]
        created = []
        for anomaly in anomalies:
            record = DetectionAnomalieIA.objects.create(
                id_appel_offre=anomaly.get("id_appel_offre", 0),
                id_soumission=anomaly.get("id_soumission"),
                type_anomalie=anomaly["type_anomalie"],
                niveau_severite=anomaly["niveau_severite"],
                score_confiance=anomaly["score_confiance"],
                details=anomaly["details"],
                appels_impliques=anomaly.get("appels_impliques"),
                statut_examen=DetectionAnomalieIA.StatutExamen.EN_ATTENTE,
            )
            created.append(record)

        from .serializers import DetectionAnomalieIASerializer
        out = DetectionAnomalieIASerializer(created, many=True)
        return Response(
            {
                "anomalies_detectees": len(created),
                "summary": result["summary"],
                "items": out.data,
            },
            status=status.HTTP_201_CREATED,
        )


class DetecterSaucissonnageAutoView(APIView):
    """
    POST /ia/saucissonnage/detecter-auto
    
    Automatically detect saucissonnage by fetching appels d'offres 
    data from the appels service for a given service contractant.
    """

    def post(self, request):
        serializer = DetecterSaucissonnageAutoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_service_contractant = serializer.validated_data["id_service_contractant"]

        # Build query params for date filtering
        params = {}
        if serializer.validated_data.get("date_debut"):
            params["date_debut"] = str(serializer.validated_data["date_debut"])
        if serializer.validated_data.get("date_fin"):
            params["date_fin"] = str(serializer.validated_data["date_fin"])

        # Fetch appels from the appels service
        appels_sync = fetch_appels_by_service_contractant(id_service_contractant, params=params)
        if not appels_sync.get("ok"):
            return Response(
                {
                    "error": "Impossible de récupérer les appels d'offres depuis le service appels",
                    "details": appels_sync.get("error", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        appels = appels_sync.get("appels", [])
        if not appels:
            return Response(
                {
                    "id_service_contractant": id_service_contractant,
                    "anomalies_detectees": 0,
                    "message": "Aucun appel d'offres trouvé pour ce service contractant",
                    "items": [],
                },
                status=status.HTTP_200_OK,
            )

        result = detect_saucissonnage(appels, service_contractant_id=id_service_contractant)

        anomalies = result["anomalies"]
        created = []
        for anomaly in anomalies:
            record = DetectionAnomalieIA.objects.create(
                id_appel_offre=anomaly.get("id_appel_offre", 0),
                id_soumission=anomaly.get("id_soumission"),
                type_anomalie=anomaly["type_anomalie"],
                niveau_severite=anomaly["niveau_severite"],
                score_confiance=anomaly["score_confiance"],
                details=anomaly["details"],
                appels_impliques=anomaly.get("appels_impliques"),
                statut_examen=DetectionAnomalieIA.StatutExamen.EN_ATTENTE,
            )
            created.append(record)

        from .serializers import DetectionAnomalieIASerializer
        out = DetectionAnomalieIASerializer(created, many=True)
        return Response(
            {
                "id_service_contractant": id_service_contractant,
                "appels_analyses": len(appels),
                "anomalies_detectees": len(created),
                "summary": result["summary"],
                "items": out.data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Anomaly Listing, Detail, Filtering
# ---------------------------------------------------------------------------
class AnomalieListView(APIView):
    """
    GET /ia/anomalies

    Query params: id_appel_offre, id_soumission, type_anomalie,
                  statut_examen, niveau_severite, categorie, page, page_size

    Response:
    {
      "page": 1, "page_size": 10, "total": 120,
      "anomalies": [ { "id_anomalie_ia": ..., "id_appel_offre": ..., ... } ]
    }
    """

    def get(self, request):
        queryset = DetectionAnomalieIA.objects.all()

        id_appel_offre = request.query_params.get("id_appel_offre")
        id_soumission = request.query_params.get("id_soumission")
        type_anomalie = request.query_params.get("type_anomalie")
        statut_examen = request.query_params.get("statut_examen")
        niveau_severite = request.query_params.get("niveau_severite")
        categorie = request.query_params.get("categorie")

        if id_appel_offre is not None:
            queryset = queryset.filter(id_appel_offre=id_appel_offre)
        if id_soumission is not None:
            queryset = queryset.filter(id_soumission=id_soumission)
        if type_anomalie:
            queryset = queryset.filter(type_anomalie=type_anomalie)
        if statut_examen:
            queryset = queryset.filter(statut_examen=statut_examen)
        if niveau_severite:
            queryset = queryset.filter(niveau_severite=niveau_severite)
        if categorie == "saucissonnage":
            queryset = queryset.filter(type_anomalie__startswith="SAUCISSONNAGE")
        elif categorie == "collusion":
            queryset = queryset.exclude(type_anomalie__startswith="SAUCISSONNAGE")

        # Pagination
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = max(1, min(100, int(request.query_params.get("page_size", 10))))
        except (ValueError, TypeError):
            page, page_size = 1, 10

        total = queryset.count()
        start = (page - 1) * page_size
        records = queryset[start: start + page_size]

        return Response({
            "page": page,
            "page_size": page_size,
            "total": total,
            "anomalies": [_serialize_anomaly_with_appel(r) for r in records],
        })


# ---------------------------------------------------------------------------
# GET /ia/anomalies/{anomalie_id}
# ---------------------------------------------------------------------------
class AnomalieDetailView(APIView):
    """
    GET /ia/anomalies/{anomalie_id}

    Response:
    {
      "id_anomalie_ia": 101, "id_soumission": 45, "id_appel_offre": 10,
      "type_anomalie": "...", "niveau_severite": "WARNING",
      "score_confiance": 0.92, "details": "...",
      "statut_examen": "EN_ATTENTE", "date_detection": "..."
    }
    """

    def get(self, request, anomalie_id):
        try:
            record = DetectionAnomalieIA.objects.get(id_detection_anomalie_ia=anomalie_id)
        except DetectionAnomalieIA.DoesNotExist:
            return Response({"error": "Anomalie non trouvée"}, status=status.HTTP_404_NOT_FOUND)

        return Response(_serialize_anomaly_with_appel(record))


# ---------------------------------------------------------------------------
# GET /ia/anomalies/appel/{appel_id}
# ---------------------------------------------------------------------------
class AnomalieParAppelView(APIView):
    """
    GET /ia/anomalies/appel/{appel_id}

    Response:
    {
      "id_appel_offre": 10, "total_anomalies": 8,
      "anomalies": [ { "id_anomalie_ia": ..., "id_soumission": ..., ... } ]
    }
    """

    def get(self, request, appel_id):
        queryset = DetectionAnomalieIA.objects.filter(id_appel_offre=appel_id)

        categorie = request.query_params.get("categorie")
        if categorie == "saucissonnage":
            queryset = queryset.filter(type_anomalie__startswith="SAUCISSONNAGE")
        elif categorie == "collusion":
            queryset = queryset.exclude(type_anomalie__startswith="SAUCISSONNAGE")

        records = list(queryset)
        return Response({
            "id_appel_offre": appel_id,
            "total_anomalies": len(records),
            "anomalies": [
                {
                    "id_anomalie_ia": r.id_detection_anomalie_ia,
                    "id_soumission": r.id_soumission,
                    "type_anomalie": r.type_anomalie,
                    "niveau_severite": r.niveau_severite,
                    "score_confiance": float(r.score_confiance),
                    "details": r.details,
                    "statut_examen": r.statut_examen,
                }
                for r in records
            ],
        })


# ---------------------------------------------------------------------------
# GET /ia/anomalies/appel/{appel_id}/summary
# ---------------------------------------------------------------------------
class AnomaliesSummaryView(APIView):
    """
    GET /ia/anomalies/appel/{appel_id}/summary

    Response:
    {
      "id_appel_offre": 10,
      "resume": {
        "total_anomalies": 18, "nb_errors": 5, "nb_warnings": 13,
        "score_severite_global": 78, "niveau_global": "CRITIQUE"
      },
      "repartition": { "PRIX_ANORMALEMENT_ELEVE": 6, ... },
      "details": "..."
    }
    """

    def get(self, request, appel_id):
        queryset = DetectionAnomalieIA.objects.filter(id_appel_offre=appel_id).exclude(
            type_anomalie__startswith="SAUCISSONNAGE"
        )
        records = list(queryset)

        anomalies_dicts = [
            {"type_anomalie": r.type_anomalie, "niveau_severite": r.niveau_severite,
             "score_confiance": float(r.score_confiance)}
            for r in records
        ]

        summary = generate_anomaly_summary(anomalies_dicts, soumissions_count=len(records))

        repartition = summary.pop("repartition_par_type", {})
        summary.pop("repartition_par_severite", None)

        return Response({
            "id_appel_offre": appel_id,
            "resume": {
                "total_anomalies": summary["total_anomalies"],
                "nb_errors": summary["nb_errors"],
                "nb_warnings": summary["nb_warnings"],
                "score_severite_global": summary["score_severite_global"],
                "niveau_global": summary["niveau_global"],
            },
            "repartition": repartition,
            "details": summary["recommandation"],
        })


# ---------------------------------------------------------------------------
# GET /ia/anomalies/soumission/{soumission_id}
# ---------------------------------------------------------------------------
class AnomalieParSoumissionView(APIView):
    """
    GET /ia/anomalies/soumission/{soumission_id}

    Response:
    {
      "id_soumission": 45,
      "anomalies": [ { "id_anomalie_ia": ..., "type_anomalie": ..., ... } ],
      "total_anomalies": 2
    }
    """

    def get(self, request, soumission_id):
        records = list(
            DetectionAnomalieIA.objects.filter(id_soumission=soumission_id)
        )
        return Response({
            "id_soumission": soumission_id,
            "anomalies": [
                {
                    "id_anomalie_ia": r.id_detection_anomalie_ia,
                    "type_anomalie": r.type_anomalie,
                    "niveau_severite": r.niveau_severite,
                    "score_confiance": float(r.score_confiance),
                    "details": r.details,
                    "statut_examen": r.statut_examen,
                }
                for r in records
            ],
            "total_anomalies": len(records),
        })


# ---------------------------------------------------------------------------
# PATCH /ia/anomalies/{anomalie_id}/statut-examen
# ---------------------------------------------------------------------------
class AnomalieStatutExamenPatchView(APIView):
    """
    PATCH /ia/anomalies/{anomalie_id}/statut-examen

    Request:  { "statut_examen": "VALIDE", "commentaire": "Anomalie confirmée après vérification" }

    Response:
    {
      "id_anomalie_ia": 101, "statut_examen": "VALIDE",
      "details": "Statut mis à jour : ...",
      "date_mise_a_jour": "2026-05-02T12:30:00Z"
    }
    """

    def patch(self, request, anomalie_id):
        serializer = StatutExamenPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            record = DetectionAnomalieIA.objects.get(id_detection_anomalie_ia=anomalie_id)
        except DetectionAnomalieIA.DoesNotExist:
            return Response({"error": "Anomalie non trouvée"}, status=status.HTTP_404_NOT_FOUND)

        new_statut = serializer.validated_data["statut_examen"]
        commentaire = serializer.validated_data.get("commentaire_examen", "")
        now = timezone.now()

        record.statut_examen = new_statut
        record.commentaire_examen = commentaire
        record.date_examen = now
        record.save(update_fields=["statut_examen", "commentaire_examen", "date_examen"])

        statut_label = dict(DetectionAnomalieIA.StatutExamen.choices).get(new_statut, new_statut)
        details_msg = f"Statut mis à jour : anomalie {statut_label.lower()} par l'analyste."
        if commentaire:
            details_msg += f" Commentaire : {commentaire}"

        return Response({
            "id_anomalie_ia": record.id_detection_anomalie_ia,
            "statut_examen": record.statut_examen,
            "commentaire_examen": record.commentaire_examen,
            "date_examen": record.date_examen.isoformat() if record.date_examen else None,
            "details": details_msg,
            "date_mise_a_jour": now.isoformat(),
        })


# ---------------------------------------------------------------------------
# Conformité (unchanged)
# ---------------------------------------------------------------------------
class VerifierConformiteSoumissionView(APIView):
    def post(self, request, soumission_id):
        serializer = VerifierConformiteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        required_documents = serializer.validated_data.get("required_documents", [])
        provided_documents = serializer.validated_data.get("provided_documents", [])
        conformite_statut, rapport = run_conformite_check(required_documents, provided_documents)

        soumission_sync = patch_soumission_conformite(
            id_soumission=soumission_id,
            conformite_statut=conformite_statut,
            conformite_rapport=rapport,
        )

        target_doc_status = "VALID" if conformite_statut == "CONFORME" else "ANOMALY"
        document_sync = []
        for doc in provided_documents:
            doc_id = doc.get("id_document")
            if doc_id is None:
                continue
            result = patch_document_ia_metadata(
                id_document=int(doc_id),
                ia_verif_statut=target_doc_status,
                ia_verif_details=rapport,
            )
            document_sync.append({"id_document": int(doc_id), **result})

        response_payload = {
            "id_soumission": soumission_id,
            "conformite_statut": conformite_statut,
            "conformite_rapport": rapport,
            "next_action": "VALIDATION_HUMAINE" if conformite_statut != "CONFORME" else "EVALUATION_TECHNIQUE",
            "integrations": {
                "soumission_sync": soumission_sync,
                "documents_sync": document_sync,
            },
        }
        return Response(response_payload)


class VerifierConformiteSoumissionAutoView(APIView):
    def post(self, request, soumission_id):
        serializer = VerifierConformiteAutomatiqueInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_appel_offre = serializer.validated_data["id_appel_offre"]
        provided_document_ids = serializer.validated_data.get("provided_document_ids", [])
        enforce_validity_checks = serializer.validated_data.get("enforce_validity_checks", True)
        perform_ocr = serializer.validated_data.get("perform_ocr", True)

        required_documents = serializer.validated_data.get("required_documents", [])
        required_document_ids = serializer.validated_data.get("required_document_ids", [])

        if required_documents:
            required_documents = [
                infer_document_type_from_text(label)
                for label in required_documents
                if str(label).strip()
            ]
            required_documents = sorted({item for item in required_documents if item})
        else:
            if not required_document_ids:
                required_ids_sync = fetch_appel_required_document_ids(id_appel_offre)
                if not required_ids_sync.get("ok"):
                    return Response(
                        {
                            "error": "Unable to fetch required documents from Appels service",
                            "details": required_ids_sync.get("error", "unknown"),
                        },
                        status=status.HTTP_502_BAD_GATEWAY,
                    )
                required_document_ids = required_ids_sync.get("document_ids", [])

            required_meta_sync = fetch_documents_metadata(required_document_ids)
            if not required_meta_sync.get("ok"):
                return Response(
                    {
                        "error": "Unable to fetch required document metadata from Documents service",
                        "details": required_meta_sync.get("error", "unknown"),
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            required_documents = build_required_documents_from_metadata(required_meta_sync.get("documents", []))

        provided_meta_sync = fetch_documents_metadata(provided_document_ids)
        if not provided_meta_sync.get("ok"):
            return Response(
                {
                    "error": "Unable to fetch provided document metadata from Documents service",
                    "details": provided_meta_sync.get("error", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        provided_documents = build_provided_documents_from_metadata(
            provided_meta_sync.get("documents", []),
            enforce_validity_checks=enforce_validity_checks,
        )

        ocr_processed = 0
        ocr_succeeded = 0
        if perform_ocr:
            original_docs_by_id = {
                doc.get("id_document"): doc
                for doc in provided_meta_sync.get("documents", [])
                if doc.get("id_document") is not None
            }

            ocr_tasks = []
            ocr_task_indices = []

            for idx, projected_doc in enumerate(provided_documents):
                doc_id = projected_doc.get("id_document")
                original_doc = original_docs_by_id.get(doc_id)
                if doc_id is not None and original_doc is not None:
                    binary = fetch_document_binary(int(doc_id))
                    if binary.get("ok"):
                        ocr_tasks.append(
                            (binary.get("content", b""), str(original_doc.get("nom", "")))
                        )
                        ocr_task_indices.append(idx)

            ocr_processed = len(ocr_tasks)
            ocr_results = extract_documents_text_parallel(ocr_tasks)

            enriched_provided = [{**doc} for doc in provided_documents]
            for task_pos, doc_idx in enumerate(ocr_task_indices):
                extraction = ocr_results[task_pos]
                if extraction.get("used"):
                    ocr_succeeded += 1
                    inferred_from_ocr = infer_document_type_from_text(extraction.get("text", ""))
                    if inferred_from_ocr:
                        enriched_provided[doc_idx]["type_document"] = inferred_from_ocr
            provided_documents = enriched_provided

        conformite_statut, rapport = run_conformite_check(required_documents, provided_documents)

        soumission_sync = patch_soumission_conformite(
            id_soumission=soumission_id,
            conformite_statut=conformite_statut,
            conformite_rapport=rapport,
        )

        document_sync = []

        return Response(
            {
                "id_soumission": soumission_id,
                "id_appel_offre": id_appel_offre,
                "conformite_statut": conformite_statut,
                "conformite_rapport": rapport,
                "next_action": "VALIDATION_HUMAINE" if conformite_statut != "CONFORME" else "EVALUATION_TECHNIQUE",
                "analysis_context": {
                    "required_documents": required_documents,
                    "required_document_ids": required_document_ids,
                    "provided_document_ids": provided_document_ids,
                    "provided_documents_detected": provided_documents,
                    "ocr": {
                        "enabled": bool(perform_ocr),
                        "processed": ocr_processed,
                        "succeeded": ocr_succeeded,
                    },
                    "missing_metadata_required_ids": required_meta_sync.get("missing_ids", [])
                    if not serializer.validated_data.get("required_documents")
                    else [],
                    "missing_metadata_provided_ids": provided_meta_sync.get("missing_ids", []),
                },
                "integrations": {
                    "soumission_sync": soumission_sync,
                    "documents_sync": document_sync,
                },
            }
        )


# ---------------------------------------------------------------------------
# CDC — Cahier des Charges (unchanged)
# ---------------------------------------------------------------------------
class CdcRedigerView(APIView):
    def post(self, request):
        serializer = CdcRedigerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sections = generate_cdc_draft(
            besoin=serializer.validated_data["besoin"],
            type_procedure=serializer.validated_data["type_procedure"],
            contraintes=serializer.validated_data.get("contraintes", []),
        )
        return Response(
            {
                "sections": sections,
                "texte_cdc": "\n\n".join([f"[{title.upper()}]\n{content}" for title, content in sections.items()]),
            }
        )


class CdcReviserView(APIView):
    def post(self, request):
        serializer = CdcReviserInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = revise_cdc_text(serializer.validated_data["texte"])
        result["alerts"] = sorted(set(result["alerts"]))
        result["audit_payload"] = json.dumps(
            {
                "alerts_count": len(result["alerts"]),
                "needs_human_validation": result["needs_human_validation"],
            },
            ensure_ascii=True,
        )
        return Response(result)


# ---------------------------------------------------------------------------
# Helper — construire le contexte appel depuis la réponse du service appels
# ---------------------------------------------------------------------------
 
def _build_contexte_from_appel_dict(appel: dict) -> dict:
    """
    Mappe les champs retournés par fetch_appel_details()
    vers le dict de contexte attendu par run_aide_redaction_pipeline().
    Les noms de champs correspondent au modèle AppelOffres du service appels.
    """
    montant = appel.get("montant_estime")
    try:
        montant = float(montant) if montant is not None else None
    except (TypeError, ValueError):
        montant = None
 
    return {
        "titre": appel.get("titre", ""),
        "description": appel.get("description", ""),
        "type_procedure": appel.get("type_procedure", ""),
        "type_prestation": appel.get("type_prestation", ""),
        "montant_estime": montant,
        "wilaya": appel.get("wilaya", ""),
        "poids_technique": int(appel.get("poids_technique", 50)),
        "poids_financier": int(appel.get("poids_financier", 50)),
        "qualification_category": appel.get("qualification_category", ""),
        "minimum_experience_years": int(appel.get("minimum_experience_years", 0)),
        "minimum_revenue_da": int(appel.get("minimum_revenue_da", 0)),
        "participation_conditions": appel.get("participation_conditions") or [],
        "required_docs_admin": appel.get("required_docs_admin") or [],
        "required_docs_tech": appel.get("required_docs_tech") or [],
    }
 
 
def _document_belongs_to_appel(id_document: int, id_appel_offres: int) -> bool:
    """
    Vérifie que le document CDC est bien lié à l'appel d'offres
    en interrogeant le service appels.
    """
    result = fetch_appel_required_document_ids(id_appel_offres)
    if not result.get("ok"):
        # Si le service est indisponible, on laisse passer avec un warning
        logger.warning(
            "Cannot verify document ownership for appel=%s (service unavailable): %s",
            id_appel_offres,
            result.get("error"),
        )
        return True
    return id_document in result.get("document_ids", [])
 
 
# ---------------------------------------------------------------------------
# Vue principale
# ---------------------------------------------------------------------------
class AideRedactionView(APIView):
    parser_classes = [MultiPartParser, FormParser]  # pour recevoir le fichier
    permission_classes = [AllowAny]
    def post(self, request):
        req_serializer = AideRedactionRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(
                {"detail": "Paramètres invalides.", "errors": req_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = req_serializer.validated_data
        fichier = data.pop("fichier_cdc")

        # Extraire le texte du CDC
        from .services.ocr import extract_document_text
        ocr = extract_document_text(fichier.read(), fichier.name)

        # Analyser
        from .services.redaction import analyse_cdc
        rapport = analyse_cdc(ocr["text"], contexte_appel=data)
        rapport["_pipeline"] = {
            "ocr_engine": ocr["engine"],
            "char_count": len(ocr["text"]),
            "ocr_used": ocr["used"],
        }

        return Response(rapport, status=status.HTTP_200_OK)
