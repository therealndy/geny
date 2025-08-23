# First run (quick success)

1) Start backend
- Ensure your virtualenv is active and dependencies installed (see `requirements.txt`).
- Start:
  - macOS/zsh: `bash ./scripts/start_backend.sh 127.0.0.1 8000`

2) Sanity checks
- GET `/healthz` → `{ "status": "ok" }`
- GET `/admin/build-info` → timestamp + optional git info

3) MemorySphere
- POST `/mem/ingest` with `{ "text": "Hello Geny memory!" }`
- GET `/mem/search?q=Geny&k=3`

4) LifeTwin & Neuro
- POST `/lifetwin/reply` with `{ "message": "What did you learn?" }`
- POST `/neuro/state` with `{ "mood": 0.8, "sleep": 0.6, "stress": 0.2 }`
- POST `/neuro/chat` with `{ "message": "Hello" }`

5) Nightly orchestration
- POST `/admin/run-nightly` with `{ "params": { "temperature": 0.7 } }`

6) Tests
- Run: `pytest backend/tests -q` → should be green.
