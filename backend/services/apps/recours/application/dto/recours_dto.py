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
    id_operateur_economique: int
    id_validation: int
    id_soumission: int
    statut: str
    motif: str
    decision: Optional[str]
    date_depot: str
    date_limite: str
    date_decision: Optional[str]
    traite_par: Optional[int]
