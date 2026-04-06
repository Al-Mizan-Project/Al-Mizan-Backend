"""
Tests for CommissionEvaluation endpoints:
  GET    /commissions-evaluation
  POST   /commissions-evaluation
  GET    /commissions-evaluation/{id}
  PATCH  /commissions-evaluation/{id}
  DELETE /commissions-evaluation/{id}
  GET    /commissions-evaluation/{id}/membres
  POST   /commissions-evaluation/{id}/membres/{membre_id}
  DELETE /commissions-evaluation/{id}/membres/{membre_id}
"""
from django.test import TestCase
from rest_framework.test import APIClient

from contractant_service.models import (
    CommissionEvaluation,
    MembresCommissionEvaluation,
    ServiceContractant,
)


def make_service():
    return ServiceContractant.objects.create(
        id_tutelle=1, categorie="Ministère", code_ordonnateur="ORD-CE-TEST"
    )


def make_commission(service=None, **kwargs):
    if service is None:
        service = make_service()
    defaults = {"nom_comission": "Commission Test", "categorie": "Travaux"}
    defaults.update(kwargs)
    return CommissionEvaluation.objects.create(id_service=service, **defaults)


class CommissionEvaluationListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        svc = make_service()
        make_commission(svc, nom_comission="CE-1")
        make_commission(svc, nom_comission="CE-2")

    def test_list_returns_200(self):
        response = self.client.get("/commissions-evaluation")
        self.assertEqual(response.status_code, 200)

    def test_list_returns_all_commissions(self):
        response = self.client.get("/commissions-evaluation")
        self.assertGreaterEqual(len(response.json()), 2)


class CommissionEvaluationCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service()

    def test_create_returns_201(self):
        payload = {
            "id_service": self.service.pk,
            "nom_comission": "Nouvelle Commission",
            "categorie": "Services",
        }
        response = self.client.post("/commissions-evaluation", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id_comission", data)
        self.assertEqual(data["nom_comission"], "Nouvelle Commission")

    def test_create_missing_nom_returns_400(self):
        payload = {"id_service": self.service.pk, "categorie": "Services"}
        response = self.client.post("/commissions-evaluation", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_invalid_service_returns_400(self):
        payload = {"id_service": 99999, "nom_comission": "X", "categorie": "Y"}
        response = self.client.post("/commissions-evaluation", payload, format="json")
        self.assertEqual(response.status_code, 400)


class CommissionEvaluationRetrieveTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission()

    def test_retrieve_returns_200_with_correct_data(self):
        response = self.client.get(f"/commissions-evaluation/{self.commission.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_comission"], self.commission.pk)

    def test_retrieve_nonexistent_returns_404(self):
        response = self.client.get("/commissions-evaluation/99999")
        self.assertEqual(response.status_code, 404)


class CommissionEvaluationUpdateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission()

    def test_patch_nom_comission(self):
        response = self.client.patch(
            f"/commissions-evaluation/{self.commission.pk}",
            {"nom_comission": "Nom Modifié"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.nom_comission, "Nom Modifié")

    def test_patch_categorie(self):
        response = self.client.patch(
            f"/commissions-evaluation/{self.commission.pk}",
            {"categorie": "Fournitures"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.categorie, "Fournitures")


class CommissionEvaluationDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission()

    def test_delete_returns_204(self):
        response = self.client.delete(f"/commissions-evaluation/{self.commission.pk}")
        self.assertEqual(response.status_code, 204)

    def test_delete_removes_from_db(self):
        pk = self.commission.pk
        self.client.delete(f"/commissions-evaluation/{pk}")
        self.assertFalse(CommissionEvaluation.objects.filter(pk=pk).exists())


class CommissionEvaluationMembresTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission()

    def test_list_membres_empty(self):
        response = self.client.get(f"/commissions-evaluation/{self.commission.pk}/membres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_add_membre_returns_201(self):
        response = self.client.post(
            f"/commissions-evaluation/{self.commission.pk}/membres/42"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            MembresCommissionEvaluation.objects.filter(
                id_comission=self.commission, id_membre=42
            ).exists()
        )

    def test_add_membre_idempotent(self):
        """Adding the same membre twice should not raise an error (get_or_create)."""
        self.client.post(f"/commissions-evaluation/{self.commission.pk}/membres/42")
        response = self.client.post(f"/commissions-evaluation/{self.commission.pk}/membres/42")
        self.assertIn(response.status_code, [200, 201])

    def test_list_membres_after_add(self):
        self.client.post(f"/commissions-evaluation/{self.commission.pk}/membres/10")
        self.client.post(f"/commissions-evaluation/{self.commission.pk}/membres/20")
        response = self.client.get(f"/commissions-evaluation/{self.commission.pk}/membres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_remove_membre_returns_204(self):
        MembresCommissionEvaluation.objects.create(id_comission=self.commission, id_membre=55)
        response = self.client.delete(f"/commissions-evaluation/{self.commission.pk}/membres/55")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            MembresCommissionEvaluation.objects.filter(
                id_comission=self.commission, id_membre=55
            ).exists()
        )

    def test_remove_nonexistent_membre_returns_404(self):
        response = self.client.delete(f"/commissions-evaluation/{self.commission.pk}/membres/9999")
        self.assertEqual(response.status_code, 404)

    def test_add_membre_to_nonexistent_commission_returns_404(self):
        response = self.client.post("/commissions-evaluation/99999/membres/1")
        self.assertEqual(response.status_code, 404)
