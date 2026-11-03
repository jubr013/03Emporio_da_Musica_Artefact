import pytest

from src.tools import credit_card_installments, format_brl, get_product_details, search_products

VIOLOES = 5


def test_search_by_name_ignores_accents_and_case():
    result = search_products(query="TAKAMINE gd20")
    assert result["found"]
    assert [p["product_id"] for p in result["products"]] == [95]


def test_search_violoes_up_to_1000_only_available():
    result = search_products(category_id=VIOLOES, max_price=1000, only_available=True, limit=50)
    prices = [p["final_price_brl"] for p in result["products"]]
    assert all(price <= 1000 for price in prices)
    assert prices == sorted(prices)  # cheapest first
    ids = [p["product_id"] for p in result["products"]]
    assert 96 not in ids   # out of stock
    assert 113 not in ids  # discontinued


def test_search_finds_steel_strings_from_specs():
    # Takamine GD20 (95) has steel strings but never says "aço" in its name or description
    ids = [p["product_id"] for p in search_products(query="violão de aço", limit=100)["products"]]
    assert 95 in ids
    assert len(ids) == 19  # every steel-string acoustic guitar


def test_search_finds_electro_acoustic_from_specs():
    result = search_products(query="violão eletroacústico", limit=100)
    assert result["total"] == 14  # every acoustic guitar with electronics == "yes"


def test_search_understands_spelled_out_numbers():
    assert search_products(query="violão sete cordas", limit=100)["total"] == 5


def test_search_matches_word_starts_only():
    # "aço" must not match "braço" (both become "aco"/"braco" without accents): no nylon guitar should appear
    results = search_products(query="violão cordas de aço", category_id=VIOLOES, limit=100)["products"]
    assert len(results) == 19
    assert not any("Nylon" in p["name"] for p in results)


@pytest.mark.parametrize("query, product_id", [
    ("Takamine GD 20", 95), ("takamine gd-20", 95), ("Takamine GD20", 95),
    ("Tagima AC39", 83), ("tagima memphis ac 39", 83),
    ("yamaha c 40", 81), ("Martin D28", 93),
])
def test_search_matches_model_codes_written_differently(query, product_id):
    ids = [p["product_id"] for p in search_products(query=query, limit=100)["products"]]
    assert product_id in ids


def test_search_does_not_glue_long_words_to_numbers():
    # "violão 7 cordas" must keep working: only short letter groups are glued to numbers
    assert search_products(query="violão 7 cordas", limit=100)["total"] == 5


def test_search_says_when_more_results_exist():
    result = search_products(category_id=VIOLOES, max_price=1000, only_available=True)  # default limit = 10
    assert (result["total"], result["showing"], result["more_available"]) == (12, 10, True)


def test_search_without_results_says_so():
    result = search_products(query="pedal de distorção")
    assert result == {"found": False, "message": "Nenhum produto encontrado com esses critérios."}


def test_details_with_expired_promotion_uses_list_price_and_pix():
    # Takamine GD20 only has an inactive 12% promotion
    details = get_product_details(95)
    assert details["promotion"] is None
    assert details["final_price_brl"] == 2199.0
    assert details["pix_price_brl"] == 2089.05


def test_details_with_active_promotion_has_no_pix_discount():
    # Ohana CK-20 (121) has an active 20% promotion
    details = get_product_details(121)
    assert details["promotion"] == {"description": "Desconto Exclusivo", "discount_percent": 20}
    assert details["final_price_brl"] == 439.2
    assert details["pix_price_brl"] is None


@pytest.mark.parametrize("amount, expected", [
    (2199.0, 12),   # R$ 183,25 each: well above R$ 100
    (1200.0, 12),   # exactly R$ 100,00 each
    (1199.0, 11),   # 12x would be R$ 99,92
    (700.0, 7),     # 7x is the first range with a R$ 100 minimum
    (699.0, 6),     # 7x would be R$ 99,86; 6x = R$ 116,50
    (441.0, 5),     # 6x would be R$ 73,50 < R$ 80
    (320.0, 4),     # exactly R$ 80,00 each
    (159.9, 3),     # cheapest product: R$ 53,30 each (R$ 50 minimum up to 3x)
    (120.0, 2),     # 3x would be R$ 40 < R$ 50
    (40.0, 1),      # below R$ 50: no installments
])
def test_credit_card_installments_follow_policy_ranges(amount, expected):
    assert credit_card_installments(amount)["max_installments"] == expected


def test_installment_value_is_rounded_to_cents():
    assert credit_card_installments(2199.0) == {"max_installments": 12, "installment_brl": 183.25}


def test_installments_use_the_promotional_price():
    # Ohana CK-20 (121): R$ 439,20 with the promotion -> 5x of R$ 87,84 (6x would be R$ 73,20 < R$ 80)
    assert get_product_details(121)["credit_card"] == {"max_installments": 5, "installment_brl": 87.84}


def test_details_availability_labels():
    assert get_product_details(96)["availability"] == "esgotado"
    assert get_product_details(113)["availability"] == "descontinuado"
    assert get_product_details(130)["availability"] == "em breve"


@pytest.mark.parametrize("value, text", [(429.9, "R$ 429,90"), (2089.05, "R$ 2.089,05"), (35.0, "R$ 35,00")])
def test_format_brl(value, text):
    assert format_brl(value) == text


def test_price_display_without_promotion():
    # Tagima Memphis (83): the model once wrote its R$ 429,90 as R$ 429,00
    assert get_product_details(83)["price_display"] == "R$ 429,90 | PIX R$ 408,40 | até 5x de R$ 85,98 sem juros"


def test_price_display_with_promotion_has_original_price_and_percent():
    display = get_product_details(121)["price_display"]
    assert display == "de R$ 549,00 por R$ 439,20 (20% off, Desconto Exclusivo) | até 5x de R$ 87,84 sem juros"


def test_out_of_stock_product_comes_with_available_alternatives():
    # Giannini GF-3D (96, steel strings, R$ 799,90) is out of stock: steel-string guitars closest in price
    alternatives = get_product_details(96)["available_alternatives"]
    assert [item["product_id"] for item in alternatives] == [107, 86, 91]
    assert all(get_product_details(item["product_id"])["availability"] == "disponivel" for item in alternatives)


def test_discontinued_7_string_gets_7_string_alternatives():
    alternatives = get_product_details(113)["available_alternatives"]
    assert all("7 Cordas" in item["name"] for item in alternatives)


def test_available_product_has_no_alternatives_field():
    assert "available_alternatives" not in get_product_details(95)


def test_search_for_a_specific_unavailable_product_includes_alternatives():
    [product] = search_products(query="Giannini GF-3D")["products"]
    assert product["availability"] == "esgotado"
    assert len(product["available_alternatives"]) == 3


def test_broad_search_does_not_attach_alternatives():
    products = search_products(category_id=5, limit=50)["products"]
    assert all("available_alternatives" not in product for product in products)


def test_details_unknown_product():
    assert get_product_details(9999)["found"] is False
