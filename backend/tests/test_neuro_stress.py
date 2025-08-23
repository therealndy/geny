from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_neuro_stress_50x():
    r = client.get("/neuro/stress50x")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "base" in data and "after" in data
    assert data["after"] >= data["base"]
