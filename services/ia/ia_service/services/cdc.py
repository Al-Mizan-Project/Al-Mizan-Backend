DISCRIMINATORY_TERMS = {
    "exclusivement",
    "obligatoirement",
    "sans equivalence",
    "fournisseur unique",
    "marque imposee",
}


def generate_cdc_draft(besoin, type_procedure, contraintes):
    contraintes_text = "\n".join(f"- {item}" for item in contraintes) if contraintes else "- Aucune contrainte supplementaire."
    sections = {
        "objet": f"Le present CDC couvre le besoin suivant: {besoin}",
        "procedure": f"Procedure retenue: {type_procedure}.",
        "exigences": contraintes_text,
        "clause_non_discrimination": (
            "Les specifications restent ouvertes aux solutions equivalentes et respectent "
            "les principes d'egalite d'acces a la commande publique."
        ),
    }
    return sections


def revise_cdc_text(texte):
    lowered = texte.lower()
    alerts = [term for term in DISCRIMINATORY_TERMS if term in lowered]
    revised = texte

    replacements = {
        "exclusivement": "de preference",
        "obligatoirement": "de maniere justifiee",
        "sans equivalence": "ou equivalence technique",
        "fournisseur unique": "fournisseur de reference",
        "marque imposee": "marque ou equivalent",
    }
    for src, dst in replacements.items():
        revised = revised.replace(src, dst)
        revised = revised.replace(src.capitalize(), dst.capitalize())

    return {
        "alerts": alerts,
        "texte_revise": revised,
        "needs_human_validation": bool(alerts),
    }