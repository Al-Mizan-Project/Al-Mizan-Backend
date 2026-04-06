"""
Tests for CommissionExterne endpoints:
  GET    /commissions-externes
  POST   /commissions-externes
  GET    /commissions-externes/{id}
  PATCH  /commissions-externes/{id}
  DELETE /commissions-externes/{id}
"""
from django.test import TestCase
from rest_framework.test import APIClient

from contractant_service.models import CommissionExterne


def make_commission_externe(**kwargs):
    defaults = {
        "nom_comission": "Commission Test",
        "niveau_competance": "Nationale",
        "seuils_competence_financiere": "> 500 000 000 DZD",
    }
    defaults.update(kwargs)
    return CommissionExterne.objects.create(**defaults)


class CommissionExterneListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        make_commission_externe(nom_comission="CE-EXT-1", niveau_competance="Nationale")
        make_commission_externe(nom_comission="CE-EXT-2", niveau_competance="Sectorielle")

    def test_list_returns_200(self):
        response = self.client.get("/commissions-externes")
        self.assertEqual(response.status_code, 200)

    def test_list_returns_all(self):
        response = self.client.get("/commissions-externes")
        self.assertGreaterEqual(len(response.json()), 2)

    def test_list_response_fields(self):
        response = self.client.get("/commissions-externes")
        first = response.json()[0]
        self.assertIn("id_comission_externe", first)
        self.assertIn("nom_comission", first)
        self.assertIn("niveau_competance", first)
        self.assertIn("seuils_competence_financiere", first)


class CommissionExterneCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_nationale_returns_201(self):
        payload = {
            "nom_comission": "Commission nationale",
            "niveau_competance": "Nationale",
            "seuils_competence_financiere": "> 500M DZD",
        }
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["niveau_competance"], "Nationale")

    def test_create_wilaya_returns_201(self):
        payload = {
            "nom_comission": "Commission de wilaya",
            "niveau_competance": "de Wilaya",
            "seuils_competence_financiere": "10M - 100M DZD",
        }
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_communale_returns_201(self):
        payload = {
            "nom_comission": "Commission communale",
            "niveau_competance": "Communale",
            "seuils_competence_financiere": "< 10M DZD",
        }
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_sectorielle_returns_201(self):
        payload = {
            "nom_comission": "Commission sectorielle",
            "niveau_competance": "Sectorielle",
            "seuils_competence_financiere": "100M - 500M DZD",
        }
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_invalid_niveau_returns_400(self):
        payload = {
            "nom_comission": "CE Bad",
            "niveau_competance": "InvalidNiveau",
            "seuils_competence_financiere": "X",
        }
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_missing_required_field_returns_400(self):
        payload = {"nom_comission": "CE Incomplete"}
        response = self.client.post("/commissions-externes", payload, format="json")
        self.assertEqual(response.status_code, 400)


class CommissionExterneRetrieveTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_externe()

    def test_retrieve_returns_200(self):
        response = self.client.get(f"/commissions-externes/{self.commission.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_comission_externe"], self.commission.pk)

    def test_retrieve_nonexistent_returns_404(self):
        response = self.client.get("/commissions-externes/99999")
        self.assertEqual(response.status_code, 404)


class CommissionExterneUpdateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_externe()

    def test_patch_nom(self):
        response = self.client.patch(
            f"/commissions-externes/{self.commission.pk}",
            {"nom_comission": "Nom Modifié"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.nom_comission, "Nom Modifié")

    def test_patch_niveau_competance(self):
        response = self.client.patch(
            f"/commissions-externes/{self.commission.pk}",
            {"niveau_competance": "Communale"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.niveau_competance, "Communale")

    def test_patch_invalid_niveau_returns_400(self):
        response = self.client.patch(
            f"/commissions-externes/{self.commission.pk}",
            {"niveau_competance": "InvalidNiveau"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class CommissionExterneDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_externe()

    def test_delete_returns_204(self):
        response = self.client.delete(f"/commissions-externes/{self.commission.pk}")
        self.assertEqual(response.status_code, 204)

    def test_delete_removes_from_db(self):
        pk = self.commission.pk
        self.client.delete(f"/commissions-externes/{pk}")
        self.assertFalse(CommissionExterne.objects.filter(pk=pk).exists())

    def test_delete_nonexistent_returns_404(self):
        response = self.client.delete("/commissions-externes/99999")
        self.assertEqual(response.status_code, 404)
