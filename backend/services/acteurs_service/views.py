from rest_framework import generics
import requests
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from .models import Membre ,OperateurEconomique , TypeDocument ,DemandeDocument, DemandeOperateur, StatutDemande ,DemandeOperateur ,Organisation, ServiceContractant, CommissionExterne, TypeEntite
from .serializers import OrganisationCreateSerializer, ServiceContractantCreateSerializer, CommissionExterneCreateSerializer, MembreDetailSerializer
from .serializers import DemandeOperateurSerializer
from .serializers import DemandeOperateurDetailSerializer , MembreListSerializer
from .serializers import CreateResponsableSerializer , MembreCreateByResponsableSerializer
from rest_framework.generics import ListAPIView
from .models import Organisation, TypeEntite
from .serializers import OrganisationListSerializer
from .permissions import IsResponsable , IsAdminRole


def _auth_service_base_url():
    return getattr(
        settings,
        'AUTH_SERVICE_URL',
        getattr(settings, 'INTERNAL_BASE_URL', 'http://backend:8000'),
    ).rstrip("/")


class DemandeOperateurListView(generics.ListAPIView):
    """
    Endpoint: GET /api/acteurs/admin/demandes/
    Description: Liste toutes les demandes des opérateurs économiques.
    """
    serializer_class = DemandeOperateurSerializer
    
    # On récupère toutes les demandes, classées de la plus récente à la plus ancienne
    queryset = DemandeOperateur.objects.all().order_by('-cree_le')

    # Note : Plus tard, quand le service Auth sera connecté, 
    # vous décommenterez la ligne ci-dessous pour sécuriser l'accès.
    # permission_classes = [IsAdminUser] 

    def get_queryset(self):
        """
        Bonus : Permet au frontend de filtrer par statut si besoin
        Ex: /api/acteurs/admin/demandes/?statut=EN_ATTENTE
        """
        queryset = super().get_queryset()
        statut = self.request.query_params.get('statut', None)
        if statut is not None:
            queryset = queryset.filter(statut=statut)
        return queryset

class DemandeOperateurDetailView(generics.RetrieveAPIView):
    """
    Endpoint: GET /api/acteurs/admin/demandes/{id}/
    Récupère les détails d'une demande ET interroge le service Document.
    """
    queryset = DemandeOperateur.objects.all()
    serializer_class = DemandeOperateurDetailSerializer
    lookup_field = 'id' # Permet d'utiliser l'UUID dans l'URL

    def retrieve(self, request, *args, **kwargs):
        # 1. Récupérer l'objet DemandeOperateur de la base de données Acteurs
        instance = self.get_object()

        # 2. Extraire la liste des IDs de documents associés à cette demande
        # On récupère tous les 'document_id' (entiers) de la table intermédiaire
        document_ids = instance.documents.values_list('document_id', flat=True)
        
        documents_data = []

        # 3. S'il y a des documents, appeler le service Document
        if document_ids:
            # Convertir [1, 2, 3] en "1,2,3" pour l'URL
            ids_string = ",".join(map(str, document_ids))
            
            # URL du microservice Document (à mettre dans settings.py idéalement)
            # Ex: DOCUMENT_SERVICE_URL = "http://localhost:8001"
            base_url = getattr(settings, 'DOCUMENTS_SERVICE_URL', 'http://127.0.0.1:8001')
            
            # Utilisation du endpoint de recherche filtré par 'ids' du DocumentFilterMixin
            target_url = f"{base_url}/api/documents/search/?ids={ids_string}"
            headers = {}
            internal_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
            if internal_token:
                headers["X-Internal-Service-Token"] = internal_token
            
            try:
                response = requests.get(target_url, headers=headers)
                if response.status_code == 200:
                    documents_data = response.json() # Récupère la liste des documents JSON
                else:
                    # Gérer le cas où le service document répond mal
                    print(f"Erreur du service Document: {response.status_code}")
            except requests.exceptions.RequestException as e:
                # Gérer le cas où le service document est down
                print(f"Le service document est injoignable : {e}")
                # Vous pouvez soit bloquer la requête (raise APIException), 
                # soit renvoyer les données sans les documents avec un message.

        # 4. Enrichir les données de notre service avec le type de document métier
        # Pour associer le "REGISTRE_COMMERCE" ou "NIF" avec les données brutes du fichier
        liens_documents = {doc.document_id: doc.type_document for doc in instance.documents.all()}
        
        for doc in documents_data:
            doc_id = doc.get('id_document')
            # Ajoute le type métier (ex: NIF) au JSON renvoyé par le service document
            doc['type_metier'] = liens_documents.get(doc_id) 

            # Optionnel: Construire le lien direct de téléchargement
            doc['download_link'] = f"{base_url}/api/documents/{doc_id}/"

        # 5. Passer les documents récupérés au Serializer via le context
        serializer = self.get_serializer(instance, context={'documents_data': documents_data})
        
        return Response(serializer.data)
    
