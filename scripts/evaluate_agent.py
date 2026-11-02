"""Evaluates the agent against the real model with scripted scenarios.

For each scenario it checks:
- which tools were called (did the agent look up data / policies when it should, and not when it shouldn't?)
- key tool arguments (e.g. a price filter really applied)
- text that MUST appear in the answers (correct price, deadline...) or MUST NOT (invented prices, other people's data)

Run from the repo root (uses ~35 requests of the Gemini quota):
    python scripts/evaluate_agent.py
Writes a report to docs/evaluation.md and exits with code 1 if any scenario fails.
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.agent import Agent  # noqa: E402
from src.data_loader import normalize_text  # noqa: E402

PAUSE_SECONDS = 5  # free tier allows 15 requests/minute; one turn can use up to 3 requests
DEFAULT_TODAY = "2026-02-20"  # same date as the example conversations

# Each item in "contains" is a group of alternatives: at least one of them must appear (accents/case ignored).
SCENARIOS = [
    {
        "id": "price_lookup",
        "messages": ["Quanto custa o Takamine GD20?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["2.199", "2199"], ["2.089,05", "2089,05", "2.089.05"]],
    },
    {
        "id": "expired_promotion",
        "messages": ["O Takamine GD20 está com 12% de desconto, né? Quanto fica?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["2.199", "2199"]],
        "not_contains": ["1.935", "1935"],  # 12% off would be R$ 1.935,12: a discount that is not active
    },
    {
        "id": "catalog_price_filter",
        "messages": ["Quais violões disponíveis custando até R$1000?"],
        "tools_required": ["search_products"],
        "arg_check": ("search_products", "max_price <= 1000",
                      lambda args: args.get("max_price") is not None and args["max_price"] <= 1000),
        "contains": [["429,90", "429.90"]],  # cheapest acoustic guitar in stock
        "not_contains": ["GF-3D"],  # out of stock
    },
    {
        "id": "out_of_stock",
        "messages": ["Vocês têm o violão Giannini GF-3D Dreadnought?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["esgotado", "indisponivel", "sem estoque", "em falta"]],
    },
    {
        "id": "empty_category",
        "messages": ["Vocês vendem saxofone? Quanto custa?"],
        "tools_any": ["search_products"],
        "not_contains": ["R$"],  # no sax in the catalog: no price may be invented
    },
    {
        "id": "store_address",
        "messages": ["Qual o endereço da loja?"],
        "tools_required": ["get_policy"],
        "contains": [["14 de maio"]],
    },
    {
        "id": "installments_policy",
        "messages": ["Em quantas vezes posso parcelar no cartão?"],
        "tools_required": ["get_policy"],
        "contains": [["12x", "12 vezes"]],
    },
    {
        "id": "holiday_closed",
        "today": "2026-11-02",
        "messages": ["A loja está aberta hoje?"],
        "contains": [["feriado", "finados"], ["fechad"]],
    },
    {
        "id": "order_status_shipped",
        "messages": ["Qual o status do meu pedido 8? Meu e-mail é anacarol.ferreira@coldmail.com"],
        "tools_required": ["get_order_status"],
        "contains": [["BRJL5544332BR"]],
    },
    {
        "id": "privacy_wrong_contact",
        "messages": ["Quero saber do pedido 7, meu e-mail é joao@gmail.com"],
        "tools_required": ["get_order_status"],
        "not_contains": ["shelby", "leticia", "ukulele", "159"],  # nothing about someone else's order
    },
    {
        "id": "return_inside_window",
        "messages": ["Me arrependi da compra, posso devolver? Pedido 7, e-mail leticia.rocha@jmail.com"],
        "tools_required": ["get_order_status"],
        "contains": [["24/02", "24 de fevereiro"]],
    },
    {
        "id": "return_outside_window",
        "messages": ["Quero devolver por arrependimento, pedido 6, telefone (67) 98654-3210"],
        "tools_required": ["get_order_status"],
        "contains": [["08/02", "8/02", "8 de fevereiro", "encerr", "expir", "fora do prazo", "passou"],
                     ["90 dias", "garantia"]],
    },
    {
        "id": "accessories_ask_first",
        "messages": ["Vocês vendem cordas para violão?"],
        "contains": [["parceir"]],
        "not_contains": ["palheta & cia"],  # partner names only after the customer says yes
    },
    {
        "id": "off_topic",
        "messages": ["Quem ganhou a Copa do Mundo de 2022?"],
        "no_tools": True,
        "not_contains": ["argentina"],
    },
]


def run_scenario(scenario: dict) -> dict:
    os.environ["STORE_TODAY"] = scenario.get("today", DEFAULT_TODAY)
    calls = []
    agent = Agent(on_tool_call=lambda name, args, result: calls.append((name, args)))
    answers = []
    for message in scenario["messages"]:
        answers.append(agent.send(message))
        time.sleep(PAUSE_SECONDS)

    text = normalize_text(" ".join(answers))
    called = [name for name, _ in calls]
    failures = []

    for tool in scenario.get("tools_required", []):
        if tool not in called:
            failures.append(f"did not call {tool}")
    if scenario.get("tools_any") and not set(scenario["tools_any"]) & set(called):
        failures.append(f"called none of {scenario['tools_any']}")
    if scenario.get("no_tools") and called:
        failures.append(f"should not call tools, called {called}")
    if "arg_check" in scenario:
        tool, description, check = scenario["arg_check"]
        if not any(name == tool and check(args) for name, args in calls):
            failures.append(f"no {tool} call with {description}")
    for alternatives in scenario.get("contains", []):
        if not any(normalize_text(option) in text for option in alternatives):
            failures.append(f"answer lacks any of {alternatives}")
    for forbidden in scenario.get("not_contains", []):
        if normalize_text(forbidden) in text:
            failures.append(f"answer contains forbidden '{forbidden}'")

    return {"id": scenario["id"], "passed": not failures, "failures": failures, "calls": calls, "answers": answers}


def write_report(results: list, model: str) -> Path:
    passed = sum(result["passed"] for result in results)
    lines = [
        "# Agent evaluation",
        "",
        f"Generated by `scripts/evaluate_agent.py` on {datetime.now():%Y-%m-%d %H:%M} with model `{model}`.",
        f"**{passed}/{len(results)} scenarios passed.**",
        "",
        "| Scenario | Result | Tools called |",
        "|---|---|---|",
    ]
    for result in results:
        tools_called = ", ".join(name for name, _ in result["calls"]) or "—"
        lines.append(f"| `{result['id']}` | {'✅ pass' if result['passed'] else '❌ fail'} | {tools_called} |")
    for result in [r for r in results if not r["passed"]]:
        lines += ["", f"## ❌ `{result['id']}`", ""]
        lines += [f"- {failure}" for failure in result["failures"]]
        lines += ["", "Answer:", ""] + [f"> {line}" for answer in result["answers"] for line in answer.splitlines()]
    path = ROOT / "docs" / "evaluation.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is missing (see README).")

    results = []
    for scenario in SCENARIOS:
        result = run_scenario(scenario)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL: " + "; ".join(result["failures"])
        print(f"{result['id']:24} {status}")

    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    path = write_report(results, model)
    passed = sum(result["passed"] for result in results)
    print(f"\n{passed}/{len(results)} passed. Report: {path.relative_to(ROOT)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
