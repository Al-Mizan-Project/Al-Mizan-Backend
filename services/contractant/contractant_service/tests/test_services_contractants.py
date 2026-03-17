"""
Tests for ServiceContractant endpoints:
  POST   /services-contractants
  GET    /services-contractants/{id}
  PATCH  /services-contractants/{id}
  DELETE /services-contractants/{id}
  GET    /services-contractants/{id}/membres
  GET    /services-contractants/{id}/commissions
"""
from django.test import TestCase
from rest_framework.test import APIClient

from contractant_service.models import (
    CommissionEvaluation,
    CommissionInterne,
    MembresCommissionEvaluation,
    MembresCommissionInterne,
    ServiceContractant,
)


def make_service(**kwargs):
    defaults = {
        "id_tutelle": 1,
        "categorie": "Ministère",
        "code_ordonnateur": "ORD-TEST",
    }
    defaults.update(kwargs)
    return ServiceContractant.objects.create(**defaults)


class ServiceContractantCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_returns_201(self):
        payload = {
            "id_tutelle": 1,
            "categorie": "Wilaya",
            "code_ordonnateur": "ORD-100",
        }
        response = self.client.post("/services-contractants", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id_service", data)
        self.assertEqual(data["code_ordonnateur"], "ORD-100")
        self.assertEqual(data["categorie"], "Wilaya")

    def test_create_missing_field_returns_400(self):
        payload = {"id_tutelle": 1}  # missing categorie and code_ordonnateur
        response = self.client.post("/services-contractants", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_persists_to_db(self):
        payload = {"id_tutelle": 2, "categorie": "Commune", "code_ordonnateur": "ORD-200"}
        self.client.post("/services-contractants", payload, format="json")
        self.assertTrue(ServiceContractant.objects.filter(code_ordonnateur="ORD-200").exists())


class ServiceContractantRetrieveTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service(code_ordonnateur="ORD-GET")

    def test_retrieve_existing_service(self):
        response = self.client.get(f"/services-contractants/{self.service.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_service"], self.service.pk)

    def test_retrieve_nonexistent_returns_404(self):
        response = self.client.get("/services-contractants/99999")
        self.assertEqual(response.status_code, 404)


class ServiceContractantUpdateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service(code_ordonnateur="ORD-PATCH")

    def test_patch_categorie(self):
        response = self.client.patch(
            f"/services-contractants/{self.service.pk}",
            {"categorie": "Nouvelle catégorie"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.categorie, "Nouvelle catégorie")

    def test_patch_code_ordonnateur(self):
        response = self.client.patch(
            f"/services-contractants/{self.service.pk}",
            {"code_ordonnateur": "ORD-UPDATED"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.code_ordonnateur, "ORD-UPDATED")

    def test_patch_nonexistent_returns_404(self):
        response = self.client.patch("/services-contractants/99999", {"categorie": "x"}, format="json")
        self.assertEqual(response.status_code, 404)


class ServiceContractantDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service(code_ordonnateur="ORD-DEL")

    def test_delete_returns_204(self):
        response = self.client.delete(f"/services-contractants/{self.service.pk}")
        self.assertEqual(response.status_code, 204)

    def test_delete_removes_from_db(self):
        pk = self.service.pk
        self.client.delete(f"/services-contractants/{pk}")
        self.assertFalse(ServiceContractant.objects.filter(pk=pk).exists())

    def test_delete_nonexistent_returns_404(self):
        response = self.client.delete("/services-contractants/99999")
        self.assertEqual(response.status_code, 404)


class ServiceContractantMembresTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service(code_ordonnateur="ORD-MEMBRES")
        self.comm_eval = CommissionEvaluation.objects.create(
            id_service=self.service,
            nom_comission="CE Test",
            categorie="Travaux",
        )
        self.comm_int = CommissionInterne.objects.create(
            id_service=self.service,
            nom_comission="CI Test",
            type_comission="parmanante",
        )
        MembresCommissionEvaluation.objects.create(id_comission=self.comm_eval, id_membre=10)
        MembresCommissionEvaluation.objects.create(id_comission=self.comm_eval, id_membre=20)
        MembresCommissionInterne.objects.create(id_commision_interne=self.comm_int, id_membre=10)
        MembresCommissionInterne.objects.create(id_commision_interne=self.comm_int, id_membre=30)

    def test_membres_returns_list(self):
        response = self.client.get(f"/services-contractants/{self.service.pk}/membres")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_membres_union_of_all_commissions(self):
        response = self.client.get(f"/services-contractants/{self.service.pk}/membres")
        ids = {item["id_membre"] for item in response.json()}
        # 10 is in both eval and interne, so union should be {10, 20, 30}
        self.assertSetEqual(ids, {10, 20, 30})


class ServiceContractantCommissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service(code_ordonnateur="ORD-COMMS")
        CommissionEvaluation.objects.create(
            id_service=self.service, nom_comission="CE-1", categorie="Fournitures",
        )
        CommissionInterne.objects.create(
            id_service=self.service, nom_comission="CI-1", type_comission="adhoc",
        )

    def test_commissions_returns_both_types(self):
        response = self.client.get(f"/services-contractants/{self.service.pk}/commissions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("commissions_evaluation", data)
        self.assertIn("commissions_internes", data)
        self.assertEqual(len(data["commissions_evaluation"]), 1)
        self.assertEqual(len(data["commissions_internes"]), 1)

    def test_commissions_nonexistent_service_returns_404(self):
        response = self.client.get("/services-contractants/99999/commissions")
        self.assertEqual(response.status_code, 404)
