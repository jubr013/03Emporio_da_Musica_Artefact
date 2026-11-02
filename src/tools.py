"""Data tools the agent can call. Each returns a plain dict (JSON-friendly) and the LLM writes the answer.

Tools never invent data: when nothing matches they say so explicitly.
"""
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from src.data_loader import (
    SEARCH_STOPWORDS, StoreData, digits_only, load_store_data, normalize_text, search_form,
)

PIX_DISCOUNT = 0.05  # policy 3: 5% off the list price, not applied on top of promotions

# The store's local time (UTC-4). Opening hours and deadlines follow it, not the machine's clock.
STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")

# Deadlines from the policy manual (sections 4.1, 4.2 and 8.1), in calendar days
RETURN_WINDOW_DAYS = 7       # from receipt
DEFECT_EXCHANGE_DAYS = 30    # from purchase
LEGAL_WARRANTY_DAYS = 90     # from receipt

STATUS_LABELS = {
    "pending": "pendente (aguardando pagamento/processamento)",
    "confirmed": "confirmado (em preparação, ainda não enviado)",
    "shipped": "enviado (em transporte)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


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


# Spelled-out numbers -> digits, as product names use digits ("7 Cordas")
NUMBER_WORDS = {"quatro": "4", "cinco": "5", "seis": "6", "sete": "7", "doze": "12"}


def _query_words(query: str) -> list:
    words = [NUMBER_WORDS.get(word, word) for word in search_form(query).split()]
    return [word for word in words if word not in SEARCH_STOPWORDS]


def _word_prefix_pattern(word: str) -> str:
    """Regex that matches `word` at the START of a word: 'baixo' matches 'baixos', but 'aco' doesn't match 'braco'."""
    return r"\b" + re.escape(word)


def search_products(
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    only_available: bool = False,
    limit: int = 10,
) -> dict:
    """Searches the catalog. Every meaningful word in `query` must appear in the product's search text
    (name, category, description and keywords from the specs).

    Price filters use the final price (with an active promotion applied), which is what the customer pays.
    """
    products = _store().products.copy()

    if query:
        for word in _query_words(query):
            products = products[products["search_text"].str.contains(_word_prefix_pattern(word), regex=True)]
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
    shown = results[:limit]
    return {
        "found": True,
        "total": len(results),
        "showing": len(shown),
        # Explicit flag: without it the model once presented 10 of 12 results as the complete list
        "more_available": len(results) > len(shown),
        "products": shown,
    }


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


def now() -> datetime:
    """Current date and time at the store (Campo Grande), whatever the time zone of the machine running the agent.

    STORE_TODAY (YYYY-MM-DD) overrides only the date, see docs/decisions.md.
    """
    current = datetime.now(STORE_TIMEZONE)
    override = os.getenv("STORE_TODAY")
    if override:
        current = datetime.combine(date.fromisoformat(override), current.timetz())
    return current


def today() -> date:
    """Current date for deadline checks (store time zone, STORE_TODAY override)."""
    return now().date()


def _identity_matches(customer: pd.Series, email: Optional[str], phone: Optional[str]) -> bool:
    """True if the e-mail or the phone given by the person belongs to the order's customer."""
    if email and normalize_text(email) == customer["email_normalized"]:
        return True
    if phone:
        given = digits_only(phone)
        # Accept the number with or without the area code (67), but not tiny fragments
        if len(given) >= 8 and customer["phone_digits"].endswith(given):
            return True
    return False


def _deadline(start: date, days: int) -> dict:
    deadline = start + timedelta(days=days)
    days_left = (deadline - today()).days
    return {
        "starts_on": start.isoformat(),  # explicit start date: without it the model once mixed it up with the deadline
        "deadline": deadline.isoformat(),
        "within_deadline": days_left >= 0,
        "days_left": max(days_left, 0),
    }


def _deadlines(order: pd.Series, received_on: Optional[str]) -> dict:
    """Return / exchange / warranty deadlines for a delivered order (rules in docs/decisions.md)."""
    order_date = order["order_date"].date()
    estimated = order["estimated_delivery"].date()
    receipt_date, source, needs_staff, warnings = estimated, "estimated", False, []

    if received_on:
        try:
            informed = date.fromisoformat(received_on)
        except ValueError:
            informed = None
            warnings.append(f"Data informada '{received_on}' inválida; usando a previsão de entrega.")
        if informed and not (order_date <= informed <= today()):
            warnings.append("Data informada fora do intervalo entre a compra e hoje; usando a previsão de entrega.")
        elif informed:
            receipt_date, source = informed, "customer"
            # A later date extends the deadline in the customer's favour -> the team confirms it
            needs_staff = informed > estimated

    return {
        "today": today().isoformat(),
        "receipt_date": receipt_date.isoformat(),
        "receipt_date_source": source,
        "requires_staff_confirmation": needs_staff,
        "warnings": warnings,
        "return_window_7_days_from_receipt": _deadline(receipt_date, RETURN_WINDOW_DAYS),
        "defect_exchange_30_days_from_purchase": _deadline(order_date, DEFECT_EXCHANGE_DAYS),
        "legal_warranty_90_days_from_receipt": _deadline(receipt_date, LEGAL_WARRANTY_DAYS),
    }


def get_order_status(
    order_id: int,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    received_on: Optional[str] = None,
) -> dict:
    """Order status for a verified customer (order number + e-mail or phone of whoever placed it).

    For delivered orders it also computes return, exchange and warranty deadlines.
    `received_on` (YYYY-MM-DD) is the receipt date confirmed by the customer, if different from the estimate.
    """
    if not email and not phone:
        return {"verified": False, "message": "Para consultar o pedido, peça o e-mail ou o telefone usado na compra."}

    store = _store()
    match = store.orders[store.orders["order_id"] == order_id]
    customer = None
    if not match.empty:
        customer = store.customers.set_index("customer_id").loc[match.iloc[0]["customer_id"]]
    # Same message for "order doesn't exist" and "identity doesn't match": don't reveal which order numbers exist
    if customer is None or not _identity_matches(customer, email, phone):
        return {"verified": False, "message": "Não encontrei um pedido com esse número e esses dados de contato."}

    order = match.iloc[0]
    items = store.order_items[store.order_items["order_id"] == order_id].merge(
        store.products[["product_id", "name"]], on="product_id", how="left"
    )
    has_delivery_estimate = pd.notna(order["estimated_delivery"])

    return {
        "verified": True,
        "order_id": int(order["order_id"]),
        "customer_first_name": customer["name"].split()[0],
        "status": order["status"],
        "status_label": STATUS_LABELS.get(order["status"], order["status"]),
        "order_date": order["order_date"].date().isoformat(),
        "total_brl": float(order["total_brl"]),
        "payment_method": order["payment_method"],
        "items": [{"name": row["name"], "quantity": int(row["quantity"])} for _, row in items.iterrows()],
        "tracking_code": order["tracking_code"],
        "estimated_delivery": order["estimated_delivery"].date().isoformat() if has_delivery_estimate else None,
        "notes": order["notes"],
        "deadlines": _deadlines(order, received_on) if order["status"] == "delivered" else None,
    }


TICKETS_FILE = Path(__file__).resolve().parent.parent / "history" / "tickets.jsonl"
TICKET_TYPES = ["devolucao", "troca", "garantia", "reclamacao", "outro"]


def create_support_ticket(
    request_type: str,
    summary: str,
    order_id: Optional[int] = None,
    customer_contact: Optional[str] = None,
) -> dict:
    """Registers a request for the human team (policy 7.3: register and forward, reply within 24 business hours).

    In this prototype the "team inbox" is a JSON Lines file (one JSON object per line) in history/.
    """
    if request_type not in TICKET_TYPES:
        return {"created": False, "message": f"Tipo inválido. Use um destes: {', '.join(TICKET_TYPES)}."}

    ticket = {
        "protocol": f"EM{today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        "created_at": now().isoformat(timespec="seconds"),
        "request_type": request_type,
        "order_id": order_id,
        "customer_contact": customer_contact,
        "summary": summary,
    }
    TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TICKETS_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(ticket, ensure_ascii=False) + "\n")
    return {"created": True, "protocol": ticket["protocol"], "response_time": "até 24 horas úteis"}
