import asyncio

from fastapi.testclient import TestClient

from backend.main import app, geny

client = TestClient(app)


def test_chat_with_mock(monkeypatch):
    async def fake_generate_reply(message: str):
        await asyncio.sleep(0)
        return f"ECHO: {message}"

    # Patch the GenyBrain.generate_reply used by the endpoint
    monkeypatch.setattr(geny, "generate_reply", fake_generate_reply)

    response = client.post("/chat", json={"message": "Hej"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("reply") == "ECHO: Hej"
    assert data.get("reply").startswith("ECHO")
