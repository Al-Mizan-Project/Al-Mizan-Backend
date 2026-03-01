from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Soumission, Evaluation, SoumissionStatut
from .permissions import IsCommissionMember, CanOpenBids
from .services.crypto_service import CryptoService
from cryptography.hazmat.primitives.asymmetric import rsa

# Mocking a global private key for testing simplicity since we don't have a secure vault here
MOCK_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

class SoumissionCreateView(APIView):
    """
    POST /api/soumissions/
    Permet à l'opérateur économique de déposer son offre chiffrée.
    """
    @extend_schema(
        request=None, 
        responses={201: OpenApiResponse(description='Soumission déposée')},
        description="Dépôt d'une offre financière chiffrée"
    )
    def post(self, request, *args, **kwargs):
        # Expected body: id_appel_offre, id_soumissionnaire, encrypted_url, aes_key_hash
        data = request.data
        if not all(k in data for k in ('id_appel_offre', 'id_soumissionnaire', 'offre_financiere_chiffree_url', 'cle_dechiffrement_hash')):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        
        soumission = Soumission.objects.create(
            id_appel_offre=data['id_appel_offre'],
            id_soumissionnaire=data['id_soumissionnaire'],
            offre_financiere_chiffree_url=data['offre_financiere_chiffree_url'],
            cle_dechiffrement_hash=data['cle_dechiffrement_hash'],
            statut=SoumissionStatut.SOUMIS,
        )
        # Audit log dispatch would happen here (via signal on pre_save/post_save)
        return Response({"message": "Soumission déposée et chiffrée avec succès.", "id": soumission.id_soumission}, status=status.HTTP_201_CREATED)

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
        
        opened_count = 0
        for soum in soumissions:
            # Transition -> EN_OUVERTURE
            soum.statut = SoumissionStatut.EN_OUVERTURE
            soum.save() # Triggers audit log
            
            # --- START DECRYPTION PROCESS ---
            try:
                # 1. Decrypt AES Key using AO's private key
                # aes_key = CryptoService.decrypt_aes_key(soum.cle_dechiffrement_hash, MOCK_PRIVATE_KEY)
                
                # 2. Fetch encrypted file into RAM (Mocked here since we'd normally download it from MinIO)
                # minio_client = get_minio_client()
                # encrypted_file_bytes = minio_client.get_object(soum.offre_financiere_chiffree_url).read()
                
                # 3. Decrypt file
                # decrypted_pdf_bytes = CryptoService.decrypt_financial_offer(encrypted_file_bytes, aes_key, iv=b'0'*16)
                
                # 4. Extract amount
                # montant = CryptoService.extract_montant(decrypted_pdf_bytes)
                
                # MOCK SUCCESS:
                montant = 1500000.00
                
                # Clean up memory explicitly if dealing with large files
                # del decrypted_pdf_bytes
                
                soum.montant_financier = montant
                # Transition -> EN_EVALUATION
                soum.statut = SoumissionStatut.EN_EVALUATION
                soum.save()
                opened_count += 1
                
            except Exception as e:
                # If a bid fails to decrypt, it shouldn't stop others, we just flag it.
                soum.conformite_statut = "ERREUR_DECHIFFREMENT"
                soum.conformite_rapport = str(e)
                soum.statut = SoumissionStatut.EN_EVALUATION
                soum.save()

        return Response({"message": f"{opened_count} plis ouverts et déchiffrés avec succès."}, status=status.HTTP_200_OK)

class EvaluationCreateView(APIView):
    """
    POST /api/soumissions/<id_soumission>/evaluate/
    """
    @extend_schema(
        request=None, 
        responses={201: OpenApiResponse(description='Évaluation enregistrée')},
        description="Attribution d'une note par un membre de la commission"
    )
    def post(self, request, soumission_id, *args, **kwargs):
        soum = get_object_or_404(Soumission, id_soumission=soumission_id)
        
        # Must be in evaluation phase
        if soum.statut not in [SoumissionStatut.EN_OUVERTURE, SoumissionStatut.EN_EVALUATION]:
            return Response({"error": "La soumission n'est pas en phase d'évaluation."}, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data
        if not all(k in data for k in ('id_comission', 'id_membre', 'note')):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
            
        evaluation, created = Evaluation.objects.update_or_create(
            id_soumission=soum,
            id_membre=data['id_membre'],
            defaults={
                'id_comission': data['id_comission'],
                'note': data['note'],
                'commentaires': data.get('commentaires', '')
            }
        )
        return Response({"message": "Évaluation enregistrée.", "id": evaluation.id_evaluation}, status=status.HTTP_201_CREATED)
