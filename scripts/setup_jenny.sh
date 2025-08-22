#!/usr/bin/env zsh
# Setup helper for Jenny Brain (Flutter) workspace
# Usage: ./scripts/setup_jenny.sh [project-path]
# Example: ./scripts/setup_jenny.sh geny_app/app

set -euo pipefail

PROJECT_PATH=${1:-"geny_app/app"}
ROOT="$(pwd)"
FULL_PATH="$ROOT/$PROJECT_PATH"

echo "Running Jenny Brain setup for Flutter project: $FULL_PATH"

if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter not found in PATH. Please install Flutter and ensure it's on your PATH." >&2
  exit 1
fi

if [ ! -f "$FULL_PATH/pubspec.yaml" ]; then
  echo "No pubspec.yaml found at $FULL_PATH" >&2
  exit 1
fi

cd "$FULL_PATH"

echo "Running flutter pub get..."
flutter pub get

echo "Optional: run the following commands if you want codegen and hive setup:"
echo "  flutter pub run build_runner build --delete-conflicting-outputs"
echo "  (and) initialize Hive boxes in app startup (see lib/brain/services/memory_service.dart)"

echo "Setup helper finished. Next: implement modules under lib/brain and run flutter analyze/test."
