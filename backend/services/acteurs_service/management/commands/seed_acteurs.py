from django.core.management.base import BaseCommand
from django.db import transaction

from acteurs_service.models import Membre, OperateurEconomique, Organisation, Tutelle


ORGANISATIONS = [
    {
        "nom_officiel": "TECHBUILD SARL",
        "adresse_siege": "Alger Centre",
        "email_contact": "contact@techbuild.dz",
        "type_entite": "Privee",
    },
    {
        "nom_officiel": "BATIPRO SPA",
        "adresse_siege": "Oran Akid",
        "email_contact": "contact@batipro.dz",
        "type_entite": "Privee",
    },
    {
        "nom_officiel": "NETSERV EURL",
        "adresse_siege": "Constantine",
        "email_contact": "contact@netserv.dz",
        "type_entite": "Privee",
    },
]

MEMBRES = [
    {
        "prenom": "Amina",
        "nom": "Khelifi",
        "telephone": "+213555001101",
        "fonction": "Directrice Generale",
        "organisation_index": 0,
    },
    {
        "prenom": "Yacine",
        "nom": "Bensaid",
        "telephone": "+213555001102",
        "fonction": "Charge AO",
        "organisation_index": 0,
    },
    {
        "prenom": "Nadia",
        "nom": "Mansouri",
        "telephone": "+213555002201",
        "fonction": "Responsable Marche",
        "organisation_index": 1,
    },
    {
        "prenom": "Kamel",
        "nom": "Haddad",
        "telephone": "+213555003301",
        "fonction": "Chef Projet",
        "organisation_index": 2,
    },
]

TUTELLES = [
    {
        "nom_tutelle": "Ministere Habitat",
        "identite_autorite": "Direction Centrale",
    },
    {
        "nom_tutelle": "Wilaya Alger",
        "identite_autorite": "Secretariat General",
    },
]

OPERATEURS = [
    {
        "nif": "001234567890123",
        "registre_commerce_num": "16B1234567",
        "casnos_vrt": "CASNOS-001",
        "cnas_vrt": "CNAS-001",
        "rib_bancaire": "007999990000111122223333",
    },
    {
        "nif": "001234567890124",
        "registre_commerce_num": "31B7654321",
        "casnos_vrt": "CASNOS-002",
        "cnas_vrt": "CNAS-002",
        "rib_bancaire": "007999990000222233334444",
    },
]


class Command(BaseCommand):
    help = "Seed acteurs data (organisations, membres, operateurs, tutelles)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing acteurs seed data before insert",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            Membre.objects.all().delete()
            OperateurEconomique.objects.all().delete()
            Organisation.objects.all().delete()
            Tutelle.objects.all().delete()
            self.stdout.write(self.style.WARNING("Flushed acteurs seed data."))

        tutelles_created = 0
        for payload in TUTELLES:
            _, created = Tutelle.objects.update_or_create(
                nom_tutelle=payload["nom_tutelle"],
                defaults=payload,
            )
            if created:
                tutelles_created += 1

        organisations = []
        created_organisations = 0
        for payload in ORGANISATIONS:
            organisation, created = Organisation.objects.update_or_create(
                nom_officiel=payload["nom_officiel"],
                defaults=payload,
            )
            organisations.append(organisation)
            if created:
                created_organisations += 1

        created_membres = 0
        for payload in MEMBRES:
            organisation_id = organisations[payload["organisation_index"]].id_organisation
            defaults = {
                "id_organisation": organisation_id,
                "telephone": payload["telephone"],
                "fonction": payload["fonction"],
            }
            _, created = Membre.objects.update_or_create(
                prenom=payload["prenom"],
                nom=payload["nom"],
                defaults=defaults,
            )
            if created:
                created_membres += 1

        created_operateurs = 0
        for payload in OPERATEURS:
            _, created = OperateurEconomique.objects.update_or_create(
                nif=payload["nif"],
                defaults=payload,
            )
            if created:
                created_operateurs += 1

        members = list(Membre.objects.order_by("id_membre").values_list("id_membre", flat=True)[:2])
        admin_member = members[0] if len(members) > 0 else None
        contractant_member = members[1] if len(members) > 1 else admin_member

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Acteurs seed completed. "
                    f"Tutelles(created={tutelles_created}), "
                    f"Organisations(created={created_organisations}), "
                    f"Membres(created={created_membres}), "
                    f"Operateurs(created={created_operateurs})."
                )
            )
        )
        if admin_member is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Recommended membre ids: "
                        f"admin={admin_member}, contractant={contractant_member}"
                    )
                )
            )
