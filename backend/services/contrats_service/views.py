import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.permissions import (
    AuthenticatedOrInternalServicePermission,
    internal_service_headers,
)

from .models import Validation, Contrat, DocumentContrat
from .serializers import (
    ValidationSerializer,
    ValidationUpdateSerializer,
    ContratSerializer,
    ContratUpdateSerializer,
    DocumentContratSerializer,
)


# ---------------------------------------------------------------------------
# Common / health
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


class ProtectedAPIView(APIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


class ProtectedListCreateAPIView(ListCreateAPIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


class ProtectedRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


# ---------------------------------------------------------------------------
# Validation CRUD
# ---------------------------------------------------------------------------

class ValidationListCreateView(ProtectedListCreateAPIView):
    queryset = Validation.objects.all().order_by("id_validation")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ValidationSerializer
        return ValidationSerializer


class ValidationRetrieveUpdateDeleteView(ProtectedRetrieveUpdateDestroyAPIView):
    queryset = Validation.objects.all()
    lookup_field = "id_validation"
    lookup_url_kwarg = "validation_id"

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ValidationUpdateSerializer
        return ValidationSerializer


class ValidationApproveView(ProtectedAPIView):
    """POST /validations/{validation_id}/approuver"""

    def post(self, request, validation_id):
        validation = Validation.objects.filter(id_validation=validation_id).first()
        if not validation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        validation.is_validated = True
        validation.save(update_fields=["is_validated", "updated_at"])
        return Response(ValidationSerializer(validation).data)


class ValidationRejectView(ProtectedAPIView):
    """POST /validations/{validation_id}/rejeter"""

    def post(self, request, validation_id):
        validation = Validation.objects.filter(id_validation=validation_id).first()
        if not validation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        commentaire = request.data.get("commentaire", "")
        validation.is_validated = False
        if commentaire:
            validation.commentaire = commentaire
        validation.save(update_fields=["is_validated", "commentaire", "updated_at"])
        return Response(ValidationSerializer(validation).data)


# ---------------------------------------------------------------------------
# Contrat CRUD
# ---------------------------------------------------------------------------

class ContratListCreateView(ProtectedListCreateAPIView):
    queryset = Contrat.objects.all().order_by("id_contrat")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ContratSerializer
        return ContratSerializer


class ContratRetrieveUpdateDeleteView(ProtectedRetrieveUpdateDestroyAPIView):
    queryset = Contrat.objects.all()
    lookup_field = "id_contrat"
    lookup_url_kwarg = "contrat_id"

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ContratUpdateSerializer
        return ContratSerializer


class ContratSignView(ProtectedAPIView):
    """POST /contrats/{contrat_id}/signer"""

    def post(self, request, contrat_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if contrat.statut == "signe" or contrat.date_signature is not None:
            return Response(
                {"detail": "Le contrat est déjà signé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contrat.statut = "signe"
        contrat.date_signature = timezone.now()
        contrat.save(update_fields=["statut", "date_signature", "updated_at"])
        return Response(ContratSerializer(contrat).data)


# ---------------------------------------------------------------------------
# Documents ↔ Contrat
# ---------------------------------------------------------------------------

class ContratDocumentsListView(ProtectedAPIView):
    """GET /contrats/{contrat_id}/documents"""

    def get(self, request, contrat_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        links = DocumentContrat.objects.filter(id_contrat=contrat).order_by("id_document")
        document_ids = list(links.values_list("id_document", flat=True))

        # Attempt to enrich with document details from documents service
        documents_service_url = getattr(settings, "DOCUMENTS_SERVICE_URL", "")
        enriched = []
        if documents_service_url:
            timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
            for doc_id in document_ids:
                url = f"{documents_service_url.rstrip('/')}/documents/{doc_id}"
                try:
                    resp = requests.get(
                        url,
                        timeout=timeout,
                        headers=internal_service_headers(),
                    )
                    if resp.status_code == 200:
                        enriched.append(resp.json())
                    else:
                        enriched.append({"id_document": doc_id})
                except requests.RequestException:
                    enriched.append({"id_document": doc_id})
        else:
            enriched = [{"id_document": doc_id} for doc_id in document_ids]

        return Response(enriched)


class ContratDocumentDetailView(ProtectedAPIView):
    """
    POST   /contrats/{contrat_id}/documents/{document_id}
    DELETE /contrats/{contrat_id}/documents/{document_id}
    """

    def post(self, request, contrat_id, document_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(
                {"detail": "Contrat not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate document exists via documents service
        documents_service_url = getattr(settings, "DOCUMENTS_SERVICE_URL", "")
        if documents_service_url:
            timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
            url = f"{documents_service_url.rstrip('/')}/documents/{document_id}"
            try:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers=internal_service_headers(),
                )
                if resp.status_code != 200:
                    return Response(
                        {"detail": "Document not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            except requests.RequestException:
                return Response(
                    {"detail": "Unable to validate document at this time."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        _, created = DocumentContrat.objects.get_or_create(
            id_contrat=contrat, id_document=document_id
        )
        if created:
            return Response(
                {"id_contrat": contrat_id, "id_document": document_id},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"id_contrat": contrat_id, "id_document": document_id},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, contrat_id, document_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deleted_count, _ = DocumentContrat.objects.filter(
            id_contrat=contrat, id_document=document_id
        ).delete()
        if deleted_count == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Cross‑entity lookups
# ---------------------------------------------------------------------------

class SoumissionContratView(ProtectedAPIView):
    """GET /soumissions/{soumission_id}/contrat"""

    def get(self, request, soumission_id):
        contrat = Contrat.objects.filter(id_soumission=soumission_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ContratSerializer(contrat).data)


class SoumissionValidationsView(ProtectedAPIView):
    """GET /soumissions/{soumission_id}/validations"""

    def get(self, request, soumission_id):
        validations = Validation.objects.filter(
            id_soumission=soumission_id
        ).order_by("-updated_at")
        return Response(ValidationSerializer(validations, many=True).data)
