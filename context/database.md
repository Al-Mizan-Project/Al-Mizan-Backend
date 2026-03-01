# 📚 AL-MIZAN : Database Schema & Architecture Reference

> **🚨 INSTRUCTIONS STRICTES POUR L'AGENT IA (CODING AGENT)**
> Ce document est ta source de vérité absolue concernant la base de données. 
> Tu dois te référer à ce schéma exact pour générer tes entités (JPA/Prisma/TypeORM), tes DTOs, et tes requêtes. Ne modifie pas les types ou les noms de colonnes sans autorisation. 
> **FOCUS ACTUEL** : Ta mission immédiate porte sur les micro-services **Document (GED)** et **Soumission**. Concentre-toi en priorité sur la Section 2 de ce document. N'oublie jamais de générer les tests unitaires et d'intégration (Testcontainers) pour chaque entité et service créés.

---

## 🏗️ 1. VUE D'ENSEMBLE DU SCHÉMA GLOBAL

La base de données est conçue pour un système d'e-procurement souverain et intelligent (Micro-services). 
L'architecture utilise un modèle d'héritage d'acteurs (L'entité centrale `Organisation` est étendue par `Services_Contractants`, `Operateurs_Economiques`, `Tutelle`, `Comission_Externe`).

---

## 🎯 2. SCOPE PRIORITAIRE : SERVICES "DOCUMENT" ET "SOUMISSION"

Voici le détail millimétré des entités que tu dois implémenter **maintenant**.

### 📄 Micro-Service Document (GED - MinIO)

Ce service gère le stockage polymorphe des fichiers physiques (MinIO) et leurs métadonnées (PostgreSQL).

