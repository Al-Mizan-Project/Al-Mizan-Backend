"""
Tests for CommissionInterne endpoints:
  GET    /commissions-internes
  POST   /commissions-internes
  GET    /commissions-internes/{id}
  PATCH  /commissions-internes/{id}
  DELETE /commissions-internes/{id}
  GET    /commissions-internes/{id}/membres
  POST   /commissions-internes/{id}/membres/{membre_id}
  DELETE /commissions-internes/{id}/membres/{membre_id}
"""
from django.test import TestCase
from rest_framework.test import APIClient

from contractant_service.models import (
    CommissionInterne,
    MembresCommissionInterne,
    ServiceContractant,
)


def make_service():
    return ServiceContractant.objects.create(
        id_tutelle=1, categorie="Commune", code_ordonnateur="ORD-CI-TEST"
    )


def make_commission_interne(service=None, **kwargs):
    if service is None:
        service = make_service()
    defaults = {"nom_comission": "CI Test", "type_comission": "parmanante"}
    defaults.update(kwargs)
    return CommissionInterne.objects.create(id_service=service, **defaults)


class CommissionInterneListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        svc = make_service()
        make_commission_interne(svc, nom_comission="CI-1", type_comission="parmanante")
        make_commission_interne(svc, nom_comission="CI-2", type_comission="adhoc")

    def test_list_returns_200(self):
        response = self.client.get("/commissions-internes")
        self.assertEqual(response.status_code, 200)

    def test_list_returns_all(self):
        response = self.client.get("/commissions-internes")
        self.assertGreaterEqual(len(response.json()), 2)


class CommissionInterneCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.service = make_service()

    def test_create_permanente_returns_201(self):
        payload = {
            "id_service": self.service.pk,
            "nom_comission": "CI Permanente",
            "type_comission": "parmanante",
        }
        response = self.client.post("/commissions-internes", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type_comission"], "parmanante")

    def test_create_adhoc_returns_201(self):
        payload = {
            "id_service": self.service.pk,
            "nom_comission": "CI Ad-Hoc",
            "type_comission": "adhoc",
        }
        response = self.client.post("/commissions-internes", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type_comission"], "adhoc")

    def test_create_invalid_type_returns_400(self):
        payload = {
            "id_service": self.service.pk,
            "nom_comission": "CI Bad",
            "type_comission": "invalide",
        }
        response = self.client.post("/commissions-internes", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_missing_fields_returns_400(self):
        payload = {"id_service": self.service.pk}
        response = self.client.post("/commissions-internes", payload, format="json")
        self.assertEqual(response.status_code, 400)


class CommissionInterneRetrieveTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_interne()

    def test_retrieve_returns_200(self):
        response = self.client.get(f"/commissions-internes/{self.commission.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_comission_interne"], self.commission.pk)

    def test_retrieve_nonexistent_returns_404(self):
        response = self.client.get("/commissions-internes/99999")
        self.assertEqual(response.status_code, 404)


class CommissionInterneUpdateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_interne()

    def test_patch_nom(self):
        response = self.client.patch(
            f"/commissions-internes/{self.commission.pk}",
            {"nom_comission": "Nouveau Nom"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.nom_comission, "Nouveau Nom")

    def test_patch_type(self):
        response = self.client.patch(
            f"/commissions-internes/{self.commission.pk}",
            {"type_comission": "adhoc"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.type_comission, "adhoc")


class CommissionInterneDeleteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_interne()

    def test_delete_returns_204(self):
        response = self.client.delete(f"/commissions-internes/{self.commission.pk}")
        self.assertEqual(response.status_code, 204)

    def test_delete_removes_from_db(self):
        pk = self.commission.pk
        self.client.delete(f"/commissions-internes/{pk}")
        self.assertFalse(CommissionInterne.objects.filter(pk=pk).exists())


class CommissionInterneMembresTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.commission = make_commission_interne()

    def test_list_membres_empty(self):
        response = self.client.get(f"/commissions-internes/{self.commission.pk}/membres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_add_membre_returns_201(self):
        response = self.client.post(f"/commissions-internes/{self.commission.pk}/membres/7")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            MembresCommissionInterne.objects.filter(
                id_commision_interne=self.commission, id_membre=7
            ).exists()
        )

    def test_add_membre_idempotent(self):
        self.client.post(f"/commissions-internes/{self.commission.pk}/membres/7")
        response = self.client.post(f"/commissions-internes/{self.commission.pk}/membres/7")
        self.assertIn(response.status_code, [200, 201])

    def test_list_membres_after_add(self):
        self.client.post(f"/commissions-internes/{self.commission.pk}/membres/1")
        self.client.post(f"/commissions-internes/{self.commission.pk}/membres/2")
        response = self.client.get(f"/commissions-internes/{self.commission.pk}/membres")
        self.assertEqual(len(response.json()), 2)

    def test_remove_membre_returns_204(self):
        MembresCommissionInterne.objects.create(id_commision_interne=self.commission, id_membre=99)
        response = self.client.delete(f"/commissions-internes/{self.commission.pk}/membres/99")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            MembresCommissionInterne.objects.filter(
                id_commision_interne=self.commission, id_membre=99
            ).exists()
        )

    def test_remove_nonexistent_membre_returns_404(self):
        response = self.client.delete(f"/commissions-internes/{self.commission.pk}/membres/9999")
        self.assertEqual(response.status_code, 404)

    def test_cascade_delete_removes_membres(self):
        MembresCommissionInterne.objects.create(id_commision_interne=self.commission, id_membre=5)
        pk = self.commission.pk
        self.commission.delete()
        self.assertFalse(MembresCommissionInterne.objects.filter(id_commision_interne_id=pk).exists())
