from django.db import models



class Organisation(models.Model):
    nom_officiel = models.CharField(max_length=20)
    adresse_siege = models.CharField(max_length=100)
    email_contact = models.EmailField(max_length=100)
    type_entite = models.CharField(max_length=30)

    def __str__(self):
        return self.nom_officiel


class Tutelle(models.Model):
    nom_tutelle = models.CharField(max_length=255)
    identite_autorite = models.CharField(max_length=255)

    def __str__(self):
        return self.nom_tutelle



class Role(models.Model):
    nom_role = models.CharField(max_length=20)

    def __str__(self):
        return self.nom_role


class Permission(models.Model):
    nom_permission = models.CharField(max_length=20)

    def __str__(self):
        return self.nom_permission


class PermissionRole(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)



class Utilisateur(models.Model):
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)

    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)

    prenom = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=30)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"



class ServiceContractant(models.Model):
    tutelle = models.ForeignKey(Tutelle, on_delete=models.CASCADE)

    categorie = models.CharField(max_length=255)
    code_ordonnateur = models.CharField(max_length=100)



class OperateurEconomique(models.Model):
    nif = models.CharField(max_length=100)
    registre_commerce_num = models.CharField(max_length=100)
    casnos_vrt = models.CharField(max_length=100)
    cnas_vrt = models.CharField(max_length=100)
    rib_bancaire = models.CharField(max_length=100)


class CommissionInterne(models.Model):
    TYPE_CHOICES = [
        ('permanante', 'Permanante'),
        ('adhoc', 'Adhoc'),
    ]

    service = models.ForeignKey(ServiceContractant, on_delete=models.CASCADE)
    nom_comission = models.CharField(max_length=255)
    type_comission = models.CharField(max_length=20, choices=TYPE_CHOICES)

class MembreCommissionInterne(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    commission_interne = models.ForeignKey(CommissionInterne, on_delete=models.CASCADE)




class CommissionExterne(models.Model):
    NIVEAU_CHOICES = [
        ('communale', 'Communale'),
        ('wilaya', 'Wilaya'),
        ('sectorielle', 'Sectorielle'),
        ('nationale', 'Nationale'),
    ]
    service = models.ForeignKey(ServiceContractant, on_delete=models.CASCADE, null=True, blank=True) 
    nom_comission = models.CharField(max_length=100)
    niveau_competance = models.CharField(max_length=20, choices=NIVEAU_CHOICES)
    seuils_competence_financiere = models.CharField(max_length=255)


class CommissionEvaluation(models.Model):
    service = models.ForeignKey(ServiceContractant, on_delete=models.CASCADE)
    nom_comission = models.CharField(max_length=255)
    categorie = models.CharField(max_length=255)


class MembreCommissionEvaluation(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE)
    commission = models.ForeignKey(CommissionEvaluation, on_delete=models.CASCADE)
