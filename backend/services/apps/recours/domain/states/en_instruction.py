from django.utils import timezone
from apps.recours.domain.states.base_state import RecoursState


class EnInstructionState(RecoursState):

    def prendre_decision(self, recours, decision: str):
        recours.decision = decision
        recours.date_decision = timezone.now()
        recours.statut = "DECISION_PRISE"
