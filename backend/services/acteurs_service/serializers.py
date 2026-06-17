from rest_framework import serializers
from .models import DemandeOperateur, DemandeDocument, Organisation, Membre

# ==========================================
# SERIALIZERS : DEMANDES (INSCRIPTION)
# ==========================================

class DemandeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandeDocument
        fields = ['id', 'document_id', 'type_document']


class DemandeOperateurSerializer(serializers.ModelSerializer):
    documents = DemandeDocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = DemandeOperateur
        fields = [
            'id', 'nom_organisation', 'email_contact', 'telephone', 
            'nif', 'num_registre_commerce', 'id_service_contractant', 'statut', 'motif_rejet',
            'cree_le', 'documents'
        ]


class DemandeOperateurDetailSerializer(serializers.ModelSerializer):
    documents_complets = serializers.SerializerMethodField()

    class Meta:
        model = DemandeOperateur
        fields = [
            'id', 'nom_organisation', 'email_contact', 'telephone', 
            'nif', 'num_registre_commerce', 'id_service_contractant', 'statut', 'motif_rejet', 'cree_le',
            'documents_complets'
        ]

    def get_documents_complets(self, obj):
        return self.context.get('documents_data', [])


class SoumettreDemandeSerializer(serializers.Serializer):
    nom_organisation = serializers.CharField(max_length=255)
    email_contact = serializers.EmailField()
    telephone = serializers.CharField(max_length=50)
    nif = serializers.CharField(max_length=50)
    num_registre_commerce = serializers.CharField(max_length=100)
    id_service_contractant = serializers.IntegerField(min_value=1)

    doc_registre_commerce = serializers.FileField()
    doc_nif = serializers.FileField()
    doc_cnas_casnos = serializers.FileField()
    doc_non_faillite = serializers.FileField()


# ==========================================
# SERIALIZERS : ORGANISATIONS (CRÉATION ET LISTE)
# ==========================================

class OrganisationCreateSerializer(serializers.Serializer):
    """Serializer de base pour créer une organisation"""
    nom_officiel = serializers.CharField(max_length=255, required=True)
    adresse_siege = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email_contact = serializers.EmailField(max_length=100, required=False, allow_blank=True)
    
    # Nouveaux champs obligatoires/facultatifs ajoutés au scope
    wilaya = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    secteur = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)


class ServiceContractantCreateSerializer(OrganisationCreateSerializer):
    """Spécifique à la création d'un Service Contractant"""
    code_service = serializers.CharField(max_length=50, default="SC-000")
    secteur_activite = serializers.CharField(max_length=100, default="Non défini")


class CommissionExterneCreateSerializer(OrganisationCreateSerializer):
    """Spécifique à la création d'une Commission Externe"""
    numero_agrement = serializers.CharField(max_length=50, default="AGR-000")
    specialite = serializers.CharField(max_length=100, default="Générale")
    niveau_competence = serializers.ChoiceField(choices=['WILAYA', 'SECTORIELLE', 'NATIONAL'], default='WILAYA')
    seuil = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.0)


class OrganisationListSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()
    id_operateur_economique = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ['id_organisation', 'id_operateur_economique', 'nom_officiel', 'email_contact', 'responsable_nom', 'wilaya', 'secteur']

    def get_responsable_nom(self, obj):
        resp = obj.membres.order_by('created_at').first()
        if resp:
            return f"{resp.prenom} {resp.nom}"
        return "Non assigné"

    def get_id_operateur_economique(self, obj):
        if getattr(obj, "type_entite", None) != "OPERATEUR_ECONOMIQUE":
            return None
        return int(str(obj.id_organisation).replace("-", "")[-8:], 16) % 2_000_000_000


class OrganisationDetailForMembreSerializer(serializers.ModelSerializer):
    type_entite_display = serializers.CharField(source='get_type_entite_display', read_only=True)

    class Meta:
        model = Organisation
        fields = [
            'id_organisation', 'nom_officiel', 'type_entite', 
            'type_entite_display', 'adresse_siege', 'email_contact',
            'wilaya', 'secteur' # Inclus pour la vue de profil détaillée
        ]


# ==========================================
# SERIALIZERS : MEMBRES
# ==========================================

class CreateResponsableSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=100)
    prenom = serializers.CharField(max_length=100)
    telephone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    fonction = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)


class MembreCreateByResponsableSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=100)
    prenom = serializers.CharField(max_length=100)
    telephone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    fonction = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role_nom = serializers.CharField(required=False, allow_blank=True)
    role = serializers.CharField(required=False, allow_blank=True)
    permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class MembreListSerializer(serializers.ModelSerializer):
    compte_auth = serializers.SerializerMethodField()

    class Meta:
        model = Membre
        fields = ['id_membre', 'nom', 'prenom', 'telephone', 'fonction', 'created_at', 'compte_auth']

    def get_compte_auth(self, obj):
        auth_data_dict = self.context.get('auth_data', {})
        return auth_data_dict.get(str(obj.id_membre), None)


class MembreDetailSerializer(serializers.ModelSerializer):
    organisation = OrganisationDetailForMembreSerializer(read_only=True)

    class Meta:
        model = Membre
        fields = ['id_membre', 'nom', 'prenom', 'telephone', 'fonction', 'created_at', 'updated_at', 'organisation']


class MembreUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membre
        fields = ['id_membre', 'nom', 'prenom', 'telephone', 'fonction', 'organisation']
        read_only_fields = ['id_membre', 'organisation']
