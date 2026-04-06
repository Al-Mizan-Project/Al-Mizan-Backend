import hashlib
import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Soumission, SoumissionStatut
from .services.integrations import send_audit_log

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Soumission)
def soumission_audit_logger(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Soumission.objects.get(pk=instance.pk)
            if old_instance.statut != instance.statut:
                if instance.statut == SoumissionStatut.EN_OUVERTURE:
                    send_audit_log(
                        utilisateur_id=instance.id_soumissionnaire,
                        action="OUVERTURE_PLIS",
                        entite_type="soumission",
                        entite_id=instance.pk,
                        details_action={
                            "previous_status": old_instance.statut,
                            "new_status": instance.statut,
                            "description": "Début de l'ouverture et déchiffrement du pli",
                        },
                    )
                elif instance.statut == SoumissionStatut.EN_EVALUATION:
                    send_audit_log(
                        utilisateur_id=instance.id_soumissionnaire,
                        action="OUVERTURE_PLIS_TERMINEE",
                        entite_type="soumission",
                        entite_id=instance.pk,
                        details_action={
                            "previous_status": old_instance.statut,
                            "new_status": instance.statut,
                            "montant_financier": str(instance.montant_financier),
                            "description": "Pli déchiffré. Montant extrait.",
                        },
                    )
                elif instance.statut == SoumissionStatut.RETRAITE:
                    send_audit_log(
                        utilisateur_id=instance.id_soumissionnaire,
                        action="RETRAIT_SOUMISSION",
                        entite_type="soumission",
                        entite_id=instance.pk,
                        details_action={
                            "previous_status": old_instance.statut,
                            "new_status": instance.statut,
                            "description": "Soumission retirée par le soumissionnaire.",
                        },
                    )
                elif instance.statut == SoumissionStatut.EVALU_TERMINEE:
                    send_audit_log(
                        utilisateur_id=instance.id_soumissionnaire,
                        action="EVALUATION_TERMINEE",
                        entite_type="soumission",
                        entite_id=instance.pk,
                        details_action={
                            "previous_status": old_instance.statut,
                            "new_status": instance.statut,
                            "description": "Phase d'évaluation clôturée.",
                        },
                    )
        except Soumission.DoesNotExist:
            pass
    else:
        # New submission
        fake_file_hash = hashlib.sha256(
            instance.offre_financiere_chiffree_url.encode("utf-8")
        ).hexdigest()
        send_audit_log(
            utilisateur_id=instance.id_soumissionnaire,
            action="DEPOT_SOUMISSION",
            entite_type="soumission",
            entite_id=0,
            details_action={
                "id_appel_offre": instance.id_appel_offre,
                "sha256_fichier": fake_file_hash,
                "pending_entity_id": "nouveau",
                "description": "Dépôt scellé d'une soumission.",
            },
        )
