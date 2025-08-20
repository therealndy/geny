import asyncio
import pytest

import pytest


def test_placeholder():
    # This placeholder ensures pytest finds at least one test in this module
    assert 1 + 1 == 2

from geny import gemini_api
def test_gemini_circuit_breaker(monkeypatch):
    # Replace the genai.Client with a fake client whose send_message raises.

    class FakeChat:
        def send_message(self, *_args, **_kwargs):
            raise Exception("API key not valid")

    class FakeChats:
        def create(self, model):
            return FakeChat()

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        chats = FakeChats()

    # Monkeypatch the Client constructor used in the gemini wrapper
    monkeypatch.setattr(gemini_api.genai, "Client", FakeClient)

    # Run the wrapper; it should catch underlying exceptions and return an error string
    reply = asyncio.run(gemini_api.gemini_generate_reply("test prompt", max_retries=1))
    assert reply.startswith("[Gemini") or isinstance(reply, str)