class DemandeApprouverView(APIView):
    """
    Endpoint: POST /api/acteurs/admin/demandes/{id}/approuver/
    Action: Passe la demande en APPROUVE et crée l'Organisation + OperateurEconomique.
    """

    def post(self, request, id, *args, **kwargs):
        # 1. Récupérer la demande
        demande = get_object_or_404(DemandeOperateur, id=id)

        # Vérifier si elle n'est pas déjà traitée
        if demande.statut != StatutDemande.EN_ATTENTE:
            return Response(
                {"erreur": f"Impossible d'approuver. La demande est actuellement : {demande.get_statut_display()}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # On utilise atomic() pour s'assurer que toutes les requêtes SQL passent, ou aucune.
        try:
            with transaction.atomic():
                # 2. Mettre à jour le statut de la demande
                demande.statut = StatutDemande.APPROUVE
                demande.save()

                # 3. Créer l'entité globale Organisation
                organisation = Organisation.objects.create(
                    nom_officiel=demande.nom_organisation,
                    email_contact=demande.email_contact,
                    type_entite=TypeEntite.OPERATEUR_ECONOMIQUE
                )

                # 4. Créer l'entité spécifique OperateurEconomique rattachée à l'organisation
                operateur = OperateurEconomique.objects.create(
                    organisation=organisation,
                    nif=demande.nif,
                    num_registre_commerce=demande.num_registre_commerce
                )

            # On renvoie l'ID de la nouvelle organisation pour que le frontend 
            # puisse enchaîner avec la création du responsable
            return Response({
                "message": "Demande approuvée avec succès. L'entreprise a été créée.",
                "demande_id": demande.id,
                "organisation_id": organisation.id_organisation
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"erreur": f"Une erreur est survenue lors de la création de l'entité : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DemandeRejeterView(APIView):
    """
    Endpoint: POST /api/acteurs/admin/demandes/{id}/rejeter/
    Action: Rejette une demande d'inscription avec un motif.
    """

    def post(self, request, id, *args, **kwargs):
        demande = get_object_or_404(DemandeOperateur, id=id)

        if demande.statut != StatutDemande.EN_ATTENTE:
            return Response(
                {"erreur": f"Impossible de rejeter. La demande est actuellement : {demande.get_statut_display()}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        motif = str(request.data.get("motif", "")).strip()
        if not motif:
            return Response(
                {"motif": ["Ce champ est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        demande.statut = StatutDemande.REJETE
        demande.motif_rejet = motif
        demande.save(update_fields=["statut", "motif_rejet", "mis_a_jour_le"])

        return Response(
            {
                "message": "Demande rejetée avec succès.",
                "demande_id": demande.id,
                "statut": demande.statut,
                "motif_rejet": demande.motif_rejet,
            },
            status=status.HTTP_200_OK,
        )


class CreerResponsableView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    def post(self, request, org_id):
        serializer = CreateResponsableSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        organisation = get_object_or_404(Organisation, id_organisation=org_id)
        data = serializer.validated_data

        # Configuration Rôle/Permission selon le type d'organisation (PDF Page 2)
        mapping = {
            TypeEntite.OPERATEUR_ECONOMIQUE: ("Operateur Economique", "responsable_operateur_economique"),
            TypeEntite.SERVICE_CONTRACTANT: ("SERVICE Contractant", "responsable_service_contratant"),
            TypeEntite.COMMISSION_EXTERNE: ("Commission Externe", "responsable_commission_externe"),
        }
        
        role_nom, perm_nom = mapping.get(organisation.type_entite, (None, None))

        try:
            with transaction.atomic():
                # ÉTAPE A : Créer le membre localement pour obtenir l'id_membre
                membre = Membre.objects.create(
                    organisation=organisation,
                    nom=data['nom'],
                    prenom=data['prenom'],
                    telephone=data.get('telephone'),
                    fonction=data.get('fonction')
                )

                # ÉTAPE B : Préparer l'appel au service Auth
                # On envoie l'id_membre pour que l'utilisateur pointe vers lui
                auth_payload = {
                    "email": data['email'],
                    "password": data['password'],
                    "id_membre": str(membre.id_membre), 
                    "role_nom": role_nom,
                    "permissions": [perm_nom],
                    "nom": data['nom'],
                    "prenom": data['prenom']
                }

               # L'URL pointe vers la nouvelle route interne
                auth_url = _auth_service_base_url() + "/internal/users/register"
                auth_response = requests.post(auth_url, json=auth_payload)
                if auth_response.status_code != 201:
                    # Si Auth échoue, on rollback la création du membre
                    raise Exception(f"Erreur Service Auth: {auth_response.text}")

            return Response({
                "message": "Responsable créé avec succès (Membre + Compte Auth)",
                "id_membre": membre.id_membre
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "erreur": "Échec de la procédure de création",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class CreerServiceContractantView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    """ POST /api/acteurs/admin/organisations/service-contractant/ """
    def post(self, request):
        serializer = OrganisationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            with transaction.atomic():
                org = Organisation.objects.create(
                    nom_officiel=data['nom_officiel'],
                    adresse_siege=data.get('adresse_siege', ''),
                    email_contact=data.get('email_contact', ''),
                    type_entite=TypeEntite.SERVICE_CONTRACTANT
                )
                ServiceContractant.objects.create(organisation=org)
                
            return Response({
                "message": "Service Contractant créé avec succès",
                "id_organisation": org.id_organisation
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"erreur": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreerCommissionExterneView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    """ POST /api/acteurs/admin/organisations/commission-externe/ """
    def post(self, request):
        serializer = OrganisationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            with transaction.atomic():
                org = Organisation.objects.create(
                    nom_officiel=data['nom_officiel'],
                    adresse_siege=data.get('adresse_siege', ''),
                    email_contact=data.get('email_contact', ''),
                    type_entite=TypeEntite.COMMISSION_EXTERNE
                )
                CommissionExterne.objects.create(organisation=org)
                
            return Response({
                "message": "Commission Externe créée avec succès",
                "id_organisation": org.id_organisation
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"erreur": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateMembreByResponsableView(APIView):
    permission_classes = [IsAuthenticated , IsResponsable] # Seul un utilisateur connecté peut créer des membres

    def post(self, request):
        serializer = MembreCreateByResponsableSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # 1. Récupérer l'organisation du responsable actuel
        # On passe par l'ID membre stocké dans le token/user du service Auth
        id_membre_responsable = request.user.id_membre 
        try:
            responsable_entite = Membre.objects.get(id_membre=id_membre_responsable)
            organisation = responsable_entite.organisation
        except Membre.DoesNotExist:
            return Response({"erreur": "Responsable non trouvé dans le service Acteurs"}, status=404)

        try:
            with transaction.atomic():
                # 2. CRÉATION DU NOUVEAU MEMBRE (Collaborateur)
                nouveau_membre = Membre.objects.create(
                    organisation=organisation,
                    nom=data['nom'],
                    prenom=data['prenom'],
                    telephone=data.get('telephone'),
                    fonction=data.get('fonction')
                )

                # 3. PRÉPARATION APPEL AUTH
                # Le rôle est le même que celui de l'organisation
                role_mapping = {
                    'SERVICE_CONTRACTANT': "SERVICE Contractant",
                    'OPERATEUR_ECONOMIQUE': "Operateur Economique",
                    'COMMISSION_EXTERNE': "Commission Externe",
                }
                
                auth_payload = {
                    "email": data['email'],
                    "password": data['password'],
                    "id_membre": str(nouveau_membre.id_membre),
                    "role_nom": role_mapping.get(organisation.type_entite),
                    "permissions": data['permissions'], # Les permissions choisies par le responsable
                    "nom": data['nom'],
                    "prenom": data['prenom']
                }

                # Appel vers le service Auth
                # L'URL pointe vers la nouvelle route interne
                auth_url = _auth_service_base_url() + "/internal/users/register"
                auth_response = requests.post(auth_url, json=auth_payload)
                if auth_response.status_code != 201:
                    raise Exception(f"Erreur Auth: {auth_response.text}")

            return Response({
                "message": "Membre et compte collaborateur créés avec succès",
                "id_membre": nouveau_membre.id_membre
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"erreur": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ListMembresOrganisationView(APIView):
    """
    Endpoint: GET /api/acteurs/organisations/{org_id}/membres/
    Action: Liste les membres d'une organisation et récupère leurs emails/permissions depuis Auth.
    """
    
    # Si vous avez l'authentification activée, décommentez la ligne suivante :
    # permission_classes = [IsAuthenticated]

    def get(self, request, org_id):
        # 1. Vérifier que l'organisation existe
        organisation = get_object_or_404(Organisation, id_organisation=org_id)
        membres = Membre.objects.filter(organisation=organisation).order_by('-created_at')

        # 3. Préparer l'appel au service Auth pour récupérer les emails et permissions
        auth_data_dict = {}
        if membres.exists():
            # Extraire la liste des IDs sous forme de strings
            membres_ids = [str(m.id_membre) for m in membres]
            ids_string = ",".join(membres_ids)
            
            # Appel au service Auth (Il faudra créer cet endpoint côté Auth s'il n'existe pas)
            auth_service_url = _auth_service_base_url()
            try:
                # On demande au service Auth de nous renvoyer les comptes liés à ces id_membre
                response = requests.get(f"{auth_service_url}/internal/users/search?membres_ids={ids_string}")
                
                if response.status_code == 200:
                    comptes = response.json() # Liste d'utilisateurs Auth
                    # On transforme la liste en dictionnaire avec 'id_membre' comme clé pour un accès rapide
                    for compte in comptes:
                        # On suppose que le service Auth renvoie l'id_membre avec le compte
                        auth_data_dict[compte.get('id_membre')] = {
                            "email": compte.get('email'),
                            "is_active": compte.get('is_active'),
                            "role": compte.get('role'),
                            "permissions": compte.get('permissions', [])
                        }
            except requests.exceptions.RequestException as e:
                print(f"Attention : Le service Auth est injoignable. Erreur: {e}")
                # On ne bloque pas la requête, on renverra juste null pour 'compte_auth'

        # 4. Sérialiser les données en passant le dictionnaire Auth dans le context
        serializer = MembreListSerializer(membres, many=True, context={'auth_data': auth_data_dict})

        return Response(serializer.data, status=status.HTTP_200_OK)

class ListServiceContractantView(ListAPIView):
    """ GET /api/acteurs/admin/organisations/service-contractant/ """
    serializer_class = OrganisationListSerializer

    def get_queryset(self):
        return Organisation.objects.filter(
            type_entite=TypeEntite.SERVICE_CONTRACTANT
        ).order_by('-created_at')


class ListCommissionExterneView(ListAPIView):
    """ GET /api/acteurs/admin/organisations/commission-externe/ """
    serializer_class = OrganisationListSerializer

    def get_queryset(self):
        return Organisation.objects.filter(
            type_entite=TypeEntite.COMMISSION_EXTERNE
        ).order_by('-created_at')



class ListOperateurEconomiqueView(ListAPIView):
    """ GET /api/acteurs/admin/organisations/operateurs/ """
    serializer_class = OrganisationListSerializer

    def get_queryset(self):
        return Organisation.objects.filter(
            type_entite=TypeEntite.OPERATEUR_ECONOMIQUE
        ).order_by('-created_at')
        

class SoumettreDemandeOperateurView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    """
    Endpoint: POST /api/acteurs/demandes/soumettre/
    Description: Permet à un opérateur économique de soumettre une demande d'inscription.
    
    Flow:
      1. Valider les données du formulaire
      2. Uploader chaque fichier vers le service Document
      3. Créer la DemandeOperateur en base
      4. Créer les DemandeDocument (liens entre demande et IDs du service Document)
    
    Format: multipart/form-data (car on envoie des fichiers)
    Permissions: Publique (pas de token requis, c'est une inscription)
    """

    def post(self, request, *args, **kwargs):
        from .serializers import SoumettreDemandeSerializer

        serializer = SoumettreDemandeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Mapping : nom du champ formulaire → TypeDocument (choix du modèle)
        FICHIERS_MAPPING = {
            'doc_registre_commerce': TypeDocument.REGISTRE_COMMERCE,
            'doc_nif':               TypeDocument.NIF,
            'doc_cnas_casnos':       TypeDocument.CNAS_CASNOS,
            'doc_non_faillite':      TypeDocument.NON_FAILLITE,
        }

        base_url = getattr(settings, 'DOCUMENTS_SERVICE_URL', 'http://127.0.0.1:8001')
        upload_url = f"{base_url}/api/documents/"

        headers = {}
        internal_token = getattr(settings, "INTERNAL_SERVICE_TOKEN", "")
        if internal_token:
            headers["X-Internal-Service-Token"] = internal_token

        # Étape 1 : Uploader tous les fichiers vers le service Document
        # On collecte les résultats avant d'écrire en base (fail-fast)
        documents_uploades = []  # Liste de dicts { 'type_document': ..., 'document_id': ... }

        for champ, type_document in FICHIERS_MAPPING.items():
            fichier = data[champ]
            try:
                response = requests.post(
                    upload_url,
                    headers=headers,
                    data={'related_type': 'demande_operateur'},
                    files={'file': (fichier.name, fichier, fichier.content_type)},
                )
            except requests.exceptions.RequestException as e:
                return Response(
                    {"erreur": f"Le service Document est injoignable : {str(e)}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            if response.status_code not in (200, 201):
                return Response(
                    {
                        "erreur": f"Échec de l'upload du document '{type_document}'.",
                        "detail": response.text,
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )

            # On récupère l'ID assigné par le service Document
            # On suppose que le service renvoie { "id_document": 42, ... }
            document_id = response.json().get('id_document')
            if not document_id:
                return Response(
                    {"erreur": f"Le service Document n'a pas renvoyé d'id_document pour '{type_document}'."},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            documents_uploades.append({
                'type_document': type_document,
                'document_id':   document_id,
            })

        # Étape 2 : Tout est uploadé → on écrit en base de manière atomique
        try:
            with transaction.atomic():
                # Créer la demande principale
                demande = DemandeOperateur.objects.create(
                    nom_organisation      = data['nom_organisation'],
                    email_contact         = data['email_contact'],
                    telephone             = data['telephone'],
                    nif                   = data['nif'],
                    num_registre_commerce = data['num_registre_commerce'],
                    # statut = EN_ATTENTE par défaut (défini dans le modèle)
                )

                # Créer les liens DemandeDocument
                DemandeDocument.objects.bulk_create([
                    DemandeDocument(
                        demande       = demande,
                        document_id   = doc['document_id'],
                        type_document = doc['type_document'],
                    )
                    for doc in documents_uploades
                ])

        except Exception as e:
            # Note : les fichiers sont déjà uploadés dans le service Document.
            # Dans une architecture robuste, il faudrait les supprimer ici (compensating transaction).
            return Response(
                {"erreur": f"Erreur lors de l'enregistrement en base : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "message": "Votre demande a été soumise avec succès. Elle est en attente de validation par l'administrateur.",
                "demande_id": str(demande.id),
                "statut":     demande.statut,
            },
            status=status.HTTP_201_CREATED
        )
        
class MembreDetailView(generics.RetrieveAPIView):
    """
    Endpoint: GET /api/acteurs/membres/{id_membre}/
    Description: Récupère les détails d'un membre spécifique et les infos de son organisation.
    """
    # L'utilisation de select_related permet d'optimiser la requête SQL (évite le problème N+1)
    queryset = Membre.objects.select_related('organisation').all()
    serializer_class = MembreDetailSerializer
    
    # On précise à DRF que l'ID dans l'URL correspond au champ 'id_membre' dans le modèle
    lookup_field = 'id_membre' 

    # Décommente cette ligne si tu veux que seul un utilisateur connecté puisse voir ces infos
    # permission_classes = [IsAuthenticated]


class OrganisationResponsableByTypeView(APIView):
    """
    GET /organisations/by-type/{entite_type}/responsable/
    """
    def get(self, request, entite_type):
        # Normalisation du type (ex: 'externe' -> 'COMMISSION_EXTERNE')
        type_map = {
            'externe': TypeEntite.COMMISSION_EXTERNE,
            'commission_externe': TypeEntite.COMMISSION_EXTERNE,
        }
        target_type = type_map.get(entite_type.lower(), entite_type)
        
        # Filtre optionnel par organisation spécifique
        org_id = request.query_params.get('org_id')
        if org_id:
            orgs = Organisation.objects.filter(id_organisation=org_id, type_entite=target_type)
        else:
            orgs = Organisation.objects.filter(type_entite=target_type)
            
        if not orgs.exists():
            return Response({"error": f"Organisation de type {target_type} non trouvée"}, status=404)
        
        # Filtre optionnel par liste de membres (IDs entiers ou UUIDs)
        membres_ids_param = request.query_params.get("membres_ids")
        if membres_ids_param:
            ids_raw = [id.strip() for id in membres_ids_param.split(",")]
            # Conversion potentielle de int vers UUID (format 0000...)
            ids_processed = []
            for ir in ids_raw:
                if len(ir) < 12 and ir.isdigit():
                    hex_id = hex(int(ir))[2:].zfill(12)
                    ids_processed.append(f"00000000-0000-0000-0000-{hex_id}")
                else:
                    ids_processed.append(ir)
            
            members_queryset = Membre.objects.filter(id_membre__in=ids_processed)
        else:
            members_queryset = Membre.objects.filter(organisation__in=orgs)

        # Recherche du responsable
        membre = members_queryset.filter(fonction__icontains='Responsable').first()
        if not membre:
            membre = members_queryset.filter(fonction__icontains='Chef').first()
        if not membre:
            membre = members_queryset.first()
            
        if not membre:
            return Response({"error": "Aucun membre trouvé"}, status=404)
            
        # Récupération de l'ID utilisateur via Auth
        id_utilisateur = None
        auth_service_url = getattr(settings, 'AUTH_SERVICE_URL', 'http://localhost:8002')
        try:
            resp = requests.get(f"{auth_service_url}/internal/users/search?membres_ids={membre.id_membre}", timeout=2)
            if resp.status_code == 200:
                users = resp.json()
                if users:
                    id_utilisateur = users[0].get('id_utilisateur')
        except Exception as e:
            print(f"Erreur Auth: {e}")

        return Response({
            "id_membre": str(membre.id_membre),
            "id_utilisateur": id_utilisateur,
            "nom": f"{membre.prenom} {membre.nom}",
            "organisation_nom": membre.organisation.nom_officiel
        })