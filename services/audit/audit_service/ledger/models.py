import uuid

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

class OutboxEvent(models.Model):
    """
    Transactional outbox table.
    Written inside the same transaction as AuditLog.
    Debezium reads this table via WAL and publishes to Kafka.
    This table must NEVER be written to from outside a transaction.atomic() block.
    """
    STATUS_PENDING   = 'PENDING'
    STATUS_PROCESSED = 'PROCESSED'
    STATUS_CHOICES   = [(STATUS_PENDING, 'Pending'), (STATUS_PROCESSED, 'Processed')]
 
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=100)       # e.g. 'AuditLog'
    aggregate_id   = models.CharField(max_length=255)       # e.g. str(audit_log.pk)
    event_type     = models.CharField(max_length=150)       # e.g. 'audit_log.created'
    payload        = models.JSONField()                      # full event data
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                      default=STATUS_PENDING, db_index=True)
    trace_id       = models.CharField(max_length=128, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)
 
    class Meta:
        db_table = 'journaux_outbox'
        ordering = ['created_at']
        indexes  = [
            models.Index(fields=['aggregate_type', 'aggregate_id']),
            models.Index(fields=['event_type', 'status']),
        ]
 
    def __str__(self):
        return f'{self.event_type}:{self.aggregate_id} [{self.status}]'
