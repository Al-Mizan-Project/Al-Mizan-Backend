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

from appels_service.models import AppelOffres, DocumentsAppel


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
            DocumentsAppel.objects.all().delete()
            AppelOffres.objects.all().delete()
            self.stdout.write(self.style.WARNING("Flushed all appels data."))

        now = timezone.now()
        appel_objects = []
        for data in APPELS:
            timeline = self._timeline_for_status(data["statut"], now)
            obj, created = AppelOffres.objects.update_or_create(
                reference=data["reference"],
                defaults={**data, **timeline},
            )
            appel_objects.append(obj)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created AppelOffres: {obj.reference}"))
            else:
                self.stdout.write(f"  Updated (exists): {obj.reference}")

        for appel_idx, doc_id in DOCUMENTS:
            appel = appel_objects[appel_idx]
            link, created = DocumentsAppel.objects.get_or_create(
                id_appel_offres=appel,
                id_document=doc_id,
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Linked document {doc_id} -> appel {appel.reference}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
