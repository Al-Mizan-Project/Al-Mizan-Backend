from datetime import datetime

from django.utils import timezone

from apps.integrations.appels_client import AppelsClient
from apps.integrations.audit_client import AuditClient
from apps.integrations.contrats_client import ContratsClient
from apps.integrations.notification_client import NotificationClient
from apps.integrations.soumissions_client import SoumissionsClient
from apps.recours.application.dto.recours_dto import (
    RecoursCreateDTO,
    RecoursDecisionDTO,
    RecoursResponseDTO,
    RecoursUpdateDTO,
)
from apps.recours.domain.exceptions import DeadlineExceeded, RecoursNotModifiable
from apps.recours.domain.entities.recours import Recours
from apps.recours.domain.repositories.recours_repository import RecoursRepository
from apps.recours.domain.services.recours_domain_service import RecoursDomainService


class RecoursService:

    def __init__(
        self,
        repository: RecoursRepository,
        domain_service: RecoursDomainService,
        soumissions_client: SoumissionsClient,
        appels_client: AppelsClient,
        notification_client: NotificationClient,
        audit_client: AuditClient,
        contrats_client: ContratsClient = None,
    ):
        self.repository = repository
        self.domain_service = domain_service
        self.soumissions_client = soumissions_client
        self.appels_client = appels_client
        self.notification_client = notification_client
        self.audit_client = audit_client
        self.contrats_client = contrats_client

    # ---------------------------
    # CREATE RECOURS
    # ---------------------------

    def create_recours(self, dto: RecoursCreateDTO) -> RecoursResponseDTO:

        # 1. Fetch soumission
        soumission = self.soumissions_client.get_soumission(dto.id_soumission)

        # 2. Validate business rules
        existing = self.repository.get_by_soumission(dto.id_soumission)
        self.domain_service.verifier_unicite_recours(existing)

        self.domain_service.verifier_proprietaire(
            dto.id_operateur_economique, soumission
        )

        self.domain_service.verifier_soumission_rejetee(soumission)

        # 3. Fetch appel offre for deadline
        appel_id = soumission.get("appel_id") or soumission.get("id_appel_offre")
        appel = self.appels_client.get_appel_offre(appel_id)
        date_limite = appel.get("date_limite_recours") or appel.get("date_limite_soumission")
        if isinstance(date_limite, str):
            try:
                date_limite = datetime.fromisoformat(date_limite.replace("Z", "+00:00"))
            except ValueError:
                date_limite = None

        now = timezone.now()
        if date_limite is not None and timezone.is_naive(date_limite):
            date_limite = timezone.make_aware(date_limite, timezone.get_current_timezone())

        if date_limite is not None:
            self.domain_service.verifier_delai(date_limite, now)
        else:
            date_limite = now

        # 3.5 Resolve id_validation — if the client didn't provide one,
        # derive it from the contrats service (latest validation on the soumission).
        id_validation = dto.id_validation
        if id_validation is None and self.contrats_client is not None:
            id_validation = self._resolve_id_validation(dto.id_soumission)

        # 4. Create domain entity
        recours = Recours(
            id_recours=None,
            id_operateur_economique=dto.id_operateur_economique,
            id_validation=id_validation,
            id_soumission=dto.id_soumission,
            motif=dto.motif,
            statut="DEPOSE",
            date_depot=now,
            date_limite=date_limite,
            version=0,
            type_recours=dto.type_recours,
            objet=dto.objet,
            explications=dto.explications,
            document_ids=list(dto.document_ids or []),
        )

        # 5. Persist
        recours = self.repository.save(recours)

        # 6. Notify + Audit
        self._safe_notify(
            utilisateur_id=dto.id_operateur_economique,
            type_notification="RECOURS_CREATED",
            titre="Recours cree",
            message=f"Le recours {recours.id_recours} a ete cree.",
            entite_liee_id=recours.id_recours,
        )

        self._safe_audit(
            utilisateur_id=dto.id_operateur_economique,
            action="CREATE_RECOURS",
            entite_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    # ---------------------------
    # READ
    # ---------------------------

    def get_recours(self, recours_id: int) -> RecoursResponseDTO:
        recours = self.repository.get_by_id(recours_id)
        return self._to_response_dto(recours)

    def list_recours(self, filters: dict):
        recours_list = self.repository.list(filters)
        return [self._to_response_dto(r) for r in recours_list]

    def update_recours(self, recours_id: int, dto: RecoursUpdateDTO) -> RecoursResponseDTO:
        recours = self.repository.get_by_id(recours_id)
        self._assert_operator_editable(recours)

        if dto.objet is not None:
            recours.objet = dto.objet
        if dto.explications is not None:
            recours.explications = dto.explications
        if dto.motif is not None:
            recours.motif = dto.motif
        elif dto.explications is not None or dto.objet is not None:
            recours.motif = recours.explications or recours.objet or recours.motif
        if dto.type_recours is not None:
            recours.type_recours = dto.type_recours
        if dto.document_ids is not None:
            recours.document_ids = list(dto.document_ids)

        recours = self.repository.save(recours)

        self._safe_audit(
            utilisateur_id=recours.id_operateur_economique,
            action="UPDATE_RECOURS",
            entite_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    # ---------------------------
    # DELETE
    # ---------------------------

    def delete_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)
        self._assert_operator_editable(recours)
        self.repository.delete(recours_id)

        self._safe_audit(
            utilisateur_id=recours.id_operateur_economique,
            action="CANCEL_RECOURS",
            entite_id=recours_id,
        )

    # ---------------------------
    # WORKFLOW ACTIONS
    # ---------------------------

    def instruire_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.instruire()

        recours = self.repository.save(recours)

        self._safe_audit(
            utilisateur_id=recours.traite_par or 0,
            action="INSTRUIRE_RECOURS",
            entite_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    def prendre_decision(self, recours_id: int, dto: RecoursDecisionDTO):
        recours = self.repository.get_by_id(recours_id)

        recours.prendre_decision(dto.decision)
        recours.traite_par = dto.traite_par

        recours = self.repository.save(recours)

        self._safe_notify(
            utilisateur_id=recours.id_operateur_economique,
            type_notification="RECOURS_DECISION",
            titre="Decision de recours",
            message=f"Une decision a ete prise pour le recours {recours.id_recours}.",
            entite_liee_id=recours.id_recours,
        )

        self._safe_audit(
            utilisateur_id=dto.traite_par,
            action="DECISION_RECOURS",
            entite_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    def accepter_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.accepter()

        recours = self.repository.save(recours)

        self._safe_notify(
            utilisateur_id=recours.id_operateur_economique,
            type_notification="RECOURS_ACCEPTE",
            titre="Recours accepte",
            message=f"Le recours {recours.id_recours} a ete accepte.",
            entite_liee_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    def rejeter_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.rejeter()

        recours = self.repository.save(recours)

        self._safe_notify(
            utilisateur_id=recours.id_operateur_economique,
            type_notification="RECOURS_REJETE",
            titre="Recours rejete",
            message=f"Le recours {recours.id_recours} a ete rejete.",
            entite_liee_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    def cloturer_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.cloturer()

        recours = self.repository.save(recours)

        self._safe_notify(
            utilisateur_id=recours.id_operateur_economique,
            type_notification="RECOURS_CLOTURE",
            titre="Recours cloture",
            message=f"Le recours {recours.id_recours} a ete cloture.",
            entite_liee_id=recours.id_recours,
        )

        self._safe_audit(
            utilisateur_id=recours.traite_par or 0,
            action="CLOTURE_RECOURS",
            entite_id=recours.id_recours,
        )

        return self._to_response_dto(recours)

    # ---------------------------
    # MAPPER
    # ---------------------------

    def _to_response_dto(self, recours: Recours) -> RecoursResponseDTO:
        state_dates = {"DEPOSE": str(recours.date_depot)}
        if recours.date_decision:
            state_dates["DECISION_PRISE"] = str(recours.date_decision)
        return RecoursResponseDTO(
            id_recours=recours.id_recours,
            id_operateur_economique=recours.id_operateur_economique,
            id_validation=recours.id_validation,
            id_soumission=recours.id_soumission,
            statut=recours.statut,
            motif=recours.motif,
            decision=recours.decision,
            date_depot=str(recours.date_depot),
            date_limite=str(recours.date_limite),
            date_decision=str(recours.date_decision)
            if recours.date_decision
            else None,
            traite_par=recours.traite_par,
            type_recours=recours.type_recours,
            objet=recours.objet or "",
            explications=recours.explications or "",
            document_ids=list(recours.document_ids or []),
            date_fin_instruction=None,
            state_history=[],
            state_dates=state_dates,
        )

    def _resolve_id_validation(self, soumission_id: int):
        """Pick the most recent rejecting validation for this soumission.
        Falls back to the latest validation, then to None.
        Any failure is swallowed — id_validation is metadata, not a gate."""
        try:
            validations = self.contrats_client.get_validations_by_soumission(
                soumission_id
            ) or []
        except Exception:
            return None
        if not validations:
            return None
        rejected = [v for v in validations if v.get("is_validated") is False]
        chosen = rejected[0] if rejected else validations[0]
        return chosen.get("id_validation")

    def _assert_operator_editable(self, recours: Recours):
        if recours.statut != "DEPOSE":
            raise RecoursNotModifiable(
                "Le recours ne peut plus etre modifie ou annule apres le debut du traitement"
            )

        now = timezone.now()
        date_limite = recours.date_limite
        if date_limite is not None and timezone.is_naive(date_limite):
            date_limite = timezone.make_aware(date_limite, timezone.get_current_timezone())
        if date_limite is not None and now > date_limite:
            raise DeadlineExceeded("Le delai de modification du recours est depasse")

    def _safe_notify(self, utilisateur_id: int, type_notification: str, titre: str, message: str, entite_liee_id: int):
        try:
            self.notification_client.send_notification(
                {
                    "utilisateur_id": utilisateur_id,
                    "type_notification": type_notification,
                    "titre": titre,
                    "message": message,
                    "priorite": "normale",
                    "categorie": "recours",
                    "entite_liee_type": "recours",
                    "entite_liee_id": entite_liee_id,
                    "statut": "cree",
                }
            )
        except Exception:
            return None
        return None

    def _safe_audit(self, utilisateur_id: int, action: str, entite_id: int):
        try:
            self.audit_client.log_action(
                {
                    "utilisateur_id": utilisateur_id,
                    "action": action,
                    "entite_type": "recours",
                    "entite_id": entite_id,
                }
            )
        except Exception:
            return None
        return None
