import json
from django.conf import settings
from django.test import TestCase, override_settings
from django.core.cache import cache

from appels_service.models import AchatSimple, AppelOffres, DocumentsAppel
from acteurs_service.models import CommissionExterne, Organisation, NiveauCompetence, TypeEntite


def make_appel(**kwargs):
    defaults = {
        "id_service_contractant": 1,
        "reference": "AO-TEST-001",
        "titre": "Test appel d'offres",
        "description": "Description test",
        "type_procedure": "publique",
        "type_prestation": "travaux",
        "visibilite": "public",
        "wilaya": "Alger",
        "secteur": "BTP",
        "localisation": "Hussein Dey",
        "montant_estime": "10000000.00",
        "poids_technique": 40,
        "poids_financier": 60,
        "statut": "non_valide",
    }
    defaults.update(kwargs)
    return AppelOffres.objects.create(**defaults)


@override_settings(
    CONTRACTANT_SERVICE_URL="",
    ACTEURS_SERVICE_URL="",
    DOCUMENTS_SERVICE_URL="",
    INTERNAL_SERVICE_TOKEN="test-internal-token",
)
class AppelsServiceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client.defaults["HTTP_X_INTERNAL_SERVICE_TOKEN"] = settings.INTERNAL_SERVICE_TOKEN

        Organisation.objects.all().delete()
        CommissionExterne.objects.all().delete()

        national_org = Organisation.objects.create(
            nom_officiel="Commission Nationale",
            type_entite=TypeEntite.COMMISSION_EXTERNE,
            wilaya="Alger",
            secteur="BTP",
        )
        CommissionExterne.objects.create(
            organisation=national_org,
            numero_agrement="NAT-001",
            specialite="Generale",
            niveau_competence=NiveauCompetence.NATIONAL,
            seuil="10000000.00",
        )

        sector_org = Organisation.objects.create(
            nom_officiel="Commission Sectorielle BTP",
            type_entite=TypeEntite.COMMISSION_EXTERNE,
            wilaya="Alger",
            secteur="BTP",
        )
        CommissionExterne.objects.create(
            organisation=sector_org,
            numero_agrement="SEC-001",
            specialite="BTP",
            niveau_competence=NiveauCompetence.SECTORIELLE,
            seuil="5000000.00",
        )

        wilaya_org = Organisation.objects.create(
            nom_officiel="Commission Wilaya Alger",
            type_entite=TypeEntite.COMMISSION_EXTERNE,
            wilaya="Alger",
            secteur="BTP",
        )
        CommissionExterne.objects.create(
            organisation=wilaya_org,
            numero_agrement="WIL-001",
            specialite="Alger",
            niveau_competence=NiveauCompetence.WILAYA,
            seuil="1000000.00",
        )


