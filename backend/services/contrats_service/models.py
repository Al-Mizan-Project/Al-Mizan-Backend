# contrats_service/models.py
# Note: The core Attribution model lives in soumissions_app.models.Attribution.
# This service imports it directly (same Django project / same DB).
# We keep this file minimal — only service-specific models if ever needed.

from django.db import models  # noqa: F401 – kept so migrations tooling stays happy
