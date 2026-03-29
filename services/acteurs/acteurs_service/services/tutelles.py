from rest_framework.exceptions import NotFound

from acteurs_service.models import Tutelle


def tutelles_queryset():
    return Tutelle.objects.order_by("id_tutelle")


def get_tutelle_or_404(tutelle_id):
    tutelle = Tutelle.objects.filter(id_tutelle=tutelle_id).first()
    if not tutelle:
        raise NotFound("Tutelle not found")
    return tutelle
