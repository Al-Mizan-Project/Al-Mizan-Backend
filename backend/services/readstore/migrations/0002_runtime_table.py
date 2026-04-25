from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("readstore", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS audit_read_projection (
                id bigint PRIMARY KEY,
                utilisateur_id bigint NOT NULL,
                action varchar(100) NOT NULL,
                entite_type varchar(50) NOT NULL,
                entite_id bigint NOT NULL,
                horodatage timestamptz NOT NULL,
                adresse_ip inet NULL,
                details_action jsonb NOT NULL
            );

            CREATE INDEX IF NOT EXISTS audit_read_projection_entite_idx
                ON audit_read_projection (entite_type, entite_id);
            CREATE INDEX IF NOT EXISTS audit_read_projection_utilisateur_horodatage_idx
                ON audit_read_projection (utilisateur_id, horodatage);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS audit_read_projection;
            """,
        ),
    ]
