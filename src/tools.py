"""Data tools the agent can call. Each returns a plain dict (JSON-friendly) and the LLM writes the answer.

Tools never invent data: when nothing matches they say so explicitly.
"""
from functools import lru_cache
from typing import Optional

import pandas as pd

from src.data_loader import StoreData, load_store_data, normalize_text

PIX_DISCOUNT = 0.05  # policy 3: 5% off the list price, not applied on top of promotions


@lru_cache(maxsize=1)
def _store() -> StoreData:
    """Loads the CSVs on first use and reuses them afterwards (a simple in-memory cache)."""
    return load_store_data()


def _availability(product: pd.Series) -> str:
    """Translates status + stock into one label the agent can explain to the customer."""
    if product["status"] == "discontinued":
        return "descontinuado"
    if product["status"] == "coming_soon":
        return "em breve"
    if product["stock_quantity"] <= 0:
        return "esgotado"
    return "disponivel"


def _active_promotion(product_id: int) -> Optional[dict]:
    """Returns the active promotion for a product, or None.

    Promotions are not cumulative (policy 6.2). If more than one were active,
    we keep the biggest discount. The current data has at most one active per product.
    """
    promos = _store().promotions
    active = promos[(promos["product_id"] == product_id) & promos["is_active"]]
    if active.empty:
        return None
    best = active.sort_values("discount_percent", ascending=False).iloc[0]
    return {"description": best["description"], "discount_percent": int(best["discount_percent"])}


def _pricing(product: pd.Series) -> dict:
    """List price, promotional price (if any) and PIX price, following policies 3 and 6.2."""
    list_price = float(product["price_brl"])
    promotion = _active_promotion(int(product["product_id"]))
    if promotion:
        promo_price = round(list_price * (1 - promotion["discount_percent"] / 100), 2)
        return {
            "list_price_brl": list_price,
            "promotion": promotion,
            "final_price_brl": promo_price,
            "pix_price_brl": None,  # PIX discount does not apply on promotional prices
        }
    return {
        "list_price_brl": list_price,
        "promotion": None,
        "final_price_brl": list_price,
        "pix_price_brl": round(list_price * (1 - PIX_DISCOUNT), 2),
    }


def search_products(
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    only_available: bool = False,
    limit: int = 10,
) -> dict:
    """Searches the catalog. Every word in `query` must appear in the product name, category or description.

    Price filters use the final price (with an active promotion applied), which is what the customer pays.
    """
    products = _store().products.copy()

    if query:
        for word in normalize_text(query).split():
            products = products[products["search_text"].str.contains(word, regex=False)]
    if category_id is not None:
        products = products[products["category_id"] == category_id]

    products["availability"] = products.apply(_availability, axis=1)
    if only_available:
        products = products[products["availability"] == "disponivel"]

    results = []
    for _, product in products.iterrows():
        pricing = _pricing(product)
        if max_price is not None and pricing["final_price_brl"] > max_price:
            continue
        if min_price is not None and pricing["final_price_brl"] < min_price:
            continue
        results.append({
            "product_id": int(product["product_id"]),
            "name": product["name"],
            "category": product["category_name"],
            "availability": product["availability"],
            **pricing,  # spreads the pricing dict into this one, like {...pricing} in JS
        })

    results.sort(key=lambda item: item["final_price_brl"])
    if not results:
        return {"found": False, "message": "Nenhum produto encontrado com esses critérios."}
    return {"found": True, "total": len(results), "products": results[:limit]}


def get_product_details(product_id: int) -> dict:
    """Full details of one product: description, specs, stock, availability and prices."""
    products = _store().products
    match = products[products["product_id"] == product_id]
    if match.empty:
        return {"found": False, "message": f"Produto {product_id} não encontrado no catálogo."}

    product = match.iloc[0]
    return {
        "found": True,
        "product_id": int(product["product_id"]),
        "name": product["name"],
        "category": product["category_name"],
        "description": product["description"],
        "specs": product["specs"],
        "stock_quantity": int(product["stock_quantity"]),
        "availability": _availability(product),
        **_pricing(product),
    }
