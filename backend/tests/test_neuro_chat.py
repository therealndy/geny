from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_neuro_state_and_chat():
    r = client.post("/neuro/state", json={"mood": 0.9, "sleep": 0.7, "stress": 0.1})
    assert r.status_code == 200
    temp = r.json()["temperature"]
    assert 0.1 <= temp <= 1.5
    rr = client.post("/neuro/chat", json={"message": "Say hi", "temperature": temp})
    assert rr.status_code == 200, rr.text
    data = rr.json()
    assert data["status"] == "ok"
    assert "reply" in data
