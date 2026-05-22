"""Seed demo data - to be run via: manage.py shell < this_file"""
from datetime import timedelta
from django.utils import timezone

from appels_service.models import AppelOffres
from soumissions_app.models import Soumission

ao1, c = AppelOffres.objects.get_or_create(
    reference="AO-2026-001",
    defaults=dict(
        id_service_contractant=1,
        titre="Fourniture de materiel informatique pour le ministere",
        description="Acquisition de 500 ordinateurs portables et accessoires",
        type_procedure="appel_offres_national_ouvert",
        type_prestation="fournitures",
        statut="publie",
        date_publication=timezone.now() - timedelta(days=30),
        date_limite_soumission=timezone.now() + timedelta(days=15),
        required_docs_admin=["Registre de commerce", "Carte fiscale (NIF)", "Attestation CNAS/CASNOS", "Certificat de non-faillite"],
        required_docs_tech=["Fiche technique des equipements", "Certificats de conformite", "Plan de livraison"],
        required_docs_fin=["Offre financiere detaillee", "Bordereau des prix unitaires", "Garantie bancaire"],
    ),
)
print(f"AO1 id={ao1.id_appel_offres} {'NEW' if c else 'EXISTS'}")

ao2, c = AppelOffres.objects.get_or_create(
    reference="AO-2026-002",
    defaults=dict(
        id_service_contractant=1,
        titre="Travaux de renovation du batiment administratif",
        description="Renovation complete du siege de la wilaya",
        type_procedure="appel_offres_national_restreint",
        type_prestation="travaux",
        statut="publie",
        date_publication=timezone.now() - timedelta(days=15),
        date_limite_soumission=timezone.now() + timedelta(days=30),
        required_docs_admin=["Registre de commerce", "Carte fiscale (NIF)", "Attestation de bonne execution"],
        required_docs_tech=["Plan architectural", "Devis quantitatif", "Planning des travaux"],
        required_docs_fin=["Soumission financiere", "Sous-detail des prix"],
    ),
)
print(f"AO2 id={ao2.id_appel_offres} {'NEW' if c else 'EXISTS'}")

s1, c = Soumission.objects.get_or_create(
    id_appel_offre=ao1.id_appel_offres,
    id_soumissionnaire=1,
    defaults=dict(
        statut="SOUMIS",
        montant_financier=45000000,
        document_ids=[1, 2, 3],
        offre_financiere_chiffree_url="http://minio:9000/almizan-documents/demo/offre1.pdf",
        cle_dechiffrement_hash="demo-key-hash-001",
    ),
)
print(f"S1 id={s1.id_soumission} {'NEW' if c else 'EXISTS'}")

s2, c = Soumission.objects.get_or_create(
    id_appel_offre=ao1.id_appel_offres,
    id_soumissionnaire=2,
    defaults=dict(
        statut="SOUMIS",
        montant_financier=52000000,
        document_ids=[4, 5],
        offre_financiere_chiffree_url="http://minio:9000/almizan-documents/demo/offre2.pdf",
        cle_dechiffrement_hash="demo-key-hash-002",
    ),
)
print(f"S2 id={s2.id_soumission} {'NEW' if c else 'EXISTS'}")

s3, c = Soumission.objects.get_or_create(
    id_appel_offre=ao2.id_appel_offres,
    id_soumissionnaire=3,
    defaults=dict(
        statut="SOUMIS",
        montant_financier=120000000,
        document_ids=[6, 7, 8, 9],
        offre_financiere_chiffree_url="http://minio:9000/almizan-documents/demo/offre3.pdf",
        cle_dechiffrement_hash="demo-key-hash-003",
    ),
)
print(f"S3 id={s3.id_soumission} {'NEW' if c else 'EXISTS'}")

print("=== SEED COMPLETE ===")
