from src.policies import get_policy, list_policy_topics


def test_all_topics_are_loaded():
    assert list_policy_topics() == [
        "sobre_a_loja", "horarios", "pagamento", "trocas_e_devolucoes",
        "frete_e_entregas", "promocoes", "atendimento", "garantia", "privacidade", "lojas_parceiras",
    ]


def test_developer_comments_are_not_returned():
    assert "<!--" not in get_policy("lojas_parceiras")["content"]


def test_get_policy_returns_section_content():
    result = get_policy("trocas_e_devolucoes")
    assert result["found"]
    assert "7 (sete) dias corridos após o recebimento" in result["content"]
    assert "## " not in result["content"]  # no other section leaked in


def test_address_is_in_store_info():
    assert "Rua 14 de Maio, 3200" in get_policy("sobre_a_loja")["content"]


def test_unknown_topic_lists_valid_ones():
    result = get_policy("receitas")
    assert result["found"] is False
    assert "horarios" in result["valid_topics"]
