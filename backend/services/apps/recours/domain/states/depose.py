from apps.recours.domain.states.base_state import RecoursState


class DeposeState(RecoursState):

    def instruire(self, recours):
        recours.statut = "EN_INSTRUCTION"
