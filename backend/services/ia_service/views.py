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
    DetectionAnomalieIASerializer,
    StatutExamenPatchSerializer,
    VerifierConformiteAutomatiqueInputSerializer,
    VerifierConformiteInputSerializer,
)
from .services.anomalies import (
    detect_price_and_similarity_anomalies,
    generate_anomaly_summary,
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
    fetch_soumissions_for_appel,
    patch_document_ia_metadata,
    patch_soumission_conformite,
)
from .services.ocr import extract_document_text, extract_documents_text_parallel
from .services.saucissonnage import detect_saucissonnage


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
# Anomaly Detection — Collusion & Price-fixing
# ---------------------------------------------------------------------------
class DetecterAnomaliesView(APIView):
    """
    POST /ia/anomalies/detecter
    
    Detect anomalies (collusion, price-fixing, bid manipulation) in 
    soumissions for a given appel d'offres.
    
    Accepts soumission data directly in the request body.
    """

    def post(self, request):
        serializer = DetecterAnomaliesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_appel_offre = serializer.validated_data["id_appel_offre"]
        soumissions = serializer.validated_data.get("soumissions", [])
        montant_estime = serializer.validated_data.get("montant_estime")
        historical_wins = serializer.validated_data.get("historical_wins")

        anomalies = detect_price_and_similarity_anomalies(
            soumissions,
            montant_estime=montant_estime,
            historical_wins=historical_wins,
        )

        created = []
        for anomaly in anomalies:
            record = DetectionAnomalieIA.objects.create(
                id_appel_offre=id_appel_offre,
                id_soumission=anomaly.get("id_soumission"),
                type_anomalie=anomaly["type_anomalie"],
                niveau_severite=anomaly["niveau_severite"],
                score_confiance=anomaly["score_confiance"],
                details=anomaly["details"],
                soumissions_impliquees=anomaly.get("soumissions_impliquees"),
                statut_examen="A_REVOIR",
            )
            created.append(record)

        summary = generate_anomaly_summary(anomalies, len(soumissions))

        out = DetectionAnomalieIASerializer(created, many=True)
        return Response(
            {
                "id_appel_offre": id_appel_offre,
                "anomalies_detectees": len(created),
                "summary": summary,
                "items": out.data,
            },
            status=status.HTTP_201_CREATED,
        )


class DetecterAnomaliesAutoView(APIView):
    """
    POST /ia/anomalies/detecter-auto
    
    Automatically detect anomalies by fetching soumission data from 
    the soumissions service. Only requires the appel d'offres ID.
    """

    def post(self, request):
        serializer = DetecterAnomaliesAutoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_appel_offre = serializer.validated_data["id_appel_offre"]
        montant_estime = serializer.validated_data.get("montant_estime")

        # Fetch soumissions from the soumissions service
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
                    "anomalies_detectees": 0,
                    "message": "Aucune soumission trouvée pour cet appel d'offres",
                    "items": [],
                },
                status=status.HTTP_200_OK,
            )

        # If montant_estime is not provided, try to fetch it from appels service
        if montant_estime is None:
            appel_sync = fetch_appel_details(id_appel_offre)
            if appel_sync.get("ok") and appel_sync.get("appel"):
                try:
                    montant_estime = appel_sync["appel"].get("montant_estime")
                except (AttributeError, KeyError):
                    pass

        anomalies = detect_price_and_similarity_anomalies(
            soumissions,
            montant_estime=montant_estime,
        )

        created = []
        for anomaly in anomalies:
            record = DetectionAnomalieIA.objects.create(
                id_appel_offre=id_appel_offre,
                id_soumission=anomaly.get("id_soumission"),
                type_anomalie=anomaly["type_anomalie"],
                niveau_severite=anomaly["niveau_severite"],
                score_confiance=anomaly["score_confiance"],
                details=anomaly["details"],
                soumissions_impliquees=anomaly.get("soumissions_impliquees"),
                statut_examen="A_REVOIR",
            )
            created.append(record)

        summary = generate_anomaly_summary(anomalies, len(soumissions))

        out = DetectionAnomalieIASerializer(created, many=True)
        return Response(
            {
                "id_appel_offre": id_appel_offre,
                "soumissions_analysees": len(soumissions),
                "anomalies_detectees": len(created),
                "summary": summary,
                "items": out.data,
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
                statut_examen="A_REVOIR",
            )
            created.append(record)

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
                statut_examen="A_REVOIR",
            )
            created.append(record)

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
    def get(self, request):
        queryset = DetectionAnomalieIA.objects.all()

        id_appel_offre = request.query_params.get("id_appel_offre")
        id_soumission = request.query_params.get("id_soumission")
        type_anomalie = request.query_params.get("type_anomalie")
        statut_examen = request.query_params.get("statut_examen")
        niveau_severite = request.query_params.get("niveau_severite")
        categorie = request.query_params.get("categorie")  # collusion / saucissonnage

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

        serializer = DetectionAnomalieIASerializer(queryset, many=True)
        return Response(serializer.data)


