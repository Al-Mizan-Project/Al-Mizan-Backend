# Soumissions Service Context

## Architecture

- **Stack:** Python, Django, Django REST Framework
- **Database:** PostgreSQL
- **Cache/Rate-Limiting:** Redis
- **Security:** Zero-Trust, RBAC, End-to-End Encryption (E2EE)
- **Deployment:** Dockerized local stacks

## Database Schema (`soumissions` app)

### `Soumission` Model

- `id_soumission` (PK)
- `id_appel_offre` (FK to Appels d'offres service/mock)
- `id_soumissionnaire` (FK to Users service/mock)
- `offre_financiere_chiffree_url` (String - MinIO URL of the encrypted document)
- `cle_dechiffrement_hash` (Text - AES key encrypted with the Appel d'Offre's public key)
- `statut` (Enums: `SOUMIS`, `EN_OUVERTURE`, `EN_EVALUATION`, `EVALU_TERMINEE`, `RETRAITE`)
- `montant_financier` (Decimal - Null until decrypted during the bid opening phase)
- `date_soumission` (Datetime - Set on deposit)
- `conformite_statut` (String - AI processing result: CONFORME, PIECE_MANQUANTE, etc.)
- `conformite_rapport` (Text - AI generated report details)

### `Evaluation` Model

- `id_evaluation` (PK)
- `id_soumission` (FK)
- `id_comission` (FK)
- `id_membre` (FK)
- `note` (Float - Score out of 100 based on weighted criteria)
- `commentaires` (Text)

## Core Workflows (Loi 23-12 & Loi 18-07)

### Phase 1: Dépôt & Chiffrement (End-to-End Encryption)

1. **Key Generation:** Each `AppelOffre` has an RSA key pair (Public/Private).
2. **Deposit:** The client encrypts the financial offer with a symmetric AES-256 key, then encrypts the AES key with the `AppelOffre` public key.
3. **Storage:** The backend receives the encrypted file + AES key hash. The file is saved (via `documents` service or directly to MinIO). `statut = SOUMIS`.
4. **Audit:** A log is generated in `journaux_audit` with the file's SHA-256 hash.

### Phase 2: Blackout Period

- Between `date_soumission` and `date_ouverture_plis`, nobody (not even admins) can access the decrypted file or the `montant_financier`.

### Phase 3: Ouverture des Plis (Déchiffrement)

1. **Access Control:** `date_ouverture_plis` must be <= `now()`. The requesting user must have the `OUVERTURE_PLIS` permission AND belong to the `Commission_evaluation` for this `AppelOffre`.
2. **Decryption:** The backend unlocks the private key, decrypts the `cle_dechiffrement_hash`, retrieves the AES key, and decrypts the file in RAM to extract `montant_financier`.
3. **State Change:** `statut` transitions `SOUMIS` -> `EN_OUVERTURE` -> `EN_EVALUATION`.
4. **Audit:** A log is generated.

### Phase 4: Vérification & Évaluation

1. AI checks administrative documents and updates `conformite_statut` and `conformite_rapport` via PATCH requests.
2. Commission members read the AI report and the technical/financial offers, then fill out an `Evaluation` saving their `note` and `commentaires`.

## Mandatory Development Rules

1. **SECURITY FIRST:** All opening/evaluation endpoints must be heavily guarded by DRF permissions (`IsCommissionMember`, `CanOpenBids`).
2. **TESTS:** Exhaustive testing for all RBAC rules (opening too early, non-member opening). Use `testcontainers-python` for Postgres/Redis where appropriate.
3. **AOP/Signals for Audit:** Use Django Signals to write to `journaux_audit` to decouple traceability from core business logic in `SoumissionService`.
