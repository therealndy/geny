import os

prompt = "Vad ser du runt dig just nu och hur mår du?"


def run_flash(api_key: str):
    # Import inside function so pytest can skip before importing google.genai
    import google.genai as genai

    client = genai.Client(api_key=api_key)
    print("Available models:")
    for model in client.models.list():
        print(model)
    chat = client.chats.create(model="models/gemini-2.5-flash")
    response = chat.send_message(prompt)
    print("Gemini Flash response:", getattr(response, "text", str(response)))


if __name__ == "__main__":
    API_KEY = os.getenv("GENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not API_KEY:
        print(
            "[Gemini Flash test] Missing API key. Set GENAI_API_KEY or GOOGLE_API_KEY in your environment."
        )
        raise SystemExit(1)
    try:
        run_flash(API_KEY)
    except Exception as e:
        print("[Gemini Flash error]", str(e))


# Pytest-friendly test function
def test_gemini_flash_runs_or_skips():
    import pytest

    API_KEY = os.getenv("GENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not API_KEY:
        pytest.skip("GENAI_API_KEY/GOOGLE_API_KEY not set; skipping live Gemini test")
    # If key present, run the flash (will raise on failures)
    run_flash(API_KEY)
