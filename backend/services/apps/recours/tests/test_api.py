from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.recours.infrastructure.models.recours_model import RecoursModel
from auth_service.models import Role

User=get_user_model()

class RecoursApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role = Role.objects.create(
            nom_role="TEST_ROLE"
        )
        self.user = User.objects.create_user(
            email="recours-user@test.com",
            password="testpassword",
            id_role=self.role,
        )
        
        self.client.force_authenticate(user=self.user)
        self.url = "/api/recours/"

    def test_requires_authenticated_actor(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        # DRF returns 401 (not 403) when no credentials are provided at all
        self.assertEqual(response.status_code, 401)

    def test_create_recours(self):
        with self._mock_integrations():
            response = self.client.post(
                self.url,
                {
                    "id_operateur_economique": 101,
                    "id_validation": 1,
                    "id_soumission": 55,
                    "motif": "Soumission rejetee a tort",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["statut"], "DEPOSE")
        self.assertEqual(response.data["id_soumission"], 55)
        self.assertIn("date_fin_instruction", response.data)
        self.assertIsNotNone(response.data["date_fin_instruction"])
        self.assertEqual(RecoursModel.objects.count(), 1)

    def test_date_limite_computed_from_ouverture_plis_plus_10_days(self):
        ouverture_plis = timezone.now() - timedelta(days=2)

        with self._mock_integrations(ouverture_plis=ouverture_plis):
            response = self.client.post(
                self.url,
                {
                    "id_operateur_economique": 101,
                    "id_validation": 1,
                    "id_soumission": 55,
                    "motif": "Soumission rejetee a tort",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        expected_date_limite = ouverture_plis + timedelta(days=10)
        actual_date_limite = response.data["date_limite"]
        self.assertEqual(actual_date_limite[:10], expected_date_limite.isoformat()[:10])

    def test_date_fin_instruction_is_date_limite_plus_15_days(self):
        ouverture_plis = timezone.now() - timedelta(days=2)

        with self._mock_integrations(ouverture_plis=ouverture_plis):
            response = self.client.post(
                self.url,
                {
                    "id_operateur_economique": 101,
                    "id_validation": 1,
                    "id_soumission": 55,
                    "motif": "Soumission rejetee a tort",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        expected_date_fin = ouverture_plis + timedelta(days=10) + timedelta(days=15)
        actual_date_fin = response.data["date_fin_instruction"]
        self.assertEqual(actual_date_fin[:10], expected_date_fin.isoformat()[:10])

    def test_create_recours_rejected_after_deadline(self):
        # ouverture_plis 11 days ago => date_limite is yesterday => should be rejected
        ouverture_plis = timezone.now() - timedelta(days=11)

        with self._mock_integrations(ouverture_plis=ouverture_plis):
            response = self.client.post(
                self.url,
                {
                    "id_operateur_economique": 101,
                    "id_validation": 1,
                    "id_soumission": 55,
                    "motif": "Soumission rejetee a tort",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecoursModel.objects.count(), 0)

    def test_list_recours(self):
        self._create_recours(id_soumission=55)
        self._create_recours(id_soumission=56, statut="EN_INSTRUCTION")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_get_recours_detail(self):
        recours = self._create_recours(id_soumission=55)

        response = self.client.get(f"{self.url}{recours.id_recours}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id_recours"], recours.id_recours)

    def test_instruire_recours(self):
        recours = self._create_recours(id_soumission=55)

        response = self.client.post(f"{self.url}{recours.id_recours}/instruire/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["statut"], "EN_INSTRUCTION")

    def test_prendre_decision(self):
        recours = self._create_recours(id_soumission=55, statut="EN_INSTRUCTION")

        response = self.client.post(
            f"{self.url}{recours.id_recours}/decision/",
            {"decision": "Recours recevable", "traite_par": 9001},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["statut"], "DECISION_PRISE")
        self.assertEqual(response.data["decision"], "Recours recevable")
        self.assertEqual(response.data["traite_par"], 9001)

    def test_accepter_recours_notifies_all_soumissionnaires(self):
        recours = self._create_recours(id_soumission=55, statut="DECISION_PRISE")
        fake_notification_client = FakeNotificationClient()

        # Must patch ALL clients on the singleton — accepter calls both
        # soumissions_client (to fetch soumissionnaires) and notification_client
        with self._mock_integrations(
            notification_client_override=fake_notification_client
        ):
            response = self.client.post(f"{self.url}{recours.id_recours}/accepter/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["statut"], "ACCEPTE")
        self.assertTrue(fake_notification_client.masse_called)
        sent_ids = fake_notification_client.masse_payload["utilisateur_ids"]
        self.assertIn(101, sent_ids)
        self.assertIn(102, sent_ids)

    def test_reject_duplicate_recours_for_same_soumission(self):
        self._create_recours(id_soumission=55)

        with self._mock_integrations():
            response = self.client.post(
                self.url,
                {
                    "id_operateur_economique": 101,
                    "id_validation": 1,
                    "id_soumission": 55,
                    "motif": "Deuxieme recours",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecoursModel.objects.count(), 1)

    # ---------------------------
    # HELPERS
    # ---------------------------

    def _create_recours(self, id_soumission, statut="DEPOSE"):
        now = timezone.now()
        date_limite = now + timedelta(days=7)
        return RecoursModel.objects.create(
            id_operateur_economique=101,
            id_validation=1,
            id_soumission=id_soumission,
            motif="Soumission rejetee a tort",
            statut=statut,
            date_depot=now,
            date_limite=date_limite,
            date_fin_instruction=date_limite + timedelta(days=15),
        )

    def _mock_integrations(self, ouverture_plis=None, notification_client_override=None):
        if ouverture_plis is None:
            # Default: 2 days ago so deadline (+10 days) is still 8 days in the future
            ouverture_plis = timezone.now() - timedelta(days=2)
        return patch.multiple(
            "apps.recours.presentation.urls.recours_service",
            soumissions_client=FakeSoumissionsClient(),
            appels_client=FakeAppelsClient(ouverture_plis),
            notification_client=notification_client_override or FakeNotificationClient(),
            audit_client=FakeAuditClient(),
        )


class FakeSoumissionsClient:
    def get_soumission(self, soumission_id):
        return {
            "id_soumission": soumission_id,
            "id_soumissionnaire": 101,
            "appel_id": 10,
            "statut": "REJETEE",
        }

    def get_soumissionnaires_by_appel(self, appel_id):
        return [
            {"id_soumissionnaire": 101},
            {"id_soumissionnaire": 102},
        ]


class FakeAppelsClient:
    def __init__(self, ouverture_plis):
        self.ouverture_plis = ouverture_plis

    def get_appel_offre(self, appel_id):
        return {
            "id_appel_offres": appel_id,
            "ouverture_plis_date": self.ouverture_plis.isoformat(),
        }


class FakeNotificationClient:
    def __init__(self):
        self.masse_called = False
        self.masse_payload = None

    def send_notification(self, payload):
        return None

    def send_bulk_notifications(self, payload):
        self.masse_called = True
        self.masse_payload = payload
        return None


class FakeAuditClient:
    def log_action(self, payload):
        return None
