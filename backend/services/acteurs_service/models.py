from django.db import models


class Organisation(models.Model):
    id_organisation = models.AutoField(primary_key=True)
    nom_officiel = models.CharField(max_length=20, db_index=True)
    adresse_siege = models.CharField(max_length=100, blank=True)
    email_contact = models.EmailField(max_length=100, blank=True)
    type_entite = models.CharField(max_length=30, db_index=True)

    class Meta:
        db_table = "Organisation"
        indexes = [
            models.Index(fields=["type_entite", "nom_officiel"], name="organisation_type_nom_idx"),
        ]


class OperateurEconomique(models.Model):
    id_operateur_economique = models.AutoField(primary_key=True)
    nif = models.CharField(max_length=100, unique=True)
    registre_commerce_num = models.CharField(max_length=100, blank=True)
    casnos_vrt = models.CharField(max_length=100, blank=True)
    cnas_vrt = models.CharField(max_length=100, blank=True)
    rib_bancaire = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "Operateurs_Economiques"


class Membre(models.Model):
    id_membre = models.AutoField(primary_key=True)
    id_organisation = models.IntegerField(null=True, blank=True, db_index=True)
    prenom = models.CharField(max_length=100, db_index=True)
    nom = models.CharField(max_length=100, db_index=True)
    telephone = models.CharField(max_length=30, blank=True)
    fonction = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "membre"
        indexes = [
            models.Index(fields=["nom", "prenom"], name="membre_nom_prenom_idx"),
        ]


class Tutelle(models.Model):
    id_tutelle = models.AutoField(primary_key=True)
    nom_tutelle = models.CharField(max_length=255, unique=True)
    identite_autorite = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "Tutelle"
