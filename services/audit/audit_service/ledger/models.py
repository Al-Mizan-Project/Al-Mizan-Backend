from django.db import models
from django.core.exceptions import ValidationError

class AuditLog(models.Model):
    utilisateur_id = models.BigIntegerField()
    action = models.CharField(max_length=100)
    entite_type = models.CharField(max_length=50)
    entite_id = models.BigIntegerField()
    horodatage = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    details_action = models.JSONField()

    hash_precedent = models.BinaryField()
    hash_actuel = models.BinaryField()
    signature = models.BinaryField(null=True, blank=True)

    class Meta:
        db_table = "journaux_audit"
        indexes = [
            models.Index(fields=["utilisateur_id"]),
            models.Index(fields=["entite_type", "entite_id"]),
            models.Index(fields=["horodatage"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Audit logs are immutable (update forbidden).")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit logs cannot be deleted.")