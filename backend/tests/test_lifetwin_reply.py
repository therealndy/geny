from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_lifetwin_reply_smoke():
    # Seed memory
    r = client.post(
        "/mem/ingest",
        json={"text": "Geny studied memory consolidation.", "meta": {"src": "test"}},
    )
    assert r.status_code == 200
    # Ask lifetwin
    rr = client.post("/lifetwin/reply", json={"message": "What did Geny study?"})
    assert rr.status_code == 200, rr.text
    data = rr.json()
    assert "reply" in data
    assert data["status"] == "ok"
