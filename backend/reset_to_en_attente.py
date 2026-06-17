import sys, os, django

# ── Script de réinitialisation de l'état des données ──────────────────────────
# À exécuter via :  python manage.py shell -c "import reset_to_en_attente; reset_to_en_attente.run()"

from django.db import transaction, connection

def run():
    with transaction.atomic():

        # ── 1. Appels d'offres ─────────────────────────────────────────────────
        # Vider appels_offres_suivis
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM appels_offres_suivis;")
            deleted_suivis = cursor.rowcount
        print(f"[1] Supprimé {deleted_suivis} enregistrement(s) dans appels_offres_suivis")

        # Remettre validated_by = NULL et statut = 'non_valide' sur tous les appels
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE appels_offres
                SET validated_by = NULL,
                    statut       = 'non_valide'
                WHERE TRUE;
            """)
            updated_appels = cursor.rowcount
        print(f"[2] {updated_appels} appels d'offres remis à non_valide / validated_by=NULL")

        # ── 2. Attributions ────────────────────────────────────────────────────
        # Pour TOUTES les attributions (interne + externe) :
        #   • statut       → 'provisoire'
        #   • validated_by → NULL
        # La validation_level reste inchangée.
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE attribution
                SET statut       = 'provisoire',
                    validated_by = NULL
                WHERE TRUE;
            """)
            updated_attr = cursor.rowcount
        print(f"[3] {updated_attr} attribution(s) remises à provisoire / validated_by=NULL")

        # ── 3. Récapitulatif ────────────────────────────────────────────────────
        with connection.cursor() as cursor:
            cursor.execute("SELECT validation_level, COUNT(*) FROM attribution GROUP BY validation_level;")
            rows = cursor.fetchall()
        print("\n── Attributions par validation_level ──")
        for row in rows:
            print(f"   {row[0]:30s} : {row[1]}")

        with connection.cursor() as cursor:
            cursor.execute("SELECT statut, COUNT(*) FROM appels_offres GROUP BY statut;")
            rows = cursor.fetchall()
        print("\n── Appels d'offres par statut ──")
        for row in rows:
            print(f"   {row[0]:30s} : {row[1]}")

        print("\n✅ Réinitialisation terminée avec succès.")

if __name__ == "__main__":
    run()