#### Entité : `documents`
*Le cœur de la GED. Contient les métadonnées de chaque fichier uploadé.*
| Colonne | Type | Contraintes | Description |
| :--- | :--- | :--- | :--- |
| **`id_document`** | `PK` | Auto-increment | Identifiant unique du document. |
| `related_type` | `varchar(30)` | Not Null | Entité liée (ex: 'soumission', 'appel_offre', 'contrat'). |
| `nom` | `varchar(255)` | Not Null | Nom original du fichier uploadé. |
| `type_document` | `varchar(50)` | Not Null | Type MIME ou extension (pdf, zip, etc). |
| `storage_url` | `varchar(500)` | Not Null | Chemin d'accès unique généré pour MinIO. |
| `hash_sha256` | `varchar(64)` | Not Null | Empreinte cryptographique (Preuve d'intégrité légale). |
| `is_encrypted` | `tinyint(1)` | Default False | Indique si le document (ex: offre financière) est chiffré. |
| `ia_verif_statut` | `varchar(30)` | Nullable | Statut du traitement NLP/OCR (ex: PENDING, CONFORME). |
| `ia_verif_details` | `text` | Nullable | Détails/Logs JSON renvoyés par l'IA. |
| `uploaded_at` | `datetime` | Default Now() | Horodatage serveur de l'upload. |

#### Tables de Jointure (Liaison polymorphe des documents)
*Note pour l'Agent IA : Ces tables font le pont entre le service Document et les autres domaines.*
1. **`documents_soumission`** : `id_document` (FK) + `id_soummision` (FK) *(Note la syntaxe issue du schéma)*
2. **`documents_appel`** : `id_document` (FK) + `id_appel_offres` (FK)
3. **`documents_contrats`** : `id_document` (FK) + `id_contrat` (FK)
4. **`documents_recours`** : `id_document` (FK) + `id_recours` (FK)

---

### 💼 Micro-Service Soumission (Offres des opérateurs)

Ce service gère le dépôt des offres (techniques, administratives, financières) par les candidats (Opérateurs Économiques) en réponse à un Appel d'Offres.

#### Entité : `soumissions`
*Représente l'acte de candidature.*
| Colonne | Type | Contraintes | Description |
| :--- | :--- | :--- | :--- |
| **`id_soumision`** | `PK` | Auto-increment | Identifiant unique de la soumission. |
| **`id_appel_offre`** | `FK` | Not Null | Lien vers l'appel d'offres visé. |
| `date_soumission` | `datetime` | Not Null | Date exacte de la candidature. |
| `montant_financier` | `decimal` | Nullable | Montant total de l'offre (peut être rempli post-ouverture). |
| `offre_financiere_chiffree_url`| `varchar(500)`| Nullable | Lien de secours ou référence directe MinIO chiffrée. |
| `cle_dechiffrement_hash` | `varchar(255)`| Nullable | Hash de la clé pour décrypter l'offre à l'ouverture des plis. |
| `statut` | `varchar(30)` | Not Null | Ex: BROUILLON, SOUMIS, REJETE, ACCEPTE. |
| `conformite_statut` | `varchar(30)` | Nullable | Résultat global de la conformité (souvent poussé par l'IA). |
| `conformite_rapport` | `text` | Nullable | Rapport détaillé sur la conformité de la soumission. |
| `created_at` | `datetime` | | |
| `updated_at` | `datetime` | | |

#### Entités directement liées aux Soumissions :
1. **`Evaluation`** : Stocke les notes données par les commissions.
   * Cols : `id_evalution` (PK), `id_comission` (FK), `id_soumission` (FK), `type` enum(administrative, technique, financiére), `note` (int), `commentaire` (Type), `created_at`, `updated_at`.
2. **`Validation`** : Validation finale d'une soumission.
   * Cols : `id_validation` (PK), `id_organisation` (FK), `id_soumission` (FK), `type` enum(interne, externe, tutelle), `is_validated` (Type), `commentaire` (Type), `created_at`, `updated_at`.
3. **`detection_anomalie_ia`** : Log des suspicions (collusion, entente) détectées sur une soumission.
   * Cols : `id_detection_anomalie_ia` (int, PK), `id_appel_offre` (int), `id_soumission` (int), `type_anomalie` (varchar 50), `niveau_severite` (varchar 20), `score_confiance` (decimal), `details` (text), `statut_examen` (varchar 30), `date_detection` (datetime).

---

## 🌍 3. RESTE DU SCHÉMA BDD (Pour contexte global)

*Agent IA : Utilise ceci pour comprendre les relations externes (Clés Étrangères) des entités Document et Soumission.*

### A. Acteurs & IAM (Identity & Access Management)
*   **`Organisation`** : `id_organisation` (PK), `nom_officiel`, `adresse_siege`, `email_contact`, `type_entite`.
*   **`Operateurs_Economiques`** (Les candidats) : `id_operateur_economique` (FK -> Organisation), `nif`, `registre_commerce_num`, `casnos_vrt`, `cnas_vrt`, `rib_bancaire`.
*   **`Services_Contractants`** (Les acheteurs) : `id_service` (FK -> Organisation), `id_tutelle` (FK), `categorie`, `code_ordonnateur`.
*   **`Tutelle`** : `id_tutelle` (PK), `nom_tutelle`, `identité_autorité`.
*   **`membre`** : `id_membre` (PK), `id_organisation` (FK), `prenom`, `nom`, `telephone`, `fonction`.
*   **`utilisateurs`** : `id_utilisateur` (PK), `id_role` (FK), `id_membre` (FK), `email`, `password_hash`.
*   **RBAC** : `role`, `permission`, `Permission_role`.

### B. Appels d'Offres & Contrats
*   **`appels_offres`** : `id_appel_offres` (PK), `id_service_contractant` (FK), `reference`, `titre`, `description`, `type_procedure`, `montant_estime`, `date_publication`, `date_limite_soumission`, `date_ouverture_plis`, `poids_technique`, `poids_financier`, `statut`.
*   **`contrats`** : `id_contrat` (PK), `id_soumission` (FK), `id_service_contractants` (FK), `numero_contrat`, `date_signature`, `statut`.
*   **`recours`** : `id_recours` (PK), `id_operateur_economique` (FK), `id_validation` (FK), `motif`, `statut`, `date_depot`, `decision`, `date_decision`, `traite_par`.

### C. Commissions (Loi 23-12)
*   **`Comission_interne`**, **`Comission_evaluation`**, **`Comission_Externe`**.
*   Tables de liaison membres-commissions : `Membres_Commission_interne`, `Membres_Commission_evaluation`.

### D. Audit & Traçabilité Souveraine
*   **`journaux_audit`** (Blockchain-like logs) : `id_journaux_audit` (PK), `utilisateur_id` (FK), `action`, `entite_type`, `entite_id`, `horodatage`, `adresse_ip`, **`hash_log_precedent`**, **`hash_log_actuel`** (garantit l'inaltérabilité), `details_action`.
*   **`notifications`** : `id` (PK), `utilisateur_id`, `type_notification`, `titre`, `message`, `priorite`, etc.

---

## 🛡️ LOG DE VÉRIFICATION DE SCHÉMA (POUR LE DÉVELOPPEUR ET L'AGENT)
*Checklist de validation effectuée suite à l'analyse de l'image source* :
- [x] La table `documents` possède bien 10 champs, dont `is_encrypted` (tinyint/boolean) et `ia_verif_statut`.
- [x] L'orthographe des tables de jointure a été respectée (ex: `documents_soumission` au singulier).
- [x] L'orthographe des champs de la table soumission a été respectée (`offre_financiere_chiffree_url`, `cle_dechiffrement_hash`).
- [x] Les types complexes (Enum) dans `Evaluation` et `Validation` ont été documentés.
- [x] Les anomalies IA (`detection_anomalie_ia`) pointent bien vers `id_soumission` et `id_appel_offre`.
- [x] La présence du système d'audit inaltérable (`hash_log_precedent`, `hash_log_actuel`) est documentée pour rappeler la contrainte de sécurité.