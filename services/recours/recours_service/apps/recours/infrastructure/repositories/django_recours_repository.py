from django.db import transaction
from django.db.models import F

from domain.entities.recours import Recours
from domain.repositories.recours_repository import RecoursRepository

from infrastructure.models.recours_model import RecoursModel

from common.exceptions import NotFoundException, ConflictException


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
            decision=model.decision,
            date_decision=model.date_decision,
            traite_par=model.traite_par,
            version=model.version,
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
            decision=recours.decision,
            date_decision=recours.date_decision,
            traite_par=recours.traite_par,
            version=recours.version,
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
            decision=recours.decision,
            date_decision=recours.date_decision,
            traite_par=recours.traite_par,
            version=F("version") + 1,
        )

        if updated_rows == 0:
            raise ConflictException(
                "Conflit de mise à jour (optimistic locking)"
            )

        # Reload updated object
        model = RecoursModel.objects.get(id_recours=recours.id_recours)
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