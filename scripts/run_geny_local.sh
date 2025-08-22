#!/usr/bin/env bash
# Lightweight helper to run the backend locally using .env variables.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
else
  echo ".env not found. Copy .env.example to .env and set GENAI_API_KEY"
  exit 1
fi

echo "Starting backend on http://127.0.0.1:8000"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
