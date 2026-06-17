from django.db import transaction
from auth_service.models import Role, Permission, PermissionRole, Utilisateur

ROLES_PERMISSIONS = {
    "ADMIN": [
        "organisation:create", "organisation:update", "organisation:deactivate",
        "user:create", "user:update", "user:deactivate",
        "role:manage", "seuil_cm:configure", "referentiel:manage",
        "log:read", "plateforme:configure",
    ],
    "RESP_SC": [
        "marche:create", "marche:read", "marche:update", "marche:publish",
        "marche:attribuer", "membre:create", "membre:update", "membre:deactivate",
        "oe:approuve", "oe:refuser", "role:assign",
        "offre:read_after_ouverture", "rapport:read", "recours:read",
    ],
    "REDACTEUR_CDC": [
        "marche:create", "marche:read", "marche:update",
        "cdc:create", "cdc:update", "cdc:submit_validation",
        "question:read", "question:repondre", "document:upload",
    ],
    "EVALUATEUR": [
        "registre_reception:read", "registre_reception:verify",
        "offre:flag_late", "offre:flag_identifying_marks", "offre:ecarted_before_opening",
        "seance_ouverture:read", "seance_ouverture:start", "seance_ouverture:close",
        "pli:open", "pli:read_content_after_opening", "offre:read_after_ouverture",
        "candidats_list:create", "candidats_list:read",
        "document_offre:paraph", "document_offre:read_after_paraph",
        "complement_request:propose", "complement_request:read",
        "complement_response:read", "document_complement:read",
        "conformite_formelle:evaluer", "offre:flag_anonymat_violation",
        "offre:flag_prix_divulgue_dans_pli_technique", "offre:ecarted_non_conformite",
        "interdiction_list:check", "conflict_interest:check", "exclusion:propose",
        "capacite_financiere:evaluer", "capacite_technique:evaluer",
        "capacite_professionnelle:evaluer", "capacite:noter",
        "offre:ecarted_capacite_insuffisante",
        "offre_technique:read", "offre_technique:evaluer", "offre_technique:noter",
        "critere_evaluation:read", "grille_notation:fill",
        "offre_technique:ecarted_note_insuffisante",
        "offre_financiere:block_if_technique_rejected",
        "offre_financiere:read", "offre_financiere:evaluer",
        "offre_financiere:controle_arithmetique",
        "offre_financiere:corriger_erreur_arithmetique",
        "offre_financiere:appliquer_marge_preference_nationale",
        "offre_financiere:noter",
        "prix_anormalement_bas:flag", "prix_anormalement_bas:analyze_justification",
        "prix_anormalement_bas:accept_justification", "prix_anormalement_bas:reject_justification",
        "prix_excessif:flag", "prix_excessif:propose_rejet",
        "atteinte_concurrence:flag", "atteinte_concurrence:propose_rejet",
        "classement:read", "classement:validate", "offre:propose_attribution",
        "document_original:read", "document_original:verify",
        "document_original:flag_non_conformite",
        "classement:reprendre_apres_exclusion", "offre:propose_infructuosite",
        "pv_ouverture:read", "pv_ouverture:signer", "pv_ouverture:add_reserve",
        "pv_evaluation:read", "pv_evaluation:create", "pv_evaluation:signer",
        "pv_evaluation:add_reserve",
        "pv_complementaire:create", "pv_complementaire:signer",
        "registre_ouverture_plis:read", "registre_evaluation_offres:read",
        "rapport_copeo:submit_to_sc",
    ],
    "MEMBRE_COMITE_TECHNIQUE": [
        "cahier_des_charges:read", "offre_technique:read", "document_offre:read",
        "analyse_technique:create", "analyse_technique:edit", "analyse_technique:read",
        "note_technique:create", "note_technique:edit",
        "commentaire_technique:add",
        "rapport_technique:create", "rapport_technique:edit",
        "rapport_technique:submit_to_copeo", "rapport_technique:read",
    ],
    "RESP_VALID_INTERN": [
        "dossier:read", "membre_civ:manage", "dossier:assigner", "rapport_cm:read",
    ],
    "VALIDATEUR_INTERNE_MARCHE": [
        "marche:valider_intern", "marche:rejeter_intern", "marche:read",
    ],
    "VALIDATEUR_INTERNE_CDC": [
        "cdc:read", "cdc:valider_intern", "cdc:rejeter_intern",
    ],
    "RESP_OE": [
        "appel_offre:read", "cdc:download",
        "offre:create", "offre:submit", "offre:signer",
        "offre:withdraw_before_deadline",
        "recours:create", "question:create",
        "membre_oe:manage", "profil_entreprise:update", "resultat:read",
    ],
    "PREPARATEUR_OE": [
        "appel_offre:read", "cdc:download",
        "offre:create", "offre:update", "document:upload", "offre:read_own",
    ],
    "RESP_CM": [
        "dossier:read", "visa:accorder", "visa:refuser",
        "membre_cm:manage", "dossier:assigner", "rapport_cm:read",
    ],
    "VALIDATEUR_EXTERNE_MARCHE": [
        "dossier:read", "marche:valider_extern", "marche:rejeter_extern",
    ],
    "VALIDATEUR_EXTERNE_CDC": [
        "dossier:read", "cdc:valider_extern", "cdc:rejeter_extern",
    ],
}

def run_seed():
    with transaction.atomic():
        print("=== Création des rôles et permissions ===")

        for role_name, permissions in ROLES_PERMISSIONS.items():
            role, role_created = Role.objects.get_or_create(nom_role=role_name)
            if role_created:
                print(f"  [+] Rôle créé : {role_name}")
            else:
                print(f"  [=] Rôle existant : {role_name}")

            for perm_name in permissions:
                perm, _ = Permission.objects.get_or_create(nom_permission=perm_name)
                PermissionRole.objects.get_or_create(id_role=role, id_permission=perm)

        print("\n=== Création du compte Admin ===")
        admin_role = Role.objects.get(nom_role="ADMIN")
        if not Utilisateur.objects.filter(email="admin@plateforme.dz").exists():
            admin = Utilisateur(
                email="admin@plateforme.dz",
                id_membre="00000000-0000-0000-0000-000000000000",
                id_role=admin_role,
                is_active=True,
            )
            admin.set_password("Admin123!")
            admin.save()
            print("  [+] Compte Admin créé : admin@plateforme.dz / Admin123!")
        else:
            print("  [=] Compte Admin existe déjà.")

        print("\n=== INITIALISATION TERMINÉE ===")
        print(f"  Rôles  : {Role.objects.count()}")
        print(f"  Permissions : {Permission.objects.count()}")
        print(f"  Liaisons rôle↔permission : {PermissionRole.objects.count()}")

run_seed()