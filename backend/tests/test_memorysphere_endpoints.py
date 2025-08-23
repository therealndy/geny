from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_ingest_and_search():
    r = client.post(
        "/mem/ingest",
        json={"text": "Geny loves learning about memory.", "meta": {"src": "test"}},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("chunks", 0) >= 1

    r2 = client.get("/mem/search", params={"q": "memory", "k": 5})
    assert r2.status_code == 200, r2.text
    res = r2.json().get("results", [])
    assert any("Geny" in item.get("text", "") for item in res)
