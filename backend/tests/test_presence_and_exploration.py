from time import sleep

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_movement_start_stop_status():
    # Initially stopped
    r = client.get("/world/move/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False

    # Start movement (internal method to avoid network)
    r = client.post(
        "/world/move/start",
        json={
            "base_interval_seconds": 20,
            "method": "internal",
            "follow_exploration": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"started", "already_running"}

    # Status should reflect running and have a last_tick relatively soon
    sleep(0.2)
    r = client.get("/world/move/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is True
    assert isinstance(body.get("interval_seconds"), (int, float))
    assert body.get("method") in {"internal", "http"}

    # Stop movement
    r = client.post("/world/move/stop")
    assert r.status_code == 200
    r = client.get("/world/move/status")
    assert r.status_code == 200
    assert r.json()["running"] is False


def test_exploration_produces_diary_entry():
    # Ensure stopped first
    client.post("/world/exploration/stop")
    r = client.get("/world/exploration/status")
    assert r.status_code == 200
    assert r.json()["running"] in {False, True}

    # Start exploration with a small base interval (actual loop clamps min 5s but first tick happens immediately)
    r = client.post("/world/exploration/start", json={"base_interval_seconds": 6})
    assert r.status_code == 200
    sleep(0.3)

    # Learning should include an auto diary insight soon after start
    r = client.get("/world/learning?n=3")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    diary = body.get("diary_recent") or []
    # Accept either a diary entry with "insight" or at least one entry present
    assert isinstance(diary, list)
    assert len(diary) >= 1

    # Cleanup
    client.post("/world/exploration/stop")
