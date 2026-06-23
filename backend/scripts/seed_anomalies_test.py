"""
Seed script pour tester la détection d'anomalies (multi-agent et classique).

Scénarios créés :
  AO#1 → "Fourniture de materiel informatique" (montant_estime = 50 000 000 DA)
    S#1:  45 000 000 DA  → Normal
    S#2:  52 000 000 DA  → Normal
    S#3: 120 000 000 DA  → MONTANT_TROP_ELEVE (> 3x estimé)
    S#4:  44 625 000 DA  → Normal
    S#11: 15 000 000 DA  → MONTANT_TROP_BAS (< 70%) + PRIX_ANORMALEMENT_BAS
    S#12: 48 000 000 DA  → Normal
    S#13: 49 500 000 DA  → Normal
    S#14: 50 200 000 DA  → Normal
    S#15: 51 000 000 DA  → Normal

  AO#4 → "Travaux de maintenance" (montant_estime = 30 000 000 DA)
    S#21: 28 000 000 DA  → Normal
    S#22: 28 500 000 DA  → Normal
    S#23: 29 000 000 DA  → Normal
    S#24: 28 800 000 DA  → Normal
    S#25: 90 000 000 DA  → MONTANT_TROP_ELEVE + PRIX_ANORMALEMENT_ELEVE

Exécution :
  docker exec -i deploy-backend-1 python manage.py shell < scripts/seed_anomalies_test.py
"""

import json
from datetime import timedelta
from django.utils import timezone

from appels_service.models import AppelOffres
from soumissions_app.models import Soumission

NOW = timezone.now()


def fmt_ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def update_or_create_soumission(**kwargs):
    sid = kwargs.pop("id_soumission")
    s, created = Soumission.objects.update_or_create(
        id_soumission=sid,
        defaults=kwargs,
    )
    status = "CREATED" if created else "UPDATED"
    print(f"  {status}: S#{s.id_soumission} | AO={s.id_appel_offre} | "
          f"montant={s.montant_financier} | {s.statut}")
    return s


# ═══════════════════════════════════════════════════════════════════════════
# 1. METTRE À JOUR L'APPEL D'OFFRE #1
# ═══════════════════════════════════════════════════════════════════════════
try:
    ao1 = AppelOffres.objects.get(id_appel_offres=1)
    ao1.montant_estime = 50000000
    ao1.titre = "Fourniture de materiel informatique pour le ministere"
    ao1.description = "Acquisition de 500 ordinateurs portables, accessoires et formation"
    ao1.type_procedure = "appel_offres_national_ouvert"
    ao1.type_prestation = "fournitures"
    ao1.statut = "publie"
    ao1.date_publication = fmt_ts(NOW - timedelta(days=45))
    ao1.date_limite_soumission = fmt_ts(NOW + timedelta(days=15))
    ao1.save()
    print(f"\n✅ AO#1 mis à jour : montant_estime={ao1.montant_estime}, "
          f"date_limite={ao1.date_limite_soumission}")
except AppelOffres.DoesNotExist:
    print("❌ AO#1 non trouvé")

# ═══════════════════════════════════════════════════════════════════════════
# 2. CRÉER / METTRE À JOUR LES SOUMISSIONS POUR AO#1
# ═══════════════════════════════════════════════════════════════════════════
print("\n📋 Soumissions pour AO#1 (montant_estime=50 000 000 DA) :")
print("-" * 70)

# S#1: Normal (dans la moyenne)
update_or_create_soumission(
    id_soumission=1,
    id_appel_offre=1,
    id_soumissionnaire=1,
    montant_financier=45000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=10)),
)

# S#2: Normal (dans la moyenne)
update_or_create_soumission(
    id_soumission=2,
    id_appel_offre=1,
    id_soumissionnaire=2,
    montant_financier=52000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=9)),
)

# S#3: Trop élevé (> 3x montant_estime)
update_or_create_soumission(
    id_soumission=3,
    id_appel_offre=1,
    id_soumissionnaire=3,
    montant_financier=160000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=8)),
)

# S#4: Normal
update_or_create_soumission(
    id_soumission=4,
    id_appel_offre=1,
    id_soumissionnaire=4,
    montant_financier=44625000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=7)),
)

