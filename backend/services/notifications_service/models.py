from django.db import models

class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    utilisateur_id = models.IntegerField()
    type_notification = models.CharField(max_length=50)
    titre = models.CharField(max_length=255)
    message = models.TextField()
    priorite = models.CharField(max_length=20)
    categorie = models.CharField(max_length=50)
    entite_liee_type = models.CharField(max_length=30)
    entite_liee_id = models.IntegerField(null=True, blank=True)
    statut = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"

    def __str__(self):
        return f"{self.titre} (User {self.utilisateur_id})"
