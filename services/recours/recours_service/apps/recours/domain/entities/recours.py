class Recours:
    id_recours: int
    id_operateur_economique: int
    id_validation: int
    id_soumission: int
    motif: str
    statut: str
    date_depot: str
    date_limite: str
    decision: str
    date_decision: str
    traite_par: int
    version: int

    def instruire(self): ...
    def prendre_decision(self, decision: str): ...
    def accepter(self): ...
    def rejeter(self): ...
    def cloturer(self): ...
    def verifier_modifiable(self): ...