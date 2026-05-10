from rest_framework import serializers
from .models import DemandeOperateur, DemandeDocument , Organisation , Membre

class DemandeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandeDocument
        # On affiche l'ID interne, l'ID du document (service Document), et le type
        fields = ['id', 'document_id', 'type_document']

class DemandeOperateurSerializer(serializers.ModelSerializer):
    # On récupère les documents associés grâce au related_name='documents' défini dans le modèle
    documents = DemandeDocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = DemandeOperateur
        # On liste tous les champs qu'on veut envoyer au frontend
        fields = [
            'id', 
            'nom_organisation', 
            'email_contact', 
            'telephone', 
            'nif', 
            'num_registre_commerce', 
            'statut', 
            'motif_rejet',
            'cree_le', 
            'documents' # Ceci inclura la liste des documents imbriquée
        ]

class DemandeOperateurDetailSerializer(serializers.ModelSerializer):
    # On définit un champ dynamique qui ne vient pas de la base de données
    documents_complets = serializers.SerializerMethodField()

    class Meta:
        model = DemandeOperateur
        fields = [
            'id', 'nom_organisation', 'email_contact', 'telephone', 
            'nif', 'num_registre_commerce', 'statut', 'motif_rejet', 'cree_le', 
            'documents_complets' # Notre nouveau champ
        ]

    def get_documents_complets(self, obj):
        # Ce champ sera rempli manuellement dans la vue via le context
        return self.context.get('documents_data', [])


class CreateResponsableSerializer(serializers.Serializer):
    # Champs pour le service Acteurs (table membre)
    nom = serializers.CharField(max_length=100)
    prenom = serializers.CharField(max_length=100)
    telephone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    fonction = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    # Champs pour le service Auth (table utilisateurs)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
class OrganisationCreateSerializer(serializers.Serializer):
    """
    Serializer pour créer une organisation (Service Contractant, Commission ou Tutelle)
    basé sur les champs exacts de la table.
    """
    nom_officiel = serializers.CharField(max_length=100, required=True)
    adresse_siege = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email_contact = serializers.EmailField(max_length=100, required=False, allow_blank=True)
    
    
class MembreCreateByResponsableSerializer(serializers.Serializer):
    # Infos pour la table Membre
    nom = serializers.CharField(max_length=100)
    prenom = serializers.CharField(max_length=100)
    telephone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    fonction = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    # Infos pour le compte Auth
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    # Liste des permissions techniques (ex: ['redacteur_cdc', 'evaluer_offre_technique'])
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        min_length=1
    )
    

class MembreListSerializer(serializers.ModelSerializer):
    # Champ dynamique pour accueillir les infos du service Auth (email, permissions...)
    compte_auth = serializers.SerializerMethodField()

    class Meta:
        model = Membre
        fields = [
            'id_membre', 
            'nom', 
            'prenom', 
            'telephone', 
            'fonction', 
            'created_at', 
            'compte_auth' # Le champ dynamique
        ]

    def get_compte_auth(self, obj):
        # On récupère le dictionnaire 'auth_data' passé via le context dans la vue
        auth_data_dict = self.context.get('auth_data', {})
        # On retourne les infos Auth correspondant à cet id_membre (s'il y en a)
        return auth_data_dict.get(str(obj.id_membre), None)


class OrganisationListSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ['id_organisation', 'nom_officiel', 'email_contact', 'responsable_nom']

    def get_responsable_nom(self, obj):
        # On cherche le premier membre créé pour cette organisation
        # (Vu que dans notre logique, le premier créé est le responsable)
        resp = obj.membres.order_by('created_at').first()
        if resp:
            return f"{resp.prenom} {resp.nom}"
        return "Non assigné"
    

class SoumettreDemandeSerializer(serializers.Serializer):
    """
    Serializer pour la soumission d'une demande d'inscription par un opérateur économique.
    Les documents sont envoyés comme fichiers multipart.
    """
    nom_organisation = serializers.CharField(max_length=255)
    email_contact    = serializers.EmailField()
    telephone        = serializers.CharField(max_length=50)
    nif              = serializers.CharField(max_length=50)
    num_registre_commerce = serializers.CharField(max_length=100)

    # Les 4 documents obligatoires (fichiers uploadés)
    doc_registre_commerce = serializers.FileField()
    doc_nif               = serializers.FileField()
    doc_cnas_casnos       = serializers.FileField()
    doc_non_faillite      = serializers.FileField()
    
    

class OrganisationDetailForMembreSerializer(serializers.ModelSerializer):
    # Ce champ permet de récupérer le libellé lisible ("Service Contractant" au lieu de "SERVICE_CONTRACTANT")
    type_entite_display = serializers.CharField(source='get_type_entite_display', read_only=True)

    class Meta:
        model = Organisation
        fields = [
            'id_organisation', 
            'nom_officiel', 
            'type_entite', 
            'type_entite_display', 
            'adresse_siege', 
            'email_contact'
        ]

class MembreDetailSerializer(serializers.ModelSerializer):
    # On imbrique le serializer de l'organisation créé juste au-dessus
    organisation = OrganisationDetailForMembreSerializer(read_only=True)

    class Meta:
        model = Membre
        fields = [
            'id_membre',
            'nom',
            'prenom',
            'telephone',
            'fonction',
            'created_at',
            'updated_at',
            'organisation' # Inclut toutes les infos de l'entité et son type
        ]
