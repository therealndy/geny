from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_world_time_endpoint():
    r = client.get("/world/time")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert isinstance(body.get("now_real_utc"), str)
    assert isinstance(body.get("now_virtual_utc"), str)
    assert isinstance(body.get("since_real_utc"), str)
    va = body.get("virtual_age")
    assert isinstance(va, dict)
    assert all(k in va for k in ["years", "days", "hours", "minutes"])
    assert 0 < body.get("scale", 0) <= 10


def test_world_learning_endpoint():
    r = client.get("/world/learning?n=3")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "life_summary" in body
    assert "virtual_age" in body
    assert "diary_recent" in body
    assert "insights" in body
    assert "interactions_recent" in body
