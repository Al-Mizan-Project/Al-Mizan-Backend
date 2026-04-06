from django.apps import AppConfig


class SoumissionsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'soumissions_app'

    def ready(self):
        import soumissions_app.signals
