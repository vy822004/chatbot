import os
import pytest
from fastapi.testclient import TestClient

# Configure environment for tests before importing app
os.environ["DATABASE_URL"] = "sqlite:///test_app.db"
os.environ["LLM_API_KEYS"] = "test_key_1,test_key_2"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["MOCK_LLM"] = "true"

from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
def setup_database():
    # Fresh database for test
    if os.path.exists("test_app.db"):
        os.remove("test_app.db")
    init_db()
    yield
    if os.path.exists("test_app.db"):
        os.remove("test_app.db")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 2
    assert data["cache_enabled"] is True


def test_chat_validation_errors(client):
    # Empty message
    r1 = client.post("/chat", json={"session_id": "s-1", "message": "   "})
    assert r1.status_code == 422
    assert "detail" in r1.json()

    # Message over 4000 characters
    r2 = client.post(
        "/chat", json={"session_id": "s-1", "message": "a" * 4001}
    )
    assert r2.status_code == 422
    assert "detail" in r2.json()

    # Missing session_id
    r3 = client.post("/chat", json={"message": "hello"})
    assert r3.status_code == 422
    assert "detail" in r3.json()


def test_chat_live_and_caching(client):
    session_id_1 = "s-test-cache-1"
    prompt = "What is the capital of France?"

    # Request 1: Should be LIVE_INFERENCE
    r1 = client.post(
        "/chat", json={"session_id": session_id_1, "message": prompt}
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["session_id"] == session_id_1
    assert "reply" in d1
    meta1 = d1["metadata"]
    assert meta1["resolution_source"] == "LIVE_INFERENCE"
    assert meta1["key_id"] == "key_1"
    assert meta1["fallback_attempts"] == 0
    assert meta1["latency_ms"] >= 0

    # Request 2 in a new session with identical message: Should hit cache
    session_id_2 = "s-test-cache-2"
    r2 = client.post(
        "/chat", json={"session_id": session_id_2, "message": prompt}
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["reply"] == d1["reply"]
    meta2 = d2["metadata"]
    assert meta2["resolution_source"] == "LLM_CACHE"
    assert meta2["key_id"] is None
    assert meta2["fallback_attempts"] == 0

    # Request 3 with different message: Must be LIVE_INFERENCE
    r3 = client.post(
        "/chat",
        json={"session_id": session_id_2, "message": "Different question?"},
    )
    assert r3.status_code == 200
    assert r3.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_failover_simulation(client):
    session_id = "s-failover-test"

    # Simulate key_1 failure with 429: should failover to key_2
    r_failover = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Hello failover"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert r_failover.status_code == 200
    data = r_failover.json()
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1

    # Simulate all keys failing with *=429: should return clean 503
    r_all_fail = client.post(
        "/chat",
        json={"session_id": "s-failed-all", "message": "Will fail"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert r_all_fail.status_code == 503
    assert r_all_fail.json() == {"detail": "all providers unavailable"}

    # Verify failed request is NOT stored in SQLite history
    r_history = client.get("/sessions/s-failed-all/messages")
    assert r_history.status_code == 404
    assert r_history.json() == {"detail": "session not found"}


def test_session_history(client):
    session_id = "s-multi-turn-history"

    # Turn 1
    client.post(
        "/chat", json={"session_id": session_id, "message": "First message"}
    )
    # Turn 2
    client.post(
        "/chat", json={"session_id": session_id, "message": "Second message"}
    )

    # Fetch history
    res = client.get(f"/sessions/{session_id}/messages")
    assert res.status_code == 200
    body = res.json()
    assert body["session_id"] == session_id
    messages = body["messages"]
    assert len(messages) == 4  # 2 user messages + 2 assistant messages
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "First message"
    assert messages[1]["role"] == "assistant"
    assert "metadata" in messages[1]
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Second message"
    assert messages[3]["role"] == "assistant"

    # Non-existent session
    res_404 = client.get("/sessions/s-nonexistent/messages")
    assert res_404.status_code == 404
    assert res_404.json() == {"detail": "session not found"}
