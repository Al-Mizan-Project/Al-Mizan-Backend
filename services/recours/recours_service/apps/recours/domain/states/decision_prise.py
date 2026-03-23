from .base_state import RecoursState


class DecisionPriseState(RecoursState):

    def accepter(self, recours):
        recours.statut = "ACCEPTE"

    def rejeter(self, recours):
        recours.statut = "REJETE"