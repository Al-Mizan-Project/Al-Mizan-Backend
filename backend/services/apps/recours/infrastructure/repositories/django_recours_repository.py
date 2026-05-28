from django.db import transaction
from django.db.models import F

from apps.common.exceptions import ConflictException, NotFoundException
from apps.recours.domain.entities.recours import Recours
from apps.recours.domain.repositories.recours_repository import RecoursRepository
from apps.recours.infrastructure.models.recours_model import (
    DocumentRecoursModel,
    RecoursModel,
)


class DjangoRecoursRepository(RecoursRepository):

    # ---------------------------
    # MAPPERS
    # ---------------------------

    def _to_domain(self, model: RecoursModel) -> Recours:
        return Recours(
            id_recours=model.id_recours,
            id_operateur_economique=model.id_operateur_economique,
            id_validation=model.id_validation,
            id_soumission=model.id_soumission,
            motif=model.motif,
            statut=model.statut,
            date_depot=model.date_depot,
            date_limite=model.date_limite,
            date_fin_instruction=model.date_fin_instruction,
            decision=model.decision,
            date_decision=model.date_decision,
            traite_par=model.traite_par,
            version=model.version,
            type_recours=model.type_recours,
            objet=model.objet,
            explications=model.explications,
            document_ids=list(
                DocumentRecoursModel.objects.filter(id_recours=model)
                .order_by("id_document")
                .values_list("id_document", flat=True)
            ),
        )

    def _to_model(self, recours: Recours) -> RecoursModel:
        return RecoursModel(
            id_recours=recours.id_recours,
            id_operateur_economique=recours.id_operateur_economique,
            id_validation=recours.id_validation,
            id_soumission=recours.id_soumission,
            motif=recours.motif,
            statut=recours.statut,
            date_depot=recours.date_depot,
            date_limite=recours.date_limite,
            date_fin_instruction=recours.date_fin_instruction,
            decision=recours.decision,
            date_decision=recours.date_decision,
            traite_par=recours.traite_par,
            version=recours.version,
            type_recours=recours.type_recours,
            objet=recours.objet or "",
            explications=recours.explications or "",
        )

    def _sync_documents(self, model: RecoursModel, document_ids):
        desired = set(document_ids or [])
        existing_qs = DocumentRecoursModel.objects.filter(id_recours=model)
        existing = set(existing_qs.values_list("id_document", flat=True))

        to_add = desired - existing
        to_remove = existing - desired

        if to_remove:
            DocumentRecoursModel.objects.filter(
                id_recours=model, id_document__in=to_remove
            ).delete()
        if to_add:
            DocumentRecoursModel.objects.bulk_create(
                [DocumentRecoursModel(id_recours=model, id_document=d) for d in to_add],
                ignore_conflicts=True,
            )

    # ---------------------------
    # SAVE (CREATE + UPDATE)
    # ---------------------------

    @transaction.atomic
    def save(self, recours: Recours) -> Recours:

        # CREATE
        if recours.id_recours is None:
            model = self._to_model(recours)
            model.save()
            self._sync_documents(model, recours.document_ids)

            return self._to_domain(model)

        # UPDATE with optimistic locking
        updated_rows = RecoursModel.objects.filter(
            id_recours=recours.id_recours,
            version=recours.version
        ).update(
            id_operateur_economique=recours.id_operateur_economique,
            id_validation=recours.id_validation,
            id_soumission=recours.id_soumission,
            motif=recours.motif,
            statut=recours.statut,
            date_depot=recours.date_depot,
            date_limite=recours.date_limite,
            date_fin_instruction=recours.date_fin_instruction,
            decision=recours.decision,
            date_decision=recours.date_decision,
            traite_par=recours.traite_par,
            type_recours=recours.type_recours,
            objet=recours.objet or "",
            explications=recours.explications or "",
            version=F("version") + 1,
        )

        if updated_rows == 0:
            raise ConflictException(
                "Conflit de mise à jour (optimistic locking)"
            )

        # Reload updated object
        model = RecoursModel.objects.get(id_recours=recours.id_recours)
        self._sync_documents(model, recours.document_ids)
        return self._to_domain(model)

    # ---------------------------
    # GETTERS
    # ---------------------------

    def get_by_id(self, recours_id: int) -> Recours:
        try:
            model = RecoursModel.objects.get(id_recours=recours_id)
            return self._to_domain(model)
        except RecoursModel.DoesNotExist:
            raise NotFoundException("Recours introuvable")

    def get_by_soumission(self, soumission_id: int):
        try:
            model = RecoursModel.objects.get(id_soumission=soumission_id)
            return self._to_domain(model)
        except RecoursModel.DoesNotExist:
            return None

    def list(self, filters: dict):

        queryset = RecoursModel.objects.all()

        if "statut" in filters:
            queryset = queryset.filter(statut=filters["statut"])

        if "id_operateur_economique" in filters:
            queryset = queryset.filter(
                id_operateur_economique=filters["id_operateur_economique"]
            )

        if "date_from" in filters:
            queryset = queryset.filter(date_depot__gte=filters["date_from"])

        if "date_to" in filters:
            queryset = queryset.filter(date_depot__lte=filters["date_to"])

        return [self._to_domain(m) for m in queryset]

    # ---------------------------
    # DELETE
    # ---------------------------

    def delete(self, recours_id: int):
        deleted, _ = RecoursModel.objects.filter(
            id_recours=recours_id
        ).delete()

        if deleted == 0:
            raise NotFoundException("Recours introuvable")
