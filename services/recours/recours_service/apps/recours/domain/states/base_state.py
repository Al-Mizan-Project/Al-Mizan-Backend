from domain.exceptions import InvalidStateTransition


class RecoursState:

    def instruire(self, recours):
        raise InvalidStateTransition("Transition vers EN_INSTRUCTION impossible")

    def prendre_decision(self, recours, decision: str):
        raise InvalidStateTransition("Prise de décision impossible")

    def accepter(self, recours):
        raise InvalidStateTransition("Acceptation impossible")

    def rejeter(self, recours):
        raise InvalidStateTransition("Rejet impossible")

    def cloturer(self, recours):
        raise InvalidStateTransition("Clôture impossible")