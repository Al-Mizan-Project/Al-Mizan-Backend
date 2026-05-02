"""
Seed the appels database with sample data.

Usage:
    python manage.py seed_appels              # insert only
    python manage.py seed_appels --flush      # drop all existing data first
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from acteurs_service.models import OperateurEconomique
from contractant_service.models import ServiceContractant
from documents_service.models import Document

from appels_service.models import AchatSimple, AppelOffres, AppelOffresOperateurInvite, DocumentsAppel


APPELS = [
    {
        "id_service_contractant": 1,
        "reference": "AO-2026-001",
        "titre": "Fourniture de matériel informatique",
        "description": "Acquisition de postes de travail et périphériques pour les directions.",
        "type_procedure": "Appel d'offres ouvert",
        "wilaya": "Alger",
        "montant_estime": "15000000.00",
        "poids_technique": 40,
        "poids_financier": 60,
        "required_docs_admin": ["Registre de commerce", "NIF", "Attestation CNAS", "Attestation CASNOS"],
        "required_docs_tech": ["Mémoire technique", "Fiches techniques des équipements", "Planning d'exécution"],
        "required_docs_fin": ["Bordereau des prix unitaires", "Devis quantitatif et estimatif"],
        "minimum_revenue_da": 20000000,
        "qualification_category": "Informatique - Catégorie B",
        "minimum_experience_years": 3,
        "participation_conditions": [
            "Au moins 2 références similaires sur les 3 dernières années",
            "Service après-vente assuré en Algérie"
        ],
        "statut": "publie",
    },
    {
        "id_service_contractant": 1,
        "reference": "AO-2026-002",
        "titre": "Travaux de réhabilitation du siège",
        "description": "Rénovation des locaux administratifs.",
        "type_procedure": "Appel d'offres restreint",
        "wilaya": "Blida",
        "montant_estime": "85000000.00",
        "poids_technique": 60,
        "poids_financier": 40,
        "required_docs_admin": ["Registre de commerce", "Attestation fiscale à jour"],
        "required_docs_tech": ["Plan méthodologique", "Planning Gantt", "CV de l'équipe clé"],
        "required_docs_fin": ["Offre financière détaillée", "BPU", "Détail estimatif"],
        "minimum_revenue_da": 120000000,
        "qualification_category": "BTP - Catégorie 3",
        "minimum_experience_years": 5,
        "participation_conditions": [
            "Qualification professionnelle BTP valide",
            "Disponibilité d'un conducteur de travaux certifié"
        ],
        "statut": "brouillon",
    },
    {
        "id_service_contractant": 2,
        "reference": "AO-2026-003",
        "titre": "Prestation de services de gardiennage",
        "description": "Surveillance et sécurité des bâtiments.",
        "type_procedure": "Consultation",
        "wilaya": "Oran",
        "montant_estime": "5400000.00",
        "poids_technique": 50,
        "poids_financier": 50,
        "required_docs_admin": ["Agrément activité sécurité", "Attestation CNAS", "Attestation CASNOS"],
        "required_docs_tech": ["Plan de déploiement", "Procédures d'intervention"],
        "required_docs_fin": ["Offre financière globale"],
        "minimum_revenue_da": 7000000,
        "qualification_category": "Sécurité privée",
        "minimum_experience_years": 2,
        "participation_conditions": ["Personnel déclaré et assuré"],
        "statut": "depot_cloture",
    },
    {
        "id_service_contractant": 2,
        "reference": "AO-2026-004",
        "titre": "Acquisition de véhicules de service",
        "description": "Achat de véhicules pour le parc automobile.",
        "type_procedure": "Appel d'offres ouvert",
        "wilaya": "Constantine",
        "montant_estime": "32000000.00",
        "poids_technique": 30,
        "poids_financier": 70,
        "required_docs_admin": ["Registre de commerce", "Attestation de conformité"],
        "required_docs_tech": ["Fiches techniques constructeurs", "Délai de livraison"],
        "required_docs_fin": ["Offre financière chiffrée", "BPU"],
        "minimum_revenue_da": 45000000,
        "qualification_category": "Distribution automobile",
        "minimum_experience_years": 3,
        "participation_conditions": ["Garantie minimale 3 ans ou 100 000 km"],
        "statut": "plis_ouverts",
    },
    {
        "id_service_contractant": 3,
        "reference": "AO-2026-005",
        "titre": "Fourniture de produits de nettoyage",
        "description": "Produits d'entretien pour les locaux.",
        "type_procedure": "Consultation",
        "wilaya": "Sétif",
        "montant_estime": "1200000.00",
        "poids_technique": 50,
        "poids_financier": 50,
        "required_docs_admin": ["Registre de commerce"],
        "required_docs_tech": ["Fiches de sécurité des produits"],
        "required_docs_fin": ["Offre financière"],
        "minimum_revenue_da": 1500000,
        "qualification_category": "Fournitures générales",
        "minimum_experience_years": 1,
        "participation_conditions": ["Produits conformes aux normes d'hygiène en vigueur"],
        "statut": "attribue",
    },
    {
        "id_service_contractant": 3,
        "reference": "AO-2026-006",
        "titre": "Maintenance du parc bureautique",
        "description": "Contrat annuel de maintenance preventive et curative.",
        "type_procedure": "Consultation",
        "wilaya": "Tizi Ouzou",
        "montant_estime": "4800000.00",
        "poids_technique": 50,
        "poids_financier": 50,
        "required_docs_admin": ["Registre de commerce", "NIF"],
        "required_docs_tech": ["Mémoire technique", "Liste des techniciens"],
        "required_docs_fin": ["Offre financière"],
        "minimum_revenue_da": 5000000,
        "qualification_category": "Maintenance IT",
        "minimum_experience_years": 2,
        "participation_conditions": ["Intervention sous 4h pour incidents bloquants"],
        "statut": "annule",
    },
    {
        "id_service_contractant": 4,
        "reference": "AO-2026-007",
        "titre": "Déploiement d'un réseau fibre inter-sites",
        "description": "Mise en place d'une infrastructure fibre entre les sites régionaux.",
        "type_procedure": "Appel d'offres ouvert",
        "wilaya": "Annaba",
        "montant_estime": "42000000.00",
        "poids_technique": 65,
        "poids_financier": 35,
        "required_docs_admin": ["Registre de commerce", "Attestation fiscale"],
        "required_docs_tech": ["Plan d'architecture réseau", "Méthodologie de migration", "Références clients"],
        "required_docs_fin": ["DQE", "BPU"],
        "minimum_revenue_da": 60000000,
        "qualification_category": "Télécom - Catégorie A",
        "minimum_experience_years": 5,
        "participation_conditions": [
            "Certification constructeurs réseau souhaitée",
            "Astreinte support 24/7"
        ],
        "statut": "publie",
    },
    {
        "id_service_contractant": 4,
        "reference": "AO-2026-008",
        "titre": "Acquisition d'une solution ERP",
        "description": "Licence, intégration et accompagnement au déploiement d'un ERP.",
        "type_procedure": "Appel d'offres restreint",
        "wilaya": "Alger",
        "montant_estime": "98000000.00",
        "poids_technique": 70,
        "poids_financier": 30,
        "required_docs_admin": ["Registre de commerce", "NIF", "Attestation CNAS"],
        "required_docs_tech": ["Architecture fonctionnelle", "Planning de déploiement", "CV experts ERP"],
        "required_docs_fin": ["Offre financière détaillée", "Plan de paiement"],
        "minimum_revenue_da": 150000000,
        "qualification_category": "Intégration SI - Catégorie A",
        "minimum_experience_years": 7,
        "participation_conditions": [
            "Au moins 3 projets ERP réussis dans le secteur public",
            "Support local obligatoire"
        ],
        "statut": "publie",
    },
    {
        "id_service_contractant": 5,
        "reference": "AO-2026-009",
        "titre": "Travaux d'extension de réseau d'assainissement",
        "description": "Extension et renouvellement de tronçons vétustes.",
        "type_procedure": "Appel d'offres ouvert",
        "wilaya": "Béjaïa",
        "montant_estime": "76000000.00",
        "poids_technique": 55,
        "poids_financier": 45,
        "required_docs_admin": ["Qualification BTP", "Attestation fiscale"],
        "required_docs_tech": ["Méthodologie d'exécution", "Plan de sécurité chantier"],
        "required_docs_fin": ["Offre financière", "BPU", "Détail estimatif"],
        "minimum_revenue_da": 90000000,
        "qualification_category": "Hydraulique - Catégorie 2",
        "minimum_experience_years": 4,
        "participation_conditions": ["Respect strict du plan HSE"],
        "statut": "depot_cloture",
    },
    {
        "id_service_contractant": 5,
        "reference": "AO-2026-010",
        "titre": "Fourniture de papier et consommables d'impression",
        "description": "Approvisionnement annuel des directions centrales.",
        "type_procedure": "Consultation",
        "wilaya": "Mostaganem",
        "montant_estime": "3900000.00",
        "poids_technique": 35,
        "poids_financier": 65,
        "required_docs_admin": ["Registre de commerce"],
        "required_docs_tech": ["Fiches techniques produits"],
        "required_docs_fin": ["Offre financière"],
        "minimum_revenue_da": 4500000,
        "qualification_category": "Fournitures bureautiques",
        "minimum_experience_years": 1,
        "participation_conditions": ["Livraison en 48h maximale"],
        "statut": "attribue",
    },
    {
        "id_service_contractant": 6,
        "reference": "AO-2026-011",
        "titre": "Audit énergétique des bâtiments administratifs",
        "description": "Campagne d'audit et recommandations d'optimisation énergétique.",
        "type_procedure": "Consultation",
        "wilaya": "Tlemcen",
        "montant_estime": "6700000.00",
        "poids_technique": 60,
        "poids_financier": 40,
        "required_docs_admin": ["Registre de commerce", "Attestation fiscale"],
        "required_docs_tech": ["Méthodologie d'audit", "CV auditeurs certifiés"],
        "required_docs_fin": ["Offre financière"],
        "minimum_revenue_da": 8000000,
        "qualification_category": "Audit énergétique",
        "minimum_experience_years": 3,
        "participation_conditions": ["Au moins 5 missions d'audit similaires"],
        "statut": "plis_ouverts",
    },
    {
        "id_service_contractant": 6,
        "reference": "AO-2026-012",
        "titre": "Services cloud pour plateforme documentaire",
        "description": "Hébergement, sauvegarde et supervision de la plateforme documentaire.",
        "type_procedure": "Appel d'offres restreint",
        "wilaya": "Alger",
        "montant_estime": "25500000.00",
        "poids_technique": 75,
        "poids_financier": 25,
        "required_docs_admin": ["Registre de commerce", "NIF", "Attestation CNAS"],
        "required_docs_tech": ["Architecture cloud proposée", "Plan PRA/PCA", "SLA détaillé"],
        "required_docs_fin": ["Offre financière triennale"],
        "minimum_revenue_da": 40000000,
        "qualification_category": "Cloud & hébergement",
        "minimum_experience_years": 4,
        "participation_conditions": ["Datacenter local conforme", "Disponibilité minimale 99.9%"],
        "statut": "brouillon",
    },
]

# Fake document IDs (cross-service refs)
DOCUMENTS = [
    # (appel_index, id_document)
    (0, 101),
    (0, 102),
    (1, 103),
    (2, 104),
    (3, 105),
    (3, 106),
    (6, 107),
    (6, 108),
    (7, 109),
    (8, 110),
    (9, 111),
    (10, 112),
    (11, 113),
]

PRIVATE_AO_INVITES_BY_REFERENCE = {
    "AO-2026-002": ["001234567890123"],
    "AO-2026-012": ["001234567890124"],
}

ACHATS_SIMPLES = [
    {
        "id_service_contractant": 1,
        "reference": "AS-2026-001",
        "objet": "Achat postes bureautiques",
        "description": "Achat simple de postes bureautiques pour renfort équipe.",
        "type_prestation": "fournitures",
        "wilaya": "Alger",
        "localisation": "Alger Centre",
        "montant_estime": "2500000.00",
        "operateur_nif": "001234567890123",
        "statut": "valide",
    },
    {
        "id_service_contractant": 2,
        "reference": "AS-2026-002",
        "objet": "Maintenance express réseau local",
        "description": "Intervention ponctuelle sur infrastructure LAN.",
        "type_prestation": "services",
        "wilaya": "Oran",
        "localisation": "Oran Akid",
        "montant_estime": "780000.00",
        "operateur_nif": "001234567890124",
        "statut": "engage",
    },
    {
        "id_service_contractant": 3,
        "reference": "AS-2026-003",
        "objet": "Etude de faisabilité extension site",
        "description": "Etude simple de faisabilité avant lancement AO complet.",
        "type_prestation": "etudes",
        "wilaya": "Constantine",
        "localisation": "Constantine Centre",
        "montant_estime": "420000.00",
        "operateur_nif": None,
        "statut": "brouillon",
    },
]


class Command(BaseCommand):
    help = "Seed the appels database with sample data."

    @staticmethod
    def _timeline_for_status(statut, now):
        if statut == "brouillon":
            return {
                "date_publication": None,
                "date_limite_soumission": None,
                "date_ouverture_plis": None,
            }
        if statut == "publie":
            return {
                "date_publication": now - timedelta(days=2),
                "date_limite_soumission": now + timedelta(days=8),
                "date_ouverture_plis": None,
            }
        if statut == "depot_cloture":
            return {
                "date_publication": now - timedelta(days=20),
                "date_limite_soumission": now - timedelta(days=2),
                "date_ouverture_plis": None,
            }
        if statut == "plis_ouverts":
            return {
                "date_publication": now - timedelta(days=28),
                "date_limite_soumission": now - timedelta(days=10),
                "date_ouverture_plis": now - timedelta(days=9),
            }
        if statut == "attribue":
            return {
                "date_publication": now - timedelta(days=45),
                "date_limite_soumission": now - timedelta(days=35),
                "date_ouverture_plis": now - timedelta(days=34),
            }
        return {
            "date_publication": now - timedelta(days=7),
            "date_limite_soumission": now - timedelta(days=1),
            "date_ouverture_plis": None,
        }

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            AchatSimple.objects.all().delete()
            AppelOffresOperateurInvite.objects.all().delete()
            DocumentsAppel.objects.all().delete()
            AppelOffres.objects.all().delete()
            self.stdout.write(self.style.WARNING("Flushed all appels data."))

        now = timezone.now()
        service_ids = list(ServiceContractant.objects.order_by("id_service").values_list("id_service", flat=True))
        operateur_nifs = {
            nif
            for nifs in PRIVATE_AO_INVITES_BY_REFERENCE.values()
            for nif in nifs
        }
        operateur_nifs.update(
            item["operateur_nif"]
            for item in ACHATS_SIMPLES
            if item.get("operateur_nif")
        )
        operateurs_by_nif = {
            row.nif: row.id_operateur_economique
            for row in OperateurEconomique.objects.filter(nif__in=operateur_nifs)
        }
        available_document_ids = list(
            Document.objects.order_by("id_document").values_list("id_document", flat=True)
        )
        use_seed_documents = bool(available_document_ids)

        appel_objects = []
        for data in APPELS:
            payload = dict(data)
            if service_ids:
                source_index = max(int(payload.get("id_service_contractant", 1)), 1) - 1
                payload["id_service_contractant"] = service_ids[source_index % len(service_ids)]

            payload.setdefault("type_prestation", "travaux")
            payload.setdefault("visibilite", "public")
            payload.setdefault("localisation", payload.get("wilaya", "") or "")

            invited_ids = [
                operateurs_by_nif[nif]
                for nif in PRIVATE_AO_INVITES_BY_REFERENCE.get(payload["reference"], [])
                if nif in operateurs_by_nif
            ]
            if invited_ids:
                payload["visibilite"] = "prive"

            timeline = self._timeline_for_status(data["statut"], now)
            obj, created = AppelOffres.objects.update_or_create(
                reference=payload["reference"],
                defaults={**payload, **timeline},
            )
            appel_objects.append(obj)

            if payload["visibilite"] == "prive" and invited_ids:
                self._sync_operateurs_invites(obj, invited_ids)
            else:
                AppelOffresOperateurInvite.objects.filter(id_appel_offres=obj).delete()

            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created AppelOffres: {obj.reference}"))
            else:
                self.stdout.write(f"  Updated (exists): {obj.reference}")

        for link_index, (appel_idx, doc_id) in enumerate(DOCUMENTS):
            appel = appel_objects[appel_idx]
            resolved_doc_id = (
                available_document_ids[link_index % len(available_document_ids)]
                if use_seed_documents
                else doc_id
            )
            link, created = DocumentsAppel.objects.get_or_create(
                id_appel_offres=appel,
                id_document=resolved_doc_id,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Linked document {resolved_doc_id} -> appel {appel.reference}"
                    )
                )

        for idx, data in enumerate(ACHATS_SIMPLES):
            payload = dict(data)
            if service_ids:
                source_index = max(int(payload.get("id_service_contractant", 1)), 1) - 1
                payload["id_service_contractant"] = service_ids[source_index % len(service_ids)]

            operateur_nif = payload.pop("operateur_nif", None)
            payload["id_operateur_economique"] = operateurs_by_nif.get(operateur_nif) if operateur_nif else None
            payload.setdefault("date_demande", now - timedelta(days=(idx + 1)))

            achat, created = AchatSimple.objects.update_or_create(
                reference=payload["reference"],
                defaults=payload,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created AchatSimple: {achat.reference}"))
            else:
                self.stdout.write(f"  Updated (exists) AchatSimple: {achat.reference}")

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    @staticmethod
    def _sync_operateurs_invites(appel, operateur_ids):
        target_ids = set(operateur_ids)
        AppelOffresOperateurInvite.objects.filter(id_appel_offres=appel).exclude(
            id_operateur_economique__in=target_ids
        ).delete()

        for operateur_id in target_ids:
            AppelOffresOperateurInvite.objects.get_or_create(
                id_appel_offres=appel,
                id_operateur_economique=operateur_id,
            )
