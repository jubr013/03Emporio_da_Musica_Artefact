"""Opening hours and holidays when the store is closed (policy 2: "Domingo e Feriados: Fechado").

Sources (checked 2026-11-02):
- National and state holidays: Campo Grande municipal decree nº 16.469 of 2025-12-04 (2026 calendar), which follows
  the federal list. Carnival and Corpus Christi are only optional days ("ponto facultativo"), so they are not here.
- Municipal holidays (Santo Antônio, the city's patron saint, and the city's anniversary): local holiday calendars
  such as proximoferiado.net/feriados/ms/campo-grande. They are set by municipal law, not by that decree.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

# Policy 2, by weekday (Monday = 0). Sunday is missing: closed. The prompt is built from this table, and a test checks
# it against data/policies.md, so hours live in one place.
OPENING_HOURS = {
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(9), time(13)),
}

FIXED_HOLIDAYS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (6, 13): "Santo Antônio, padroeiro de Campo Grande",
    (8, 26): "Aniversário de Campo Grande",
    (9, 7): "Independência do Brasil",
    (10, 11): "Criação do Estado de Mato Grosso do Sul",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}


def easter_sunday(year: int) -> date:
    """Gregorian Easter date (Meeus/Jones/Butcher algorithm). Needed because Good Friday moves every year."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holiday_name(day: date) -> Optional[str]:
    """Name of the holiday on this day, or None if it's not a holiday."""
    if day == easter_sunday(day.year) - timedelta(days=2):
        return "Paixão de Cristo (Sexta-feira Santa)"
    return FIXED_HOLIDAYS.get((day.month, day.day))


def hours_on(day: date) -> Optional[tuple]:
    """(opening, closing) times on this day, or None if the store is closed (Sunday or holiday)."""
    if holiday_name(day):
        return None
    return OPENING_HOURS.get(day.weekday())


def is_open(moment: datetime) -> bool:
    hours = hours_on(moment.date())
    return hours is not None and hours[0] <= moment.time() < hours[1]


def next_opening(moment: datetime) -> datetime:
    """When the store (and its human team) is next open after `moment`. Only meaningful while it is closed.

    Computed in code because "when is the team back?" on a Saturday afternoon or the day before a holiday is the kind
    of date arithmetic LLMs get wrong.
    """
    for offset in range(15):  # a long run of closed days never exceeds a few days; 15 is a safe bound
        day = moment.date() + timedelta(days=offset)
        hours = hours_on(day)
        if hours is None:
            continue
        opening = datetime.combine(day, hours[0], tzinfo=moment.tzinfo)
        if opening > moment:
            return opening
    raise ValueError(f"No opening found in the 15 days after {moment}")


def upcoming_holidays(start: date, days: int = 14) -> list:
    """Holidays from `start` (inclusive) over the next `days` days, as (date, name) pairs."""
    result = []
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        name = holiday_name(day)
        if name:
            result.append((day, name))
    return result
