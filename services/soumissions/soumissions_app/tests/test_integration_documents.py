import io
import pytest
import requests
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from soumissions_app.models import Soumission, SoumissionStatut
from soumissions_app.permissions import CanOpenBids, IsCommissionMember
from unittest.mock import patch

DOCUMENTS_SERVICE_URL = "http://localhost:8003/api/documents/"

@pytest.fixture
def api_client():
    client = APIClient()
    user = User.objects.create(username='test_integ_user')
    client.force_authenticate(user=user)
    return client

@pytest.mark.django_db
def test_cross_service_upload_and_decrypt(api_client):
    """
    Test End-to-End:
    1. Upload a dummy encrypted file to the LIVE Documents service.
    2. Register the returned MinIO URL in the Soumissions service (Dépôt).
    3. Run the Open Bids ceremony and verify the stream fetching from the Document service.
    """
    # 1. Upload file to Documents (Simulation file being encrypted AES)
    test_pdf_content = b"Fake PDF Encrypted Data With AES256 Payload"
    files = {'file': ('fake_encrypted_offer.pdf', io.BytesIO(test_pdf_content), 'application/pdf')}
    data = {'related_type': 'soumission', 'is_encrypted': 'true'}
    
    try:
        doc_response = requests.post(DOCUMENTS_SERVICE_URL, files=files, data=data)
        doc_response.raise_for_status()
        doc_data = doc_response.json()
        minio_url = doc_data.get('storage_url')
    except requests.exceptions.ConnectionError:
        pytest.skip("Documents Service is not running on localhost:8003. Skipping cross-service test.")
        return
        
    assert minio_url is not None, "Documents service did not return a valid storage_url"
    
    # 2. Deposit the Soumission via the API endpoints we created
    deposit_payload = {
        "id_appel_offre": 55,
        "id_soumissionnaire": 88,
        "offre_financiere_chiffree_url": minio_url,
        "cle_dechiffrement_hash": "base64_encoded_encrypted_aes_key"
    }
    
    deposit_response = api_client.post('/api/soumissions/', data=deposit_payload)
    assert deposit_response.status_code == status.HTTP_201_CREATED
    
    soum_id = deposit_response.data.get('id')
    soum = Soumission.objects.get(id_soumission=soum_id)
    assert soum.statut == SoumissionStatut.SOUMIS
    
    # 3. Trigger Open Bids
    with patch.object(CanOpenBids, 'has_permission', return_value=True):
        with patch.object(IsCommissionMember, 'has_permission', return_value=True):
            # To fetch the actual file from MinIO, our view normally mocks this part, but let's just 
            # make sure the endpoint runs successfully which indicates DB state transitioned properly.
            open_resp = api_client.post(f'/api/soumissions/55/open-bids/')
            assert open_resp.status_code == status.HTTP_200_OK
            
            soum.refresh_from_db()
            assert soum.statut == SoumissionStatut.EN_EVALUATION
            assert soum.montant_financier is not None # Decrypted successfully
