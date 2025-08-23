from fastapi.testclient import TestClient

import backend.main as main
from backend.main import app

client = TestClient(app)


def test_admin_run_nightly_open(monkeypatch):
    # Ensure no admin token is enforced during this test
    monkeypatch.delenv("IMPORT_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(main, "_get_import_token_source", lambda: (None, None))
    # No token set in tests; endpoint should allow and return report
    r = client.post("/admin/run-nightly", json={"params": {"temperature": 0.7}})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "summary" in data
    assert "params" in data
