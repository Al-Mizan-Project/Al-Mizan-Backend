from django.core.management.base import BaseCommand
from django.db import connections

from apps.recours.infrastructure.models.document_recours_model import DocumentRecoursModel
from apps.recours.infrastructure.models.recours_model import RecoursModel
from ia_service.models import DetectionAnomalieIA
from ledger.models import AuditLog, OutboxEvent
from readstore.models import AuditLogRead


class Command(BaseCommand):
    help = "Ensure routed runtime tables exist in the temporary unified architecture"

    TABLES_BY_ALIAS = {
        "default": [DetectionAnomalieIA, RecoursModel, DocumentRecoursModel],
        "ledger": [AuditLog, OutboxEvent],
        "read": [AuditLogRead],
    }

    def handle(self, *args, **options):
        for alias, models in self.TABLES_BY_ALIAS.items():
            connection = connections[alias]
            existing_tables = set(connection.introspection.table_names())
            missing_models = [model for model in models if model._meta.db_table not in existing_tables]

            if not missing_models:
                self.stdout.write(f"{alias}: all runtime tables present")
                continue

            with connection.schema_editor() as schema_editor:
                for model in missing_models:
                    schema_editor.create_model(model)
                    self.stdout.write(f"{alias}: created {model._meta.db_table}")
