from pathlib import Path

import pytest

from src.tools import (
    FREE_LOCAL_DELIVERY_FROM, LOCAL_DELIVERY_CITIES, LOCAL_DELIVERY_FEE, OTHER_CITIES_OPTIONS, format_brl,
    get_delivery_info,
)

POLICIES_FILE = Path(__file__).resolve().parent.parent / "data" / "policies.md"


def test_delivery_rules_in_code_match_the_policy():
    # get_delivery_info answers from constants in src/tools.py; get_policy shows data/policies.md (itself checked
    # against the PDF). If either changes alone, this fails.
    section = POLICIES_FILE.read_text(encoding="utf-8").split("## frete_e_entregas")[1].split("\n## ")[0]
    assert f"pedidos acima de {format_brl(FREE_LOCAL_DELIVERY_FROM)}" in section
    assert f"taxa fixa de {format_brl(LOCAL_DELIVERY_FEE)}" in section
    assert "1 a 3 dias úteis" in section
    for option in OTHER_CITIES_OPTIONS:
        assert f"| {option['service']} | {option['delivery_time']} |" in section
    for city in LOCAL_DELIVERY_CITIES:
        assert city in section


@pytest.mark.parametrize("city", ["Campo Grande", "campo grande/MS", "Campo Grande - MS", "SIDROLANDIA", "Terenos"])
def test_cities_of_the_campo_grande_region_get_local_delivery(city):
    result = get_delivery_info(city)
    assert result["region"] == "regiao_de_campo_grande"
    assert result["delivery_time"] == "1 a 3 dias úteis"


@pytest.mark.parametrize("total, fee", [(2199.0, 0.0), (500.0, 0.0), (499.99, 35.0), (159.9, 35.0)])
def test_local_fee_is_free_from_500(total, fee):
    assert get_delivery_info("Campo Grande", order_total_brl=total)["fee_brl"] == fee


def test_local_fee_unknown_without_total():
    assert get_delivery_info("Campo Grande")["fee_brl"] is None


@pytest.mark.parametrize("city", ["Dourados", "Três Lagoas", "São Paulo"])
def test_other_cities_get_carrier_options_and_no_price(city):
    result = get_delivery_info(city, order_total_brl=2199.0)  # even above R$ 500: no free shipping outside the region
    assert result["region"] == "outras_cidades"
    assert result["fee_brl"] is None
    assert [option["service"] for option in result["options"]] == ["PAC (Correios)", "SEDEX (Correios)", "Jadlog (.package)"]
