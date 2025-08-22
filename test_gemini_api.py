import os

import pytest

try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None


def test_gemini_api_live():
    """Live integration test for Gemini — skipped when GENAI_API_KEY is not set.

    This test intentionally skips on CI unless a secret `GENAI_API_KEY` is provided
    so developers can run it locally with a .env file for manual verification.
    """
    api_key = os.getenv("GENAI_API_KEY")
    if not api_key or genai is None:
        pytest.skip(
            "Skipping live Gemini test: GENAI_API_KEY not set or genai client missing"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content("Hello Gemini, are you working?")
    # Ensure we received a response object (basic smoke check)
    assert response is not None
