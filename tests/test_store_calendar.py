from datetime import date, datetime

import pytest

from src.prompts import build_system_prompt
from src.store_calendar import easter_sunday, holiday_name, upcoming_holidays


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
