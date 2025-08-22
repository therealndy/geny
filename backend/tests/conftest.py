import pytest

from geny import gemini_api


def pytest_configure(config):
    # Minimal configuration hook placeholder
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Prevent accidental network calls in unit tests by stubbing socket.create_connection."""

    import socket

    def fake_create_connection(*a, **k):
        raise RuntimeError("Network calls disabled in tests")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)


@pytest.fixture(autouse=True)
def mock_gemini_client(monkeypatch):
    """Default test fixture that replaces genai.Client with a harmless fake
    client so unit tests don't call the real Gemini API.
    Tests that need to exercise error paths can override this fixture.
    """

    class FakeChat:
        def send_message(self, *_args, **_kwargs):
            class Resp:
                text = "Test fake reply"

            return Resp()

    class FakeChats:
        def create(self, model):
            return FakeChat()

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        chats = FakeChats()

    monkeypatch.setattr(gemini_api, "genai", gemini_api.genai)
    monkeypatch.setattr(gemini_api.genai, "Client", FakeClient)

    yield
