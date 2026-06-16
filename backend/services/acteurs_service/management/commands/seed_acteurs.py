from django.core.management.base import BaseCommand
from django.db import transaction

from acteurs_service.models import Membre, OperateurEconomique, Organisation


ORGANISATIONS = [
    {
        "nom_officiel": "TECHBUILD SARL",
        "adresse_siege": "Alger Centre",
        "email_contact": "contact@techbuild.dz",
        "type_entite": "SERVICE_CONTRACTANT",
    },
    {
        "nom_officiel": "BATIPRO SPA",
        "adresse_siege": "Oran Akid",
        "email_contact": "contact@batipro.dz",
        "type_entite": "OPERATEUR_ECONOMIQUE",
    },
    {
        "nom_officiel": "NETSERV EURL",
        "adresse_siege": "Constantine",
        "email_contact": "contact@netserv.dz",
        "type_entite": "OPERATEUR_ECONOMIQUE",
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

OPERATEURS = [
    {
        "nif": "001234567890123",
        "num_registre_commerce": "16B1234567",
    },
    {
        "nif": "001234567890124",
        "num_registre_commerce": "31B7654321",
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
            self.stdout.write(self.style.WARNING("Flushed acteurs seed data."))

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
                "organisation_id": organisation_id,
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
            org, _ = Organisation.objects.update_or_create(
                nom_officiel=f"Operateur {payload['nif'][-4:]}",
                defaults={
                    "type_entite": "OPERATEUR_ECONOMIQUE",
                    "email_contact": f"op{payload['nif'][-4:]}@example.dz",
                },
            )
            _, created = OperateurEconomique.objects.update_or_create(
                organisation=org,
                defaults={
                    "nif": payload["nif"],
                    "num_registre_commerce": payload["num_registre_commerce"],
                },
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
