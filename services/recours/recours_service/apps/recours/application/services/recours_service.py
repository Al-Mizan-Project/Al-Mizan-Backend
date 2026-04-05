from datetime import datetime

from domain.entities.recours import Recours
from domain.services.recours_domain_service import RecoursDomainService

from domain.repositories.recours_repository import RecoursRepository

from integrations.soumissions_client import SoumissionsClient
from integrations.appels_client import AppelsClient
from integrations.notification_client import NotificationClient
from integrations.audit_client import AuditClient

from application.dto.recours_dto import (
    RecoursCreateDTO,
    RecoursDecisionDTO,
    RecoursResponseDTO,
)


class RecoursService:

    def __init__(
        self,
        repository: RecoursRepository,
        domain_service: RecoursDomainService,
        soumissions_client: SoumissionsClient,
        appels_client: AppelsClient,
        notification_client: NotificationClient,
        audit_client: AuditClient,
    ):
        self.repository = repository
        self.domain_service = domain_service
        self.soumissions_client = soumissions_client
        self.appels_client = appels_client
        self.notification_client = notification_client
        self.audit_client = audit_client

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
        appel = self.appels_client.get_appel_offre(soumission["appel_id"])
        date_limite = appel.get("date_limite_recours")

        now = datetime.utcnow()
        self.domain_service.verifier_delai(date_limite, now)

        # 4. Create domain entity
        recours = Recours(
            id_recours=None,
            id_operateur_economique=dto.id_operateur_economique,
            id_validation=dto.id_validation,
            id_soumission=dto.id_soumission,
            motif=dto.motif,
            statut="DEPOSE",
            date_depot=now,
            date_limite=date_limite,
            version=0,
        )

        # 5. Persist
        recours = self.repository.save(recours)

        # 6. Notify + Audit
        self.notification_client.send_notification({
            "type": "RECOURS_CREATED",
            "recours_id": recours.id_recours,
        })

        self.audit_client.log_action({
            "action": "CREATE_RECOURS",
            "recours_id": recours.id_recours,
        })

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

    # ---------------------------
    # DELETE
    # ---------------------------

    def delete_recours(self, recours_id: int):
        self.repository.delete(recours_id)

        self.audit_client.log_action({
            "action": "DELETE_RECOURS",
            "recours_id": recours_id,
        })

    # ---------------------------
    # WORKFLOW ACTIONS
    # ---------------------------

    def instruire_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.instruire()

        recours = self.repository.save(recours)

        self.audit_client.log_action({
            "action": "INSTRUIRE_RECOURS",
            "recours_id": recours.id_recours,
        })

        return self._to_response_dto(recours)

    def prendre_decision(self, recours_id: int, dto: RecoursDecisionDTO):
        recours = self.repository.get_by_id(recours_id)

        recours.prendre_decision(dto.decision)
        recours.traite_par = dto.traite_par

        recours = self.repository.save(recours)

        self.notification_client.send_notification({
            "type": "RECOURS_DECISION",
            "recours_id": recours.id_recours,
        })

        self.audit_client.log_action({
            "action": "DECISION_RECOURS",
            "recours_id": recours.id_recours,
        })

        return self._to_response_dto(recours)

    def accepter_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.accepter()

        recours = self.repository.save(recours)

        self.notification_client.send_notification({
            "type": "RECOURS_ACCEPTE",
            "recours_id": recours.id_recours,
        })

        return self._to_response_dto(recours)

    def rejeter_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.rejeter()

        recours = self.repository.save(recours)

        self.notification_client.send_notification({
            "type": "RECOURS_REJETE",
            "recours_id": recours.id_recours,
        })

        return self._to_response_dto(recours)

    def cloturer_recours(self, recours_id: int):
        recours = self.repository.get_by_id(recours_id)

        recours.cloturer()

        recours = self.repository.save(recours)

        self.notification_client.send_notification({
            "type": "RECOURS_CLOTURE",
            "recours_id": recours.id_recours,
        })

        self.audit_client.log_action({
            "action": "CLOTURE_RECOURS",
            "recours_id": recours.id_recours,
        })

        return self._to_response_dto(recours)

    # ---------------------------
    # MAPPER
    # ---------------------------

    def _to_response_dto(self, recours: Recours) -> RecoursResponseDTO:
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
        )