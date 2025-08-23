from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_rate_limit_4_per_hour():
    # Fire 4 requests should pass
    for i in range(4):
        r = client.post("/chat", json={"message": f"hello {i}"})
        assert r.status_code == 200, r.text
    # 5th should be 429
    r5 = client.post("/chat", json={"message": "hello 5"})
    assert r5.status_code == 429, r5.text
    data = r5.json()
    assert data.get("status") == "rate_limited"
    assert data.get("limit") == 4
