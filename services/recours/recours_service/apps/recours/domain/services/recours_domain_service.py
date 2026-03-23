from datetime import datetime
from ..exceptions import (
    DuplicateRecours,
    DeadlineExceeded,
    UnauthorizedAction,
)


class RecoursDomainService:

    def verifier_unicite_recours(self, existing_recours):
        if existing_recours is not None:
            raise DuplicateRecours("Un recours existe déjà pour cette soumission")

    def verifier_delai(self, date_limite: datetime, date_actuelle: datetime):
        if date_actuelle > date_limite:
            raise DeadlineExceeded("Le délai de recours est dépassé")

    def verifier_proprietaire(self, operateur_id: int, soumission: dict):
        if soumission.get("operateur_id") != operateur_id:
            raise UnauthorizedAction("L'opérateur n'est pas propriétaire de la soumission")

    def verifier_soumission_rejetee(self, soumission: dict):
        if soumission.get("statut") != "REJETEE":
            raise UnauthorizedAction("La soumission n'est pas rejetée")