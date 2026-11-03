"""Evaluates the agent against the real model with scripted scenarios.

For each scenario it checks:
- which tools were called (did the agent look up data / policies when it should, and not when it shouldn't?)
- key tool arguments (e.g. a price filter really applied)
- text that MUST appear in the answers (correct price, deadline...) or MUST NOT (invented prices, other people's data)

The model is not deterministic, so each scenario can be run several times to get a pass rate.

Run from the repo root (each run of all scenarios uses an estimated 80-100 requests of the Gemini quota):
    python scripts/evaluate_agent.py            # 1 run
    python scripts/evaluate_agent.py --runs 3   # 3 runs, reports e.g. "3/3" per scenario
    python scripts/evaluate_agent.py --only price_lookup out_of_stock   # only these scenarios
Writes a report to docs/evaluation.md (docs/evaluation_rerun.md with --only) and exits with code 1 if any run of
any scenario fails. "Today" is DEFAULT_TODAY unless a scenario sets its own date.
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.agent import Agent  # noqa: E402
from src.data_loader import normalize_text  # noqa: E402

PAUSE_SECONDS = 5  # free tier allows 15 requests/minute; one turn can use up to 3 requests
DEFAULT_TODAY = "2026-02-20"  # same date as the example conversations

# Internal wording that must never reach a customer, checked in every scenario.
# ("sistema" is only checked where it can't come from a product description, e.g. "Sistema ES2" pickups.)
ALWAYS_FORBIDDEN = ["ferramenta", "manual interno"]

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
        "id": "grounded_recommendation",
        "messages": ["Sou iniciante, qual violão de nylon até R$ 700 você me indica?"],
        "tools_any": ["search_products"],
        # Claims that are not in the product data, or internal wording the customer shouldn't see
        "not_contains": ["professor", "mais vendido", "queridinho", "sistema", "ferramenta"],
    },
    {
        "id": "out_of_stock",
        "messages": ["Vocês têm o violão Giannini GF-3D Dreadnought?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["esgotado", "indisponivel", "sem estoque", "em falta"],
                     # Policy 7.3: suggest an available alternative. These are the ones computed in code for
                     # product 96 (same strings, closest price); a product that is not in the catalog can't match.
                     ["shelby sgd-195e", "tagima dallas", "tagima woodstock"]],
        # No promotion on this product: no rain-check talk. GN-14 / GD20-NS were invented in an earlier run.
        "not_contains": ["nao fica reservado", "gn-14", "gd20-ns", "gd20 ns"],
    },
    {
        # Discontinued product (113): say it left the catalog and look for an equivalent (policy 7.3)
        "id": "discontinued_product",
        "messages": ["Quero o violão Shelby SN-7C de 7 cordas, quanto está?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["descontinu", "nao faz mais parte", "saiu do catalogo", "saiu do nosso catalogo", "fora de linha",
                      "nao trabalhamos mais"],
                     # Equivalents computed in code: other 7-string nylon guitars
                     ["gwne-7", "rv-174", "rv-175"]],
        "not_contains": ["gn-14", "gd20-ns", "gd20 ns", "gc1 nylon"],  # invented in an earlier run
    },
    {
        # No manufacturer warranty term in the data: legal 90 days + "see the certificate", never a specific term
        "id": "manufacturer_warranty",
        "messages": ["Qual a garantia do Takamine GD20?"],
        "contains": [["90 dias", "noventa dias"], ["certificado"]],
        "not_contains": ["garantia de 1 ano", "garantia de um ano", "garantia de 2 anos", "garantia de dois anos",
                         "garantia de 12 meses", "takamine oferece"],
    },
    {
        # Coverage of a concrete damage is for the team to assess (policy 8.3), not the agent
        "id": "warranty_coverage_not_decided",
        "messages": ["Meu violão rachou no tampo, a garantia cobre?"],
        "contains": [["equipe", "avali", "solicita"]],
        "not_contains": ["esta coberto", "sim, a garantia cobre", "nao esta coberto", "nao e coberto", "a garantia nao cobre esse"],
    },
    {
        # Data deletion (policy 9): point to the team's channels, never claim it was done
        "id": "data_deletion_request",
        "messages": ["Quero que vocês apaguem todos os meus dados."],
        "contains": [["3321-4500", "whatsapp", "contato@emporiodamusica"]],
        "not_contains": ["exclui seus dados", "apaguei", "dados foram excluidos", "dados foram apagados"],
    },
    {
        # "Coming soon" product (130): not on sale yet, alternatives computed in code
        "id": "coming_soon_product",
        "messages": ["Quanto custa o ukulele Kala KA-ABP-CTG barítono?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["em breve", "ainda nao esta a venda", "ainda nao chegou", "nao esta disponivel para venda"],
                     ["ka-srt-ctg", "bk-35e", "tk-35g"]],
    },
    {
        # Complaint (policy 7.3): listen, register it after the customer agrees, 24 business hours to reply
        "id": "complaint_registered",
        "messages": ["Quero fazer uma reclamação: fui muito mal atendido na loja ontem.", "Sim, pode registrar."],
        "tools_required": ["create_support_ticket"],
        "contains": [["24 horas"]],
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
        # Cheapest product, R$ 159,90: at most 3x of R$ 53,30 (R$ 50 minimum up to 3x, R$ 80 from 4x), computed in code
        "id": "installments_for_cheap_product",
        "messages": ["Quanto custa o ukulele Shelby SU-21S? Dá pra parcelar em 12x?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["3x", "3 vezes", "três vezes"], ["53,30", "53.30"]],
        "not_contains": ["12x de", "12x sem juros de", "em até 12x sem juros"],
    },
    {
        # Outside the Campo Grande region there is no fixed price and no free shipping, even above R$ 500
        "id": "shipping_other_city",
        "messages": ["Moro em Dourados. Quanto fica o frete do Takamine GD20?"],
        "tools_required": ["get_delivery_info"],
        "contains": [["cep"], ["pac", "sedex", "jadlog"]],
        "not_contains": ["frete gratis", "frete e gratis", "r$ 35"],
    },
    {
        # Inside the region (Sidrolândia) and above R$ 500: free local delivery, computed in code
        "id": "shipping_local_free",
        "messages": ["Moro em Sidrolândia, o frete do Takamine GD20 é grátis?"],
        "tools_required": ["get_delivery_info"],
        "contains": [["gratis", "grátis", "sem custo"], ["1 a 3 dias"]],
    },
    {
        # Saturday 14:00, store closed since 13:00: the team is back on Monday 09/11 at 09:00 (computed in code)
        "id": "after_hours_next_opening",
        "today": "2026-11-07T14:00",
        "messages": ["Oi, a loja está aberta agora? Queria falar com um atendente"],
        "contains": [["fechad"], ["segunda"], ["9h", "09:00", "9:00", "09h"]],
        "not_contains": ["domingo, 08/11 às", "amanhã às 9", "amanha as 9"],
    },
    {
        # Black Friday month, but no active promotion for this product: the campaign calendar is not a discount
        "id": "campaign_month_no_promise",
        "today": "2026-11-03",
        "messages": ["É Black Friday, né? Quanto fica o Takamine GD20 com o desconto?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["2.199", "2199"]],
        # 15% / 30% off (the policy's Black Friday range) would be R$ 1.869,15 / R$ 1.539,30
        "not_contains": ["1.869", "1869", "1.539", "1539"],
    },
    {
        # The agent can't place orders: it must send the customer to the team, not offer to close the sale
        "id": "no_order_placement",
        "messages": ["Quanto custa o Takamine GD20?", "Gostei! Quero comprar, pode fechar pra mim?"],
        "tools_any": ["search_products", "get_product_details"],
        "contains": [["3321-4500", "33214500", "loja fisica", "na loja"]],
        # Offers only: a correct answer says "não consigo fechar o pedido", so the bare phrase can't be forbidden
        "not_contains": ["quer fechar o pedido", "posso fechar o pedido", "vamos fechar o pedido",
                         "fazer o pedido por aqui", "pedido realizado", "reservei", "pedido criado"],
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
        # Preference exchange (policy 4.3): deadline from code and a stock check of the desired product
        "id": "preference_exchange",
        "messages": ["Quero trocar meu ukulele por um Kala KA-15S Mogno. Pedido 7, e-mail leticia.rocha@jmail.com"],
        "tools_required": ["get_order_status"],
        "tools_any": ["search_products", "get_product_details"],
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
    if "min_calls" in scenario:
        tools_counted, minimum = scenario["min_calls"]
        made = sum(name in tools_counted for name in called)
        if made < minimum:
            failures.append(f"made {made} call(s) to {tools_counted}, expected at least {minimum}")
    if "arg_check" in scenario:
        tool, description, check = scenario["arg_check"]
        if not any(name == tool and check(args) for name, args in calls):
            failures.append(f"no {tool} call with {description}")
    for alternatives in scenario.get("contains", []):
        if not any(normalize_text(option) in text for option in alternatives):
            failures.append(f"answer lacks any of {alternatives}")
    for forbidden in scenario.get("not_contains", []) + ALWAYS_FORBIDDEN:
        if normalize_text(forbidden) in text:
            failures.append(f"answer contains forbidden '{forbidden}'")

    return {"id": scenario["id"], "passed": not failures, "failures": failures, "calls": calls, "answers": answers}


def write_report(runs_by_scenario: dict, runs: int, model: str, only: Optional[list] = None) -> Path:
    """runs_by_scenario: {scenario id: [result of run 1, result of run 2, ...]}

    A partial re-run (`only`) goes to its own file, so it never replaces the report of the full evaluation.
    """
    all_results = [result for results in runs_by_scenario.values() for result in results]
    passed_runs = sum(result["passed"] for result in all_results)
    always_passed = sum(all(result["passed"] for result in results) for results in runs_by_scenario.values())
    lines = [
        "# Agent evaluation" + (" (partial re-run)" if only else ""),
        "",
        f"Generated by `scripts/evaluate_agent.py --runs {runs}{' --only ' + ' '.join(only) if only else ''}` "
        f"on {datetime.now():%Y-%m-%d %H:%M} with model `{model}`.",
        "",
        f"**{passed_runs}/{len(all_results)} runs passed; {always_passed}/{len(runs_by_scenario)} scenarios passed "
        f"in every run.**",
        "",
        "| Scenario | Runs passed | Tools called (last run) |",
        "|---|---|---|",
    ]
    for scenario_id, results in runs_by_scenario.items():
        passed = sum(result["passed"] for result in results)
        icon = "✅" if passed == len(results) else "❌"
        tools_called = ", ".join(name for name, _ in results[-1]["calls"]) or "—"
        lines.append(f"| `{scenario_id}` | {icon} {passed}/{len(results)} | {tools_called} |")
    for scenario_id, results in runs_by_scenario.items():
        for run, result in enumerate(results, start=1):
            if result["passed"]:
                continue
            lines += ["", f"## ❌ `{scenario_id}` (run {run})", ""]
            lines += [f"- {failure}" for failure in result["failures"]]
            lines += ["", "Answer:", ""]
            lines += [f"> {line}" for answer in result["answers"] for line in answer.splitlines()]
    path = ROOT / "docs" / ("evaluation_rerun.md" if only else "evaluation.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluate the agent against the real model.")
    parser.add_argument("--runs", type=int, default=1, help="how many times to run each scenario")
    parser.add_argument("--only", nargs="+", metavar="SCENARIO_ID",
                        help="re-run only these scenarios (report goes to docs/evaluation_rerun.md)")
    args = parser.parse_args()
    runs, only = args.runs, args.only
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is missing (see README).")

    scenarios = SCENARIOS
    if only:
        known = {scenario["id"] for scenario in SCENARIOS}
        unknown = [scenario_id for scenario_id in only if scenario_id not in known]
        if unknown:
            sys.exit(f"Unknown scenario(s): {', '.join(unknown)}")
        scenarios = [scenario for scenario in SCENARIOS if scenario["id"] in only]

    runs_by_scenario = {scenario["id"]: [] for scenario in scenarios}
    for run in range(1, runs + 1):
        print(f"--- run {run}/{runs}", flush=True)
        for scenario in scenarios:
            result = run_scenario(scenario)
            runs_by_scenario[scenario["id"]].append(result)
            status = "PASS" if result["passed"] else "FAIL: " + "; ".join(result["failures"])
            print(f"{result['id']:24} {status}", flush=True)  # flush: show progress even when output is redirected

    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    path = write_report(runs_by_scenario, runs, model, only)
    all_results = [result for results in runs_by_scenario.values() for result in results]
    passed = sum(result["passed"] for result in all_results)
    print(f"\n{passed}/{len(all_results)} runs passed. Report: {path.relative_to(ROOT)}")
    sys.exit(0 if passed == len(all_results) else 1)


if __name__ == "__main__":
    main()
