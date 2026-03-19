from decimal import Decimal, InvalidOperation


def _safe_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def detect_price_and_similarity_anomalies(soumissions):
    anomalies = []
    montants = []

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is not None:
            montants.append(montant)

    moyenne = sum(montants) / len(montants) if montants else None

    by_hash = {}
    for soumission in soumissions:
        signature = str(soumission.get("signature_document", "")).strip()
        if signature:
            by_hash.setdefault(signature, []).append(soumission)

    for signature, items in by_hash.items():
        if len(items) < 2:
            continue
        for soumission in items:
            anomalies.append(
                {
                    "id_soumission": int(soumission["id_soumission"]),
                    "type_anomalie": "SIMILARITE_DOCUMENTAIRE",
                    "niveau_severite": "MOYEN",
                    "score_confiance": Decimal("0.78"),
                    "details": f"Signature documentaire identique detectee ({signature[:16]}...).",
                }
            )

    if moyenne is None or moyenne == 0:
        return anomalies

    for soumission in soumissions:
        montant = _safe_decimal(soumission.get("montant_financier"))
        if montant is None:
            continue
        ecart_relatif = abs(montant - moyenne) / moyenne
        if ecart_relatif <= Decimal("0.005"):
            anomalies.append(
                {
                    "id_soumission": int(soumission["id_soumission"]),
                    "type_anomalie": "SIMILARITE_PRIX",
                    "niveau_severite": "ELEVEE",
                    "score_confiance": Decimal("0.85"),
                    "details": "Montant financier tres proche de la moyenne collective des offres.",
                }
            )

    return anomalies