#!/usr/bin/env bash
set -euo pipefail

# Modular setup for Geny AI extensions. Safe defaults; heavy deps behind flags.
# Usage:
#   bash geny_ai/scripts/setup.sh [--full] [--audio] [--vision]

FULL=0
AUDIO=0
VISION=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    --audio) AUDIO=1 ;;
    --vision) VISION=1 ;;
  esac
  shift || true
done

PY=python3
if command -v pyenv >/dev/null 2>&1; then
  PY=$(pyenv which python || echo python3)
fi

# Create venv if missing
if [ ! -d .venv ]; then
  echo "[setup] Creating venv"; $PY -m venv .venv
fi
source .venv/bin/activate

pip install --upgrade pip wheel
# Base deps
pip install streamlit requests pyyaml

# Optional heavy deps
if [ "$FULL" -eq 1 ]; then
  pip install langchain chromadb faiss-cpu sentence-transformers accelerate peft trl
fi
if [ "$AUDIO" -eq 1 ]; then
  pip install openai-whisper || true
fi
if [ "$VISION" -eq 1 ]; then
  pip install opencv-python pytesseract
fi

echo "[setup] OK. Try:"
echo "  BACKEND_URL=http://127.0.0.1:8000 .venv/bin/streamlit run geny_ai/app.py"
