"""Guards the hand transcription of the policy manual: every key number or contact in the original PDF must appear,
written the same way, in data/policies.md. If the manual changes and the transcription doesn't, this test fails.
"""
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

DATA = Path(__file__).resolve().parent.parent / "data"

KEY_FACTS = [
    # store data
    "Rua 14 de Maio, 3200", "79202-333", "(67) 3341-4444", "(67) 3321-4500", "12.345.678/0001-90",
    # opening hours
    "09:00 às 18:00", "09:00 às 13:00",
    # payment and installments
    "5% de desconto", "Até 12x sem juros", "R$ 50,00", "R$ 80,00", "R$ 100,00", "R$ 2.000,00", "3 dias úteis",
    # returns, exchanges, warranty
    "7 (sete) dias corridos", "30 (trinta) dias corridos", "10 dias úteis", "90 (noventa) dias", "6 meses a 2 anos",
    # shipping
    "R$ 500,00", "R$ 35,00", "1 a 3 dias úteis", "5 a 12 dias úteis", "2 a 5 dias úteis", "3 a 8 dias úteis",
    # service
    "24 horas úteis",
]


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text)


PDF_TEXT = _one_line(" ".join(page.extract_text() for page in PdfReader(DATA / "politicas_da_loja.pdf").pages))
POLICIES_TEXT = _one_line((DATA / "policies.md").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fact", KEY_FACTS)
def test_key_fact_is_in_pdf_and_in_transcription(fact):
    assert fact in PDF_TEXT, "fact list is out of date with the PDF"
    assert fact in POLICIES_TEXT, "data/policies.md differs from the original manual"
