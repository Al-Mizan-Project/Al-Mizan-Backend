import json
import logging

from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from .models import Soumission, SoumissionStatut
from .permissions import IsCommissionMember, CanOpenBids
from .serializers import SoumissionListSerializer, SoumissionCreateSerializer, EvaluationCreateSerializer
from .services.crypto_service import CryptoService
from .services.integrations import (
    validate_appel_offre,
    validate_document_ids,
    fetch_evaluations_for_soumission,
    create_evaluation,
    fetch_appel_private_key,
    download_encrypted_file,
)
from cryptography.hazmat.primitives.serialization import load_pem_private_key

logger = logging.getLogger(__name__)

class SoumissionCreateView(APIView):
    """
    POST /api/soumissions/
    Permet à l'opérateur économique de déposer son offre chiffrée.
    """
    def get(self, request, *args, **kwargs):
        queryset = Soumission.objects.all().order_by("-date_soumission")

        id_soumissionnaire = request.query_params.get("id_soumissionnaire")
        id_appel_offre = request.query_params.get("id_appel_offre")

        if id_soumissionnaire is not None:
            queryset = queryset.filter(id_soumissionnaire=id_soumissionnaire)
        if id_appel_offre is not None:
            queryset = queryset.filter(id_appel_offre=id_appel_offre)

        serializer = SoumissionListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SoumissionCreateSerializer,
        responses={201: OpenApiResponse(description='Soumission déposée')},
        description="Dépôt d'une offre financière chiffrée"
    )
    def post(self, request, *args, **kwargs):
        serializer = SoumissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Validate appel d'offre exists via Appels service
        appel_exists, _ = validate_appel_offre(data['id_appel_offre'])
        if not appel_exists:
            return Response({"error": f"Appel d'offre {data['id_appel_offre']} introuvable."}, status=status.HTTP_400_BAD_REQUEST)

        document_ids = data.get('document_ids', [])

        # Validate document IDs exist via Documents service
        if document_ids:
            docs_valid, missing = validate_document_ids(document_ids)
            if not docs_valid:
                return Response({"error": f"Documents introuvables: {missing}"}, status=status.HTTP_400_BAD_REQUEST)

        soumission = Soumission.objects.create(
            id_appel_offre=data['id_appel_offre'],
            id_soumissionnaire=data['id_soumissionnaire'],
            offre_financiere_chiffree_url=data['offre_financiere_chiffree_url'],
            cle_dechiffrement_hash=data['cle_dechiffrement_hash'],
            document_ids=document_ids,
            statut=SoumissionStatut.SOUMIS,
        )
        return Response({"message": "Soumission déposée et chiffrée avec succès.", "id": soumission.id_soumission}, status=status.HTTP_201_CREATED)


class SoumissionDetailView(APIView):
    """
    GET /api/soumissions/<id_soumission>/
    """

    def get(self, request, soumission_id, *args, **kwargs):
        soum = get_object_or_404(Soumission, id_soumission=soumission_id)
        serializer = SoumissionListSerializer(soum)
        return Response(serializer.data, status=status.HTTP_200_OK)

class OpenBidsView(APIView):
    """
    POST /api/soumissions/<id_appel_offre>/open-bids/
    """
    permission_classes = [CanOpenBids, IsCommissionMember]

    @extend_schema(
        request=None, 
        responses={200: OpenApiResponse(description='Plis ouverts'), 404: OpenApiResponse(description='Aucune soumission')},
        description="Cérémonie d'ouverture des plis et déchiffrement E2EE"
    )
    def post(self, request, id_appel_offre, *args, **kwargs):
        soumissions = Soumission.objects.filter(id_appel_offre=id_appel_offre, statut=SoumissionStatut.SOUMIS)
        if not soumissions.exists():
            return Response({"message": "Aucune soumission à ouvrir pour cet appel d'offres."}, status=status.HTTP_404_NOT_FOUND)

        # Fetch the appel d'offre's private RSA key for decryption
        private_key_pem = fetch_appel_private_key(id_appel_offre)
        private_key = None
        if private_key_pem:
            try:
                private_key = load_pem_private_key(private_key_pem, password=None)
            except Exception as exc:
                logger.error("Failed to load private key for AO %s: %s", id_appel_offre, exc)

        opened_count = 0
        for soum in soumissions:
            # Transition -> EN_OUVERTURE
            soum.statut = SoumissionStatut.EN_OUVERTURE
            soum.save()  # Triggers audit log

            try:
                montant = None

                if private_key:
                    # 1. Decrypt AES key using AO's private RSA key
                    aes_key = CryptoService.decrypt_aes_key(
                        soum.cle_dechiffrement_hash, private_key
                    )

                    # 2. Download encrypted file from MinIO / object storage
                    encrypted_file_bytes = download_encrypted_file(
                        soum.offre_financiere_chiffree_url
                    )
                    if encrypted_file_bytes is None:
                        raise RuntimeError(
                            f"Impossible de télécharger le fichier: {soum.offre_financiere_chiffree_url}"
                        )

                    # 3. Decrypt file with AES
                    decrypted_pdf_bytes = CryptoService.decrypt_financial_offer(
                        encrypted_file_bytes, aes_key, iv=b"\x00" * 16
                    )

                    # 4. Extract amount from decrypted PDF
                    montant = CryptoService.extract_montant(decrypted_pdf_bytes)

                    # Clean up sensitive data from memory
                    del decrypted_pdf_bytes
                    del encrypted_file_bytes
                else:
                    logger.warning(
                        "No private key available for AO %s — decryption skipped for soumission %s",
                        id_appel_offre,
                        soum.id_soumission,
                    )

                soum.montant_financier = montant
                soum.statut = SoumissionStatut.EN_EVALUATION
                soum.save()
                opened_count += 1

            except Exception as e:
                logger.error(
                    "Decryption failed for soumission %s: %s",
                    soum.id_soumission,
                    e,
                )
                soum.conformite_statut = "ERREUR_DECHIFFREMENT"
                soum.conformite_rapport = str(e)
                soum.statut = SoumissionStatut.EN_EVALUATION
                soum.save()

        return Response({"message": f"{opened_count} plis ouverts et déchiffrés avec succès."}, status=status.HTTP_200_OK)

