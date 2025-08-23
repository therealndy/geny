# geny_ai (extensions)

This package adds Streamlit UI and stubs for MemorySphere, LifeTwin, Neuro, and Orchestrator.
It does not replace the existing FastAPI backend.

Quickstart:
- Create venv and install minimal deps:
  - bash geny_ai/scripts/setup.sh
- Run Streamlit UI:
  - BACKEND_URL=http://127.0.0.1:8000 .venv/bin/streamlit run geny_ai/app.py
