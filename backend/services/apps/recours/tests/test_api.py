from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.recours.infrastructure.models.recours_model import RecoursModel


class RecoursApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_INTERNAL_SERVICE_TOKEN="dev-internal-token")
        self.url = "/api/recours/"

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
        self.assertEqual(RecoursModel.objects.count(), 1)

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

    def _create_recours(self, id_soumission, statut="DEPOSE"):
        return RecoursModel.objects.create(
            id_operateur_economique=101,
            id_validation=1,
            id_soumission=id_soumission,
            motif="Soumission rejetee a tort",
            statut=statut,
            date_depot=timezone.now(),
            date_limite=timezone.now() + timedelta(days=7),
        )

    def _mock_integrations(self):
        deadline = (timezone.now() + timedelta(days=7)).isoformat()
        return patch.multiple(
            "apps.recours.presentation.urls.recours_service",
            soumissions_client=FakeSoumissionsClient(),
            appels_client=FakeAppelsClient(deadline),
            notification_client=FakeNotificationClient(),
            audit_client=FakeAuditClient(),
        )


class FakeSoumissionsClient:
    def get_soumission(self, soumission_id):
        return {
            "id_soumission": soumission_id,
            "id_soumissionnaire": 101,
            "id_appel_offre": 10,
            "statut": "REJETEE",
        }


class FakeAppelsClient:
    def __init__(self, deadline):
        self.deadline = deadline

    def get_appel_offre(self, appel_id):
        return {
            "id_appel_offres": appel_id,
            "date_limite_soumission": self.deadline,
        }


class FakeNotificationClient:
    def send_notification(self, payload):
        return None


class FakeAuditClient:
    def log_action(self, payload):
        return None
