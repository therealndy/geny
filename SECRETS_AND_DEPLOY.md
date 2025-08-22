Secrets & deploy checklist
==========================

This file documents the repository secrets required for CI, Android signing, and Render deploys — plus step-by-step instructions to add them and trigger the post-merge deploy workflows.

Required repository secrets
---------------------------
- GENAI_API_KEY — (string) Gemini / Google GenAI API key. Used by `geny/gemini_api.py` when resolving keys from the environment.
- RENDER_SERVICE_ID — (string) Render service ID used by the Render deploy workflow.
- RENDER_API_TOKEN — (string) Render API token with permission to trigger deploys.
- ANDROID_KEYSTORE_BASE64 — (base64) base64-encoded JKS keystore for Android signing (optional for debug builds, required for signed AABs).
- ANDROID_KEYSTORE_PASSWORD — (string) password for the keystore.
- ANDROID_KEY_ALIAS — (string) key alias inside the keystore.
- ANDROID_KEY_PASSWORD — (string) password for the private key.

Optional / environment guidance
------------------------------
- If you prefer Secret Manager for GENAI_API_KEY, the backend code will attempt to fetch from Google Secret Manager when the env var is not present. CI and Render need the secret available as a repo secret or in the environment used by the runner.

How to add secrets (GitHub UI)
-------------------------------
1. Open the repository on GitHub.
2. Go to Settings -> Secrets and variables -> Actions -> New repository secret.
3. Add each secret name above with the correct value and click Save.

How to add secrets (gh CLI)
----------------------------
Run (macOS zsh):

```bash
# interactive prompt for value
gh secret set GENAI_API_KEY --body "$(cat /path/to/genai-key.txt)"
gh secret set RENDER_API_TOKEN --body "YOUR_RENDER_API_TOKEN"
gh secret set RENDER_SERVICE_ID --body "YOUR_RENDER_SERVICE_ID"
gh secret set ANDROID_KEYSTORE_BASE64 --body "$(base64 -w0 path/to/keystore.jks)"
gh secret set ANDROID_KEYSTORE_PASSWORD --body "your-keystore-password"
gh secret set ANDROID_KEY_ALIAS --body "your-key-alias"
gh secret set ANDROID_KEY_PASSWORD --body "your-key-password"
```

How to trigger the manual Render deploy workflow (after secrets are set)
---------------------------------------------------------------------
Preferred (GitHub UI):
1. Go to Actions -> "Deploy to Render" (or the workflow named "Deploy to Render").
2. Click "Run workflow" and select the branch (e.g. `feat/auto-fixes-clean`) and any inputs.

Optional (API / curl):
```bash
# replace OWNER/REPO and workflow filename if different
GITHUB_TOKEN="$(gh auth token)"
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/therealndy/geny/actions/workflows/deploy-render.yml/dispatches \
  -d '{"ref":"feat/auto-fixes-clean"}'
```

After deploy: run the post-deploy smoke tests
--------------------------------------------
1. In Actions, locate the `Post-deploy smoke tests` workflow.
2. Click "Run workflow" and provide the base URL of the deployed Render service (e.g. https://geny-1.onrender.com).

If you want me to trigger the deploy after you add the secrets, reply here with "secrets added" and I will dispatch the workflow and run the smoke tests.
