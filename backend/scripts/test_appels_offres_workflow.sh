#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
INTERNAL_SERVICE_TOKEN=${INTERNAL_SERVICE_TOKEN:-dev-internal-token}

# Prerequis:
# - CommissionExterne (acteurs_service) configurees avec des seuils.
# - Les validations externes (ACTEURS_SERVICE_URL, DOCUMENTS_SERVICE_URL) peuvent etre vides pour ce test.

HEADER_INTERNAL="X-Internal-Service-Token: ${INTERNAL_SERVICE_TOKEN}"
HEADER_JSON="Content-Type: application/json"

request() {
  local method=$1
  local path=$2
  local data=${3:-}
  local result
  if [ -n "$data" ]; then
    result=$(curl -sS -w "\n%{http_code}" -X "$method" -H "$HEADER_INTERNAL" -H "$HEADER_JSON" "$BASE_URL$path" -d "$data")
  else
    result=$(curl -sS -w "\n%{http_code}" -X "$method" -H "$HEADER_INTERNAL" "$BASE_URL$path")
  fi
  local body
  local code
  body=$(printf "%s" "$result" | sed '$d')
  code=$(printf "%s" "$result" | tail -n 1)
  if [ "${code:0:1}" != "2" ]; then
    echo "Request failed: $method $path (HTTP $code)" >&2
    echo "$body" >&2
    exit 1
  fi
  printf "%s" "$body"
}

json_get() {
  local key=$1
  python - "$key" <<'PY'
import json
import sys
key = sys.argv[1]
data = json.load(sys.stdin)
value = data.get(key, "")
print(value)
PY
}

RUN_ID=$(date +%s)

echo "== Scenario: consultation (auto valide) =="
consultation_payload=$(cat <<JSON
{
  "id_service_contractant": 1,
  "reference": "AO-CONS-${RUN_ID}",
  "titre": "Consultation test",
  "type_procedure": "consultation",
  "type_prestation": "fournitures",
  "visibilite": "public",
  "wilaya": "Alger",
  "secteur": "BTP",
  "montant_estime": "5000000",
  "id_operateur_choisi": 42,
  "id_doc_besoin": 5001,
  "date_limite_soumission": "2030-01-01T10:00:00Z",
  "poids_technique": 70,
  "poids_financier": 30
}
JSON
)
consultation_resp=$(request POST "/appels-offres" "$consultation_payload")
consultation_id=$(printf "%s" "$consultation_resp" | json_get id_appel_offres)
echo "consultation_id=$consultation_id"


echo "== Scenario: publique -> validation -> execution =="
public_payload=$(cat <<JSON
{
  "id_service_contractant": 1,
  "reference": "AO-PUB-${RUN_ID}",
  "titre": "Publique test",
  "type_procedure": "publique",
  "type_prestation": "travaux",
  "visibilite": "public",
  "wilaya": "Alger",
  "secteur": "BTP",
  "montant_estime": "12000000"
}
JSON
)
public_resp=$(request POST "/appels-offres" "$public_payload")
public_id=$(printf "%s" "$public_resp" | json_get id_appel_offres)
echo "public_id=$public_id"

request POST "/appels-offres/${public_id}/soumettre-validation" '{"validated_by":"00000000-0000-0000-0000-000000000001"}' > /dev/null
request POST "/appels-offres/${public_id}/valider" '{"validated_by":"00000000-0000-0000-0000-000000000001"}' > /dev/null
request POST "/appels-offres/${public_id}/publier" > /dev/null
request POST "/appels-offres/${public_id}/cloturer-depot" > /dev/null
request POST "/appels-offres/${public_id}/ouvrir-plis" > /dev/null


echo "== Scenario: restreint -> validation =="
restreint_payload=$(cat <<JSON
{
  "id_service_contractant": 1,
  "reference": "AO-RES-${RUN_ID}",
  "titre": "Restreint test",
  "type_procedure": "restreint",
  "type_prestation": "services",
  "visibilite": "prive",
  "wilaya": "Alger",
  "secteur": "BTP",
  "montant_estime": "6000000",
  "id_doc_cdc": 3101,
  "id_doc_justification": 3102,
  "operateurs_invites": [10, 20]
}
JSON
)
restreint_resp=$(request POST "/appels-offres" "$restreint_payload")
restreint_id=$(printf "%s" "$restreint_resp" | json_get id_appel_offres)
echo "restreint_id=$restreint_id"

request POST "/appels-offres/${restreint_id}/soumettre-validation" '{"validated_by":"00000000-0000-0000-0000-000000000002"}' > /dev/null
request POST "/appels-offres/${restreint_id}/valider" '{"validated_by":"00000000-0000-0000-0000-000000000002"}' > /dev/null


echo "== Scenario: gre_a_gre -> refuser =="
gre_payload=$(cat <<JSON
{
  "id_service_contractant": 1,
  "reference": "AO-GRE-${RUN_ID}",
  "titre": "Gre a gre test",
  "type_procedure": "gre_a_gre",
  "type_prestation": "services",
  "visibilite": "prive",
  "wilaya": "Alger",
  "secteur": "BTP",
  "montant_estime": "2000000",
  "id_operateur_choisi": 77,
  "id_doc_cdc": 4101,
  "id_doc_justification": 4102,
  "date_limite_soumission": "2030-01-01T10:00:00Z",
  "poids_technique": 80,
  "poids_financier": 20
}
JSON
)
gre_resp=$(request POST "/appels-offres" "$gre_payload")
gre_id=$(printf "%s" "$gre_resp" | json_get id_appel_offres)
echo "gre_a_gre_id=$gre_id"

request POST "/appels-offres/${gre_id}/soumettre-validation" '{"validated_by":"00000000-0000-0000-0000-000000000003"}' > /dev/null
request POST "/appels-offres/${gre_id}/refuser" '{"validated_by":"00000000-0000-0000-0000-000000000003"}' > /dev/null


echo "All scenarios completed."
