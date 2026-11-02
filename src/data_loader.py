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


# Words that carry no meaning in a product search ("violão DE aço ATÉ mil") and would only cut results.
# "corda(s)" is here too: customers say "cordas de aço", but product texts rarely contain the word.
SEARCH_STOPWORDS = {
    "de", "da", "do", "das", "dos", "com", "sem", "para", "pra", "e", "o", "a", "os", "as", "um", "uma", "ate", "em",
    "corda", "cordas",
}


def _join_model_code(match: re.Match) -> str:
    letters = match.group(1)
    return match.group(0) if letters in SEARCH_STOPWORDS else letters


def search_form(text: str) -> str:
    """Normalized text for keyword search, applied the same way to product texts and to queries:
    - no accents, lowercase;
    - '-ões' plurals -> '-ão' ('violões' -> 'violao'); regular '-s' plurals are handled by prefix matching;
    - model codes glued together, so 'GD 20', 'GD-20' and 'GD20' all become 'gd20' ('AC-39' -> 'ac39').
      Only short letter groups (up to 4) are glued, so 'violão 7 cordas' stays as it is.
    """
    text = re.sub(r"oes\b", "ao", normalize_text(text))
    text = re.sub(r"\b([a-z]+)-(?=\d)", r"\1", text)
    return re.sub(r"\b([a-z]{1,4})\s+(?=\d)", _join_model_code, text)


def digits_only(text: str) -> str:
    """'(67) 99812-3456' -> '67998123456'. Used to compare phone numbers."""
    return re.sub(r"\D", "", str(text))


def _spec_keywords(specs: dict) -> str:
    """Words a customer would search for that sometimes only exist in the specs, not in the name/description.

    E.g. 3 steel-string guitars never say "aço" in their text, and 2 with a pickup never say "eletroacústico".
    """
    words = []
    if specs.get("strings") == "steel":
        words.append("aco")
    elif specs.get("strings") == "nylon":
        words.append("nylon")
    if specs.get("electronics") == "yes":
        words.append("eletroacustico eletrico captacao")
    return " ".join(words)


def _load_products(data_dir: Path, categories: pd.DataFrame) -> pd.DataFrame:
    products = pd.read_csv(data_dir / "products.csv")

    # specs is a JSON string in every row; parse it once into a dict
    products["specs"] = products["specs"].apply(json.loads)
    products["created_at"] = pd.to_datetime(products["created_at"])

    # Attach the category name so tools don't need to join every time
    category_names = categories.set_index("category_id")["name"]
    products["category_name"] = products["category_id"].map(category_names)

    # Accent-free text used for keyword search (name + category + description + keywords from specs)
    products["search_text"] = (
        products["name"] + " " + products["category_name"] + " " + products["description"]
        + " " + products["specs"].apply(_spec_keywords)
    ).apply(search_form)

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
