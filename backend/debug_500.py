import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from contrats_service.views import AttributionDetailView
from django.test import RequestFactory

factory = RequestFactory()
request = factory.get('/attributions-provisoires/1/')
AttributionDetailView.permission_classes = []
view = AttributionDetailView.as_view()

try:
    response = view(request, attribution_provisoire_id=1)
    print(f"Status Code: {response.status_code}")
except Exception as e:
    import traceback
    traceback.print_exc()
