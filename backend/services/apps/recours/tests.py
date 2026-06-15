from django.test import TestCase

from apps.recours.application.dto.recours_dto import RecoursResponseDTO
from apps.recours.presentation.serializers.recours_serializers import RecoursResponseSerializer


class RecoursMobileResponseContractTest(TestCase):
    def test_response_contains_optional_mobile_timeline_fields(self):
        dto = RecoursResponseDTO(
            id_recours=1,
            id_operateur_economique=10,
            id_validation=None,
            id_soumission=20,
            statut="DEPOSE",
            motif="Motif",
            decision=None,
            date_depot="2026-06-01T10:00:00Z",
            date_limite="2026-06-11T10:00:00Z",
            date_decision=None,
            traite_par=None,
            document_ids=[],
            date_fin_instruction=None,
            state_history=[],
            state_dates={"DEPOSE": "2026-06-01T10:00:00Z"},
        )

        data = RecoursResponseSerializer(dto.__dict__).data

        self.assertIn("date_fin_instruction", data)
        self.assertIn("state_history", data)
        self.assertIn("state_dates", data)
        self.assertEqual(data["state_history"], [])
        self.assertEqual(data["state_dates"]["DEPOSE"], "2026-06-01T10:00:00Z")