class AnomalieDetailView(APIView):
    def get(self, request, anomalie_id):
        try:
            anomaly = DetectionAnomalieIA.objects.get(id_detection_anomalie_ia=anomalie_id)
        except DetectionAnomalieIA.DoesNotExist:
            return Response({"error": "Anomalie non trouvee"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DetectionAnomalieIASerializer(anomaly)
        return Response(serializer.data)


class AnomalieParAppelView(APIView):
    def get(self, request, appel_id):
        queryset = DetectionAnomalieIA.objects.filter(id_appel_offre=appel_id)

        # Apply optional category filter
        categorie = request.query_params.get("categorie")
        if categorie == "saucissonnage":
            queryset = queryset.filter(type_anomalie__startswith="SAUCISSONNAGE")
        elif categorie == "collusion":
            queryset = queryset.exclude(type_anomalie__startswith="SAUCISSONNAGE")

        serializer = DetectionAnomalieIASerializer(queryset, many=True)
        return Response(serializer.data)


class AnomalieParSoumissionView(APIView):
    def get(self, request, soumission_id):
        queryset = DetectionAnomalieIA.objects.filter(id_soumission=soumission_id)
        serializer = DetectionAnomalieIASerializer(queryset, many=True)
        return Response(serializer.data)


class AnomalieStatutExamenPatchView(APIView):
    def patch(self, request, anomalie_id):
        serializer = StatutExamenPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            anomaly = DetectionAnomalieIA.objects.get(id_detection_anomalie_ia=anomalie_id)
        except DetectionAnomalieIA.DoesNotExist:
            return Response({"error": "Anomalie non trouvee"}, status=status.HTTP_404_NOT_FOUND)

        anomaly.statut_examen = serializer.validated_data["statut_examen"]
        anomaly.commentaire_examen = serializer.validated_data.get("commentaire_examen", "")
        anomaly.date_examen = timezone.now()

        anomaly.save(update_fields=["statut_examen", "commentaire_examen", "date_examen"])

        out = DetectionAnomalieIASerializer(anomaly)
        return Response(out.data)


class AnomaliesSummaryView(APIView):
    """
    GET /ia/anomalies/summary/<appel_id>
    
    Get a summary/dashboard view of all anomalies for an appel d'offres.
    """

    def get(self, request, appel_id):
        queryset = DetectionAnomalieIA.objects.filter(id_appel_offre=appel_id)
        anomalies_data = DetectionAnomalieIASerializer(queryset, many=True).data

        # Build summary
        by_type = {}
        by_severity = {}
        affected_soumissions = set()

        for a in anomalies_data:
            t = a.get("type_anomalie", "UNKNOWN")
            s = a.get("niveau_severite", "UNKNOWN")
            by_type[t] = by_type.get(t, 0) + 1
            by_severity[s] = by_severity.get(s, 0) + 1
            if a.get("id_soumission"):
                affected_soumissions.add(a["id_soumission"])

        total = len(anomalies_data)
        severity_weights = {"CRITIQUE": 4, "ELEVEE": 3, "MOYEN": 2, "FAIBLE": 1}
        weighted_score = sum(
            severity_weights.get(a.get("niveau_severite", ""), 1)
            * float(a.get("score_confiance", 0))
            for a in anomalies_data
        )

        max_possible = max(total * 4, 1)
        risk_score = min(100, int((weighted_score / max_possible) * 100))

        if risk_score >= 70:
            risk_level = "CRITIQUE"
        elif risk_score >= 40:
            risk_level = "ELEVE"
        elif risk_score >= 20:
            risk_level = "MOYEN"
        elif total > 0:
            risk_level = "FAIBLE"
        else:
            risk_level = "AUCUN"

        collusion_count = sum(1 for a in anomalies_data if not a.get("type_anomalie", "").startswith("SAUCISSONNAGE"))
        saucissonnage_count = sum(1 for a in anomalies_data if a.get("type_anomalie", "").startswith("SAUCISSONNAGE"))

        return Response({
            "id_appel_offre": appel_id,
            "total_anomalies": total,
            "soumissions_affectees": len(affected_soumissions),
            "repartition_par_type": by_type,
            "repartition_par_severite": by_severity,
            "anomalies_collusion": collusion_count,
            "anomalies_saucissonnage": saucissonnage_count,
            "score_risque": risk_score,
            "niveau_risque": risk_level,
            "anomalies": anomalies_data,
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
            # Build lookup by id_document to avoid misalignment when
            # build_provided_documents_from_metadata() filters out entries.
            original_docs_by_id = {
                doc.get("id_document"): doc
                for doc in provided_meta_sync.get("documents", [])
                if doc.get("id_document") is not None
            }

            # ── Phase 1: Fetch binaries & collect OCR tasks ─────────────
            ocr_tasks = []          # (index, payload, filename)
            ocr_task_indices = []   # indices into provided_documents

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

            # ── Phase 2: Run OCR in parallel ────────────────────────────
            ocr_results = extract_documents_text_parallel(ocr_tasks)

            # ── Phase 3: Enrich provided_documents with OCR results ─────
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