# Contrats Service Curl

Base URL: `http://localhost:18085`

## Setup Variables

```bash
BASE_CONTRATS="http://localhost:18085"
```

## Common Endpoints

```bash
curl -sS "$BASE_CONTRATS/health"
curl -sS "$BASE_CONTRATS/ready"
curl -sS "$BASE_CONTRATS/openapi.json"
```

## Validations

### List all validations

```bash
curl -sS "$BASE_CONTRATS/validations"
```

### Create a validation

```bash
curl -sS -X POST "$BASE_CONTRATS/validations" \
  -H 'Content-Type: application/json' \
  -d '{"id_organisation":1,"id_soumission":1,"type":"interne","commentaire":"Validation initiale"}'
```

### Get a validation

```bash
curl -sS "$BASE_CONTRATS/validations/1"
```

### Update a validation

```bash
curl -sS -X PATCH "$BASE_CONTRATS/validations/1" \
  -H 'Content-Type: application/json' \
  -d '{"commentaire":"Mise à jour du commentaire"}'
```

### Delete a validation

```bash
curl -sS -X DELETE "$BASE_CONTRATS/validations/1"
```

### Approve a validation

```bash
curl -sS -X POST "$BASE_CONTRATS/validations/1/approuver"
```

### Reject a validation

```bash
curl -sS -X POST "$BASE_CONTRATS/validations/1/rejeter" \
  -H 'Content-Type: application/json' \
  -d '{"commentaire":"Motif du rejet"}'
```

## Contrats

### List all contrats

```bash
curl -sS "$BASE_CONTRATS/contrats"
```

### Create a contrat

```bash
curl -sS -X POST "$BASE_CONTRATS/contrats" \
  -H 'Content-Type: application/json' \
  -d '{"id_soumission":1,"id_service_contractants":1,"numero_contrat":"CTR-2026-001"}'
```

### Get a contrat

```bash
curl -sS "$BASE_CONTRATS/contrats/1"
```

### Update a contrat

```bash
curl -sS -X PATCH "$BASE_CONTRATS/contrats/1" \
  -H 'Content-Type: application/json' \
  -d '{"statut":"en_cours"}'
```

### Delete a contrat

```bash
curl -sS -X DELETE "$BASE_CONTRATS/contrats/1"
```

### Sign a contrat

```bash
curl -sS -X POST "$BASE_CONTRATS/contrats/1/signer"
```

## Contrat Documents

### List documents of a contrat

```bash
curl -sS "$BASE_CONTRATS/contrats/1/documents"
```

### Attach a document to a contrat

```bash
curl -sS -X POST "$BASE_CONTRATS/contrats/1/documents/1"
```

### Remove a document from a contrat

```bash
curl -sS -X DELETE "$BASE_CONTRATS/contrats/1/documents/1"
```

## Cross-entity Lookups

### Get contrat by soumission

```bash
curl -sS "$BASE_CONTRATS/soumissions/1/contrat"
```
