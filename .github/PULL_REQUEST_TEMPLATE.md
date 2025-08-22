## What this PR does

- Short description of changes.

## Checklist for reviewers / maintainers

- [ ] Confirm unit tests pass locally and in CI.
- [ ] Confirm repository secrets required for deploy are present (see `SECRETS_AND_DEPLOY.md`).
- [ ] If release AAB / signed artifacts are required, ensure keystore secrets are present:
  - `ANDROID_KEYSTORE_BASE64`
  - `ANDROID_KEYSTORE_PASSWORD`
  - `ANDROID_KEY_ALIAS`
  - `ANDROID_KEY_PASSWORD`
- [ ] If deploying to Render, ensure `RENDER_SERVICE_ID` and `RENDER_API_TOKEN` are set.
- [ ] If using Gemini, ensure `GENAI_API_KEY` is set in Secrets or via Secret Manager.
- [ ] After merge, run the `Deploy to Render` workflow and then `Post-deploy smoke tests` with the deployed URL.

## Notes

- CI workflows updated to use `dart format` instead of `flutter format`.
- If you want me to trigger the Deploy + Smoke tests after secrets are added, comment "secrets added" in this PR and I'll proceed.
