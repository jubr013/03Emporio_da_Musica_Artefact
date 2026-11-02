"""Tests for the web API (src/api.py) with a fake model: no API key or quota needed."""
import os

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from src.agent import FALLBACK_ANSWER
from src.api import create_app
from tests.fake_model import make_agent, text_response, tool_call_response


def client_with(*scripts: list) -> TestClient:
    """App whose Nth new conversation gets an agent that follows the Nth script."""
    pending = list(scripts)
    return TestClient(create_app(agent_factory=lambda: make_agent(pending.pop(0))))


@pytest.fixture(autouse=True)
def no_store_today(monkeypatch):
    monkeypatch.delenv("STORE_TODAY", raising=False)


def test_health():
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_returns_answer_and_tool_calls():
    client = client_with([tool_call_response("get_policy", {"topic": "horarios"}), text_response("Abrimos às 9h.")])
    response = client.post("/api/chat", json={"message": "que horas abre?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Abrimos às 9h."
    assert body["tool_calls"] == [{"name": "get_policy", "args": {"topic": "horarios"}}]
    assert body["session_id"]


def test_same_session_keeps_the_conversation():
    client = client_with([text_response("Oi!"), text_response("Lembro sim.")])
    first = client.post("/api/chat", json={"message": "oi"}).json()
    second = client.post("/api/chat", json={"message": "lembra de mim?", "session_id": first["session_id"]}).json()

    assert second["session_id"] == first["session_id"]
    assert second["answer"] == "Lembro sim."
    assert second["tool_calls"] == []  # tool calls are reported per message, not accumulated


def test_unknown_session_starts_a_new_conversation():
    client = client_with([text_response("Oi!")])
    body = client.post("/api/chat", json={"message": "oi", "session_id": "does-not-exist"}).json()
    assert body["session_id"] != "does-not-exist"


@pytest.mark.parametrize("payload", [{"message": ""}, {"message": "   "}, {"message": "x" * 2001},
                                     {"message": "oi", "today": "20/02/2026"}, {}])
def test_invalid_requests_are_rejected(payload):
    response = client_with([text_response("never used")]).post("/api/chat", json=payload)
    assert response.status_code == 422


def test_today_is_applied_to_the_conversation():
    seen = {}

    def factory():
        agent = make_agent([text_response("ok")])
        original_send = agent.send

        def send(message):
            seen["store_today"] = os.getenv("STORE_TODAY")
            return original_send(message)

        agent.send = send
        return agent

    client = TestClient(create_app(agent_factory=factory))
    client.post("/api/chat", json={"message": "oi", "today": "2026-02-20"})
    assert seen["store_today"] == "2026-02-20"


def test_model_errors_become_a_friendly_answer():
    busy = errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})
    body = client_with([busy]).post("/api/chat", json={"message": "oi"}).json()
    assert body["answer"] == FALLBACK_ANSWER


def test_end_chat_removes_the_session():
    client = client_with([text_response("Oi!")])
    session_id = client.post("/api/chat", json={"message": "oi"}).json()["session_id"]

    assert client.delete(f"/api/chat/{session_id}").json() == {"removed": True}
    assert client.delete(f"/api/chat/{session_id}").json() == {"removed": False}
