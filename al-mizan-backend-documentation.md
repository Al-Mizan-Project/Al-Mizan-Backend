# Al-Mizan Backend Documentation

---

# Service: auth

## Tables

### `utilisateurs`
- `id_utilisateur` - int, PK
- `id_role` - int, FK
- `id_membre` - int, FK
- `email` - varchar(255)
- `password_hash` - varchar(255)
- `created_at` - datetime
- `updated_at` - datetime

### `role`
- `id_role` - int, PK
- `nom_role` - varchar(20)

### `permission`
- `id_permission` - int, PK
- `nom_permission` - varchar(20)

### `Permission_role`
- `id_role` - int, FK
- `id_permission` - int, FK

## Endpoints
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/change-password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /users`
- `POST /users`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `PATCH /users/{user_id}/role`
- `GET /users/{user_id}/permissions`
- `GET /roles`
- `POST /roles`
- `GET /roles/{role_id}`
- `PATCH /roles/{role_id}`
- `DELETE /roles/{role_id}`
- `GET /permissions`
- `POST /permissions`
- `GET /permissions/{permission_id}`
- `PATCH /permissions/{permission_id}`
- `DELETE /permissions/{permission_id}`
- `GET /roles/{role_id}/permissions`
- `PUT /roles/{role_id}/permissions`
- `POST /roles/{role_id}/permissions/{permission_id}`
- `DELETE /roles/{role_id}/permissions/{permission_id}`

---

# Service: acteurs

## Tables

### `Organisation`
- `id_organisation` - int, PK
- `nom_officiel` - varchar(20)
- `adresse_siege` - varchar(100)
- `email_contact` - varchar(100)
- `type_entite` - varchar(30)



### `Operateurs_Economiques`
- `id_operateur_economique` - int, PK
- `nif` - varchar(100)
- `registre_commerce_num` - varchar(100)
- `casnos_vrt` - varchar(100)
- `cnas_vrt` - varchar(100)
- `rib_bancaire` - varchar(100)

### `membre`
- `id_membre` - int, PK
- `id_organisation` - int, FK
- `prenom` - varchar(100)
- `nom` - varchar(100)
- `telephone` - varchar(30)
- `fonction` - varchar(50)
- `created_at` - datetime
- `updated_at` - datetime

### `Tutelle`
- `id_tutelle` - int, PK
- `nom_tutelle` - varchar(255)
- `identite_autorite` - varchar(255)

### `Comission_Externe`
- `id_comission_externe` - int, PK
- `nom_comission` - varchar(100)
- `niveau_competance` - enum(Communale, de Wilaya, Sectorielle, Nationale)
- `seuils_competence_financiere` - varchar(255)

## Endpoints
- `GET /organisations`
- `POST /organisations`
- `GET /organisations/{organisation_id}`
- `PATCH /organisations/{organisation_id}`
- `DELETE /organisations/{organisation_id}`
- `GET /organisations/{organisation_id}/membres`
- `GET /services-contractants`
- `GET /operateurs-economiques`
- `POST /operateurs-economiques`
- `GET /operateurs-economiques/{operateur_id}`
- `PATCH /operateurs-economiques/{operateur_id}`
- `DELETE /operateurs-economiques/{operateur_id}`
- `GET /operateurs-economiques/by-nif/{nif}`
- `GET /membres`
- `POST /membres`
- `GET /membres/{membre_id}`
- `PATCH /membres/{membre_id}`
- `DELETE /membres/{membre_id}`
- `GET /tutelles`
- `POST /tutelles`
- `GET /tutelles/{tutelle_id}`
- `PATCH /tutelles/{tutelle_id}`
- `DELETE /tutelles/{tutelle_id}`

---

# Service: contractant

## Tables

### `Comission_evaluation`
- `id_comission` - int, PK
- `id_service` - int, FK
- `nom_comission` - varchar(255)
- `categorie` - varchar(255)

### `Comission_interne`
- `id_comission_interne` - int, PK
- `id_service` - int, FK
- `nom_comission` - varchar(255)
- `type_comission` - enum(parmanante, adhoc)

### `Membres_Commission_evaluation`
- `id_membre` - int, FK
- `id_comission` - int, FK

### `Membres_Commission_interne`
- `id_membre` - int, FK
- `id_commision_interne` - int, FK

### `Services_Contractants`
- `id_service` - int, PK
- `id_tutelle` - int, FK
- `categorie` - varchar(255)
- `code_ordonnateur` - varchar(100)


## Endpoints
- `GET /commissions-evaluation`
- `POST /commissions-evaluation`
- `GET /commissions-evaluation/{commission_id}`
- `PATCH /commissions-evaluation/{commission_id}`
- `DELETE /commissions-evaluation/{commission_id}`
- `GET /commissions-evaluation/{commission_id}/membres`
- `POST /commissions-evaluation/{commission_id}/membres/{membre_id}`
- `DELETE /commissions-evaluation/{commission_id}/membres/{membre_id}`
- `GET /commissions-internes`
- `POST /commissions-internes`
- `GET /commissions-internes/{commission_interne_id}`
- `PATCH /commissions-internes/{commission_interne_id}`
- `DELETE /commissions-internes/{commission_interne_id}`
- `GET /commissions-internes/{commission_interne_id}/membres`
- `POST /commissions-internes/{commission_interne_id}/membres/{membre_id}`
- `DELETE /commissions-internes/{commission_interne_id}/membres/{membre_id}`
- `GET /services-contractants/{service_id}/commissions`
- `POST /services-contractants`
- `GET /services-contractants/{service_id}`
- `PATCH /services-contractants/{service_id}`
- `DELETE /services-contractants/{service_id}`
- `GET /services-contractants/{service_id}/membres`
- `GET /commissions-externes`
- `POST /commissions-externes`
- `GET /commissions-externes/{commission_externe_id}`
- `PATCH /commissions-externes/{commission_externe_id}`
- `DELETE /commissions-externes/{commission_externe_id}`

---

# Service: appels

## Tables

### `appels_offres`
- `id_appel_offres` - int, PK
- `id_service_contractant` - int, FK
- `reference` - varchar(80)
- `titre` - varchar(255)
- `description` - text
- `type_procedure` - varchar(50)
- `montant_estime` - decimal
- `date_publication` - datetime
- `date_limite_soumission` - datetime
- `date_ouverture_plis` - datetime
- `poids_technique` - int
- `poids_financier` - int
- `statut` - varchar(30)
- `created_at` - datetime
- `updated_at` - datetime

### `documents_appel`
- `id_document` - int, FK
- `id_appel_offres` - int, FK

## Endpoints
- `GET /appels-offres`
- `POST /appels-offres`
- `GET /appels-offres/{appel_id}`
- `PATCH /appels-offres/{appel_id}`
- `DELETE /appels-offres/{appel_id}`
- `POST /appels-offres/{appel_id}/publier`
- `POST /appels-offres/{appel_id}/cloturer-depot`
- `POST /appels-offres/{appel_id}/ouvrir-plis`
- `POST /appels-offres/{appel_id}/annuler`
- `GET /appels-offres/{appel_id}/documents`
- `POST /appels-offres/{appel_id}/documents/{document_id}`
- `DELETE /appels-offres/{appel_id}/documents/{document_id}`
- `GET /services-contractants/{service_id}/appels-offres`

---

# Service: documents

## Tables

### `documents`
- `id_document` - int, PK
- `related_type` - varchar(30)
- `nom` - varchar(255)
- `type_document` - varchar(50)
- `storage_url` - varchar(500)
- `hash_sha256` - varchar(64)
- `is_encrypted` - tinyint(1)
- `ia_verif_statut` - varchar(30)
- `ia_verif_details` - text
- `uploaded_at` - datetime

## Endpoints
- `GET /documents`
- `POST /documents`
- `GET /documents/{document_id}`
- `PATCH /documents/{document_id}`
- `DELETE /documents/{document_id}`
- `GET /documents/{document_id}/download-url`
- `POST /documents/{document_id}/verify-hash`
- `POST /documents/{document_id}/encrypt`
- `POST /documents/{document_id}/decrypt`
- `PATCH /documents/{document_id}/ia-status`
- `GET /documents/by-related/{related_type}/{related_id}`

---

# Service: soumissions

## Tables

### `soumissions`
- `id_soummision` - int, PK
- `id_appel_offre` - int, FK
- `date_soumission` - datetime
- `montant_financier` - decimal
- `offre_financiere_chiffree_url` - varchar(500)
- `cle_dechiffrement_hash` - varchar(255)
- `statut` - varchar(30)
- `conformite_statut` - varchar(30)
- `conformite_rapport` - text
- `created_at` - datetime
- `updated_at` - datetime

### `documents_soumission`
- `id_soummision` - int, FK
- `id_document` - int, FK

## Endpoints
- `GET /soumissions`
- `POST /soumissions`
- `GET /soumissions/{soumission_id}`
- `PATCH /soumissions/{soumission_id}`
- `DELETE /soumissions/{soumission_id}`
- `POST /soumissions/{soumission_id}/finaliser`
- `POST /soumissions/{soumission_id}/retirer`
- `POST /soumissions/{soumission_id}/verifier-conformite`
- `GET /soumissions/{soumission_id}/documents`
- `POST /soumissions/{soumission_id}/documents/{document_id}`
- `DELETE /soumissions/{soumission_id}/documents/{document_id}`
- `GET /appels-offres/{appel_id}/soumissions`
- `GET /operateurs-economiques/{operateur_id}/soumissions`

---

# Service: evaluations

## Tables

### `Evaluation`
- `id_evalution` - int, PK
- `id_comission` - int, FK
- `id_soumission` - int, FK
- `type` - enum(administrative, technique, financiere)
- `note` - int
- `commentaire` - text
- `created_at` - datetime
- `updated_at` - datetime

## Endpoints
- `GET /evaluations`
- `POST /evaluations`
- `GET /evaluations/{evaluation_id}`
- `PATCH /evaluations/{evaluation_id}`
- `DELETE /evaluations/{evaluation_id}`
- `GET /soumissions/{soumission_id}/evaluations`
- `GET /appels-offres/{appel_id}/evaluations`
- `POST /appels-offres/{appel_id}/calculer-classement`
- `GET /appels-offres/{appel_id}/classement`
- `POST /appels-offres/{appel_id}/valider-notes`

---

# Service: ia

## Tables

### `detection_anomalie_ia`
- `id_detection_anomalie_ia` - int, PK
- `id_appel_offre` - int
- `id_soumission` - int
- `type_anomalie` - varchar(50)
- `niveau_severite` - varchar(20)
- `score_confiance` - decimal
- `details` - text
- `statut_examen` - varchar(30)
- `date_detection` - datetime

## Endpoints
- `POST /ia/anomalies/detecter`
- `GET /ia/anomalies`
- `GET /ia/anomalies/{anomalie_id}`
- `GET /ia/anomalies/appel/{appel_id}`
- `GET /ia/anomalies/soumission/{soumission_id}`
- `PATCH /ia/anomalies/{anomalie_id}/statut-examen`
- `POST /ia/conformite/verifier-soumission/{soumission_id}`
- `POST /ia/cdc/rediger`
- `POST /ia/cdc/reviser`

---

# Service: contrats

## Tables

### `Validation`
- `id_validation` - int, PK
- `id_organisation` - int, FK
- `id_soumission` - int, FK
- `type` - enum(interne, externe, tutelle)
- `is_validated` - boolean
- `commentaire` - text
- `created_at` - datetime
- `updated_at` - datetime

### `contrats`
- `id_contrat` - int, PK
- `id_soumission` - int, FK
- `id_service_contractants` - int, FK
- `numero_contrat` - varchar(80)
- `date_signature` - datetime
- `statut` - varchar(30)
- `created_at` - datetime
- `updated_at` - datetime

### `documents_contrats`
- `id_document` - int, FK
- `id_contrat` - int, FK

## Endpoints
- `GET /validations`
- `POST /validations`
- `GET /validations/{validation_id}`
- `PATCH /validations/{validation_id}`
- `DELETE /validations/{validation_id}`
- `POST /validations/{validation_id}/approuver`
- `POST /validations/{validation_id}/rejeter`
- `GET /contrats`
- `POST /contrats`
- `GET /contrats/{contrat_id}`
- `PATCH /contrats/{contrat_id}`
- `DELETE /contrats/{contrat_id}`
- `POST /contrats/{contrat_id}/signer`
- `GET /contrats/{contrat_id}/documents`
- `POST /contrats/{contrat_id}/documents/{document_id}`
- `DELETE /contrats/{contrat_id}/documents/{document_id}`
- `GET /soumissions/{soumission_id}/contrat`

---

# Service: recours

## Tables

### `recours`
- `id_recours` - int, PK
- `id_operateur_economique` - int, FK
- `id_validation` - int, FK
- `motif` - text
- `statut` - varchar(30)
- `date_depot` - datetime
- `decision` - text
- `date_decision` - datetime
- `traite_par` - int

### `documents_recours`
- `id_recours` - int, FK
- `id_document` - int, FK

## Endpoints
- `GET /recours`
- `POST /recours`
- `GET /recours/{recours_id}`
- `PATCH /recours/{recours_id}`
- `DELETE /recours/{recours_id}`
- `POST /recours/{recours_id}/instruire`
- `POST /recours/{recours_id}/decision`
- `POST /recours/{recours_id}/accepter`
- `POST /recours/{recours_id}/rejeter`
- `GET /recours/{recours_id}/documents`
- `POST /recours/{recours_id}/documents/{document_id}`
- `DELETE /recours/{recours_id}/documents/{document_id}`
- `GET /operateurs-economiques/{operateur_id}/recours`

---

# Service: notifications

## Tables

### `notifications`
- `id` - int, PK
- `utilisateur_id` - int, FK
- `type_notification` - varchar(50)
- `titre` - varchar(255)
- `message` - text
- `priorite` - varchar(20)
- `categorie` - varchar(50)
- `entite_liee_type` - varchar(30)
- `entite_liee_id` - int
- `statut` - varchar(30)
- `created_at` - datetime
- `sent_at` - datetime
- `read_at` - datetime

## Endpoints
- `GET /notifications`
- `POST /notifications`
- `GET /notifications/{notification_id}`
- `PATCH /notifications/{notification_id}`
- `DELETE /notifications/{notification_id}`
- `GET /users/{user_id}/notifications`
- `POST /notifications/{notification_id}/envoyer`
- `POST /notifications/{notification_id}/marquer-lu`
- `POST /users/{user_id}/notifications/marquer-tout-lu`
- `POST /notifications/envoi-masse`

---

# Service: audit

## Tables

### `journaux_audit`
- `id_journaux_audit` - int, PK
- `utilisateur_id` - int, FK
- `action` - varchar(100)
- `entite_type` - varchar(30)
- `entite_id` - int
- `horodatage` - datetime
- `adresse_ip` - varchar(45)
- `hash_log_precedent` - varchar(64)
- `hash_log_actuel` - varchar(64)
- `details_action` - text

## Endpoints
- `GET /journaux-audit/list`
- `POST /journaux-audit/create`
- `GET /journaux-audit/{log_id}`
- `GET /journaux-audit/entity/{entity_type}/{entity_id}`
- `GET /journaux-audit/user/{user_id}`
- `GET /journaux-audit/verifier-integrite`
- `GET /journaux-audit/verifier-integrite/record/{record_id}`

---

# Common Endpoints
- `GET /health`
- `GET /ready`
- `GET /openapi.json`
