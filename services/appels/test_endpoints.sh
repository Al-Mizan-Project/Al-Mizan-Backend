#!/bin/sh
# ============================================================
# Al-Mizan – Appels service endpoint test script
# Usage:  sh test_endpoints.sh [BASE_URL]
# Default BASE_URL: http://localhost:18083
# ============================================================
set -eu

BASE="${1:-http://localhost:18083}"
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
  printf '%s' "$2" | sed 's/.*"'"$1"'":\s*\([0-9]*\).*/\1/'
}

echo ""
echo "=== Al-Mizan Appels Service — Endpoint Tests ==="
echo "Base URL: $BASE"
echo ""

# ── Health & Ready ───────────────────────────────────────────
echo "--- [Health] ---"
expect "GET /health"       200 "$(http_code GET "$BASE/health")"
expect "GET /ready"        200 "$(http_code GET "$BASE/ready")"
expect "GET /openapi.json" 200 "$(http_code GET "$BASE/openapi.json")"

# ── Create AppelOffres ────────────────────────────────────────
echo ""
echo "--- [AppelOffres CRUD] ---"

AO_RESP="$(curl -s -X POST "$BASE/appels-offres" \
  -H "Content-Type: application/json" \
  -d '{"id_service_contractant":1,"reference":"AO-CURL-001","titre":"Test curl","type_procedure":"Consultation","montant_estime":"5000000","poids_technique":50,"poids_financier":50}')"
AO_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/appels-offres" \
  -H "Content-Type: application/json" \
  -d '{"id_service_contractant":1,"reference":"AO-CURL-002","titre":"Test curl 2","type_procedure":"Consultation","montant_estime":"3000000","poids_technique":40,"poids_financier":60}')"
expect "POST /appels-offres" 201 "$AO_CODE"

AO_ID="$(json_field id_appel_offres "$AO_RESP")"
printf "  Created appel ID: %s\n" "$AO_ID"

expect "GET  /appels-offres" 200 "$(http_code GET "$BASE/appels-offres")"
expect "GET  /appels-offres/$AO_ID" 200 "$(http_code GET "$BASE/appels-offres/$AO_ID")"
expect "PATCH /appels-offres/$AO_ID" 200 \
  "$(http_code PATCH "$BASE/appels-offres/$AO_ID" '{"titre":"Titre modifié"}')"
expect "GET  /appels-offres/99999 (404)" 404 "$(http_code GET "$BASE/appels-offres/99999")"

# ── Filter by service contractant ────────────────────────────
echo ""
echo "--- [Filter by service contractant] ---"
expect "GET /services-contractants/1/appels-offres" 200 \
  "$(http_code GET "$BASE/services-contractants/1/appels-offres")"
expect "GET /services-contractants/999/appels-offres (empty list)" 200 \
  "$(http_code GET "$BASE/services-contractants/999/appels-offres")"

# ── Workflow actions ──────────────────────────────────────────
echo ""
echo "--- [Workflow actions] ---"

expect "POST /appels-offres/$AO_ID/publier" 200 \
  "$(http_code POST "$BASE/appels-offres/$AO_ID/publier")"

expect "POST /appels-offres/$AO_ID/publier again (400)" 400 \
  "$(http_code POST "$BASE/appels-offres/$AO_ID/publier")"

expect "POST /appels-offres/$AO_ID/cloturer-depot" 200 \
  "$(http_code POST "$BASE/appels-offres/$AO_ID/cloturer-depot")"

expect "POST /appels-offres/$AO_ID/ouvrir-plis" 200 \
  "$(http_code POST "$BASE/appels-offres/$AO_ID/ouvrir-plis")"

expect "POST /appels-offres/$AO_ID/annuler from plis_ouverts (400)" 400 \
  "$(http_code POST "$BASE/appels-offres/$AO_ID/annuler")"

# Create fresh appel to test annuler
AO2_RESP="$(curl -s -X POST "$BASE/appels-offres" \
  -H "Content-Type: application/json" \
  -d '{"id_service_contractant":1,"reference":"AO-CURL-ANN","titre":"Annulation test","type_procedure":"Consultation"}')"
AO2_ID="$(json_field id_appel_offres "$AO2_RESP")"
expect "POST /appels-offres/$AO2_ID/annuler (from brouillon)" 200 \
  "$(http_code POST "$BASE/appels-offres/$AO2_ID/annuler")"

expect "POST /appels-offres/99999/publier (404)" 404 \
  "$(http_code POST "$BASE/appels-offres/99999/publier")"

# ── Documents ─────────────────────────────────────────────────
echo ""
echo "--- [Documents] ---"

AO3_RESP="$(curl -s -X POST "$BASE/appels-offres" \
  -H "Content-Type: application/json" \
  -d '{"id_service_contractant":2,"reference":"AO-CURL-DOC","titre":"Docs test","type_procedure":"Consultation"}')"
AO3_ID="$(json_field id_appel_offres "$AO3_RESP")"

expect "GET  /appels-offres/$AO3_ID/documents (empty)" 200 \
  "$(http_code GET "$BASE/appels-offres/$AO3_ID/documents")"

expect "POST /appels-offres/$AO3_ID/documents/501" 201 \
  "$(http_code POST "$BASE/appels-offres/$AO3_ID/documents/501")"

expect "POST /appels-offres/$AO3_ID/documents/502" 201 \
  "$(http_code POST "$BASE/appels-offres/$AO3_ID/documents/502")"

expect "POST /appels-offres/$AO3_ID/documents/501 (idempotent)" 201 \
  "$(http_code POST "$BASE/appels-offres/$AO3_ID/documents/501")"

expect "GET  /appels-offres/$AO3_ID/documents (2 items)" 200 \
  "$(http_code GET "$BASE/appels-offres/$AO3_ID/documents")"

expect "DELETE /appels-offres/$AO3_ID/documents/502" 204 \
  "$(http_code DELETE "$BASE/appels-offres/$AO3_ID/documents/502")"

expect "DELETE /appels-offres/$AO3_ID/documents/99999 (404)" 404 \
  "$(http_code DELETE "$BASE/appels-offres/$AO3_ID/documents/99999")"

expect "GET  /appels-offres/99999/documents (404)" 404 \
  "$(http_code GET "$BASE/appels-offres/99999/documents")"

# ── Validation ────────────────────────────────────────────────
echo ""
echo "--- [Validation] ---"
expect "POST missing reference (400)" 400 \
  "$(http_code POST "$BASE/appels-offres" '{"id_service_contractant":1,"titre":"No ref"}')"

# ── Cleanup ───────────────────────────────────────────────────
echo ""
echo "--- [Cleanup] ---"
expect "DELETE /appels-offres/$AO3_ID" 204 "$(http_code DELETE "$BASE/appels-offres/$AO3_ID")"
expect "DELETE /appels-offres/$AO2_ID" 204 "$(http_code DELETE "$BASE/appels-offres/$AO2_ID")"
expect "DELETE /appels-offres/$AO_ID" 204 "$(http_code DELETE "$BASE/appels-offres/$AO_ID")"
expect "DELETE /appels-offres/$AO_ID again (404)" 404 "$(http_code DELETE "$BASE/appels-offres/$AO_ID")"

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "============================================"
printf "Results: \033[0;32m%d passed\033[0m, \033[0;31m%d failed\033[0m\n" "$PASS" "$FAIL"
echo "============================================"
[ "$FAIL" -eq 0 ]
