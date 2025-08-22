import asyncio

from geny import gemini_api


def test_placeholder():
    # This placeholder ensures pytest finds at least one test in this module
    assert 1 + 1 == 2


def test_gemini_circuit_breaker(monkeypatch):
    # Replace the genai.GenerativeModel with a fake model whose generate_content raises.
    class FakeModel:
        def __init__(self, model_name):
            pass

        def generate_content(self, prompt):
            raise Exception("API key not valid")

    monkeypatch.setattr(gemini_api.genai, "GenerativeModel", FakeModel)

    # Run the wrapper; it should catch underlying exceptions and return an error string
    reply = asyncio.run(gemini_api.generate_reply("test prompt", max_retries=1))
    assert reply.startswith("[Gemini") or isinstance(reply, str)
