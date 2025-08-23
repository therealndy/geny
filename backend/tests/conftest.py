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
    """Default test fixture that replaces google.generativeai with a harmless fake.

    Newer code uses genai.configure + genai.GenerativeModel(...).generate_content().
    We stub those to avoid any network calls while keeping behavior predictable.
    """

    class FakeResponse:
        text = "Test fake reply"

    class FakeModel:
        def __init__(self, *_a, **_k):
            pass

        def generate_content(self, *_a, **_k):
            return FakeResponse()

    class FakeGenAI:
        def configure(self, **_k):
            return None

        GenerativeModel = FakeModel

    monkeypatch.setattr(gemini_api, "genai", FakeGenAI())

    yield
