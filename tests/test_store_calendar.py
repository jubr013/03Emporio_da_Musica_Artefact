import re
from datetime import date, datetime, time
from pathlib import Path

import pytest

from src.prompts import build_system_prompt
from src.store_calendar import OPENING_HOURS, easter_sunday, holiday_name, is_open, next_opening, upcoming_holidays

POLICIES_FILE = Path(__file__).resolve().parent.parent / "data" / "policies.md"


@pytest.mark.parametrize("year, expected", [(2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))])
def test_easter_dates(year, expected):
    assert easter_sunday(year) == expected


@pytest.mark.parametrize("day, name", [
    (date(2026, 4, 3), "Paixão de Cristo (Sexta-feira Santa)"),  # matches the municipal decree for 2026
    (date(2026, 10, 11), "Criação do Estado de Mato Grosso do Sul"),
    (date(2026, 11, 2), "Finados"),
    (date(2026, 11, 20), "Dia Nacional de Zumbi e da Consciência Negra"),
    (date(2026, 8, 26), "Aniversário de Campo Grande"),
])
def test_known_holidays(day, name):
    assert holiday_name(day) == name


@pytest.mark.parametrize("day", [date(2026, 2, 16), date(2026, 6, 4), date(2026, 2, 20)])
def test_optional_days_and_normal_days_are_not_holidays(day):
    # 16/02 Carnival and 04/06 Corpus Christi are only "ponto facultativo"; 20/02 is a normal Friday
    assert holiday_name(day) is None


def test_upcoming_holidays_window():
    assert [name for _, name in upcoming_holidays(date(2026, 11, 10))] == [
        "Proclamação da República", "Dia Nacional de Zumbi e da Consciência Negra",
    ]


def test_prompt_says_store_is_closed_on_a_holiday():
    prompt = build_system_prompt(datetime(2026, 11, 2, 10, 0))
    assert "HOJE É FERIADO (Finados): a loja está fechada." in prompt


def test_prompt_lists_upcoming_holiday():
    prompt = build_system_prompt(datetime(2026, 11, 12, 10, 0))
    assert "Hoje não é feriado." in prompt
    assert "15/11 (domingo): Proclamação da República" in prompt


@pytest.mark.parametrize("moment, expected", [
    (datetime(2026, 11, 4, 9, 0), True),     # Wednesday, opening minute
    (datetime(2026, 11, 4, 17, 59), True),
    (datetime(2026, 11, 4, 18, 0), False),   # closing time: already closed
    (datetime(2026, 11, 7, 12, 30), True),   # Saturday morning
    (datetime(2026, 11, 7, 13, 0), False),   # Saturday after 13:00
    (datetime(2026, 11, 8, 10, 0), False),   # Sunday
    (datetime(2026, 11, 2, 10, 0), False),   # Monday, but Finados
])
def test_is_open(moment, expected):
    assert is_open(moment) is expected


@pytest.mark.parametrize("moment, expected", [
    (datetime(2026, 11, 4, 7, 0), datetime(2026, 11, 4, 9, 0)),     # early morning: same day
    (datetime(2026, 11, 4, 19, 0), datetime(2026, 11, 5, 9, 0)),    # weeknight: next morning
    (datetime(2026, 11, 7, 14, 0), datetime(2026, 11, 9, 9, 0)),    # Saturday afternoon: Monday
    (datetime(2026, 11, 1, 10, 0), datetime(2026, 11, 3, 9, 0)),    # Sunday before Finados: Tuesday
    (datetime(2026, 11, 19, 19, 0), datetime(2026, 11, 21, 9, 0)),  # eve of Consciência Negra (Fri): Saturday
    (datetime(2026, 12, 24, 19, 0), datetime(2026, 12, 26, 9, 0)),  # Christmas Eve: Saturday the 26th
])
def test_next_opening_skips_sundays_and_holidays(moment, expected):
    assert next_opening(moment) == expected


def test_prompt_says_when_the_team_is_back():
    prompt = build_system_prompt(datetime(2026, 11, 7, 14, 0))
    assert "A loja está FECHADA agora. Próxima abertura: segunda-feira, 09/11 às 09:00." in prompt
    assert "A loja está ABERTA agora." in build_system_prompt(datetime(2026, 11, 4, 10, 0))


def test_prompt_hours_line_comes_from_the_table():
    prompt = build_system_prompt(datetime(2026, 11, 4, 10, 0))
    assert "segunda a sexta 09:00–18:00, sábado 09:00–13:00, domingo e feriados fechado" in prompt


def test_opening_hours_match_the_policy():
    # The prompt and next_opening() use OPENING_HOURS; the policy text is what get_policy shows the customer.
    # If either changes alone, this fails.
    section = POLICIES_FILE.read_text(encoding="utf-8").split("## horarios")[1].split("\n## ")[0]
    rows = dict(re.findall(r"\| (.+?) \| (.+?) \|", section))
    assert rows["Segunda a Sexta-feira"] == "09:00 às 18:00"
    assert rows["Sábado"] == "09:00 às 13:00"
    assert rows["Domingo e Feriados"] == "Fechado"
    assert all(OPENING_HOURS[day] == (time(9), time(18)) for day in range(5))
    assert OPENING_HOURS[5] == (time(9), time(13))
    assert 6 not in OPENING_HOURS
