# Documentation globale - Analyse de conformite (OCR/NLP)

## 1) Objectif fonctionnel

La fonctionnalite d'analyse de conformite du service IA verifie automatiquement la completude administrative d'un dossier de soumission.

Elle combine:
- une verification structurelle (pieces requises vs pieces fournies),
- un controle de validite des pieces (statut IA document),
- une inferrence de type documentaire basee sur metadonnees et OCR (approche NLP par dictionnaire de synonymes).

Le resultat est un statut de conformite exploitable metier, synchronise vers les microservices Soumissions et Documents.

## 2) Perimetre et composants

Le pipeline est implemente dans le service IA, principalement dans:
- `ia_service/views.py`
- `ia_service/services/conformite.py`
- `ia_service/services/ocr.py`
- `ia_service/services/integrations.py`
- `ia_service/serializers.py`

### Services externes relies
- Service Appels: recuperation des pieces requises d'un appel d'offres.
- Service Documents: recuperation metadonnees et binaire des pieces, puis ecriture metadata IA.
- Service Soumissions: ecriture du statut de conformite final.

## 3) Endpoints exposes

## 3.1 Verification manuelle

POST `/ia/conformite/verifier-soumission/<soumission_id>`

Usage:
- Le client fournit directement `required_documents` et `provided_documents`.
- Le service calcule le statut de conformite et synchronise les resultats.

Payload typique:
```json
{
  "required_documents": ["rc", "nif", "attestation_fiscale"],
  "provided_documents": [
    {"id_document": 33, "type_document": "rc", "is_valid": true},
    {"id_document": 34, "type_document": "nif", "is_valid": true}
  ]
}
```

## 3.2 Verification automatique (avec OCR optionnel)

POST `/ia/conformite/verifier-soumission-auto/<soumission_id>`

Usage:
- Le client fournit `id_appel_offre` et `provided_document_ids`.
- Le service IA recupere automatiquement les pieces requises et les metadonnees.
- Si `perform_ocr=true`, il enrichit l'identification des types documentaires via OCR.

Payload minimum:
```json
{
  "id_appel_offre": 77,
  "provided_document_ids": [9001, 9002],
  "perform_ocr": true
}
```

Options importantes:
- `required_document_ids`: permet de bypasser la recuperation Appels.
- `required_documents`: permet de fournir directement les labels metier requis.
- `enforce_validity_checks` (defaut: true): utilise `ia_verif_statut` pour determiner la validite document.
- `perform_ocr` (defaut: true): active/desactive l'enrichissement OCR.

## 4) Logique metier de conformite

La logique de decision est concentree dans `run_conformite_check`.

## 4.1 Entrees normalisees
- `required_documents`: liste canonique des types attendus.
- `provided_documents`: liste des pieces detectees/fournies, avec `type_document` et `is_valid`.

## 4.2 Regles de decision

Le statut suit une priorite stricte:
1. Si au moins une piece requise est absente -> `PIECES_MANQUANTES`
2. Sinon, si au moins une piece fournie est invalide -> `NON_CONFORME`
3. Sinon -> `CONFORME`

Rapport produit:
- `required_count`
- `provided_count`
- `missing_documents`
- `invalid_documents`
- `conformite_statut`

## 5) NLP de classification documentaire

Le composant NLP repose sur une normalisation textuelle et un dictionnaire de synonymes.

## 5.1 Normalisation
- suppression des accents,
- passage en minuscule,
- nettoyage des caracteres non alphanumeriques,
- compactage des espaces.

## 5.2 Synonymes supportes (exemples)
- `rc`: registre de commerce
- `nif`: numero d'identification fiscale
- `nis`: numero d'identification statistique
- `ai`: article/attestation d'imposition
- `cnas`, `casnos`
- `attestation_fiscale`: quitus fiscal, extrait role
- `declaration_probite`
- `offre_technique`, `offre_financiere`

Cette inferrence est appliquee sur:
- `type_document_label`
- `nom` du fichier
- `type_document`
- `ocr_text` (si OCR actif)

## 6) Pipeline OCR

Le pipeline OCR est execute pour la voie automatique si `perform_ocr=true`.

## 6.1 Strategie d'extraction

Pour chaque document:
1. Controle de taille (`MAX_OCR_FILE_SIZE`).
2. Si PDF: extraction texte native via `pypdf`.
3. Si PDF sans texte (scan): fallback `pdf2image + pytesseract`.
4. Si image (png/jpg/tif/bmp): OCR `pytesseract`.
5. Si extension inconnue et fallback active: tentative OCR image.

Sortie OCR unitaire:
```json
{
  "text": "...",
  "engine": "pypdf|pdf2image+tesseract|tesseract|none",
  "used": true
}
```

