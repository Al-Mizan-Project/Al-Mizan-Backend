"""
Quick seed: create one AppelOffres for operator testing.
Run: cat scripts/seed_test_ao.py | docker exec -i deploy-backend-1 python manage.py shell
"""
import datetime
from appels_service.models import AppelOffres

ao = AppelOffres.objects.create(
    id_service_contractant=1,
    reference="AO-2026-TEST-001",
    titre="Acquisition de matériel informatique",
    description="Appel d'offres national pour l'acquisition de matériel informatique destiné aux services du ministère.",
    type_procedure="publique",
    type_prestation="fournitures",
    visibilite="public",
    statut="valide",
    etat_execution="publie",
    montant_estime=50000000.00,
    date_publication=datetime.datetime.now(),
    date_limite_soumission=datetime.datetime.now() + datetime.timedelta(days=30),
    date_ouverture_plis=datetime.datetime.now() + datetime.timedelta(days=31),
    poids_technique=60,
    poids_financier=40,
    wilaya="Alger",
    localisation="Alger centre",
    methodology="weighted",
    required_docs_admin=[
        "declaration a souscrire",
        "attestation de probite",
    ],
    required_docs_tech=[
        "offre technique",
    ],
    required_docs_fin=[
        "offre financiere",
        "bordereau des prix",
    ],
)
print(f"Created AppelOffres #{ao.id_appel_offres}: {ao.reference}")
