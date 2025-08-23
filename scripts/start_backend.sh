
#!/usr/bin/env bash
set -euo pipefail

# Start backend with env from Secret Manager or env var, ensure only one uvicorn process
PROJECT="geny-469516"
SECRET_NAME="genai-api-key"
HOST=${1:-127.0.0.1}
PORT=${2:-8000}

if [ ! -d ".venv" ]; then
  echo ".venv not found. Create a virtualenv and install dependencies first."
  exit 1
fi

# Kill any running uvicorn for a clean start
pkill -f "uvicorn backend.main:app" || true
sleep 1

# Prefer env var, else try Secret Manager
if [ -n "${GENAI_API_KEY:-}" ]; then
  echo "Using GENAI_API_KEY from environment."
elif command -v gcloud >/dev/null 2>&1; then
  set +e
  KEY=$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$PROJECT" 2>/dev/null)
  RC=$?
  set -e
  if [ $RC -eq 0 ] && [ -n "$KEY" ]; then
    export GENAI_API_KEY="$KEY"
    echo "Fetched GENAI_API_KEY from Secret Manager."
  else
    echo "Warning: could not read secret $SECRET_NAME from project $PROJECT. Falling back to echo mode."
  fi
else
  echo "Warning: gcloud not found and GENAI_API_KEY not set. Falling back to echo mode."
fi

mkdir -p backend
nohup .venv/bin/python -m uvicorn backend.main:app --host "$HOST" --port "$PORT" --reload > backend/nohup.out 2>&1 &
echo $! > /tmp/uvicorn_pid.txt
sleep 5
tail -n 20 backend/nohup.out || true

# TODO: For production, add error handling, log rotation, and health checks.
