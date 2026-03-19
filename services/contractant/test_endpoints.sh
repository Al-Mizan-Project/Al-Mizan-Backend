#!/bin/sh
# ============================================================
# Al-Mizan – Contractant service endpoint test script
# Usage:  sh test_endpoints.sh [BASE_URL]
# Default BASE_URL: http://localhost:18082
# ============================================================
set -eu

BASE="${1:-http://localhost:18082}"
PASS=0
FAIL=0

# ── helpers ─────────────────────────────────────────────────
green() { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
red()   { printf '\033[0;31m✗ %s\033[0m\n' "$*"; }

expect() {
  LABEL="$1"
  EXPECTED="$2"
  ACTUAL="$3"
  if [ "$ACTUAL" = "$EXPECTED" ]; then
    green "$LABEL (HTTP $ACTUAL)"
    PASS=$((PASS+1))
  else
    red "$LABEL — expected HTTP $EXPECTED, got HTTP $ACTUAL"
    FAIL=$((FAIL+1))
  fi
}

http_code() {
  # $1 method, $2 url, $3 optional body
  if [ -n "${3:-}" ]; then
    curl -s -o /dev/null -w "%{http_code}" \
      -X "$1" "$2" \
      -H "Content-Type: application/json" \
      -d "$3"
  else
    curl -s -o /dev/null -w "%{http_code}" -X "$1" "$2"
  fi
}

json_field() {
  # extract a top-level integer field with a minimal sed approach
  # $1 = field name, $2 = json string
  printf '%s' "$2" | sed 's/.*"'"$1"'":\s*\([0-9]*\).*/\1/'
}

echo ""
echo "=== Al-Mizan Contractant Service — Endpoint Tests ==="
echo "Base URL: $BASE"
echo ""

# ── Health & Ready ───────────────────────────────────────────
echo "--- [Health] ---"
expect "GET /health" 200 "$(http_code GET "$BASE/health")"
expect "GET /ready"  200 "$(http_code GET "$BASE/ready")"
expect "GET /openapi.json" 200 "$(http_code GET "$BASE/openapi.json")"

# ── ServiceContractant ───────────────────────────────────────
echo ""
echo "--- [ServiceContractant] ---"

SC_RESP="$(curl -s -X POST "$BASE/services-contractants" \
  -H "Content-Type: application/json" \
  -d '{"id_tutelle":1,"categorie":"Ministère","code_ordonnateur":"ORD-CURL-001"}')"
SC_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/services-contractants" \
  -H "Content-Type: application/json" \
  -d '{"id_tutelle":2,"categorie":"Wilaya","code_ordonnateur":"ORD-CURL-002"}')"
expect "POST /services-contractants" 201 "$SC_CODE"

# Get the ID of the first created service
SC_ID="$(json_field id_service "$SC_RESP")"
printf "  Created service ID: %s\n" "$SC_ID"

expect "GET  /services-contractants/$SC_ID" 200 \
  "$(http_code GET "$BASE/services-contractants/$SC_ID")"

expect "PATCH /services-contractants/$SC_ID" 200 \
  "$(http_code PATCH "$BASE/services-contractants/$SC_ID" '{"categorie":"Commune"}')"

expect "GET  /services-contractants/99999 (404)" 404 \
  "$(http_code GET "$BASE/services-contractants/99999")"

# ── CommissionEvaluation ─────────────────────────────────────
echo ""
echo "--- [CommissionEvaluation] ---"

expect "GET  /commissions-evaluation" 200 "$(http_code GET "$BASE/commissions-evaluation")"

CE_RESP="$(curl -s -X POST "$BASE/commissions-evaluation" \
  -H "Content-Type: application/json" \
  -d "{\"id_service\":$SC_ID,\"nom_comission\":\"CE Curl Test\",\"categorie\":\"Travaux\"}")"
CE_CODE="$(printf '%s' "$CE_RESP" | grep -o '"id_comission":[0-9]*' | head -1 | wc -c)"
CE_FULL_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/commissions-evaluation" \
  -H "Content-Type: application/json" \
  -d "{\"id_service\":$SC_ID,\"nom_comission\":\"CE Curl Test 2\",\"categorie\":\"Services\"}")"
expect "POST /commissions-evaluation" 201 "$CE_FULL_CODE"

CE_ID="$(json_field id_comission "$CE_RESP")"
printf "  Created commission eval ID: %s\n" "$CE_ID"

expect "GET  /commissions-evaluation/$CE_ID" 200 \
  "$(http_code GET "$BASE/commissions-evaluation/$CE_ID")"

expect "PATCH /commissions-evaluation/$CE_ID" 200 \
  "$(http_code PATCH "$BASE/commissions-evaluation/$CE_ID" '{"categorie":"Fournitures"}')"

expect "GET  /commissions-evaluation/99999 (404)" 404 \
  "$(http_code GET "$BASE/commissions-evaluation/99999")"

# Membres for CommissionEvaluation
expect "GET  /commissions-evaluation/$CE_ID/membres" 200 \
  "$(http_code GET "$BASE/commissions-evaluation/$CE_ID/membres")"

expect "POST /commissions-evaluation/$CE_ID/membres/10" 201 \
  "$(http_code POST "$BASE/commissions-evaluation/$CE_ID/membres/10")"

expect "POST /commissions-evaluation/$CE_ID/membres/20" 201 \
  "$(http_code POST "$BASE/commissions-evaluation/$CE_ID/membres/20")"

expect "POST /commissions-evaluation/$CE_ID/membres/10 (idempotent)" 201 \
  "$(http_code POST "$BASE/commissions-evaluation/$CE_ID/membres/10")"

expect "DELETE /commissions-evaluation/$CE_ID/membres/20" 204 \
  "$(http_code DELETE "$BASE/commissions-evaluation/$CE_ID/membres/20")"

expect "DELETE /commissions-evaluation/$CE_ID/membres/99999 (404)" 404 \
  "$(http_code DELETE "$BASE/commissions-evaluation/$CE_ID/membres/99999")"

# ── CommissionInterne ────────────────────────────────────────
echo ""
echo "--- [CommissionInterne] ---"

expect "GET  /commissions-internes" 200 "$(http_code GET "$BASE/commissions-internes")"

CI_RESP="$(curl -s -X POST "$BASE/commissions-internes" \
  -H "Content-Type: application/json" \
  -d "{\"id_service\":$SC_ID,\"nom_comission\":\"CI Curl Test\",\"type_comission\":\"parmanante\"}")"
CI_FULL_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/commissions-internes" \
  -H "Content-Type: application/json" \
  -d "{\"id_service\":$SC_ID,\"nom_comission\":\"CI Adhoc\",\"type_comission\":\"adhoc\"}")"
expect "POST /commissions-internes" 201 "$CI_FULL_CODE"

CI_ID="$(json_field id_comission_interne "$CI_RESP")"
printf "  Created commission interne ID: %s\n" "$CI_ID"

expect "GET  /commissions-internes/$CI_ID" 200 \
  "$(http_code GET "$BASE/commissions-internes/$CI_ID")"

expect "PATCH /commissions-internes/$CI_ID" 200 \
  "$(http_code PATCH "$BASE/commissions-internes/$CI_ID" '{"type_comission":"adhoc"}')"

expect "POST  /commissions-internes/$CI_ID/membres/5" 201 \
  "$(http_code POST "$BASE/commissions-internes/$CI_ID/membres/5")"

expect "GET   /commissions-internes/$CI_ID/membres" 200 \
  "$(http_code GET "$BASE/commissions-internes/$CI_ID/membres")"

expect "DELETE /commissions-internes/$CI_ID/membres/5" 204 \
  "$(http_code DELETE "$BASE/commissions-internes/$CI_ID/membres/5")"

expect "DELETE /commissions-internes/$CI_ID/membres/99999 (404)" 404 \
  "$(http_code DELETE "$BASE/commissions-internes/$CI_ID/membres/99999")"

expect "GET  /commissions-internes/99999 (404)" 404 \
  "$(http_code GET "$BASE/commissions-internes/99999")"

# ── ServiceContractant – commissions & membres ───────────────
echo ""
echo "--- [ServiceContractant commissions & membres] ---"

expect "GET /services-contractants/$SC_ID/commissions" 200 \
  "$(http_code GET "$BASE/services-contractants/$SC_ID/commissions")"

expect "GET /services-contractants/$SC_ID/membres" 200 \
  "$(http_code GET "$BASE/services-contractants/$SC_ID/membres")"

# ── CommissionExterne ────────────────────────────────────────
echo ""
echo "--- [CommissionExterne] ---"

expect "GET  /commissions-externes" 200 "$(http_code GET "$BASE/commissions-externes")"

CEX_RESP="$(curl -s -X POST "$BASE/commissions-externes" \
  -H "Content-Type: application/json" \
  -d '{"nom_comission":"CEX Curl","niveau_competance":"Nationale","seuils_competence_financiere":">500M"}')"
CEX_FULL_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/commissions-externes" \
  -H "Content-Type: application/json" \
  -d '{"nom_comission":"CEX Wilaya","niveau_competance":"de Wilaya","seuils_competence_financiere":"10M-100M"}')"
expect "POST /commissions-externes" 201 "$CEX_FULL_CODE"

CEX_ID="$(json_field id_comission_externe "$CEX_RESP")"
printf "  Created commission externe ID: %s\n" "$CEX_ID"

expect "GET  /commissions-externes/$CEX_ID" 200 \
  "$(http_code GET "$BASE/commissions-externes/$CEX_ID")"

expect "PATCH /commissions-externes/$CEX_ID" 200 \
  "$(http_code PATCH "$BASE/commissions-externes/$CEX_ID" '{"niveau_competance":"Sectorielle"}')"

expect "GET  /commissions-externes/99999 (404)" 404 \
  "$(http_code GET "$BASE/commissions-externes/99999")"

# ── Cleanup (DELETE) ─────────────────────────────────────────
echo ""
echo "--- [Cleanup – DELETE] ---"

expect "DELETE /commissions-externes/$CEX_ID" 204 \
  "$(http_code DELETE "$BASE/commissions-externes/$CEX_ID")"

expect "DELETE /commissions-evaluation/$CE_ID" 204 \
  "$(http_code DELETE "$BASE/commissions-evaluation/$CE_ID")"

expect "DELETE /commissions-internes/$CI_ID" 204 \
  "$(http_code DELETE "$BASE/commissions-internes/$CI_ID")"

expect "DELETE /services-contractants/$SC_ID" 204 \
  "$(http_code DELETE "$BASE/services-contractants/$SC_ID")"

expect "DELETE /services-contractants/$SC_ID again (404)" 404 \
  "$(http_code DELETE "$BASE/services-contractants/$SC_ID")"

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "============================================"
printf "Results: \033[0;32m%d passed\033[0m, \033[0;31m%d failed\033[0m\n" "$PASS" "$FAIL"
echo "============================================"
[ "$FAIL" -eq 0 ]
