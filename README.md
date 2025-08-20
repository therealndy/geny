(Minimal README)

Prereqs
- gcloud authenticated and project set to `geny-469516`.
- Python 3.12 and .venv created (project contains requirements.txt).

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


