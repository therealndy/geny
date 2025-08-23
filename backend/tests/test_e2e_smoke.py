from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_e2e_smoke():
    # Health
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"

    # Memory ingest & search
    r = client.post(
        "/mem/ingest",
        json={
            "text": "Geny learned about attention and memory.",
            "meta": {"src": "e2e"},
        },
    )
    assert r.status_code == 200 and r.json()["chunks"] >= 1
    r = client.get("/mem/search", params={"q": "memory", "k": 3})
    assert r.status_code == 200 and len(r.json().get("results", [])) >= 1

    # LifeTwin reply (RAG)
    r = client.post("/lifetwin/reply", json={"message": "What did Geny learn?"})
    assert r.status_code == 200 and r.json().get("status") == "ok"

    # Neuro state + chat
    r = client.post("/neuro/state", json={"mood": 0.8, "sleep": 0.6, "stress": 0.2})
    assert r.status_code == 200 and "temperature" in r.json()
    r = client.post("/neuro/chat", json={"message": "Hello from e2e"})
    assert r.status_code == 200 and r.json().get("status") == "ok"

    # Nightly orchestration (open in tests)
    import backend.main as main

    # ensure no token for test
    main._get_import_token_source = lambda: (None, None)
    r = client.post("/admin/run-nightly", json={"params": {"temperature": 0.7}})
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body and "params" in body
