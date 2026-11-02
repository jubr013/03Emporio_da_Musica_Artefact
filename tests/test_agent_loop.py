"""Tests for the function-calling loop in src/agent.py, using a fake model instead of the Gemini API.

The fake returns scripted responses built with the SDK's real types, so the agent code runs exactly as in production.
"""
from google.genai import errors, types

from src.agent import FALLBACK_ANSWER, MAX_TOOL_ROUNDS, Agent, run_tool
from tests.fake_model import make_agent, text_response, tool_call_response


SERVER_BUSY = errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})


def test_plain_text_answer():
    agent = make_agent([text_response("Oi! Como posso ajudar?")])
    assert agent.send("oi") == "Oi! Como posso ajudar?"
    assert [content.role for content in agent.history] == ["user", "model"]


def test_tool_call_is_executed_and_result_sent_back():
    calls_seen = []
    agent = make_agent(
        [tool_call_response("get_policy", {"topic": "horarios"}, call_id="abc"), text_response("Abrimos às 9h.")],
        on_tool_call=lambda name, args, result: calls_seen.append((name, args, result["found"])),
    )

    assert agent.send("que horas abre?") == "Abrimos às 9h."
    assert calls_seen == [("get_policy", {"topic": "horarios"}, True)]

    # The second request to the model must end with the tool result, linked to the call by id and name
    tool_message = agent.client.models.requests[1][-1]
    response = tool_message.parts[0].function_response
    assert (response.id, response.name) == ("abc", "get_policy")
    assert "09:00" in response.response["content"]


def test_api_error_returns_fallback_and_rolls_back_the_turn():
    agent = make_agent([text_response("Oi!"), SERVER_BUSY])
    agent.send("oi")
    history_after_first_turn = list(agent.history)

    assert agent.send("quanto custa o GD20?") == FALLBACK_ANSWER
    assert agent.history == history_after_first_turn  # the failed turn left nothing behind


def test_api_error_after_a_tool_call_also_rolls_back():
    agent = make_agent([tool_call_response("get_policy", {"topic": "horarios"}), SERVER_BUSY])
    assert agent.send("que horas abre?") == FALLBACK_ANSWER
    assert agent.history == []


def test_stops_after_max_tool_rounds():
    script = [tool_call_response("get_policy", {"topic": "horarios"}) for _ in range(MAX_TOOL_ROUNDS)]
    agent = make_agent(script)
    assert agent.send("?") == FALLBACK_ANSWER
    assert len(agent.client.models.requests) == MAX_TOOL_ROUNDS


def test_run_tool_reports_unknown_tool():
    assert run_tool("delete_everything", {}) == {"error": "Ferramenta desconhecida: delete_everything"}


def test_run_tool_turns_exceptions_into_errors():
    result = run_tool("get_product_details", {"wrong_argument": 1})
    assert result["error"].startswith("Falha ao executar get_product_details")


def test_empty_model_response_returns_fallback():
    agent = make_agent([types.GenerateContentResponse(candidates=[])])
    assert agent.send("oi") == FALLBACK_ANSWER


def order_lookup_turn(email: str, call_id: str) -> list:
    """Script for one customer turn: the model asks for an order lookup, then answers with text."""
    return [tool_call_response("get_order_status", {"order_id": 7, "email": email}, call_id), text_response("ok")]


def last_tool_result(agent: Agent) -> dict:
    return agent.history[-2].parts[0].function_response.response


def test_order_lookups_blocked_after_three_failed_verifications():
    script = []
    for attempt in range(3):
        script += order_lookup_turn(f"wrong{attempt}@x.com", f"bad-{attempt}")
    script += order_lookup_turn("leticia.rocha@jmail.com", "right")  # correct e-mail, but too late
    agent = make_agent(script)

    for attempt in range(3):
        agent.send("pedido 7")
        assert last_tool_result(agent)["verified"] is False
    agent.send("pedido 7, agora o e-mail certo")

    result = last_tool_result(agent)
    assert result["blocked"] is True
    assert "customer_first_name" not in result  # nothing about the order leaks


def test_missing_contact_does_not_count_as_failed_attempt():
    script = []
    for attempt in range(3):
        script += [tool_call_response("get_order_status", {"order_id": 7}, f"no-contact-{attempt}"), text_response("ok")]
    script += order_lookup_turn("leticia.rocha@jmail.com", "right")
    agent = make_agent(script)

    for _ in range(4):
        agent.send("pedido 7")
    assert last_tool_result(agent)["verified"] is True


QUOTA_EXHAUSTED = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})


def test_switches_to_fallback_model_when_quota_is_exhausted(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "backup-model")
    agent = make_agent([QUOTA_EXHAUSTED, text_response("Oi!"), text_response("Tudo certo.")])

    assert agent.send("oi") == "Oi!"
    assert agent.send("e aí?") == "Tudo certo."
    # First call on the main model failed; the retry and the next turn used the fallback
    assert agent.client.models.models_used == ["fake-model", "backup-model", "backup-model"]


def test_quota_error_without_fallback_returns_fallback_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    agent = make_agent([QUOTA_EXHAUSTED])
    assert agent.send("oi") == FALLBACK_ANSWER
    assert agent.history == []


def test_other_client_errors_do_not_trigger_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "backup-model")
    bad_request = errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})
    agent = make_agent([bad_request])
    assert agent.send("oi") == FALLBACK_ANSWER
    assert agent.client.models.models_used == ["fake-model"]
