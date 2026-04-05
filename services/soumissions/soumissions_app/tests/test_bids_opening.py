import pytest
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from soumissions_app.models import Soumission, SoumissionStatut
from soumissions_app.permissions import CanOpenBids, IsCommissionMember
from soumissions_app.services.crypto_service import CryptoService

from django.contrib.auth.models import User

@pytest.fixture
def api_client():
    client = APIClient()
    user = User.objects.create(username='testuser')
    client.force_authenticate(user=user)
    return client

@pytest.fixture
def setup_soumission(db):
    soum = Soumission.objects.create(
        id_appel_offre=10,
        id_soumissionnaire=100,
        offre_financiere_chiffree_url='http://minio/bucket/file.pdf.enc',
        cle_dechiffrement_hash='fake_encrypted_aes_key',
        statut=SoumissionStatut.SOUMIS,
    )
    return soum

@pytest.mark.django_db
def test_bid_opening_too_early(api_client, setup_soumission):
    """
    Test 1: Attempt to open bids BEFORE the legal date.
    Should return 403 Forbidden (simulating BidOpeningTooEarlyException).
    """
    # Mock CanOpenBids to return False (simulating date < now)
    with patch.object(CanOpenBids, 'has_permission', return_value=False):
        response = api_client.post(f'/api/soumissions/{setup_soumission.id_appel_offre}/open-bids/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_not_a_commission_member_opening(api_client, setup_soumission):
    """
    Test 2: Attempt to open bids by a non-commission member.
    Should return 403 Forbidden (simulating NotACommissionMemberException).
    """
    # Mock CanOpenBids to True, but IsCommissionMember to False
    with patch.object(CanOpenBids, 'has_permission', return_value=True):
        with patch.object(IsCommissionMember, 'has_permission', return_value=False):
            response = api_client.post(f'/api/soumissions/{setup_soumission.id_appel_offre}/open-bids/')
            assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_full_bids_opening_success(api_client, setup_soumission):
    """
    Test 3: Full state transition SOUMIS -> EN_OUVERTURE -> EN_EVALUATION
    with mocked private key and decrypt pipeline.
    """
    assert setup_soumission.statut == SoumissionStatut.SOUMIS
    assert setup_soumission.montant_financier is None

    mock_key = MagicMock()

    with patch.object(CanOpenBids, 'has_permission', return_value=True), \
         patch.object(IsCommissionMember, 'has_permission', return_value=True), \
         patch('soumissions_app.views.fetch_appel_private_key', return_value=b'fake-pem'), \
         patch('soumissions_app.views.load_pem_private_key', return_value=mock_key), \
         patch.object(CryptoService, 'decrypt_aes_key', return_value=b'fake-aes-key'), \
         patch('soumissions_app.views.download_encrypted_file', return_value=b'encrypted-data'), \
         patch.object(CryptoService, 'decrypt_financial_offer', return_value=b'decrypted-pdf'), \
         patch.object(CryptoService, 'extract_montant', return_value=1500000.00):

        response = api_client.post(f'/api/soumissions/{setup_soumission.id_appel_offre}/open-bids/')

        assert response.status_code == status.HTTP_200_OK
        assert "1 plis ouverts et déchiffrés" in response.data['message']

        setup_soumission.refresh_from_db()
        assert setup_soumission.statut == SoumissionStatut.EN_EVALUATION
        assert setup_soumission.montant_financier == 1500000.00
