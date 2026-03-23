from dataclasses import dataclass
from typing import Optional


@dataclass
class RecoursCreateDTO:
    id_operateur_economique: int
    id_validation: int
    id_soumission: int
    motif: str


@dataclass
class RecoursDecisionDTO:
    decision: str
    traite_par: int


@dataclass
class RecoursResponseDTO:
    id_recours: int
    statut: str
    decision: Optional[str]
    date_depot: str
    date_decision: Optional[str]