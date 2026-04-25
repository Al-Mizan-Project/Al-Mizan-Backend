from django.apps import AppConfig


class AuditCommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "common"
    label = "audit_common"
