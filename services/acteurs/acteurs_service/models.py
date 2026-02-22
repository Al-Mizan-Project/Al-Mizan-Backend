from django.db import models


class Membre(models.Model):
    id_membre = models.AutoField(primary_key=True)
    id_organisation = models.IntegerField(null=True, blank=True)
    prenom = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=30, blank=True)
    fonction = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "membre"
