class RecoursCreateDTO:
    id_operateur_economique: int
    id_validation: int
    id_soumission: int
    motif: str


class RecoursResponseDTO:
    id_recours: int
    statut: str
    decision: str