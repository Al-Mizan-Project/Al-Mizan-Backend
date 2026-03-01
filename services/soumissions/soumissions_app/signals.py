import hashlib
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Soumission, SoumissionStatut
from django.utils import timezone

# Mocking the journaux_audit table interaction since it's probably in an 'audit' service
# or a separate app.
def log_to_audit_table(action, entite_id, details):
    # In a real app, we'd insert into journaux_audit
    print(f"[AUDIT LOG] {timezone.now()} - {action} - ID: {entite_id} - {details}")

@receiver(pre_save, sender=Soumission)
def soumission_audit_logger(sender, instance, **kwargs):
    if instance.pk:
        # Check if status is changing
        try:
            old_instance = Soumission.objects.get(pk=instance.pk)
            if old_instance.statut != instance.statut:
                if instance.statut == SoumissionStatut.EN_OUVERTURE:
                    log_to_audit_table(
                        action="OUVERTURE_PLIS",
                        entite_id=instance.pk,
                        details="Début de l'ouverture et déchiffrement du pli"
                    )
                elif instance.statut == SoumissionStatut.EN_EVALUATION:
                    log_to_audit_table(
                        action="OUVERTURE_PLIS_TERMINEE",
                        entite_id=instance.pk,
                        details=f"Pli déchiffré. Montant extrait: {instance.montant_financier}"
                    )
        except Soumission.DoesNotExist:
            pass
    else:
        # New submission: generate SHA-256 of the encrypted URL reference to simulate physical file hash
        # In reality, this would hash the physical bytes of the file received.
        fake_file_hash = hashlib.sha256(instance.offre_financiere_chiffree_url.encode('utf-8')).hexdigest()
        log_to_audit_table(
            action="DEPOT_SOUMISSION",
            entite_id="N/A (Cree)",
            details=f"Dépôt scellé. SHA-256 du fichier: {fake_file_hash}"
        )
