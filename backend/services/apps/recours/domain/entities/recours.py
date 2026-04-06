from datetime import datetime
from apps.recours.domain.exceptions import RecoursNotModifiable
from apps.recours.domain.states.accepte import AccepteState
from apps.recours.domain.states.cloture import ClotureState
from apps.recours.domain.states.decision_prise import DecisionPriseState
from apps.recours.domain.states.depose import DeposeState
from apps.recours.domain.states.en_instruction import EnInstructionState
from apps.recours.domain.states.rejete import RejeteState


class Recours:

    def __init__(
        self,
        id_recours: int,
        id_operateur_economique: int,
        id_validation: int,
        id_soumission: int,
        motif: str,
        statut: str,
        date_depot: datetime,
        date_limite: datetime,
        decision: str = None,
        date_decision: datetime = None,
        traite_par: int = None,
        version: int = 0,
    ):
        self.id_recours = id_recours
        self.id_operateur_economique = id_operateur_economique
        self.id_validation = id_validation
        self.id_soumission = id_soumission
        self.motif = motif
        self.statut = statut
        self.date_depot = date_depot
        self.date_limite = date_limite
        self.decision = decision
        self.date_decision = date_decision
        self.traite_par = traite_par
        self.version = version

    # -------- STATE RESOLUTION --------

    def _get_state(self):
        mapping = {
            "DEPOSE": DeposeState(),
            "EN_INSTRUCTION": EnInstructionState(),
            "DECISION_PRISE": DecisionPriseState(),
            "ACCEPTE": AccepteState(),
            "REJETE": RejeteState(),
            "CLOTURE": ClotureState(),
        }
        return mapping[self.statut]

    # -------- BUSINESS METHODS --------

    def instruire(self):
        self.verifier_modifiable()
        state = self._get_state()
        state.instruire(self)

    def prendre_decision(self, decision: str):
        self.verifier_modifiable()
        state = self._get_state()
        state.prendre_decision(self, decision)

    def accepter(self):
        self.verifier_modifiable()
        state = self._get_state()
        state.accepter(self)

    def rejeter(self):
        self.verifier_modifiable()
        state = self._get_state()
        state.rejeter(self)

    def cloturer(self):
        state = self._get_state()
        state.cloturer(self)

    # -------- RULES --------

    def verifier_modifiable(self):
        if self.statut in ["ACCEPTE", "REJETE", "CLOTURE"]:
            raise RecoursNotModifiable("Recours non modifiable après décision finale")

    def est_dans_delai(self, now: datetime):
        return now <= self.date_limite
