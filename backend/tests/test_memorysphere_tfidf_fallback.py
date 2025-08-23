from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_tfidf_backend_fallback_without_sklearn(monkeypatch):
    # Request tfidf backend but do not install sklearn; service should fallback to memory and still work
    monkeypatch.setenv("GENY_MS_BACKEND", "tfidf")
    r = client.post(
        "/mem/ingest", json={"text": "TFIDF should fallback.", "meta": {"src": "test"}}
    )
    assert r.status_code == 200
    r = client.get("/mem/search", params={"q": "fallback", "k": 3})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("results"), list)
    # Reset env not strictly necessary as TestClient instances are isolated per test
