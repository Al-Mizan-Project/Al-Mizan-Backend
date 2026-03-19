import json

from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DetectionAnomalieIA
from .serializers import (
    CdcRedigerInputSerializer,
    CdcReviserInputSerializer,
    DetecterAnomaliesInputSerializer,
    DetectionAnomalieIASerializer,
    StatutExamenPatchSerializer,
    VerifierConformiteInputSerializer,
)
from .services.anomalies import detect_price_and_similarity_anomalies
from .services.cdc import generate_cdc_draft, revise_cdc_text
from .services.conformite import run_conformite_check
from .services.integrations import patch_document_ia_metadata, patch_soumission_conformite


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


class DetecterAnomaliesView(APIView):
    def post(self, request):
        serializer = DetecterAnomaliesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_appel_offre = serializer.validated_data["id_appel_offre"]
        soumissions = serializer.validated_data.get("soumissions", [])
        anomalies = detect_price_and_similarity_anomalies(soumissions)

        created = []
        for anomaly in anomalies:
            record = DetectionAnomalieIA.objects.create(
                id_appel_offre=id_appel_offre,
                id_soumission=anomaly["id_soumission"],
                type_anomalie=anomaly["type_anomalie"],
                niveau_severite=anomaly["niveau_severite"],
                score_confiance=anomaly["score_confiance"],
                details=anomaly["details"],
                statut_examen="A_REVOIR",
            )
            created.append(record)

        out = DetectionAnomalieIASerializer(created, many=True)
        return Response(
            {
                "id_appel_offre": id_appel_offre,
                "anomalies_detectees": len(created),
                "items": out.data,
            },
            status=status.HTTP_201_CREATED,
        )


class AnomalieListView(APIView):
    def get(self, request):
        queryset = DetectionAnomalieIA.objects.all()

        id_appel_offre = request.query_params.get("id_appel_offre")
        id_soumission = request.query_params.get("id_soumission")
        type_anomalie = request.query_params.get("type_anomalie")
        statut_examen = request.query_params.get("statut_examen")

        if id_appel_offre is not None:
            queryset = queryset.filter(id_appel_offre=id_appel_offre)
        if id_soumission is not None:
            queryset = queryset.filter(id_soumission=id_soumission)
        if type_anomalie:
            queryset = queryset.filter(type_anomalie=type_anomalie)
        if statut_examen:
            queryset = queryset.filter(statut_examen=statut_examen)

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
        anomaly.save(update_fields=["statut_examen"])

        out = DetectionAnomalieIASerializer(anomaly)
        return Response(out.data)


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