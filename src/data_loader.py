"""Loads the store CSVs into pandas DataFrames and cleans them once, at startup.

The dataset is tiny (< 200 rows in total), so everything lives in memory.
Data quirks and the reasoning behind each cleaning step are in docs/data_exploration.md.
"""
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class StoreData:
    """All store tables, already cleaned. Similar to a typed object holding each table."""

    products: pd.DataFrame
    categories: pd.DataFrame
    customers: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    promotions: pd.DataFrame


def normalize_text(text: str) -> str:
    """Lowercase and strip accents, so 'Violão' matches 'violao' and 'VIOLÃO'."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.lower().strip()


def digits_only(text: str) -> str:
    """'(67) 99812-3456' -> '67998123456'. Used to compare phone numbers."""
    return re.sub(r"\D", "", str(text))


def _load_products(data_dir: Path, categories: pd.DataFrame) -> pd.DataFrame:
    products = pd.read_csv(data_dir / "products.csv")

    # specs is a JSON string in every row; parse it once into a dict
    products["specs"] = products["specs"].apply(json.loads)
    products["created_at"] = pd.to_datetime(products["created_at"])

    # Attach the category name so tools don't need to join every time
    category_names = categories.set_index("category_id")["name"]
    products["category_name"] = products["category_id"].map(category_names)

    # Accent-free text used for keyword search (name + category + description)
    products["search_text"] = (
        products["name"] + " " + products["category_name"] + " " + products["description"]
    ).apply(normalize_text)

    return products.sort_values("product_id").reset_index(drop=True)


def _load_customers(data_dir: Path) -> pd.DataFrame:
    customers = pd.read_csv(data_dir / "customers.csv")
    # Normalized columns for identity checks (emails are case-insensitive, phones vary in format)
    customers["email_normalized"] = customers["email"].str.strip().str.lower()
    customers["phone_digits"] = customers["phone"].apply(digits_only)
    return customers


def _load_orders(data_dir: Path) -> pd.DataFrame:
    orders = pd.read_csv(data_dir / "orders.csv")
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    # Empty for orders that were not shipped yet -> becomes NaT ("not a time", like null)
    orders["estimated_delivery"] = pd.to_datetime(orders["estimated_delivery"])
    # Replace NaN with None in text columns so tools return clean JSON-friendly values
    for column in ["tracking_code", "notes"]:
        orders[column] = orders[column].astype(object).where(orders[column].notna(), None)
    return orders


def _load_promotions(data_dir: Path) -> pd.DataFrame:
    promotions = pd.read_csv(data_dir / "promotions.csv")
    promotions["is_active"] = promotions["is_active"].astype(bool)
    return promotions


def load_store_data(data_dir: Path = DEFAULT_DATA_DIR) -> StoreData:
    """Reads every CSV in data_dir and returns the cleaned tables."""
    categories = pd.read_csv(data_dir / "categories.csv")
    return StoreData(
        products=_load_products(data_dir, categories),
        categories=categories,
        customers=_load_customers(data_dir),
        orders=_load_orders(data_dir),
        order_items=pd.read_csv(data_dir / "order_items.csv"),
        promotions=_load_promotions(data_dir),
    )
