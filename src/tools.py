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

# Policy 3.1, credit card without interest: (up to N installments, minimum installment in R$).
# "Até 3x: sem valor mínimo de parcela (exceto abaixo de R$ 50,00)" is read as a R$ 50 minimum installment
# (see README, Assumptions). 1x is always allowed.
INSTALLMENT_RULES = [(3, 50.0), (6, 80.0), (12, 100.0)]

# The store's local time (UTC-4). Opening hours and deadlines follow it, not the machine's clock.
STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")

# Deadlines from the policy manual (sections 4.1, 4.2, 4.3 and 8.1), in calendar days
RETURN_WINDOW_DAYS = 7       # from receipt
PREFERENCE_EXCHANGE_DAYS = 7  # from receipt (the manual says only "em até 7 dias"; see README, Assumptions)
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


def credit_card_installments(amount: float) -> dict:
    """Most interest-free installments allowed for this amount (policy 3.1) and the value of each one.

    Computed in code because "how many times can I split R$ 349,90?" needs the per-range minimums, the kind of
    arithmetic an LLM gets wrong.
    """
    best = 1
    for count in range(2, 13):
        minimum = next(min_value for max_count, min_value in INSTALLMENT_RULES if count <= max_count)
        if amount / count >= minimum:
            best = count
    return {"max_installments": best, "installment_brl": round(amount / best, 2)}


def format_brl(value: float) -> str:
    """1234.5 -> 'R$ 1.234,50'. The model once read 429.9 as 'R$ 429,00', so prices also go out as ready text."""
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _price_display(pricing: dict) -> str:
    """One line with every price the customer may need, formatted exactly as the agent should write it."""
    card = pricing["credit_card"]
    parts = []
    if pricing["promotion"]:
        parts.append(f"de {format_brl(pricing['list_price_brl'])} por {format_brl(pricing['final_price_brl'])} "
                     f"({pricing['promotion']['discount_percent']}% off, {pricing['promotion']['description']})")
    else:
        parts.append(f"{format_brl(pricing['final_price_brl'])} | PIX {format_brl(pricing['pix_price_brl'])}")
    if card["max_installments"] > 1:
        parts.append(f"até {card['max_installments']}x de {format_brl(card['installment_brl'])} sem juros")
    return " | ".join(parts)


def _pricing(product: pd.Series) -> dict:
    """List price, promotional price (if any), PIX price and credit card installments, following policies 3 and 6.2."""
    list_price = float(product["price_brl"])
    promotion = _active_promotion(int(product["product_id"]))
    if promotion:
        promo_price = round(list_price * (1 - promotion["discount_percent"] / 100), 2)
        pricing = {
            "list_price_brl": list_price,
            "promotion": promotion,
            "final_price_brl": promo_price,
            "pix_price_brl": None,  # PIX discount does not apply on promotional prices
            "credit_card": credit_card_installments(promo_price),
        }
    else:
        pricing = {
            "list_price_brl": list_price,
            "promotion": None,
            "final_price_brl": list_price,
            "pix_price_brl": round(list_price * (1 - PIX_DISCOUNT), 2),
            "credit_card": credit_card_installments(list_price),
        }
    pricing["price_display"] = _price_display(pricing)
    return pricing


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
            "_row": product,
        })

    results.sort(key=lambda item: item["final_price_brl"])
    if not results:
        return {"found": False, "message": "Nenhum produto encontrado com esses critérios."}
    shown = results[:limit]
    # A specific unavailable product (1-2 results, e.g. a model the customer named) comes with alternatives, so the
    # model never has to invent them. Broad searches already list what is available.
    for item in shown:
        row = item.pop("_row")
        if len(shown) <= 2 and item["availability"] != "disponivel":
            item["availability_note"] = UNAVAILABLE_NOTES[item["availability"]]
            item["available_alternatives"] = _available_alternatives(row)
    return {
        "found": True,
        "total": len(results),
        "showing": len(shown),
        # Explicit flag: without it the model once presented 10 of 12 results as the complete list
        "more_available": len(results) > len(shown),
        "products": shown,
    }


# Next to the alternatives, so the model reads what the label means for the customer where it uses the data.
# In one run it gave the price of a "coming soon" product and only offered alternatives, with the rule only in the
# prompt.
_SHOW_ALTERNATIVES = "Mostre ao cliente as opções de available_alternatives (nome e price_display)."
UNAVAILABLE_NOTES = {
    "esgotado": "Esgotado: temporariamente indisponível. " + _SHOW_ALTERNATIVES,
    "descontinuado": "Descontinuado: saiu do catálogo. " + _SHOW_ALTERNATIVES,
    "em breve": "Em breve: ainda não está à venda, não ofereça o preço como compra possível. " + _SHOW_ALTERNATIVES,
}


def _similarity_key(product: pd.Series, candidate: pd.Series) -> tuple:
    """Sort key for alternatives: same string type and same number of strings first, then the closest price."""
    def strings(item):
        return item["specs"].get("strings") if isinstance(item["specs"], dict) else None

    def seven_strings(item):
        return "7 cordas" in normalize_text(item["name"])

    return (
        strings(candidate) != strings(product),
        seven_strings(candidate) != seven_strings(product),
        abs(float(candidate["price_brl"]) - float(product["price_brl"])),
    )


