from decimal import Decimal
import json

from django.core.management.base import BaseCommand, CommandError

from appels_service.models import AppelOffres
from auth_service.models import Role, Utilisateur
from documents_service.models import Document
from soumissions_app.models import Soumission, SoumissionStatut


DEFAULT_SEED_EMAIL = "c@a.dz"
DEFAULT_SEED_PASSWORD = "test1234"


def _rapport_soumis():
    return None


def _rapport_en_ouverture():
    return json.dumps({
        "accuse": {"date": "2026-03-22 10:15", "numero": "ACC-2026-0201"},
    })


def _rapport_en_evaluation():
    return json.dumps({
        "accuse": {"date": "2026-02-15 09:00", "numero": "ACC-2026-0101"},
        "ouverture": {"date": "2026-03-10 14:00", "nb_offres": 8},
        "evaluation": {"date_debut": "2026-03-12"},
    })


def _rapport_attribue():
    return json.dumps({
        "accuse": {"date": "2026-01-20 08:30", "numero": "ACC-2026-0301"},
        "ouverture": {"date": "2026-02-15 10:00", "nb_offres": 6},
        "evaluation": {"date_debut": "2026-02-18"},
        "resultat": {
            "score_technique": 52,
            "max_technique": 60,
            "score_financier": 35,
            "max_financier": 40,
            "rang": 1,
            "nb_offres": 6,
            "fin_recours": "2026-05-20",
            "attribution_date": "Apres le 2026-05-20",
            "contact_service": "Direction de l'education - Alger",
        },
    })


def _rapport_non_retenu():
    return json.dumps({
        "accuse": {"date": "2026-01-18 11:00", "numero": "ACC-2026-0401"},
        "ouverture": {"date": "2026-02-10 09:30", "nb_offres": 5},
        "evaluation": {"date_debut": "2026-02-12"},
        "resultat": {
            "score_technique": 38,
            "max_technique": 60,
            "score_financier": 28,
            "max_financier": 40,
            "rang": 3,
            "nb_offres": 5,
            "motif_rejet": (
                "Offre technique insuffisante - references non conformes au "
                "cahier des charges"
            ),
            "expire_recours": "2026-05-10",
            "jours_restants": 7,
        },
    })


def _rapport_infructueux():
    return json.dumps({
        "accuse": {"date": "2026-02-01 09:00", "numero": "ACC-2026-0501"},
        "ouverture": {"date": "2026-03-01 14:30", "nb_offres": 3},
        "evaluation": {"date_debut": "2026-03-05"},
        "resultat": {
            "motif": (
                "Aucune offre conforme recue - les soumissions presentaient "
                "des non-conformites substantielles"
            ),
        },
    })


def _rapport_evalu_terminee():
    return json.dumps({
        "accuse": {"date": "2026-01-10 08:45", "numero": "ACC-2026-0601"},
        "ouverture": {"date": "2026-02-05 10:00", "nb_offres": 7},
        "evaluation": {"date_debut": "2026-02-08"},
    })


SEED_RECORDS = [
    (SoumissionStatut.SOUMIS, None, _rapport_soumis),
    (SoumissionStatut.EN_OUVERTURE, Decimal("18500000.00"), _rapport_en_ouverture),
    (SoumissionStatut.EN_EVALUATION, Decimal("15200000.00"), _rapport_en_evaluation),
    (SoumissionStatut.ATTRIBUE, Decimal("9800000.00"), _rapport_attribue),
    (SoumissionStatut.NON_RETENU, Decimal("12000000.00"), _rapport_non_retenu),
    (SoumissionStatut.INFRUCTUEUX, None, _rapport_infructueux),
    (SoumissionStatut.EVALU_TERMINEE, Decimal("7400000.00"), _rapport_evalu_terminee),
]


class Command(BaseCommand):
    help = "Generate deterministic test data for soumissions and mobile recours flows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all soumissions before seeding",
        )
        parser.add_argument(
            "--soumissionnaire-id",
            type=int,
            default=None,
            help="Use an existing auth user id as soumissionnaire",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=len(SEED_RECORDS),
            help="Number of soumissions to seed",
        )

    def handle(self, *args, **options):
        flush = options["flush"]
        count = max(1, int(options["count"]))

        if flush:
            deleted, _ = Soumission.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing soumission rows."))

        soumissionnaire = self._resolve_soumissionnaire(options.get("soumissionnaire_id"))
        appel_ids = self._resolve_appel_ids(count)
        document_ids = self._operator_document_ids(soumissionnaire.id_utilisateur)

        created = 0
        updated = 0
        for idx, appel_id in enumerate(appel_ids, start=1):
            statut, montant, rapport_fn = SEED_RECORDS[(idx - 1) % len(SEED_RECORDS)]
            rapport = rapport_fn() if rapport_fn else None

            payload = {
                "offre_financiere_chiffree_url": (
                    f"http://minio/almizan-documents/"
                    f"seed-soumission-{soumissionnaire.id_utilisateur}-{appel_id}.pdf.enc"
                ),
                "cle_dechiffrement_hash": (
                    f"seed_encrypted_aes_key_{soumissionnaire.id_utilisateur}_{appel_id}"
                ),
                "document_ids": document_ids,
                "statut": statut,
                "montant_financier": montant,
                "conformite_statut": "CONFORME" if idx % 2 == 0 else "A_VERIFIER",
                "conformite_rapport": rapport,
            }

            soumission, was_created = Soumission.objects.update_or_create(
                id_appel_offre=appel_id,
                id_soumissionnaire=soumissionnaire.id_utilisateur,
                defaults=payload,
            )

            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created soumission #{soumission.id_soumission} "
                        f"for AO {appel_id} ({statut})"
                    )
                )
            else:
                updated += 1
                self.stdout.write(
                    f"Updated soumission #{soumission.id_soumission} "
                    f"for AO {appel_id} ({statut})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Soumissions seed completed. Created={created}, Updated={updated}, "
                    f"Soumissionnaire={soumissionnaire.id_utilisateur} ({soumissionnaire.email}), "
                    f"Documents={document_ids}"
                )
            )
        )

    def _resolve_soumissionnaire(self, explicit_user_id):
        if explicit_user_id is not None:
            user = Utilisateur.objects.filter(id_utilisateur=explicit_user_id).first()
            if not user:
                raise CommandError(f"No Utilisateur found with id {explicit_user_id}")
            return user

        existing = Utilisateur.objects.select_related("id_role").order_by("id_utilisateur").first()
        if existing:
            return existing

        role, _ = Role.objects.get_or_create(nom_role="admin")
        user = Utilisateur.objects.filter(email=DEFAULT_SEED_EMAIL).first()
        if not user:
            user = Utilisateur(id_role=role, id_membre=1, email=DEFAULT_SEED_EMAIL)
            user.set_password(DEFAULT_SEED_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created fallback seed user {DEFAULT_SEED_EMAIL}"))
        return user

    def _resolve_appel_ids(self, count):
        appel_ids = list(
            AppelOffres.objects.order_by("id_appel_offres")
            .values_list("id_appel_offres", flat=True)[:count]
        )
        if appel_ids:
            return appel_ids

        self.stdout.write(
            self.style.WARNING(
                "No appels-offres found; using synthetic appel ids. "
                "Run seed_appels first for fully linked test data."
            )
        )
        return [100 + i for i in range(1, count + 1)]

    def _operator_document_ids(self, operator_id):
        return list(
            Document.objects.filter(
                id_operateur_economique=operator_id,
                related_type="soumission",
            ).values_list("id_document", flat=True)[:2]
        )
