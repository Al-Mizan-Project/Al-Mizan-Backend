from django.core.management.base import BaseCommand
from documents_service.models import Document
from soumissions_app.models import Soumission, SoumissionStatut
import json

TEST_SOUMISSIONNAIRE_ID = 1


def _rapport_soumis():
    return None


def _rapport_en_ouverture():
    return json.dumps({
        "accuse": {
            "date": "2026-03-22 10:15",
            "numero": "ACC-2026-0201",
        },
    })


def _rapport_en_evaluation():
    return json.dumps({
        "accuse": {
            "date": "2026-02-15 09:00",
            "numero": "ACC-2026-0101",
        },
        "ouverture": {
            "date": "2026-03-10 14:00",
            "nb_offres": 8,
        },
        "evaluation": {
            "date_debut": "2026-03-12",
        },
    })


def _rapport_attribue():
    return json.dumps({
        "accuse": {
            "date": "2026-01-20 08:30",
            "numero": "ACC-2026-0301",
        },
        "ouverture": {
            "date": "2026-02-15 10:00",
            "nb_offres": 6,
        },
        "evaluation": {
            "date_debut": "2026-02-18",
        },
        "resultat": {
            "score_technique": 52,
            "max_technique": 60,
            "score_financier": 35,
            "max_financier": 40,
            "rang": 1,
            "nb_offres": 6,
            "fin_recours": "2026-05-20",
            "attribution_date": "Après le 2026-05-20",
            "contact_service": "Direction de l'éducation — Alger",
        },
    })


def _rapport_non_retenu():
    return json.dumps({
        "accuse": {
            "date": "2026-01-18 11:00",
            "numero": "ACC-2026-0401",
        },
        "ouverture": {
            "date": "2026-02-10 09:30",
            "nb_offres": 5,
        },
        "evaluation": {
            "date_debut": "2026-02-12",
        },
        "resultat": {
            "score_technique": 38,
            "max_technique": 60,
            "score_financier": 28,
            "max_financier": 40,
            "rang": 3,
            "nb_offres": 5,
            "motif_rejet": "Offre technique insuffisante — capacités références non conformes au cahier des charges",
            "expire_recours": "2026-05-10",
            "jours_restants": 7,
        },
    })


def _rapport_infructueux():
    return json.dumps({
        "accuse": {
            "date": "2026-02-01 09:00",
            "numero": "ACC-2026-0501",
        },
        "ouverture": {
            "date": "2026-03-01 14:30",
            "nb_offres": 3,
        },
        "evaluation": {
            "date_debut": "2026-03-05",
        },
        "resultat": {
            "motif": "Aucune offre conforme reçue — les trois soumissions présentaient "
                     "des non-conformités substantielles au cahier des charges",
        },
    })


def _rapport_evalu_terminee():
    return json.dumps({
        "accuse": {
            "date": "2026-01-10 08:45",
            "numero": "ACC-2026-0601",
        },
        "ouverture": {
            "date": "2026-02-05 10:00",
            "nb_offres": 7,
        },
        "evaluation": {
            "date_debut": "2026-02-08",
        },
    })


AO_METADATA = {
    1: ("AO-2026-001", "Construction d'un complexe scolaire — Alger"),
    2: ("AO-2026-002", "Réhabilitation de la route nationale RN5 — Blida"),
    3: ("AO-2026-003", "Équipement laboratoire universitaire — Oran"),
    4: ("AO-2026-004", "Fourniture mobilier de bureau — Direction régionale Sétif"),
    5: ("AO-2026-005", "Modernisation réseau fibre optique — Constantine"),
    6: ("AO-2026-006", "Acquisition de matériel informatique — DGSN"),
    7: ("AO-2026-007", "Aménagement espaces verts — Annaba"),
}


SEED_RECORDS = [
    (1, SoumissionStatut.SOUMIS, None, _rapport_soumis),
    (2, SoumissionStatut.EN_OUVERTURE, 18_500_000.00, _rapport_en_ouverture),
    (3, SoumissionStatut.EN_EVALUATION, 15_200_000.00, _rapport_en_evaluation),
    (4, SoumissionStatut.ATTRIBUE, 9_800_000.00, _rapport_attribue),
    (5, SoumissionStatut.NON_RETENU, 12_000_000.00, _rapport_non_retenu),
    (6, SoumissionStatut.INFRUCTUEUX, None, _rapport_infructueux),
    (7, SoumissionStatut.EVALU_TERMINEE, 7_400_000.00, _rapport_evalu_terminee),
]


class Command(BaseCommand):
    help = 'Seed one soumission per status so every screen can be tested'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Deleting existing soumissions...'))
        Soumission.objects.all().delete()
        document_ids = list(
            Document.objects.filter(
                id_operateur_economique=TEST_SOUMISSIONNAIRE_ID,
                related_type="soumission",
            ).values_list("id_document", flat=True)[:2]
        )

        for ao_id, statut, montant, rapport_fn in SEED_RECORDS:
            rapport = rapport_fn() if rapport_fn else None
            Soumission.objects.create(
                id_appel_offre=ao_id,
                id_soumissionnaire=TEST_SOUMISSIONNAIRE_ID,
                offre_financiere_chiffree_url=f'http://minio/dev-bucket/ao{ao_id}.pdf.enc',
                cle_dechiffrement_hash=f'fake_aes_key_ao{ao_id}',
                document_ids=document_ids,
                statut=statut,
                montant_financier=montant,
                conformite_rapport=rapport,
            )
            ref_ao, titre_ao = AO_METADATA.get(ao_id, (f"AO-{ao_id}", ""))
            self.stdout.write(f'  {ref_ao} | {statut:<16} | {titre_ao}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone - {len(SEED_RECORDS)} soumissions seeded for '
            f'id_soumissionnaire={TEST_SOUMISSIONNAIRE_ID}'
        ))
