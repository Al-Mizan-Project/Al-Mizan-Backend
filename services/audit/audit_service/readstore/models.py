from django.db import models


class AuditLogRead(models.Model):
    id = models.BigIntegerField(primary_key=True)
    utilisateur_id = models.BigIntegerField(db_index=True)
    action = models.CharField(max_length=100)
    entite_type = models.CharField(max_length=50, db_index=True)
    entite_id = models.BigIntegerField(db_index=True)
    horodatage = models.DateTimeField(db_index=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    details_action = models.JSONField()

    class Meta:
        db_table = "audit_read_projection"
        managed = True
        indexes = [
            models.Index(fields=["entite_type", "entite_id"]),
            models.Index(fields=["utilisateur_id", "horodatage"]),
        ]