# List
class AppelOffresListTest(AppelsServiceTestCase):
    def test_list_empty(self):
        response = self.client.get("/appels-offres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_returns_created_items(self):
        make_appel(reference="AO-LST-001")
        make_appel(reference="AO-LST-002")
        response = self.client.get("/appels-offres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_list_fields_present(self):
        make_appel(reference="AO-FLD-001")
        data = self.client.get("/appels-offres").json()[0]
        for field in [
            "id_appel_offres",
            "reference",
            "titre",
            "statut",
            "type_procedure",
            "type_prestation",
            "visibilite",
            "wilaya",
            "localisation",
            "location",
        ]:
            self.assertIn(field, data)


# Create
class AppelOffresCreateTest(AppelsServiceTestCase):
    def _post(self, payload):
        return self.client.post(
            "/appels-offres",
            json.dumps(payload),
            content_type="application/json",
        )

    def test_create_valid(self):
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AO-CRT-001",
            "titre": "Creation test",
            "type_procedure": "Consultation",
            "type_prestation": "fournitures",
            "visibilite": "public",
            "location": "Zone industrielle Rouiba",
            "montant_estime": "5000000",
            "id_operateur_choisi": 42,
            "id_doc_besoin": 5001,
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["reference"], "AO-CRT-001")
        self.assertEqual(data["type_prestation"], "fournitures")
        self.assertEqual(data["localisation"], "Zone industrielle Rouiba")
        self.assertEqual(data["statut"], "valide")

    def test_create_missing_required(self):
        response = self._post({"id_service_contractant": 1})
        self.assertEqual(response.status_code, 400)

    def test_create_duplicate_reference(self):
        make_appel(reference="AO-DUP-001")
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AO-DUP-001",
            "titre": "Duplicate",
            "type_procedure": "Consultation",
        })
        self.assertEqual(response.status_code, 400)

    def test_create_returns_id(self):
        response = self._post({
            "id_service_contractant": 2,
            "reference": "AO-ID-001",
            "titre": "ID test",
            "type_procedure": "Appel d'offres restreint",
            "type_prestation": "etudes",
            "wilaya": "Alger",
            "secteur": "BTP",
            "montant_estime": "6000000",
            "id_doc_cdc": 3001,
            "id_doc_justification": 3002,
            "operateurs_invites": [101, 102],
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn("id_appel_offres", response.json())


class AppelOffresPrivateVisibilityTest(AppelsServiceTestCase):
    def _post(self, payload):
        return self.client.post(
            "/appels-offres",
            json.dumps(payload),
            content_type="application/json",
        )

    def test_create_private_requires_invited_operators(self):
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AO-PRV-001",
            "titre": "AO privee sans invites",
            "type_procedure": "Appel d'offres restreint",
            "type_prestation": "services",
            "visibilite": "prive",
            "wilaya": "Alger",
            "secteur": "BTP",
            "montant_estime": "6000000",
            "id_doc_cdc": 3101,
            "id_doc_justification": 3102,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("operateurs_invites", response.json().get("error", {}).get("details", {}))

    def test_create_private_with_invited_operators(self):
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AO-PRV-002",
            "titre": "AO privee avec operateurs",
            "type_procedure": "Appel d'offres restreint",
            "type_prestation": "services",
            "visibilite": "prive",
            "wilaya": "Alger",
            "secteur": "BTP",
            "montant_estime": "6000000",
            "id_doc_cdc": 3201,
            "id_doc_justification": 3202,
            "operateurs_invites": [10, 20, 20],
        })
        self.assertEqual(response.status_code, 201)

        appel_id = response.json()["id_appel_offres"]
        details = self.client.get(f"/appels-offres/{appel_id}")
        self.assertEqual(details.status_code, 200)
        payload = details.json()

        self.assertEqual(payload["visibilite"], "prive")
        self.assertEqual(len(payload["operateurs_invites"]), 2)
        returned_ids = {item["id_operateur_economique"] for item in payload["operateurs_invites"]}
        self.assertEqual(returned_ids, {10, 20})

    def test_create_public_refuses_invited_operators(self):
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AO-PUB-INV-001",
            "titre": "AO public avec invites",
            "type_procedure": "Appel d'offres ouvert",
            "type_prestation": "travaux",
            "visibilite": "public",
            "wilaya": "Alger",
            "secteur": "BTP",
            "montant_estime": "12000000",
            "operateurs_invites": [11, 12],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("operateurs_invites", response.json().get("error", {}).get("details", {}))


# Retrieve
class AppelOffresRetrieveTest(AppelsServiceTestCase):
    def setUp(self):
        super().setUp()
        self.appel = make_appel(reference="AO-RTV-001")

    def test_retrieve_existing(self):
        response = self.client.get(f"/appels-offres/{self.appel.id_appel_offres}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reference"], "AO-RTV-001")

    def test_retrieve_not_found(self):
        response = self.client.get("/appels-offres/99999")
        self.assertEqual(response.status_code, 404)