def _available_alternatives(product: pd.Series, limit: int = 3) -> list:
    """Available products of the same category, most similar first (policy 7.3: suggest alternatives).

    Computed in code: when the model was told to look for alternatives itself, it listed products and prices that
    don't exist in the catalog instead of searching again.
    """
    products = _store().products
    candidates = products[(products["category_id"] == product["category_id"])
                          & (products["product_id"] != product["product_id"])]
    candidates = [row for _, row in candidates.iterrows() if _availability(row) == "disponivel"]
    candidates.sort(key=lambda row: _similarity_key(product, row))
    return [{"product_id": int(row["product_id"]), "name": row["name"], **_pricing(row)} for row in candidates[:limit]]


def get_product_details(product_id: int) -> dict:
    """Full details of one product: description, specs, stock, availability and prices."""
    products = _store().products
    match = products[products["product_id"] == product_id]
    if match.empty:
        return {"found": False, "message": f"Produto {product_id} não encontrado no catálogo."}

    product = match.iloc[0]
    availability = _availability(product)
    details = {
        "found": True,
        "product_id": int(product["product_id"]),
        "name": product["name"],
        "category": product["category_name"],
        "description": product["description"],
        "specs": product["specs"],
        "stock_quantity": int(product["stock_quantity"]),
        "availability": availability,
        **_pricing(product),
    }
    if availability != "disponivel":
        details["availability_note"] = UNAVAILABLE_NOTES[availability]
        details["available_alternatives"] = _available_alternatives(product)
    return details


def now() -> datetime:
    """Current date and time at the store (Campo Grande), whatever the time zone of the machine running the agent.

    STORE_TODAY overrides it, see docs/decisions.md: YYYY-MM-DD replaces only the date (keeps the real time);
    YYYY-MM-DDTHH:MM replaces date and time (used by the evaluation to simulate e.g. a Saturday afternoon).
    """
    current = datetime.now(STORE_TIMEZONE)
    override = os.getenv("STORE_TODAY")
    if override and "T" in override:
        current = datetime.fromisoformat(override).replace(tzinfo=STORE_TIMEZONE)
    elif override:
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
        "preference_exchange_7_days_from_receipt": _deadline(receipt_date, PREFERENCE_EXCHANGE_DAYS),
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


# Policy 5.1 local delivery. Campo Grande has no metropolitan region set by law, so the "região metropolitana" of the
# manual is read as IBGE's Região Geográfica Imediata de Campo Grande (see README, Assumptions).
LOCAL_DELIVERY_CITIES = [
    "Bandeirantes", "Camapuã", "Campo Grande", "Corguinho", "Dois Irmãos do Buriti", "Jaraguari",
    "Nova Alvorada do Sul", "Ribas do Rio Pardo", "Rio Negro", "Rochedo", "São Gabriel do Oeste", "Sidrolândia",
    "Terenos",
]
FREE_LOCAL_DELIVERY_FROM = 500.0  # "frete grátis para pedidos acima de R$ 500,00": R$ 500,00 itself is free (decided)
LOCAL_DELIVERY_FEE = 35.0

OTHER_CITIES_OPTIONS = [
    {"service": "PAC (Correios)", "delivery_time": "5 a 12 dias úteis"},
    {"service": "SEDEX (Correios)", "delivery_time": "2 a 5 dias úteis"},
    {"service": "Jadlog (.package)", "delivery_time": "3 a 8 dias úteis"},
]


def get_delivery_info(city: str, order_total_brl: Optional[float] = None) -> dict:
    """Delivery rules for the customer's city (policy 5): local fee computed here, other cities have no fixed price.

    `order_total_brl` is the final price of what the customer wants to buy (with promotion, if any).
    """
    by_normalized_name = {normalize_text(name): name for name in LOCAL_DELIVERY_CITIES}
    local_city = by_normalized_name.get(normalize_text(city.split("/")[0].split("-")[0]))
    if local_city:
        result = {
            "city": local_city,
            "region": "regiao_de_campo_grande",
            "carrier": "motoboy próprio (o cliente é contactado por telefone antes da entrega)",
            "delivery_time": "1 a 3 dias úteis",
            "rule": "frete grátis a partir de R$ 500,00; abaixo disso, taxa fixa de R$ 35,00",
            "fee_brl": None,
        }
        if order_total_brl is not None:
            result["fee_brl"] = 0.0 if order_total_brl >= FREE_LOCAL_DELIVERY_FROM else LOCAL_DELIVERY_FEE
        return result
    return {
        "city": city,
        "region": "outras_cidades",
        "options": OTHER_CITIES_OPTIONS,
        "fee_brl": None,
        "fee_note": ("Valor calculado pelo CEP de destino, peso e dimensões do produto; não há valor fixo nem frete "
                     "grátis. A equipe informa o valor. Baterias acústicas, pianos digitais e contrabaixos podem "
                     "exigir cotação individual."),
        "insurance": "todos os envios têm rastreamento e seguro contra extravio e danos",
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
