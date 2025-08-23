#!/usr/bin/env bash
# Autostart helper: enables background indexing and periodic curiosity pokes
set -euo pipefail

HOST=${1:-127.0.0.1}
PORT=${2:-8000}

# Enable background indexer in backend
export GENY_BACKGROUND_INDEX=1
export GENY_BACKGROUND_INDEX_INTERVAL=${GENY_BACKGROUND_INDEX_INTERVAL:-300}

# Start backend (non-blocking)
./scripts/start_backend.sh "$HOST" "$PORT"

# Small background loop to poke Geny with a curiosity request every N seconds
# This helps Geny run exploration and invoke Gemini/DDG fallbacks.
# Runs in background and logs to ./backend/curiosity.log
INTERVAL=${3:-600}
(
  while true; do
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') - curiosity ping" >> backend/curiosity.log
    # Try a friendly curiosity endpoint that will cause Geny to pop a question
    curl -sS --fail "http://$HOST:$PORT/world/questions/ask" -m 10 >> backend/curiosity.log 2>&1 || true
    sleep "$INTERVAL"
  done
) &

echo "Autostart requested: backend started on http://$HOST:$PORT; curiosity pinger running every ${INTERVAL}s (see backend/curiosity.log)."
