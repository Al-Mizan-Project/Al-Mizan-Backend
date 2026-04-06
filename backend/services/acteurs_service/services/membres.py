from rest_framework.exceptions import NotFound

from acteurs_service.models import Membre


def membres_queryset():
    return Membre.objects.order_by("id_membre")


def get_membre_or_404(membre_id):
    membre = Membre.objects.filter(id_membre=membre_id).first()
    if not membre:
        raise NotFound("Membre not found")
    return membre
