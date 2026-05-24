# Database Schema Summary

Snapshot generated from the current PostgreSQL database on 2026-05-03.

## Global Inventory

- Total tables in `public`: 43
- Populated core tables:
  - `utilisateurs`: 5 rows
  - `membre`: 5 rows
  - `role`: 5 rows
  - `auth_permission`: 156 rows
  - `django_content_type`: 39 rows
  - `django_migrations`: 49 rows
- Most business tables are currently empty, which means the instance is still mostly a clean test database.

## Main Domain Tables

### Identity and Access

- `role`
  - `id_role` (PK)
  - `nom_role`
- `permission`
  - `id_permission` (PK)
  - `nom_permission`
- `Permission_role`
  - `id` (PK)
  - `id_role` (FK)
  - `id_permission` (FK)
- `utilisateurs`
  - `id_utilisateur` (PK)
  - `id_role` (FK)
  - `id_membre`
  - `email`
  - `password_hash`
  - `last_login`
  - `created_at`
  - `updated_at`
  - `is_active`
- `membre`
  - `id_membre` (PK)
  - `id_organisation` (nullable)
  - `prenom`
  - `nom`
  - `telephone`
  - `fonction`
  - `created_at`
  - `updated_at`

### Procurement Core

- `appels_offres`
  - Offer record with contractant, dates, weights, status, conditions, required docs, and location fields.
- `soumissions`
  - Submission record linked to an offer and a supplier.
  - Includes encrypted financial offer URL, decryption hash, status, amount, conformity status and JSON document list.
- `contrats`
  - Contract generated from a submission.
- `documents`
  - Generic document registry with hash, encryption flag, AI verification status, and visibility timing.
- `evaluation`
  - Evaluation record linked to a submission, a user, and a commission.
- `recours`
  - Appeal / complaint record linked to an operator, validation entry, and submission.
- `notifications`
  - User notification table with priority, category, status, and read/sent timestamps.

### Commission and Service Tables

- `Comission_evaluation`
- `Comission_interne`
- `Membres_Commission_evaluation`
- `Membres_Commission_interne`
- `Services_Contractants`
- `Operateurs_Economiques`
- `Comission_Externe`
- `Tutelle`
- `Organisation`

These tables manage service-contractant structures, commissions, and member assignment.

### Document Linking Tables

- `documents_appel`
- `documents_contrats`
- `documents_recours`

These act as relation tables between documents and business entities.

### Offer Tracking Tables

- `appels_offres_suivis`
- `appels_offres_operateurs_invites`
- `achats_simples`

### Technical / Platform Tables

- `auth_group`
- `auth_group_permissions`
- `auth_permission`
- `django_admin_log`
- `django_content_type`
- `django_migrations`
- `django_session`
- `journaux_audit`
- `journaux_outbox`
- `audit_read_projection`
- `detection_anomalie_ia`
- `validation`

## Foreign Key Map

- `utilisateurs.id_role` -> `role.id_role`
- `Permission_role.id_role` -> `role.id_role`
- `Permission_role.id_permission` -> `permission.id_permission`
- `Comission_evaluation.id_service` -> `Services_Contractants.id_service`
- `Comission_interne.id_service` -> `Services_Contractants.id_service`
- `Membres_Commission_evaluation.id_comission` -> `Comission_evaluation.id_comission`
- `Membres_Commission_interne.id_commision_interne` -> `Comission_interne.id_comission_interne`
- `membres_commission_evaluation.id_comission` -> `comission_evaluation.id_comission`
- `evaluation.id_comission` -> `comission_evaluation.id_comission`
- `documents_appel.id_appel_offres` -> `appels_offres.id_appel_offres`
- `documents_contrats.id_contrat` -> `contrats.id_contrat`
- `appels_offres_suivis.id_appel_offres` -> `appels_offres.id_appel_offres`
- `appels_offres_operateurs_invites.id_appel_offres` -> `appels_offres.id_appel_offres`
- `recours_documentrecoursmodel.recours_id` -> `recours_recoursmodel.id`
- `django_admin_log.user_id` -> `utilisateurs.id_utilisateur`

## Practical Notes

- The schema mixes singular, plural, uppercase, lowercase, and French spellings.
- A few names contain typos inherited from the data model, for example `Comission_*` and `id_evalution`.
- For UI testing, the important login/auth state is now present in `utilisateurs`.
- For role testing, most functional tables are still empty, so screens may show empty lists unless additional test data is inserted.

## Current Test Users

- `admin@example.com`
- `service.contractant@example.com`
- `commission.externe@example.com`
- `operateur.economique@example.com`
- `tutelle@example.com`

All use the same password:

- `StrongPassword123!`
