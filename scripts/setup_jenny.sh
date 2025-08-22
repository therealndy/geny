#!/usr/bin/env zsh
# Setup helper for Jenny Brain (Flutter) workspace
# Usage: ./scripts/setup_jenny.sh [project-path]
# Example: ./scripts/setup_jenny.sh geny_app/app

set -euo pipefail

PROJECT_PATH=${1:-"android_app/app"}
ROOT="$(pwd)"
FULL_PATH="$ROOT/$PROJECT_PATH"

SKIP_CODEGEN=0
SKIP_RUN=0

for arg in "$@"; do
  case "$arg" in
    --skip-codegen) SKIP_CODEGEN=1 ;;
    --skip-run) SKIP_RUN=1 ;;
  esac
done

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

echo "1) flutter pub get"
flutter pub get

if [ "$SKIP_CODEGEN" -eq 0 ]; then
  if grep -q "build_runner" pubspec.yaml 2>/dev/null || grep -q "hive_generator" pubspec.yaml 2>/dev/null; then
    echo "2) running build_runner codegen (delete-conflicting-outputs)"
    flutter pub run build_runner build --delete-conflicting-outputs || echo "codegen failed (continuing)"
  else
    echo "2) no codegen dependencies found; skipping build_runner"
  fi
else
  echo "2) skipping codegen as requested"
fi

echo "3) flutter analyze"
flutter analyze || (echo "analyze failed" && exit 1)

echo "4) flutter test"
flutter test --reporter=expanded || (echo "tests failed" && exit 1)

if [ "$SKIP_RUN" -eq 0 ]; then
  # Only attempt to run if a device is available
  if flutter devices --machine | grep -q '\"id\"'; then
    echo "5) device detected — running 'flutter run' (press Ctrl+C to stop)"
    echo "If you prefer, re-run with --skip-run to avoid launching the app."
    flutter run
  else
    echo "5) no connected device/emulator found — skip flutter run"
  fi
else
  echo "5) skipping flutter run as requested"
fi

echo "Setup helper finished. Repo is analyzed and tests passed."
