import types


def test_genai_shim_basic(monkeypatch):
    """Verify the google.genai shim works with a mocked google.generativeai implementation."""

    # Build a fake generativeai module
    class FakePart:
        def __init__(self, text):
            self.text = text

    class FakeContent:
        def __init__(self, parts):
            self.parts = parts

    class FakeCandidate:
        def __init__(self, content):
            self.content = content

    class FakeResponse:
        def __init__(self, text):
            self.candidates = [FakeCandidate(FakeContent([FakePart(text)]))]

    class ChatSession:
        def __init__(self):
            self.sent = []

        def send_message(self, content):
            self.sent.append(content)
            return FakeResponse(f"echo:{content}")

    class GenerativeModel:
        def __init__(self, model):
            self.model = model

        def start_chat(self):
            return ChatSession()

    fake = types.SimpleNamespace()
    fake.GenerativeModel = GenerativeModel
    fake.list_models = lambda: ["models/fake-1", "models/fake-2"]
    fake.configure = lambda **kw: None

    # Patch into the real google package namespace
    import google

    monkeypatch.setattr(google, "generativeai", fake)

    # Now import the shim and exercise it
    import importlib

    genai_shim = importlib.import_module("google.genai")

    c = genai_shim.Client(api_key="fake")
    # models.list should proxy to fake.list_models
    models = list(c.models.list())
    assert "models/fake-1" in models

    chat = c.chats.create(model="models/fake-1")
    resp = chat.send_message("hello")
    assert hasattr(resp, "text")
    assert str(resp).startswith("echo:")
