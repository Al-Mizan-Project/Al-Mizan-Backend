from datetime import datetime
from .base_state import RecoursState


class EnInstructionState(RecoursState):

    def prendre_decision(self, recours, decision: str):
        recours.decision = decision
        recours.date_decision = datetime.utcnow()
        recours.statut = "DECISION_PRISE"