En cas de fichier trop volumineux:
```json
{
  "text": "",
  "engine": "none",
  "used": false,
  "skipped_reason": "file_too_large"
}
```

## 6.2 Parallelisation
- OCR multi-documents via thread pool (`OCR_MAX_WORKERS`).
- Conservation de l'ordre des resultats.
- Echec OCR unitaire non bloquant (retour neutre pour le document concerne).

## 6.3 Role de l'OCR dans la decision
L'OCR sert a mieux inferer le type documentaire (ex: detecter "registre de commerce" dans un scan).

Important: l'absence d'OCR exploitable n'interrompt pas la verification. Le moteur continue avec les metadonnees disponibles.

## 7) Orchestration bout-en-bout (endpoint auto)

1. Validation du payload.
2. Resolution des pieces requises:
   - soit depuis `required_documents`,
   - soit via Appels + metadonnees Documents.
3. Recuperation metadonnees des pieces fournies.
4. Construction des `provided_documents` projetes.
5. (Optionnel) OCR sur binaires Documents + enrichissement du `type_document`.
6. Calcul `conformite_statut` + rapport.
7. Synchronisation:
   - patch Soumission (`conformite_statut`, `conformite_rapport`),
   - patch Documents (`ia_verif_statut`, `ia_verif_details`).
8. Retour API avec `analysis_context` detaille.

## 8) Synchronisation inter-services

## 8.1 Lecture
- Appels -> documents requis d'un appel.
- Documents -> recherche metadonnees par IDs.
- Documents -> telechargement binaire d'une piece.

## 8.2 Ecriture
- Soumissions:
  - PATCH `/api/soumissions/{id}/conformite/`
  - payload: `conformite_statut`, `conformite_rapport`
- Documents:
  - PATCH `/api/documents/{id}/ia-metadata/`
  - payload: `ia_verif_statut`, `ia_verif_details` (JSON serialise)

## 8.3 Authentification inter-services
Si configure, le header `X-Internal-Service-Token` est ajoute aux appels internes.

## 9) Statuts et actions metier

Statuts de conformite renvoyes:
- `CONFORME`
- `NON_CONFORME`
- `PIECES_MANQUANTES`

Action metier proposee:
- `EVALUATION_TECHNIQUE` si conforme
- `VALIDATION_HUMAINE` sinon

Statut IA document applique:
- `VALID` si soumission conforme
- `ANOMALY` sinon

## 10) Gestion d'erreurs et resilence

Erreurs bloquantes (retour 502):
- echec de recuperation des pieces requises (Appels/Documents),
- echec de recuperation des metadonnees des pieces fournies.

Erreurs non bloquantes:
- echec OCR sur un ou plusieurs documents,
- echec patch d'un document individuel,
- OCR indisponible localement (dependances absentes).

Le service tente de produire un resultat de conformite meme en presence d'echecs partiels.

## 11) Variables d'environnement et tuning

Parametres principaux:
- `OCR_TESSERACT_LANG` (defaut: `fra+ara`)
- `OCR_FALLBACK_IMAGE_ATTEMPT` (defaut: `true`)
- `MAX_OCR_FILE_SIZE` (defaut: `20971520` = 20 MB)
- `OCR_MAX_WORKERS` (defaut: `4`)
- `REMOTE_SERVICE_TIMEOUT` (defaut: `3` secondes)
- `INTERNAL_SERVICE_TOKEN` (optionnel)

URLs de services:
- `SOUMISSIONS_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `APPELS_SERVICE_URL`

## 12) Dependances techniques

Dependances OCR/NLP utilisees:
- `pypdf`
- `pytesseract`
- `pdf2image`
- `pillow`

Dependances systeme (environnement Docker/local):
- `tesseract-ocr`
- `tesseract-ocr-fra`
- `tesseract-ocr-ara`
- `poppler-utils` (pour pdf2image)

## 13) Couverture tests pertinente

Les tests existants valident notamment:
- fallback PDF scanne vers OCR,
- limite de taille OCR,
- parallelisation OCR et ordre des resultats,
- endpoint auto avec OCR active,
- synchronisation inter-services,
- non-blocage en cas d'echec partiel de patch document.

## 14) Limites actuelles et pistes d'amelioration

Limites:
- NLP base sur dictionnaire de synonymes (pas de modele semantique avance).
- Statut document binaire (`VALID`/`ANOMALY`) applique uniformement selon statut global de soumission.
- Pas de score de confiance par document dans la sortie conformite.

Ameliorations recommandees:
- ajouter une classification NLP semantique (embeddings/modeles FR-AR),
- distinguer statut IA par document selon resultat individuel,
- stocker trace OCR par document (engine, confidence, erreurs),
- ajouter un mode asynchrone pour gros volumes.
