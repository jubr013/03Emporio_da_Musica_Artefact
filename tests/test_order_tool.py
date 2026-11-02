import pytest

from src.tools import get_order_status

NOT_FOUND = "Não encontrei um pedido com esse número e esses dados de contato."

# Order 7: customer 14 (Letícia), ordered 2026-02-03, estimated delivery 2026-02-17
LETICIA = {"email": "leticia.rocha@jmail.com", "phone": "(67) 99789-0123"}
# Order 6: customer 9 (Gabriel), ordered 2026-01-18, estimated delivery 2026-02-01
GABRIEL_EMAIL = "gabriel.araujo@jmail.com"


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    # Same "today" as the example conversations (docs/decisions.md)
    monkeypatch.setenv("STORE_TODAY", "2026-02-20")


def test_requires_email_or_phone():
    result = get_order_status(7)
    assert result["verified"] is False


def test_wrong_contact_and_unknown_order_get_the_same_answer():
    assert get_order_status(7, email="someone@else.com")["message"] == NOT_FOUND
    assert get_order_status(999, email=LETICIA["email"])["message"] == NOT_FOUND


def test_verifies_by_email_ignoring_case():
    result = get_order_status(7, email="LETICIA.Rocha@jmail.com")
    assert result["verified"]
    assert result["customer_first_name"] == "Letícia"
    assert result["items"] == [{"name": "Shelby SU-21S Soprano Sunburst", "quantity": 1}]


@pytest.mark.parametrize("phone", ["(67) 99789-0123", "67997890123", "99789-0123"])
def test_verifies_by_phone_in_any_format(phone):
    assert get_order_status(7, phone=phone)["verified"]


def test_delivered_inside_return_window():
    deadlines = get_order_status(7, email=LETICIA["email"])["deadlines"]
    assert deadlines["receipt_date"] == "2026-02-17"
    assert deadlines["receipt_date_source"] == "estimated"
    assert deadlines["return_window_7_days_from_receipt"] == {
        "starts_on": "2026-02-17", "deadline": "2026-02-24", "within_deadline": True, "days_left": 4,
    }
    assert deadlines["defect_exchange_30_days_from_purchase"]["starts_on"] == "2026-02-03"
    assert deadlines["defect_exchange_30_days_from_purchase"]["deadline"] == "2026-03-05"


def test_delivered_outside_return_window_but_under_warranty():
    deadlines = get_order_status(6, email=GABRIEL_EMAIL)["deadlines"]
    assert deadlines["return_window_7_days_from_receipt"]["within_deadline"] is False
    assert deadlines["defect_exchange_30_days_from_purchase"]["within_deadline"] is False
    assert deadlines["legal_warranty_90_days_from_receipt"]["within_deadline"] is True


def test_later_receipt_date_from_customer_needs_staff_confirmation():
    deadlines = get_order_status(7, email=LETICIA["email"], received_on="2026-02-19")["deadlines"]
    assert deadlines["receipt_date_source"] == "customer"
    assert deadlines["requires_staff_confirmation"] is True
    assert deadlines["return_window_7_days_from_receipt"]["deadline"] == "2026-02-26"


def test_earlier_receipt_date_from_customer_is_accepted():
    deadlines = get_order_status(7, email=LETICIA["email"], received_on="2026-02-15")["deadlines"]
    assert deadlines["receipt_date"] == "2026-02-15"
    assert deadlines["requires_staff_confirmation"] is False


@pytest.mark.parametrize("received_on", ["2026-01-01", "2026-03-01", "17/02/2026"])
def test_invalid_receipt_dates_fall_back_to_estimate(received_on):
    deadlines = get_order_status(7, email=LETICIA["email"], received_on=received_on)["deadlines"]
    assert deadlines["receipt_date_source"] == "estimated"
    assert deadlines["warnings"]


def test_shipped_order_has_tracking_and_no_deadlines():
    # Order 8: customer 2 (Ana Carolina), shipped
    result = get_order_status(8, email="anacarol.ferreira@coldmail.com")
    assert result["tracking_code"] == "BRJL5544332BR"
    assert result["deadlines"] is None


def test_cancelled_order_shows_reason():
    # Order 17: customer 15 (Matheus), cancelled
    result = get_order_status(17, email="matheus.correia@hayoo.com.br")
    assert result["status"] == "cancelled"
    assert result["notes"] == "Pedido cancelado pelo cliente antes do processamento"
