# Documentation des Endpoints : Module Soumissions

This document details all implemented endpoints in the highly secure **Soumissions** module, their expected payloads, and the required contexts to test them effectively using tools like Postman or cURL.

## Architecture Context

The service runs independently on port **8004** (`http://localhost:8004/api/soumissions/`). It expects encrypted AES keys (`cle_dechiffrement_hash`) and the URL to the physical encrypted file stored by the **Documents** service (MinIO).

---

## 1. Soumettre une Offre Financière (Phase 1: Dépôt)

- **URL** : `POST /api/soumissions/`
- **Description** : Permet de sceller et déposer une offre. Le fichier PDF de l'offre doit d'abord être chiffré côté client avec une clé AES-256 (E2EE), uploadé vers le service **Documents** pour obtenir l'URL MinIO, et la clé AES doit être chiffrée avec la clé publique (RSA) de l'appel d'offres.
- **Headers** : (Optionnel: Authentication token)

### Sample Payload (Body - JSON)

```json
{
  "id_appel_offre": 105,
  "id_soumissionnaire": 42,
  "offre_financiere_chiffree_url": "http://minio:9000/almizan-documents/soumission_105_42.pdf.enc",
  "cle_dechiffrement_hash": "base64_encoded_encrypted_aes_key"
}
```

### Successful Response (201 Created)

```json
{
  "message": "Soumission déposée et chiffrée avec succès.",
  "id": 1
}
```

---

## 2. Ouverture des Plis (Phase 3: Cérémonie de Déchiffrement)

- **URL** : `POST /api/soumissions/{id_appel_offre}/open-bids/`
- **Description** : Cette action est protégée par Zero-Trust et RBAC. Elle n'est accessible qu'après la `date_ouverture_plis` et uniquement par un membre de la commission (rôle `OUVERTURE_PLIS`). Le système récupère la clé privée de l'AO, déchiffre l'AES, déchiffre le PDF dans la RAM, extrait le montant, l'enregistre dans la DB et détruit les données temporaires.
- **Headers** :
  - `Authorization: Bearer <token>` (L'utilisateur doit être dans la table Commission !)

### Sample Payload (Body)

_(Aucun body n'est requis. L'action opère sur toutes les soumissions de cet `id_appel_offre` en statut `SOUMIS`)_.

### Successful Response (200 OK)

```json
{
  "message": "5 plis ouverts et déchiffrés avec succès."
}
```

---

## 3. Évaluation d'une Soumission (Phase 4: Vérification)

- **URL** : `POST /api/soumissions/{id_soumission}/evaluate/`
- **Description** : Permet à un membre de la commission d'attribuer une note textuelle et numérique à une soumission qui a été déchiffrée (au statut `EN_OUVERTURE` ou `EN_EVALUATION`).
- **Headers** :
  - `Authorization: Bearer <token>`

### Sample Payload (Body - JSON)

```json
{
  "id_comission": 10,
  "id_membre": 8,
  "note": 85.5,
  "commentaires": "Dossier conforme, prix très compétitif vis-à-vis de l'estimation du projet."
}
```

### Successful Response (201 Created)

```json
{
  "message": "Évaluation enregistrée.",
  "id": 1
}
```

---

## Testing State Transitions (End-to-End Mock)

To test the database without sending real AES hashes and PDFs:

1. Run `python manage.py seed_data` inside the `soumissions` container (or your local venv). This will generate 5 random soumissions.
2. Call the Swagger UI at `http://localhost:8004/api/schema/swagger-ui/`.
3. You can execute requests directly from the Swagger UI interface using the IDs listed above.
