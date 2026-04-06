from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from .models import ComissionEvaluation, MembresCommissionEvaluation, Evaluation

class EvaluationsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.comission = ComissionEvaluation.objects.create(
            id_service=1,
            nom_comission="Commission Test",
            categorie="Fournitures"
        )
        self.membre1 = MembresCommissionEvaluation.objects.create(
            id_comission=self.comission,
            id_utilisateur=101
        )
        self.membre2 = MembresCommissionEvaluation.objects.create(
            id_comission=self.comission,
            id_utilisateur=102
        )

    @patch('requests.post')
    def test_decrypt_soumission_success(self, mock_post):
        # Mock the external Document service call
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "decrypted"}

        url = reverse('decrypt_soumission', args=[999])
        data = {"id_comission": self.comission.id_comission}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['details']['status'], "decrypted")
        mock_post.assert_called_once()

    def test_create_evaluation(self):
        url = reverse('create_evaluation')
        data = {
            "id_comission": self.comission.id_comission,
            "id_soumission": 999,
            "id_utilisateur": 101,
            "type": "technique",
            "note": 85,
            "commentaire": "Bonne offre technique"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Evaluation.objects.count(), 1)

    @patch('requests.post')
    def test_close_appel_offre_success(self, mock_post):
        # Création de plusieurs évaluations pour différentes soumissions
        # Soumission 999: moyenne 80
        Evaluation.objects.create(id_comission=self.comission, id_soumission=999, id_utilisateur=101, type="technique", note=90)
        Evaluation.objects.create(id_comission=self.comission, id_soumission=999, id_utilisateur=102, type="technique", note=70)
        
        # Soumission 888: moyenne 95 (sera le gagnant)
        Evaluation.objects.create(id_comission=self.comission, id_soumission=888, id_utilisateur=101, type="financière", note=100)
        Evaluation.objects.create(id_comission=self.comission, id_soumission=888, id_utilisateur=102, type="financière", note=90)

        # Mock the external Contrats service call
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id_contrat": 1}

        url = reverse('close_appel_offre', args=[555]) # appel_offre_id
        data = {"id_comission": self.comission.id_comission}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify it picked soumission 888 as winner
        self.assertEqual(response.data['gagnant']['id_soumission'], 888)
        self.assertEqual(response.data['gagnant']['moyenne'], 95)
        # Verify it called the contract service
        mock_post.assert_called_once()
