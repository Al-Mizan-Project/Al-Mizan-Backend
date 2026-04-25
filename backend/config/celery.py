import os
import sys
from pathlib import Path

from celery import Celery


ROOT_DIR = Path(__file__).resolve().parent.parent
SERVICES_DIR = ROOT_DIR / "services"

for path in (ROOT_DIR, SERVICES_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("almizan")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
