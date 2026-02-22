# Acteurs Service Curl

Base URL: `http://localhost:18081`

## Setup Variables
```bash
BASE_ACTEURS="http://localhost:18081"
```

## Common Endpoints
```bash
curl -sS "$BASE_ACTEURS/health"
curl -sS "$BASE_ACTEURS/ready"
curl -sS "$BASE_ACTEURS/openapi.json"
```

## Implemented Endpoints
```bash
curl -sS -X POST "$BASE_ACTEURS/membres" \
  -H 'Content-Type: application/json' \
  -d '{"id_organisation":1,"prenom":"Admin","nom":"User","telephone":"000","fonction":"Responsable"}'

curl -sS "$BASE_ACTEURS/membres/1"
```
