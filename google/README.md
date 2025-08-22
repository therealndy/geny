Compatibility shim: `google/genai.py`

Purpose
- Provide a thin compatibility layer so existing code that imports `google.genai`
  can continue to run while the project uses `google.generativeai`.

What it does
- Exposes `Client(api_key=...)` with `models.list()` and `chats.create(...)`
  implemented by delegating to `google.generativeai` primitives.
- Normalizes chat responses to expose a simple `.text` attribute and a safe
  `__str__` representation so tests and scripts can depend on string output.

Notes and best practices
- This shim is a short-term compatibility layer. Prefer migrating code to use
  `google.generativeai` directly in the future.
- Keep API keys out of version control. Use a local `.env` or the platform
  secrets store (GitHub Secrets / Render environment variables) in production.
- If you expose any real API keys accidentally, rotate them immediately.

Testing
- A unit test `backend/test_genai_shim.py` mocks `google.generativeai` and
  verifies the shim behavior without performing network requests.

Contact
- If you need the shim extended to support more features, update the
  implementation and add tests mirroring expected `generativeai` responses.
