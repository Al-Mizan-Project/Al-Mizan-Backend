from domain.states.base_state import RecoursState


class RejeteState(RecoursState):

    def cloturer(self, recours):
        recours.statut = "CLOTURE"