class EvaluationCreateView(APIView):
    """
    GET  /api/soumissions/<id_soumission>/evaluate/ → list evaluations (from Evaluations service)
    POST /api/soumissions/<id_soumission>/evaluate/ → create evaluation (proxied to Evaluations service)
    """

    def get(self, request, soumission_id, *args, **kwargs):
        get_object_or_404(Soumission, id_soumission=soumission_id)
        evaluations = fetch_evaluations_for_soumission(soumission_id)
        return Response(evaluations, status=status.HTTP_200_OK)

    @extend_schema(
        request=EvaluationCreateSerializer,
        responses={201: OpenApiResponse(description='Évaluation enregistrée')},
        description="Attribution d'une note par un membre de la commission (proxied to Evaluations service)"
    )
    def post(self, request, soumission_id, *args, **kwargs):
        soum = get_object_or_404(Soumission, id_soumission=soumission_id)

        if soum.statut not in [SoumissionStatut.EN_OUVERTURE, SoumissionStatut.EN_EVALUATION]:
            return Response({"error": "La soumission n'est pas en phase d'évaluation."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EvaluationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        payload = {
            "id_comission": validated["id_comission"],
            "id_soumission": soumission_id,
            "id_utilisateur": validated["id_utilisateur"],
            "type": validated["type"],
            "note": validated["note"],
            "commentaire": validated.get("commentaire", ""),
        }

        resp_status, resp_body = create_evaluation(payload)
        return Response(resp_body, status=resp_status)


class SoumissionWithdrawView(APIView):
    """
    POST /api/soumissions/<id_soumission>/retirer/
    Permet au soumissionnaire de retirer sa soumission (avant ouverture des plis).
    """

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Soumission retirée')},
        description="Retrait d'une soumission avant l'ouverture des plis"
    )
    def post(self, request, soumission_id, *args, **kwargs):
        soum = get_object_or_404(Soumission, id_soumission=soumission_id)

        if soum.statut != SoumissionStatut.SOUMIS:
            return Response(
                {"error": "Seule une soumission au statut SOUMIS peut être retirée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        soum.statut = SoumissionStatut.RETRAITE
        soum.save()
        return Response(
            {"message": "Soumission retirée avec succès.", "id_soumission": soum.id_soumission, "statut": soum.statut},
            status=status.HTTP_200_OK,
        )


class SoumissionTerminerEvaluationView(APIView):
    """
    POST /api/soumissions/<id_soumission>/terminer-evaluation/
    Clôture la phase d'évaluation d'une soumission.
    """

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Évaluation terminée')},
        description="Clôture de la phase d'évaluation"
    )
    def post(self, request, soumission_id, *args, **kwargs):
        soum = get_object_or_404(Soumission, id_soumission=soumission_id)

        if soum.statut != SoumissionStatut.EN_EVALUATION:
            return Response(
                {"error": "La soumission doit être en phase EN_EVALUATION."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        soum.statut = SoumissionStatut.EVALU_TERMINEE
        soum.save()
        return Response(
            {"message": "Évaluation terminée.", "id_soumission": soum.id_soumission, "statut": soum.statut},
            status=status.HTTP_200_OK,
        )


class SoumissionConformitePatchView(APIView):
    """
    PATCH /api/soumissions/<soumission_id>/conformite/
    Permet au service IA de publier le résultat de conformité.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Conformité mise à jour')},
        description="Mise à jour du statut et rapport de conformité d'une soumission"
    )
    def patch(self, request, soumission_id, *args, **kwargs):
        # Inter-service call path: allow internal token for IA service while
        # preserving authenticated user access for backoffice/manual operations.
        is_authenticated_user = bool(getattr(request, "user", None) and request.user.is_authenticated)
        internal_token = request.headers.get("X-Internal-Service-Token", "")
        expected_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")

        if not is_authenticated_user:
            if not expected_token or internal_token != expected_token:
                return Response({"error": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        soum = get_object_or_404(Soumission, id_soumission=soumission_id)

        conformite_statut = request.data.get("conformite_statut")
        conformite_rapport = request.data.get("conformite_rapport")

        if conformite_statut is None:
            return Response(
                {"error": "conformite_statut est requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        soum.conformite_statut = conformite_statut
        if conformite_rapport is not None:
            soum.conformite_rapport = conformite_rapport
        soum.save(update_fields=["conformite_statut", "conformite_rapport"])

        return Response(
            {
                "id_soumission": soum.id_soumission,
                "conformite_statut": soum.conformite_statut,
                "conformite_rapport": soum.conformite_rapport,
            },
            status=status.HTTP_200_OK,
        )
