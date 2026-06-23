from django.db import transaction
from auth_service.models import Role, Utilisateur
from acteurs_service.models import Organisation, Membre
import uuid

with transaction.atomic():

    role_eval = Role.objects.get(nom_role="EVALUATEUR")
    role_ct = Role.objects.get(nom_role="MEMBRE_COMITE_TECHNIQUE")

    org = Organisation.objects.first()

    # -------------------
    # Evaluateur
    # -------------------
    if not Utilisateur.objects.filter(email="evaluateur@plateforme.dz").exists():

        m = Membre.objects.create(
            id_membre=uuid.uuid4(),
            organisation=org,
            nom="Eval",
            prenom="User",
            fonction="Evaluateur"
        )

        u = Utilisateur(
            email="evaluateur@plateforme.dz",
            id_membre=m.id_membre,
            id_role=role_eval,
            is_active=True
        )
        u.set_password("Evaluateur123!")
        u.save()

    # -------------------
    # CT
    # -------------------
    if not Utilisateur.objects.filter(email="comite.technique@plateforme.dz").exists():

        m = Membre.objects.create(
            id_membre=uuid.uuid4(),
            organisation=org,
            nom="CT",
            prenom="User",
            fonction="Comité Technique"
        )

        u = Utilisateur(
            email="comite.technique@plateforme.dz",
            id_membre=m.id_membre,
            id_role=role_ct,
            is_active=True
        )
        u.set_password("ComiteTech123!")
        u.save()

print("DONE")