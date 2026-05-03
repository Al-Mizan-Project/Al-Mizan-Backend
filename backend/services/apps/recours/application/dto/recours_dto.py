from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RecoursCreateDTO:
    id_operateur_economique: int
    id_soumission: int
    motif: str
    type_recours: Optional[str] = None
    objet: str = ""
    explications: str = ""
    document_ids: List[int] = field(default_factory=list)
    id_validation: Optional[int] = None


@dataclass
class RecoursDecisionDTO:
    decision: str
    traite_par: int


@dataclass
class RecoursResponseDTO:
    id_recours: int
    id_operateur_economique: int
    id_validation: Optional[int]
    id_soumission: int
    statut: str
    motif: str
    decision: Optional[str]
    date_depot: str
    date_limite: str
    date_decision: Optional[str]
    traite_par: Optional[int]
    type_recours: Optional[str] = None
    objet: str = ""
    explications: str = ""
    document_ids: List[int] = field(default_factory=list)