# Update
class AppelOffresUpdateTest(AppelsServiceTestCase):
    def setUp(self):
        super().setUp()
        self.appel = make_appel(reference="AO-UPD-001")

    def test_patch_titre(self):
        response = self.client.patch(
            f"/appels-offres/{self.appel.id_appel_offres}",
            json.dumps({"titre": "Nouveau titre"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["titre"], "Nouveau titre")

    def test_patch_not_found(self):
        response = self.client.patch(
            "/appels-offres/99999",
            json.dumps({"titre": "x"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_montant(self):
        response = self.client.patch(
            f"/appels-offres/{self.appel.id_appel_offres}",
            json.dumps({"montant_estime": "99999999.00"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["montant_estime"], "99999999.00")


# Delete
class AppelOffresDeleteTest(AppelsServiceTestCase):
    def test_delete_existing(self):
        appel = make_appel(reference="AO-DEL-001")
        response = self.client.delete(f"/appels-offres/{appel.id_appel_offres}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(AppelOffres.objects.count(), 0)

    def test_delete_not_found(self):
        response = self.client.delete("/appels-offres/99999")
        self.assertEqual(response.status_code, 404)


# Workflow actions
class AppelOffresPublierTest(AppelsServiceTestCase):
    def test_publier_from_brouillon(self):
        appel = make_appel(reference="AO-PUB-001", statut="valide", etat_execution="brouillon")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/publier")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["etat_execution"], "publie")

    def test_publier_already_publie_fails(self):
        appel = make_appel(reference="AO-PUB-002", statut="valide", etat_execution="publie")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/publier")
        self.assertEqual(response.status_code, 400)

    def test_publier_not_found(self):
        response = self.client.post("/appels-offres/99999/publier")
        self.assertEqual(response.status_code, 404)


class AppelOffresCloturerDepotTest(AppelsServiceTestCase):
    def test_cloturer_from_publie(self):
        appel = make_appel(reference="AO-CLO-001", statut="valide", etat_execution="publie")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/cloturer-depot")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["etat_execution"], "depot_cloture")

    def test_cloturer_from_brouillon_fails(self):
        appel = make_appel(reference="AO-CLO-002", statut="valide", etat_execution="brouillon")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/cloturer-depot")
        self.assertEqual(response.status_code, 400)


class AppelOffresOuvrirPlisTest(AppelsServiceTestCase):
    def test_ouvrir_from_depot_cloture(self):
        appel = make_appel(reference="AO-OUV-001", statut="valide", etat_execution="depot_cloture")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/ouvrir-plis")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["etat_execution"], "plis_ouverts")

    def test_ouvrir_from_publie_fails(self):
        appel = make_appel(reference="AO-OUV-002", statut="valide", etat_execution="publie")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/ouvrir-plis")
        self.assertEqual(response.status_code, 400)


class AppelOffresAnnulerTest(AppelsServiceTestCase):
    def test_annuler_from_brouillon(self):
        appel = make_appel(reference="AO-ANN-001", statut="valide", etat_execution="brouillon")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/annuler")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["etat_execution"], "annule")

    def test_annuler_from_publie(self):
        appel = make_appel(reference="AO-ANN-002", statut="valide", etat_execution="publie")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/annuler")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["etat_execution"], "annule")

    def test_annuler_from_plis_ouverts_fails(self):
        appel = make_appel(reference="AO-ANN-003", statut="valide", etat_execution="plis_ouverts")
        response = self.client.post(f"/appels-offres/{appel.id_appel_offres}/annuler")
        self.assertEqual(response.status_code, 400)

    def test_annuler_not_found(self):
        response = self.client.post("/appels-offres/99999/annuler")
        self.assertEqual(response.status_code, 404)


# Documents
class AppelOffresDocumentsTest(AppelsServiceTestCase):
    def setUp(self):
        super().setUp()
        self.appel = make_appel(reference="AO-DOC-001")

    def test_list_documents_empty(self):
        response = self.client.get(f"/appels-offres/{self.appel.id_appel_offres}/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_add_document(self):
        response = self.client.post(
            f"/appels-offres/{self.appel.id_appel_offres}/documents/200"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DocumentsAppel.objects.count(), 1)

    def test_add_document_idempotent(self):
        self.client.post(f"/appels-offres/{self.appel.id_appel_offres}/documents/200")
        response = self.client.post(
            f"/appels-offres/{self.appel.id_appel_offres}/documents/200"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DocumentsAppel.objects.count(), 1)

    def test_list_documents_after_add(self):
        self.client.post(f"/appels-offres/{self.appel.id_appel_offres}/documents/201")
        self.client.post(f"/appels-offres/{self.appel.id_appel_offres}/documents/202")
        response = self.client.get(f"/appels-offres/{self.appel.id_appel_offres}/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_remove_document(self):
        self.client.post(f"/appels-offres/{self.appel.id_appel_offres}/documents/300")
        response = self.client.delete(
            f"/appels-offres/{self.appel.id_appel_offres}/documents/300"
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(DocumentsAppel.objects.count(), 0)

    def test_remove_document_not_found(self):
        response = self.client.delete(
            f"/appels-offres/{self.appel.id_appel_offres}/documents/99999"
        )
        self.assertEqual(response.status_code, 404)

    def test_documents_deleted_on_appel_delete(self):
        self.client.post(f"/appels-offres/{self.appel.id_appel_offres}/documents/400")
        self.appel.delete()
        self.assertEqual(DocumentsAppel.objects.count(), 0)

    def test_documents_not_found_for_unknown_appel(self):
        response = self.client.get("/appels-offres/99999/documents")
        self.assertEqual(response.status_code, 404)


# Filter by service contractant
class ServiceContractantAppelsTest(AppelsServiceTestCase):
    def setUp(self):
        super().setUp()
        make_appel(reference="AO-SVC-001", id_service_contractant=1)
        make_appel(reference="AO-SVC-002", id_service_contractant=1)
        make_appel(reference="AO-SVC-003", id_service_contractant=2)

    def test_filter_by_service(self):
        response = self.client.get("/services-contractants/1/appels-offres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_filter_by_service_with_no_appels(self):
        response = self.client.get("/services-contractants/999/appels-offres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_filter_isolates_services(self):
        response = self.client.get("/services-contractants/2/appels-offres")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["reference"], "AO-SVC-003")


# Achats simples
class AchatSimpleCrudTest(AppelsServiceTestCase):
    def _post(self, payload):
        return self.client.post(
            "/achats-simples",
            json.dumps(payload),
            content_type="application/json",
        )

    def test_create_and_retrieve(self):
        response = self._post({
            "id_service_contractant": 1,
            "reference": "AS-001",
            "objet": "Achat simple test",
            "type_prestation": "fournitures",
            "wilaya": "Blida",
            "localisation": "Zone logistique",
            "montant_estime": "250000.00",
            "id_operateur_economique": 55,
        })
        self.assertEqual(response.status_code, 201)

        achat_id = response.json()["id_achat_simple"]
        details = self.client.get(f"/achats-simples/{achat_id}")
        self.assertEqual(details.status_code, 200)
        payload = details.json()

        self.assertEqual(payload["reference"], "AS-001")
        self.assertEqual(payload["type_prestation"], "fournitures")
        self.assertEqual(payload["localisation"], "Zone logistique")

    def test_list_and_filter_by_service(self):
        AchatSimple.objects.create(
            id_service_contractant=1,
            reference="AS-100",
            objet="Achat A",
            type_prestation="services",
        )
        AchatSimple.objects.create(
            id_service_contractant=2,
            reference="AS-200",
            objet="Achat B",
            type_prestation="travaux",
        )

        list_resp = self.client.get("/achats-simples")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()), 2)

        by_service_resp = self.client.get("/services-contractants/1/achats-simples")
        self.assertEqual(by_service_resp.status_code, 200)
        self.assertEqual(len(by_service_resp.json()), 1)
        self.assertEqual(by_service_resp.json()[0]["reference"], "AS-100")
