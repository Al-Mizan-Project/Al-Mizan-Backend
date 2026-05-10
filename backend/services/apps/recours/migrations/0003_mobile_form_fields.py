from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("recours", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE recours
                ALTER COLUMN id_validation DROP NOT NULL,
                ADD COLUMN IF NOT EXISTS type_recours varchar(20) NULL,
                ADD COLUMN IF NOT EXISTS objet varchar(255) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS explications text NOT NULL DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE recours
                DROP COLUMN IF EXISTS explications,
                DROP COLUMN IF EXISTS objet,
                DROP COLUMN IF EXISTS type_recours,
                ALTER COLUMN id_validation SET NOT NULL;
            """,
        ),
    ]
