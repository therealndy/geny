(Minimal README)

Prereqs

Start backend (one command)
1. Upload your GENAI key to Secret Manager as `genai-api-key` (see scripts above).
2. Run:
```bash
./scripts/start_backend.sh
```

Run tests locally
```bash
source .venv/bin/activate
export GENAI_API_KEY="$(gcloud secrets versions access latest --secret='genai-api-key' --project='geny-469516')"
.venv/bin/python -m pytest backend -q
```
## Run tests locally (mocked, no secret required)

```bash
source .venv/bin/activate
# Tests are mocked by default; no GENAI_API_KEY required for unit tests
.venv/bin/python -m pytest backend -q
```

## Run live integration tests (optional)

If you want to run live tests against Gemini, set the secret and run pytest only for integration tests:

```bash
export GENAI_API_KEY="$(gcloud secrets versions access latest --secret='genai-api-key' --project='geny-469516')"
# e.g. run a specific integration test file
.venv/bin/python -m pytest tests/integration/test_live_gemini.py -q
```

## CI

This project includes a GitHub Actions workflow that runs Flutter tests for the Android app.

[![Flutter Tests](https://github.com/therealndy/geny/actions/workflows/flutter_tests.yml/badge.svg)](https://github.com/therealndy/geny/actions/workflows/flutter_tests.yml)

## Override backend URL (development)

Flutter app:
- Run with a different backend using dart-define:
	flutter run --dart-define=BACKEND_URL=http://10.0.2.2:8000

Web chat:
- Open `web_chat.html` with a query param, e.g. `web_chat.html?backend=http://localhost:8000` to point the web UI to a local backend.

## Gemini API key (GENAI) and CI / deployment secrets

The backend calls Gemini (Google GenAI). For local development you can set the `GENAI_API_KEY` environment variable. The repository already attempts to read the key from:

- `GENAI_API_KEY` environment variable (preferred for local dev)
- `GOOGLE_API_KEY` environment variable (alternative)
- Google Secret Manager (configurable via `GENAI_SECRET_PROJECT` and `GENAI_SECRET_NAME`)

If no key is present, the code falls back to a safe local reply for tests and development (no live Gemini calls).

To add the key to GitHub Actions (for deploy or integration workflows) add a repository secret named `GENAI_API_KEY` in the repository settings and reference it in workflows as `${{ secrets.GENAI_API_KEY }}`. Do NOT commit the key to source.

Example (Cloud Deploy / Cloud Run workflows already use this secret):
- In repository: Settings → Secrets → Actions → New repository secret → Name: `GENAI_API_KEY`, Value: <your-key>
- The deployment workflow can set the environment variable so the running service can call Gemini.

Note: Unit tests are mocked by default and do not require a Gemini key.

Shim docs
---------

There is a small compatibility shim at `google/genai.py` to preserve older
imports that expect `google.genai`. See `google/README.md` for details and
testing notes.

## Dev helper: start backend and run Flutter

There is a small helper script that starts the backend (using the existing helper which will attempt to load `GENAI_API_KEY`) and then runs the Flutter app pointed at the local backend.

Usage:

```bash
./scripts/run_dev.sh [HOST] [PORT]
# Example: start backend on 127.0.0.1:8000 and run flutter targeting it
./scripts/run_dev.sh 127.0.0.1 8000
```

The script will call `./scripts/start_backend.sh` and then run `flutter run --dart-define=BACKEND_URL=http://HOST:PORT` in `android_app/app`.



