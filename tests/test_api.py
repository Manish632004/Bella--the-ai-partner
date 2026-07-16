from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from bella.app import app


def test_index_route():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "BELLA" in response.text
    assert "qwen2.5:0.5b-instruct" in response.text


def test_health_check_ok():
    client = TestClient(app)
    with patch("bella.core.llm.llm.check_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = True
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "ollama": True,
            "model": "qwen2.5:0.5b-instruct"
        }


def test_health_check_degraded():
    client = TestClient(app)
    with patch("bella.core.llm.llm.check_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = False
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["ollama"] is False


def test_chat_non_streaming():
    client = TestClient(app)
    with patch("bella.core.llm.llm.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Hello! I am BELLA."
        response = client.post(
            "/api/chat",
            json={
                "message": "Hi",
                "stream": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! I am BELLA."
        assert "session_id" in data


def test_clear_chat():
    client = TestClient(app)
    # First send a chat to establish session
    with patch("bella.core.llm.llm.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Response"
        response = client.post(
            "/api/chat",
            json={
                "message": "Hi",
                "stream": False
            }
        )
        session_id = response.json()["session_id"]

    # Clear chat
    clear_response = client.post(
        "/api/chat/clear",
        json={"session_id": session_id}
    )
    assert clear_response.status_code == 200
    assert clear_response.json() == {
        "status": "cleared",
        "session_id": session_id
    }
