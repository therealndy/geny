#!/usr/bin/env bash
set -euo pipefail

HOST=${1:-127.0.0.1}
PORT=${2:-8000}

# Start backend (will try to read GENAI_API_KEY from env or Secret Manager)
./scripts/start_backend.sh "$HOST" "$PORT"

# Run flutter app pointing at the local backend
pushd android_app/app >/dev/null
flutter pub get
flutter run --dart-define=BACKEND_URL="http://$HOST:$PORT"
popd >/dev/null
