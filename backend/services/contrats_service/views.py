import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.permissions import (
    AuthenticatedOrInternalServicePermission,
    internal_service_headers,
)

from .models import Validation, Contrat, DocumentContrat
from .serializers import (
    ValidationSerializer,
    ValidationUpdateSerializer,
    ContratSerializer,
    ContratUpdateSerializer,
    DocumentContratSerializer,
)

# --- ADDITION ---
import logging
logger = logging.getLogger(__name__)
# --- END ADDITION ---


# ---------------------------------------------------------------------------
# Common / health
# ---------------------------------------------------------------------------

class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ready = False
        cache_ready = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_ready = cursor.fetchone()[0] == 1
        except Exception:
            db_ready = False
        try:
            probe_key = "contrats:ready"
            cache.set(probe_key, "1", timeout=5)
            cache_ready = cache.get(probe_key) == "1"
        except Exception:
            cache_ready = False
        if db_ready and cache_ready:
            return Response({"status": "ready"})
        return Response(
            {"status": "not_ready", "database": db_ready, "cache": cache_ready},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ProtectedAPIView(APIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


class ProtectedListCreateAPIView(ListCreateAPIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


class ProtectedRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [AuthenticatedOrInternalServicePermission]


# ---------------------------------------------------------------------------
# Validation CRUD
# ---------------------------------------------------------------------------

class ValidationListCreateView(ProtectedListCreateAPIView):
    queryset = Validation.objects.all().order_by("id_validation")
    
    def get_queryset(self):
        # --- ADDITION FOR SERVICE ISOLATION ---
        queryset = self.queryset
        auth_header = self.request.headers.get("Authorization")
        if auth_header:
            headers = {"Authorization": auth_header}
            url_my_service = f"{settings.CONTRACTANT_SERVICE_URL}/my-service"
            try:
                resp_s = requests.get(url_my_service, headers=headers, timeout=3)
                if resp_s.status_code == 200:
                    service_id = resp_s.json().get("id_service")
                    if service_id:
                        url_appels = f"{settings.APPELS_SERVICE_URL}/services-contractants/{service_id}/appels-offres"
                        resp_a = requests.get(url_appels, headers=internal_service_headers(), timeout=3)
                        if resp_a.status_code == 200:
                            data_a = resp_a.json()
                            appels = data_a if isinstance(data_a, list) else data_a.get("results", [])
                            ao_ids = [a.get("id_appel_offres") or a.get("id_appel_offre") for a in appels]
                            ao_ids = [x for x in ao_ids if x is not None]

                            if ao_ids:
                                # FIX: correct path is /api/soumissions/
                                url_soums = f"{settings.SOUMISSIONS_SERVICE_URL}/api/soumissions/"
                                resp_soums = requests.get(url_soums, headers=internal_service_headers(), timeout=3)
                                if resp_soums.status_code == 200:
                                    data_s = resp_soums.json()
                                    soums = data_s if isinstance(data_s, list) else data_s.get("results", [])
                                    # FIX: handle both field name variants
                                    allowed_soum_ids = [
                                        s.get("id_soumission")
                                        for s in soums
                                        if (s.get("id_appel_offres") or s.get("id_appel_offre")) in ao_ids
                                    ]
                                    allowed_soum_ids = [x for x in allowed_soum_ids if x is not None]
                                    if allowed_soum_ids:
                                        queryset = queryset.filter(id_soumission__in=allowed_soum_ids)
            except Exception as e:
                logger.warning(f"Service isolation filter failed (returning all): {e}")

        # --- AJOUT : FILTRAGE PAR PARAMÈTRES DE REQUÊTE ---
        # Permet d'éviter de tout récupérer côté client
        id_user = self.request.query_params.get('id_utilisateur')
        if id_user:
            queryset = queryset.filter(id_utilisateur=id_user)
            
        id_soum = self.request.query_params.get('id_soumission')
        if id_soum:
            queryset = queryset.filter(id_soumission=id_soum)
            
        is_val = self.request.query_params.get('is_validated')
        if is_val is not None:
            queryset = queryset.filter(is_validated=is_val.lower() == 'true')
        # --------------------------------------------------

        return queryset
        # --- END ADDITION ---

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ValidationSerializer
        return ValidationSerializer


class ValidationRetrieveUpdateDeleteView(ProtectedRetrieveUpdateDestroyAPIView):
    queryset = Validation.objects.all()
    lookup_field = "id_validation"
    lookup_url_kwarg = "validation_id"

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ValidationUpdateSerializer
        return ValidationSerializer


class ValidationApproveView(ProtectedAPIView):
    """POST /validations/{validation_id}/approuver"""

    def post(self, request, validation_id):
        validation = Validation.objects.filter(id_validation=validation_id).first()
        if not validation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        commentaire = request.data.get("commentaire", "")
        validation.is_validated = True
        if commentaire:
            validation.commentaire = commentaire
            
        validation.save(update_fields=["is_validated", "commentaire", "updated_at"])
        return Response(ValidationSerializer(validation).data)


class ValidationRejectView(ProtectedAPIView):
    """POST /validations/{validation_id}/rejeter"""

    def post(self, request, validation_id):
        validation = Validation.objects.filter(id_validation=validation_id).first()
        if not validation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        commentaire = request.data.get("commentaire", "")
        validation.is_validated = False
        if commentaire:
            validation.commentaire = commentaire
        validation.save(update_fields=["is_validated", "commentaire", "updated_at"])
        return Response(ValidationSerializer(validation).data)


# ---------------------------------------------------------------------------
# Contrat CRUD
# ---------------------------------------------------------------------------

class ContratListCreateView(ProtectedListCreateAPIView):
    queryset = Contrat.objects.all().order_by("id_contrat")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ContratSerializer
        return ContratSerializer


class ContratRetrieveUpdateDeleteView(ProtectedRetrieveUpdateDestroyAPIView):
    queryset = Contrat.objects.all()
    lookup_field = "id_contrat"
    lookup_url_kwarg = "contrat_id"

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ContratUpdateSerializer
        return ContratSerializer


class ContratSignView(ProtectedAPIView):
    """POST /contrats/{contrat_id}/signer"""

    def post(self, request, contrat_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if contrat.statut == "signe" or contrat.date_signature is not None:
            return Response(
                {"detail": "Le contrat est déjà signé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contrat.statut = "signe"
        contrat.date_signature = timezone.now()
        contrat.save(update_fields=["statut", "date_signature", "updated_at"])
        return Response(ContratSerializer(contrat).data)


# ---------------------------------------------------------------------------
# Documents ↔ Contrat
# ---------------------------------------------------------------------------

class ContratDocumentsListView(ProtectedAPIView):
    """GET /contrats/{contrat_id}/documents"""

    def get(self, request, contrat_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        links = DocumentContrat.objects.filter(id_contrat=contrat).order_by("id_document")
        document_ids = list(links.values_list("id_document", flat=True))

        # Attempt to enrich with document details from documents service
        documents_service_url = getattr(settings, "DOCUMENTS_SERVICE_URL", "")
        enriched = []
        if documents_service_url:
            timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
            for doc_id in document_ids:
                url = f"{documents_service_url.rstrip('/')}/documents/{doc_id}"
                try:
                    resp = requests.get(
                        url,
                        timeout=timeout,
                        headers=internal_service_headers(),
                    )
                    if resp.status_code == 200:
                        enriched.append(resp.json())
                    else:
                        enriched.append({"id_document": doc_id})
                except requests.RequestException:
                    enriched.append({"id_document": doc_id})
        else:
            enriched = [{"id_document": doc_id} for doc_id in document_ids]

        return Response(enriched)


class ContratDocumentDetailView(ProtectedAPIView):
    """
    POST   /contrats/{contrat_id}/documents/{document_id}
    DELETE /contrats/{contrat_id}/documents/{document_id}
    """

    def post(self, request, contrat_id, document_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(
                {"detail": "Contrat not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate document exists via documents service
        documents_service_url = getattr(settings, "DOCUMENTS_SERVICE_URL", "")
        if documents_service_url:
            timeout = getattr(settings, "REMOTE_SERVICE_TIMEOUT", 3)
            url = f"{documents_service_url.rstrip('/')}/documents/{document_id}"
            try:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers=internal_service_headers(),
                )
                if resp.status_code != 200:
                    return Response(
                        {"detail": "Document not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            except requests.RequestException:
                return Response(
                    {"detail": "Unable to validate document at this time."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        _, created = DocumentContrat.objects.get_or_create(
            id_contrat=contrat, id_document=document_id
        )
        if created:
            return Response(
                {"id_contrat": contrat_id, "id_document": document_id},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"id_contrat": contrat_id, "id_document": document_id},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, contrat_id, document_id):
        contrat = Contrat.objects.filter(id_contrat=contrat_id).first()
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deleted_count, _ = DocumentContrat.objects.filter(
            id_contrat=contrat, id_document=document_id
        ).delete()
        if deleted_count == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Cross‑entity lookups
# ---------------------------------------------------------------------------

class SoumissionContratView(ProtectedAPIView):
    """GET /soumissions/{soumission_id}/contrat"""

    def get(self, request, soumission_id):
        if not contrat:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ContratSerializer(contrat).data)


# --- ADDITION FOR AFFECTATION WORKFLOW ---

class AffectationDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    """
    GET /affectation-details/{soumission_id}
    Aggregates all data needed for the assignment page.
    """
    def get(self, request, soumission_id):
        # Forward the user's JWT for authenticated calls
        auth_header = request.headers.get("Authorization", "")
        user_jwt_headers = {"Authorization": auth_header} if auth_header else {}

        # 1. Fetch Soumission details (Internal call with service token)
        url_soum = f"{settings.SOUMISSIONS_SERVICE_URL}/soumissions/{soumission_id}"
        try:
            resp_soum = requests.get(url_soum, headers=internal_service_headers(), timeout=3)
            if resp_soum.status_code != 200:
                return Response({"error": "Soumission non trouvée"}, status=404)
            soum_data = resp_soum.json()
        except Exception as e:
            return Response({"error": f"Service soumissions injoignable: {str(e)}"}, status=503)

        # 2. Fetch User's Service ID — forward the user's JWT so Django identifies them
        url_my_service = f"{settings.CONTRACTANT_SERVICE_URL}/my-service"
        try:
            resp_ms = requests.get(url_my_service, headers=user_jwt_headers, timeout=3)
            if resp_ms.status_code != 200:
                logger.error(f"MyService failed: {resp_ms.status_code} - {resp_ms.text}")
                return Response({"error": "Service contractant non identifié"}, status=400)
            service_id = resp_ms.json().get("id_service")
        except Exception as e:
            logger.error(f"MyService exception: {e}")
            return Response({"error": "Service contractant injoignable"}, status=503)

        # 3. Fetch Members of the commission
        members_list = []
        try:
            # Get commissions for this service
            url_commissions = f"{settings.CONTRACTANT_SERVICE_URL}/services-contractants/{service_id}/commissions"
            resp_comm = requests.get(url_commissions, headers=internal_service_headers(), timeout=3)
            
            if resp_comm.status_code == 200:
                comm_data = resp_comm.json()
                
                # On combine les commissions internes et d'évaluation
                all_comms = []
                if isinstance(comm_data, dict):
                    all_comms.extend([{'id': c['id_comission_interne'], 'type': 'internes'} for c in comm_data.get('commissions_internes', [])])
                    all_comms.extend([{'id': c['id_comission'], 'type': 'evaluation'} for c in comm_data.get('commissions_evaluation', [])])
                
                # For each commission, get members
                seen_members = set()
                for comm in all_comms:
                    c_id = comm['id']
                    c_type = comm['type']
                    
                    url_m = f"{settings.CONTRACTANT_SERVICE_URL}/commissions-{c_type}/{c_id}/membres"
                    resp_m = requests.get(url_m, headers=internal_service_headers(), timeout=3)
                    if resp_m.status_code == 200:
                        comm_members = resp_m.json()
                        for m in comm_members:
                            uid = m.get("id_membre")
                            if uid in seen_members: continue
                            seen_members.add(uid)

                            # Calcul de la charge (local)
                            workload = Validation.objects.filter(id_utilisateur=uid, is_validated=False).count()
                            
                            # Tentative de récupération du nom réel et de l'id_utilisateur via le service Acteurs
                            real_name = f"Membre #{uid}"
                            actual_user_id = uid # Fallback
                            try:
                                # On convertit l'ID entier en format hex pour retrouver le membre
                                hex_id = hex(uid)[2:].zfill(12)
                                member_uuid = f"00000000-0000-0000-0000-{hex_id}"
                                url_actor = f"{getattr(settings, 'ACTEURS_SERVICE_URL', '').rstrip('/')}/membres/{member_uuid}"
                                resp_actor = requests.get(url_actor, headers=internal_service_headers(), timeout=1)
                                if resp_actor.status_code == 200:
                                    actor_data = resp_actor.json()
                                    real_name = f"{actor_data.get('nom', '')} {actor_data.get('prenom', '')}".strip() or real_name
                                    # L'id_utilisateur est souvent stocké dans les métadonnées ou lié par l'email
                                    # Pour ce projet, on va tenter de récupérer l'id_utilisateur s'il est présent dans la réponse
                                    # Sinon, on garde l'ID de membre comme fallback (si le seed est 1:1)
                                    if 'id_utilisateur' in actor_data:
                                        actual_user_id = actor_data['id_utilisateur']
                            except Exception:
                                pass

                            members_list.append({
                                "id_membre": uid,
                                "id_utilisateur": actual_user_id, 
                                "nom": real_name,
                                "charge_actuelle": workload,
                                "disponibilite": "Disponible" if workload < 3 else "Chargé"
                            })
        except Exception as e:
            logger.error(f"Error fetching members: {e}")

        # 4. Fetch User IDs from Auth Service to ensure correct mapping
        try:
            if seen_members:
                # On convertit les IDs en UUIDs pour le service Auth
                uuid_list = [f"00000000-0000-0000-0000-{hex(uid)[2:].zfill(12)}" for uid in seen_members]
                ids_string = ",".join(uuid_list)
                auth_url = f"{getattr(settings, 'AUTH_SERVICE_URL', '').rstrip('/')}/internal/users/search?membres_ids={ids_string}"
                resp_auth = requests.get(auth_url, timeout=2)
                
                if resp_auth.status_code == 200:
                    auth_users = resp_auth.json()
                    # Mapping member_uuid -> id_utilisateur
                    auth_map = {u.get('id_membre'): u.get('id_utilisateur') for u in auth_users}
                    
                    for m in members_list:
                        m_uuid = f"00000000-0000-0000-0000-{hex(m['id_membre'])[2:].zfill(12)}"
                        if m_uuid in auth_map:
                            m['id_utilisateur'] = auth_map[m_uuid]
        except Exception as e:
            logger.error(f"Error resolving auth IDs: {e}")

        return Response({
            "soumission": soum_data,
            "service_id": service_id,
            "membres": members_list
        })


class ValidationTransmitView(APIView):
    """
    POST /validations/transmettre
    Body: { "id_soumission": 123 }
    """
    def post(self, request, *args, **kwargs):
        print(f"DEBUG: ValidationTransmitView (CONTRATS) REÇU: {request.data}")
        soumission_id = request.data.get("id_soumission")
        if not soumission_id:
            return Response({"error": "id_soumission is required"}, status=400)
        
        try:
            soumission_id = int(soumission_id)
        except (ValueError, TypeError):
            return Response({"error": "id_soumission must be an integer"}, status=400)
            
        # 0. Vérifier si le dossier est déjà transmis (type externe ou tutelle)
        already_transmitted = Validation.objects.filter(id_soumission=soumission_id, type__in=['externe', 'tutelle']).exists()
        print(f"DEBUG: Check already_transmitted for {soumission_id}: {already_transmitted}")
        if already_transmitted:
            return Response({"error": "Ce dossier a déjà été transmis (Commission Externe ou Tutelle)."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 1. Récupérer les détails de la soumission pour avoir l'appel_id
        soumission_url = f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}/api/soumissions/{soumission_id}"
        try:
            resp_s = requests.get(soumission_url, headers=internal_service_headers(), timeout=3)
            if resp_s.status_code != 200:
                # Fallback URL if /api/ is not used
                soumission_url = f"{settings.SOUMISSIONS_SERVICE_URL.rstrip('/')}/soumissions/{soumission_id}"
                resp_s = requests.get(soumission_url, headers=internal_service_headers(), timeout=3)
                
            if resp_s.status_code != 200:
                return Response({"error": "Soumission non trouvée"}, status=404)
            soum_data = resp_s.json()
            appel_id = soum_data.get("id_appel_offres") or soum_data.get("id_appel_offre")
        except Exception as e:
            logger.error(f"Error fetching soumission: {e}")
            return Response({"error": "Service soumissions injoignable"}, status=503)

        # 2. Déterminer la destination (Commission Externe vs Tutelle)
        contractant_url = getattr(settings, 'CONTRACTANT_SERVICE_URL', 'http://localhost:8000')
        dest_type = 'tutelle'
        dest_org_name = 'la Tutelle'
        
        try:
            url_ce = f"{contractant_url}/commissions-externes/competente/{appel_id}"
            resp_ce = requests.get(url_ce, headers=internal_service_headers(), timeout=3)
            if resp_ce.status_code == 200:
                ce_data = resp_ce.json()
                if ce_data.get("id_comission_externe"):
                    dest_type = 'externe'
                    dest_org_name = ce_data.get("nom_comission")
        except Exception as e:
            logger.warning(f"Error determining competent commission: {e}")

        # 3. Identifier le Responsable cible
        acteurs_url = getattr(settings, 'ACTEURS_SERVICE_URL', 'http://localhost:8000')
        target_user_id = 1 # Fallback
        
        try:
            url_resp = f"{acteurs_url}/organisations/by-type/{dest_type}/responsable/"
            resp_params = {}

            if dest_type == 'externe' and 'id_comission_externe' in ce_data:
                # Récupérer les membres de la commission externe spécifique
                url_m = f"{contractant_url}/commissions-externes/{ce_data['id_comission_externe']}/membres"
                resp_m = requests.get(url_m, headers=internal_service_headers(), timeout=2)
                if resp_m.status_code == 200:
                    m_list = resp_m.json()
                    ids = [str(m['id_membre']) for m in m_list]
                    if ids:
                        resp_params['membres_ids'] = ",".join(ids)
            
            elif dest_type == 'tutelle':
                # Pour la tutelle, on cherche l'organisation correspondante
                # On récupère d'abord le service contractant de l'appel
                appels_url = getattr(settings, 'APPELS_SERVICE_URL', 'http://localhost:8000')
                url_ao = f"{appels_url}/api/appels-offres/{appel_id}"
                resp_ao = requests.get(url_ao, headers=internal_service_headers(), timeout=2)
                if resp_ao.status_code == 200:
                    ao_data = resp_ao.json()
                    service_id = ao_data.get("id_service")
                    if service_id:
                        url_sc = f"{contractant_url}/services-contractants/{service_id}"
                        resp_sc = requests.get(url_sc, headers=internal_service_headers(), timeout=2)
                        if resp_sc.status_code == 200:
                            sc_data = resp_sc.json()
                            id_tutelle = sc_data.get("id_tutelle")
                            if id_tutelle:
                                # On suppose que id_tutelle est le dernier segment de l'UUID de l'organisation
                                # ou on peut chercher par org_id si on a la correspondance
                                hex_id = hex(int(id_tutelle))[2:].zfill(12)
                                org_id = f"00000000-0000-0000-0000-{hex_id}"
                                resp_params['org_id'] = org_id

            resp_r = requests.get(url_resp, params=resp_params, headers=internal_service_headers(), timeout=3)
            if resp_r.status_code == 200:
                r_data = resp_r.json()
                target_user_id = r_data.get("id_utilisateur") or target_user_id
        except Exception as e:
            logger.warning(f"Error finding responsable: {e}")

        # 4. Créer la nouvelle Validation
        validation = Validation.objects.create(
            id_soumission=soumission_id,
            id_utilisateur=target_user_id,
            type=dest_type,
            is_validated=False,
            commentaire=f"Transmis automatiquement vers {dest_org_name}"
        )

        # 5. Envoyer la Notification
        notifications_url = getattr(settings, 'NOTIFICATIONS_SERVICE_URL', 'http://localhost:8000')
        try:
            notif_payload = {
                "utilisateur_id": target_user_id,
                "type_notification": "validation_requise",
                "titre": "Nouveau dossier à valider",
                "message": f"Le dossier ID-{str(soumission_id).zfill(3)} vous a été transmis pour validation (Entité : {dest_org_name}).",
                "priorite": "haute",
                "categorie": "validation",
                "entite_liee_type": "soumission",
                "entite_liee_id": soumission_id,
                "statut": "envoyée"
            }
            requests.post(f"{notifications_url}/notifications", json=notif_payload, headers=internal_service_headers(), timeout=2)
        except Exception as e:
            logger.warning(f"Error sending notification: {e}")

        return Response(ValidationSerializer(validation).data, status=status.HTTP_201_CREATED)

# --- END ADDITION ---
