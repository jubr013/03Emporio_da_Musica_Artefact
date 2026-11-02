import json

import pytest

from src import tools


@pytest.fixture(autouse=True)
def temp_tickets_file(tmp_path, monkeypatch):
    # Write tickets to a temporary folder instead of the real history/ (pytest cleans it up)
    monkeypatch.setattr(tools, "TICKETS_FILE", tmp_path / "tickets.jsonl")
    monkeypatch.setenv("STORE_TODAY", "2026-02-20")


def test_creates_ticket_and_saves_it():
    result = tools.create_support_ticket("devolucao", "Cliente quer devolver o ukulele", order_id=7)
    assert result["created"]
    assert result["protocol"].startswith("EM20260220-")

    saved = [json.loads(line) for line in tools.TICKETS_FILE.read_text(encoding="utf-8").splitlines()]
    assert len(saved) == 1
    assert saved[0]["order_id"] == 7
    assert saved[0]["protocol"] == result["protocol"]


def test_each_ticket_gets_its_own_protocol():
    first = tools.create_support_ticket("reclamacao", "Atraso na entrega")
    second = tools.create_support_ticket("reclamacao", "Atraso na entrega")
    assert first["protocol"] != second["protocol"]


def test_rejects_unknown_type():
    result = tools.create_support_ticket("pizza", "?")
    assert result["created"] is False
    assert not tools.TICKETS_FILE.exists()
