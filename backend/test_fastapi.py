import pytest
from fastapi.testclient import TestClient
from backend.main import app


client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_chat_echo():
    r = client.post("/chat", json={"message": "hello"})
    assert r.status_code == 200
    assert isinstance(r.json().get("reply"), str)


def test_chat_monkeypatch(monkeypatch):
    async def fake_generate(msg: str):
        return "patched"

    # patch the brain instance used by the app
    import backend.main as bm
    monkeypatch.setattr(bm.brain, 'generate_reply', fake_generate)
    r = client.post("/chat", json={"message": "x"})
    assert r.status_code == 200
    assert r.json()["reply"] == "patched"


def test_sync_and_summary():
    r = client.post("/sync", json={"a": 1})
    assert r.status_code == 200
    assert r.json()["status"] == "synced"
    r2 = client.get("/summary")
    assert r2.status_code == 200
    assert "summary" in r2.json()
