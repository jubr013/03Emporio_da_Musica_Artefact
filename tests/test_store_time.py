from datetime import date, timedelta

from src import tools
from src.prompts import build_system_prompt


def test_now_uses_campo_grande_time_zone(monkeypatch):
    monkeypatch.delenv("STORE_TODAY", raising=False)
    assert tools.now().utcoffset() == timedelta(hours=-4)  # Campo Grande has no daylight saving time


def test_store_today_overrides_only_the_date(monkeypatch):
    monkeypatch.setenv("STORE_TODAY", "2026-02-20")
    current = tools.now()
    assert current.date() == date(2026, 2, 20)
    assert current.utcoffset() == timedelta(hours=-4)
    assert tools.today() == date(2026, 2, 20)


def test_system_prompt_shows_weekday_and_date(monkeypatch):
    monkeypatch.setenv("STORE_TODAY", "2026-02-20")  # a Friday
    prompt = build_system_prompt(tools.now())
    assert "sexta-feira, 20/02/2026" in prompt
