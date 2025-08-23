from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_build_info_endpoint():
    r = client.get("/admin/build-info")
    assert r.status_code == 200
    body = r.json()
    assert "timestamp_utc" in body
    # git fields are optional; presence is a bonus
    assert isinstance(body.get("timestamp_utc"), str)
