import pandas as pd
import pytest

from src.data_loader import digits_only, load_store_data, normalize_text


@pytest.fixture(scope="module")
def store():
    # Loaded once for every test in this file (like beforeAll in Jest)
    return load_store_data()


def test_normalize_text_removes_accents_and_case():
    assert normalize_text("  Violão Eletroacústico ") == "violao eletroacustico"


def test_digits_only():
    assert digits_only("(67) 99812-3456") == "67998123456"


def test_row_counts(store):
    assert len(store.products) == 65
    assert len(store.categories) == 9
    assert len(store.customers) == 50
    assert len(store.orders) == 20
    assert len(store.order_items) == 22
    assert len(store.promotions) == 25


def test_specs_are_parsed_into_dicts(store):
    takamine = store.products.set_index("product_id").loc[95]
    assert takamine["specs"]["top"] == "Cedro Sólido"


def test_products_have_category_name_and_search_text(store):
    takamine = store.products.set_index("product_id").loc[95]
    assert takamine["category_name"] == "Violões"
    assert "takamine gd20" in takamine["search_text"]
    assert "violoes" in takamine["search_text"]


def test_customer_identity_columns(store):
    lucas = store.customers.set_index("customer_id").loc[1]
    assert lucas["phone_digits"] == "67998123456"
    assert lucas["email_normalized"] == "lucas.mendes@jmail.com"


def test_orders_dates_and_empty_values(store):
    orders = store.orders.set_index("order_id")
    assert orders.loc[1, "estimated_delivery"] == pd.Timestamp("2025-10-25")
    # Order 9 is only confirmed: no tracking code or delivery estimate yet
    assert orders.loc[9, "tracking_code"] is None
    assert pd.isna(orders.loc[9, "estimated_delivery"])


def test_active_promotions(store):
    active = store.promotions[store.promotions["is_active"]]
    assert sorted(active["product_id"]) == [90, 94, 121, 127]
