from src.tools import get_product_details, search_products

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


def test_details_availability_labels():
    assert get_product_details(96)["availability"] == "esgotado"
    assert get_product_details(113)["availability"] == "descontinuado"
    assert get_product_details(130)["availability"] == "em breve"


def test_details_unknown_product():
    assert get_product_details(9999)["found"] is False