# S#11: Trop bas (< 70%) + outlier IQR
update_or_create_soumission(
    id_soumission=11,
    id_appel_offre=1,
    id_soumissionnaire=11,
    montant_financier=15000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=6)),
)

# S#12: Normal
update_or_create_soumission(
    id_soumission=12,
    id_appel_offre=1,
    id_soumissionnaire=12,
    montant_financier=48000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=5)),
)

# S#13: Normal
update_or_create_soumission(
    id_soumission=13,
    id_appel_offre=1,
    id_soumissionnaire=13,
    montant_financier=49500000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=4)),
)

# S#14: Normal
update_or_create_soumission(
    id_soumission=14,
    id_appel_offre=1,
    id_soumissionnaire=14,
    montant_financier=50200000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=3)),
)

# S#15: Normal (pour compléter le jeu)
update_or_create_soumission(
    id_soumission=15,
    id_appel_offre=1,
    id_soumissionnaire=15,
    montant_financier=51000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=2)),
)

# S#16: Hors délai (soumis après date limite)
update_or_create_soumission(
    id_soumission=16,
    id_appel_offre=1,
    id_soumissionnaire=16,
    montant_financier=47000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW + timedelta(days=30)),
)

# ═══════════════════════════════════════════════════════════════════════════
# 3. CRÉER UN NOUVEL AO#4 POUR TESTER DISPERSION ANORMALE
# ═══════════════════════════════════════════════════════════════════════════
ao4, created = AppelOffres.objects.update_or_create(
    id_appel_offres=4,
    defaults=dict(
        id_service_contractant=1,
        reference="AO-2026-004",
        titre="Travaux de maintenance des batiments administratifs",
        description="Maintenance des installations techniques",
        montant_estime=30000000,
        type_procedure="appel_offres_national_ouvert",
        type_prestation="services",
        statut="publie",
        date_publication=fmt_ts(NOW - timedelta(days=30)),
        date_limite_soumission=fmt_ts(NOW + timedelta(days=20)),
    ),
)
print(f"\n✅ AO#4 {'CRÉÉ' if created else 'MIS À JOUR'} : "
      f"montant_estime={ao4.montant_estime}")

# ═══════════════════════════════════════════════════════════════════════════
# 4. SOUMISSIONS POUR AO#4 — DISPERSION ANORMALE (CV < 2%)
# ═══════════════════════════════════════════════════════════════════════════
print("\n📋 Soumissions pour AO#4 (montant_estime=30 000 000 DA) :")
print("-" * 70)

montants_dispersion = [28100000, 28500000, 29000000, 28800000, 28300000]
for i, montant in enumerate(montants_dispersion):
    sid = 21 + i
    update_or_create_soumission(
        id_soumission=sid,
        id_appel_offre=4,
        id_soumissionnaire=100 + i,
        montant_financier=montant,
        statut="SOUMIS",
        date_soumission=fmt_ts(NOW - timedelta(days=5 - i)),
    )

# S#26: Prix anormalement élevé pour dispersion
update_or_create_soumission(
    id_soumission=26,
    id_appel_offre=4,
    id_soumissionnaire=110,
    montant_financier=90000000,
    statut="SOUMIS",
    date_soumission=fmt_ts(NOW - timedelta(days=3)),
)

print("\n" + "=" * 70)
print("✅ SEED TERMINÉ")
print("=" * 70)
print(f"\nRécapitulatif :")
print(f"  AO#1: 10 soumissions (dont 3 avec anomalies)")
print(f"  AO#4: 6 soumissions (dont dispersion anormale + prix élevé)")
print(f"\nCommandes de test :")
print(f"  # Analyser S#11 (prix trop bas) avec multi-agent :")
print(f"  curl -X POST http://localhost:8082/ia/anomalies/detecter-multi-agent \\")
print(f"    -H 'Content-Type: application/json' \\")
print(f"    -H 'Authorization: Bearer <token>' \\")
print(f"    -d '{{\"id_soumission\": 11, \"id_appel_offre\": 1, \"trace\": true}}'")
print(f"\n  # Analyser tout l'AO#4 (dispersion anormale) :")
print(f"  curl -X POST http://localhost:8082/ia/anomalies/detecter-auto \\")
print(f"    -H 'Content-Type: application/json' \\")
print(f"    -H 'Authorization: Bearer <token>' \\")
print(f"    -d '{{\"id_appel_offre\": 4}}'")
