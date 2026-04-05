from domain.states.base_state import RecoursState


class AccepteState(RecoursState):

    def cloturer(self, recours):
        recours.statut = "CLOTURE"