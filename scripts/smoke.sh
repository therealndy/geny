#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE="http://${HOST}:${PORT}"

curl_json() {
  local method="$1" path="$2" data="${3:-}"
  if [ -n "$data" ]; then
    curl -sS -f -X "$method" "$BASE$path" -H 'Content-Type: application/json' -d "$data" | sed -e 's/.*/OK: &/'
  else
    curl -sS -f -X "$method" "$BASE$path" | sed -e 's/.*/OK: &/'
  fi
}

echo "== Smoke: $BASE =="

# Discover optional admin token
AUTH_HEADER=""
if [ -n "${IMPORT_ADMIN_TOKEN:-}" ]; then
  AUTH_HEADER="Authorization: Bearer ${IMPORT_ADMIN_TOKEN}"
elif [ -f /tmp/IMPORT_ADMIN_TOKEN ]; then
  TOK=$(cat /tmp/IMPORT_ADMIN_TOKEN || true)
  if [ -n "$TOK" ]; then AUTH_HEADER="Authorization: Bearer ${TOK}"; fi
fi

# 1) Health + build-info
curl_json GET "/healthz"
curl_json GET "/admin/build-info"

# 2) MemorySphere
curl_json POST "/mem/ingest" '{"text":"Hello Geny memory!","meta":{"source":"smoke"}}'
curl_json GET "/mem/search?q=Geny&k=3"

# 3) LifeTwin & Neuro
curl_json POST "/lifetwin/reply" '{"message":"What did you learn?"}'
curl_json POST "/neuro/state" '{"mood":0.8,"sleep":0.6,"stress":0.2}'
curl_json POST "/neuro/chat" '{"message":"Hello from smoke"}'

# 4) Nightly orchestration
if [ -n "$AUTH_HEADER" ]; then
  curl -sS -f -X POST "$BASE/admin/run-nightly" -H 'Content-Type: application/json' -H "$AUTH_HEADER" -d '{"params":{"temperature":0.7}}' | sed -e 's/.*/OK: &/'
else
  # If no token configured, endpoint may be open; try without header
  curl_json POST "/admin/run-nightly" '{"params":{"temperature":0.7}}'
fi

echo "== Smoke completed successfully =="
