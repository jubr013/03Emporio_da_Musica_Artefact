# Design decisions

Decisions taken during development. They feed the "Design decisions" and "Assumptions" sections of the README.

## Order tool (decided 2026-10-31)

1. **"Today" for deadline checks:** real current date by default; `STORE_TODAY` in `.env` overrides it.
   Example conversations use `STORE_TODAY=2026-02-20`, so order 7 (received ~2026-02-17) is inside the 7-day
   return window and order 6 (received ~2026-02-01) is outside it but still under the 90-day legal warranty.
   Side effect: orders dated after 2026-02-20 look like they are "in the future" with that override.
2. **Identity check (LGPD):** order details are only shown when the customer gives the order number **and**
   the e-mail or phone of the customer who placed that order. On mismatch, nothing is revealed.
3. **Receipt date (base for the 7-day return window and the 90-day legal warranty):**
   - Default: `estimated_delivery` (there is no real delivery date in the data), returned as `receipt_date_source: "estimated"`.
   - The agent confirms the date with the customer. The customer may give another date (`received_on`), accepted
     only between the order date and today.
   - If the customer's date is **later** than the estimate (it extends the deadline), deadlines use it but the
     result is flagged `requires_staff_confirmation: true`: the agent says the team will confirm, without denying
     or promising the refund.
   - If it is the same or earlier, it is accepted as is.
4. **Who computes deadlines:** the code, not the LLM. The tool returns ready-made dates and flags
   (e.g. inside the return window, days left) because LLMs are unreliable at date arithmetic.
   - Return (arrependimento) and legal warranty count from the **receipt** date; defect exchange (30 days) counts
     from the **purchase** (order) date, as written in the policy manual.

## Agent (decided 2026-11-02)

1. **Tool-calling loop written by hand** (automatic function calling of the SDK disabled): send message →
   model asks for a tool → code runs it → result goes back → repeat until a text answer. Every step is visible,
   easy to explain and to log.
2. **Persona name: melodIA** — the store's virtual assistant. Name chosen by me; the manual only says "assistente virtual".
3. **Partner stores for accessories:** the manual says to suggest partner stores "when possible" but lists none.
   Two **fictional** partner stores were added to `data/policies.md` (section `lojas_parceiras`), clearly marked
   as an addition that is not in the original manual. The agent first explains that the store doesn't sell
   accessories and **asks** whether the customer wants partner suggestions; it only lists them if they say yes.
4. **Support tickets:** in a first real test the agent claimed it had "forwarded" a return request although it had
   no way to do that. Added `create_support_ticket`, which writes the request to `history/tickets.jsonl` and returns
   a protocol number (the prototype's stand-in for the team's inbox). The prompt forbids claiming any action
   without calling the matching tool.
5. **Model errors:** the free tier sometimes answers 503 (high demand). The client retries with exponential backoff;
   if it still fails, the agent answers with a polite fallback message and rolls back the unfinished turn.
6. **Default model: `gemini-3.5-flash-lite`.** `gemini-3.5-flash` was used first, but its free tier allows only
   20 requests per day per model, and each agent turn takes 2–3 requests (tool call + answer). The quota ran out
   while recording the examples. The lite model has its own quota, answered correctly in a test conversation
   (tools, expired promotion, installments) and is faster. Switching back is one line in `.env`.

## Final improvements (decided 2026-11-02)

1. **Search tuned on measured failures.** I ran customer-style queries against the catalog and fixed only what failed:
   spec-derived keywords in the search text ("aco", "nylon", "eletroacustico"), word-start matching instead of
   substring ("aco" was matching "braco"), "-ões" → "-ão", spelled-out numbers → digits, and filler words ignored.
2. **Store time zone.** Dates and times use `America/Campo_Grande` (UTC-4) instead of the machine's clock, so opening
   hours are right wherever the agent runs. `tzdata` was added because Windows has no built-in time zone database.
3. **Agent loop tests with a fake model.** `Agent` accepts an injected client; tests script the model's responses with
   the SDK's real types and check that tool results go back with the right id, API errors roll back the turn, and the
   round limit holds. No API key or quota needed.

4. **Holidays.** Policy 2 says the store is closed on holidays, so `src/store_calendar.py` computes them (national and
   MS state holidays from Campo Grande's decree nº 16.469/2025; municipal Santo Antônio 13/06 and city anniversary
   26/08 from local calendars; Good Friday from Easter). Optional days such as Carnival and Corpus Christi are not
   holidays. The prompt states whether today is a holiday and lists the next two weeks' holidays.
5. **Identity attempt limit.** At most 3 failed order verifications per conversation; then lookups are blocked and
   the customer is sent to the team. The counter lives in `Agent`, because the tool is stateless.
6. **Scenario evaluation.** `scripts/evaluate_agent.py` runs 14 scripted messages against the real model and checks
   tools called, key arguments and required/forbidden text. The first run (13/14) showed the agent omitting the
   return deadline date and inventing an "inspection" condition; the prompt was fixed (not the test) and the next
   run passed 14/14. Quota on my account (AI Studio, 2026-11-02): flash-lite 15 RPM / 500 RPD.
7. **Examples re-recorded with the final prompt.** Reviewing them showed the agent presenting 10 of 12 results as the
   whole list (→ `showing` / `more_available` in `search_products` + prompt rule) and guessing when the 10-business-day
   refund starts, which the manual doesn't say (→ prompt: state the 10 days, don't specify the start). Conversations
   1 and 3 were recorded again after the fix, and the evaluation re-run passed 14/14.

## Last round of limitation fixes (decided 2026-11-02)

1. **Grounded recommendations.** The prompt now says recommendations must cite product data and must not attribute
   opinions to others ("teachers recommend") or make unsupported claims ("best seller"); temperature 0.3 → 0. A new
   evaluation scenario fails on those phrases and on internal wording ("sistema", "ferramenta", "manual interno").
2. **Fallback model.** On a 429 that survives the SDK's retries (daily quota), the agent switches once to
   `GEMINI_FALLBACK_MODEL` (`gemini-3.1-flash-lite`, its own 500/day quota) for the rest of the conversation.
3. **Policy transcription test.** `tests/test_policies_match_pdf.py` reads the original PDF with `pypdf` and checks
   that 26 key facts appear identically in `data/policies.md`.
4. **Model codes in search.** Typo tolerance was not added (the LLM writes the query and already fixes typos); model
   codes are glued instead, so "GD 20" / "GD-20" / "GD20" match. Only letter groups of up to 4 characters are glued,
   so "violão 7 cordas" keeps working.
5. **Evaluation pass rate.** `--runs N` runs every scenario N times and reports passes per scenario. Final run:
   15 scenarios × 3 runs, 45/45 passed. Example 01 was re-recorded: recommendations now cite the product descriptions.
6. **Not done on purpose:** locking an order after failed verifications (it would let anyone block another customer's
   order); holidays from a library (municipal holidays missing, extra dependency); reloading saved conversations and
   a real helpdesk (little value for a prototype).

## Optional web UI (decided 2026-11-02)

1. **Why:** the role is full-stack and React/TypeScript is my main stack. Built on a separate branch and merged only
   after tests and my approval; the CLI stays the main interface.
2. **Backend:** FastAPI (`src/api.py`) reusing the same `Agent`; one conversation per browser session in memory, one
   request at a time (local, single user). The `today` field mirrors `--today`; without it the `.env` value is used.
3. **Frontend:** Vite + React + TypeScript + Tailwind in `web/`, files written by hand (no generator) so every file is
   understood. Vite forwards `/api` to the Python server, so no CORS setup. Under each answer the UI shows the tool
   calls as labels (data / policy / ticket): it makes the agent's "when to consult what" decision visible.
4. **Tests:** 12 API tests with the fake model, 11 frontend tests (Vitest + Testing Library, `fetch` mocked), and an
   end-to-end check in the browser (return flow with ticket, mobile width, API down).

## Review before submission (decided 2026-11-03)

A last review against the challenge found two cases of the agent going beyond what it should, plus two loop edge
cases. Same principle as before: enforce in code what a tool makes enforceable; what is only wording goes in the
prompt and is checked by the evaluation.

1. **Tickets on unverified orders (code).** `create_support_ticket` could be called with any order number, so someone
   could open a return or complaint on another customer's order. The agent now remembers which orders were verified
   in the conversation and refuses a ticket tied to any other order (tickets without an order, e.g. a general
   complaint, still work). The prompt also tells the model to verify the order first.
2. **Offering to close a sale (prompt + evaluation).** Example 02 ended with "Quer fechar o pedido por aqui?", but the
   agent has no way to create orders. There is no tool to block, so this is a prompt rule (no orders, reservations or
   closing sales; send the customer to WhatsApp or the store) and a new evaluation scenario (`no_order_placement`).
   Example 02 was kept as recorded and is flagged in the README instead of being edited.
3. **History rollback.** An empty model response or hitting the tool round limit left the history ending on an
   unanswered message or on tool results. Those turns are now rolled back like API errors.
4. **Campaign calendar is not a discount (prompt + evaluation).** Policy 6.1 lists when campaigns usually happen
   (e.g. Black Friday in November, 15–30% "em todo o catálogo"), but every Black Friday row in `promotions.csv` is
   inactive. In November the model could read the calendar as an active discount. The data wins (policy 7.3: check
   that the promotion is active): the prompt says the calendar only describes when campaigns usually happen, and a
   new scenario (`campaign_month_no_promise`, today = 2026-11-03) fails if a Black Friday price is computed.
5. **Opening hours in code.** "When is the team back?" was left to the model (Saturday afternoon → Monday; eve of
   a holiday → the day after). `src/store_calendar.py` now has the weekly hours (`OPENING_HOURS`), `is_open` and
   `next_opening` (skips Sundays and holidays); the prompt gets "open now / next opening" every turn and its hours
   line is generated from the same table. A test checks the table against the `horarios` section of
   `data/policies.md`, so the two can't drift apart. `STORE_TODAY` also accepts `YYYY-MM-DDTHH:MM` so the evaluation
   can simulate a time (scenario `after_hours_next_opening`, Saturday 14:00).
6. **Extended hours (policy 2).** The agent doesn't know if or when hours are extended on special dates, so it
   must not confirm them; it says changes are announced on social media and WhatsApp.
7. **Installments in code.** The model worked out the maximum installments from the policy text, which needs the
   per-range minimums (R$ 349,90 → 4x; 7x only from R$ 700). `credit_card_installments` in `src/tools.py` computes
   it on the final price and every product result carries `credit_card` (`max_installments`, `installment_brl`).
   Several products together are still summed by the model (documented limitation). Scenario
   `installments_for_cheap_product` checks the cheapest product (3x of R$ 53,30).
8. **"Exceto abaixo de R$ 50,00" (policy 3.1, up to 3x).** The first transcription silently turned it into "purchases
   below R$ 50". It now keeps the manual's words, and the code reads it as a R$ 50 minimum installment (the
   sentence is about the installment value). No current product is affected by the difference.
9. **Preference exchange (policy 4.3).** Not computed before: the model would reuse the regret deadline without
   saying so. Now `preference_exchange_7_days_from_receipt` is computed in code (7 calendar days after receipt, my
   reading of "em até 7 dias", documented in `data/policies.md`), and the prompt requires checking the desired
   product's stock first. Scenario `preference_exchange`.
10. **Items not eligible (policy 4.4).** Nothing in the data says if an order had setup/customization or was a
    "venda final" sale, so the agent can't decide. It mentions the exclusions, asks, notes the answer in the ticket,
    and the team confirms. Mouthpieces only if asked (no wind instruments in the catalog).
11. **Intermediation after 30 days (policy 4.2).** The prompt now has the agent offer a `garantia` ticket so the
    store intermediates with the manufacturer, as the policy allows on request.
12. **Shipping tool (policy 5).** 26 of 50 customers live outside Campo Grande, and nothing stopped the model from
    applying "free above R$ 500" to them. New tool `get_delivery_info(city, order_total_brl)`: decides in code if the
    city is in the local region (IBGE Região Geográfica Imediata de Campo Grande, since there is no legal
    metropolitan region) and computes the fee (free from R$ 500,00 inclusive, else R$ 35); other cities get PAC /
    SEDEX / Jadlog times and no price. The prompt makes the agent ask the city first, warn that large instruments may
    need a special quote, and explain tracking for orders not yet shipped and what to do on damage. Scenarios
    `shipping_other_city` and `shipping_local_free`.
13. **Correios API: not used.** Price/deadline APIs need a Correios contract (CWS token) and the products have no
    weight/dimensions; documented under "What I would do with more time".
14. **No rain check (policy 6.2).** If a product on promotion is out of stock, the agent says the promotion depends on
    stock and the promotional price is not held for when it comes back. Prompt only: no current promoted product is
    out of stock.
15. **Service flow and special situations (policy 7).** The prompt now spells out the 5-step flow of 7.2 (greet by
    name only if known, never asking the name just for that; close by asking if anything else is needed) and a
    complaint section (empathy, then register the ticket once the customer agrees). New scenarios:
    `discontinued_product` and `complaint_registered`; `out_of_stock` and `discontinued_product` require a second
    lookup (`min_calls`), since suggesting alternatives needs one.
16. **Warranty (policy 8).** No product has a manufacturer warranty term in the data, so the agent never states one
    (only the legal 90 days and "see the certificate"); it never decides if a concrete damage is covered (the team
    assesses, via a `garantia` ticket); and the prompt spells out the order for defects: 30 days from purchase
    (exchange), 90 days from receipt (legal warranty), then the manufacturer. Scenarios `manufacturer_warranty` and
    `warranty_coverage_not_decided`.
17. **Privacy requests (policy 9).** Data deletion needs the team to confirm the requester's identity, so the agent
    points to WhatsApp / e-mail and never claims it deleted data; marketing consent is also handled by the team.
    Scenario `data_deletion_request`. Local logs (`history/`) holding personal data are documented as a limitation
    (masking would make them useless as example sources).
18. **Alternatives computed in code (found by the evaluation).** The full run with all the changes above passed
    73/81: the agent offered to look for alternatives instead of suggesting them (policy 7.3), mentioned "no rain
    check" for a product without promotion, copied a PIX price without the cents once, and one check of
    `no_order_placement` matched a correct refusal ("não consigo fechar o pedido"). A prompt rule to "suggest
    alternatives in the same answer" made it worse: with a single search, the model listed guitars that don't exist
    (e.g. "Giannini GN-14", "Takamine GD20-NS" at R$ 3.490). Final fix: `get_product_details` and specific searches
    return `available_alternatives` for unavailable products (same category; same strings and number of strings
    first; closest price), the prompt only lets the model cite products and prices returned in the conversation,
    the rain-check warning only when there is a promotion, prices copied with cents. The scenarios now require one
    of the computed alternatives and forbid the invented names; the `no_order_placement` check forbids offers only.
    Re-run of the 11 product scenarios × 3: 30/33 (once "R$ 429,00" for R$ 429,90, once "queridinho dos
    professores"). Two more code fixes: prices go out pre-formatted (`price_display`), and `src/agent.py` checks each
    answer for forbidden phrases and asks the model for one rewrite (only the clean answer stays in the history).
    Final full run (27 scenarios × 1, the quota left for the day): **27/27**.
19. **Assumption made explicit:** `orders.csv` has no sales channel; every order has shipping data, so all orders are
   treated as online purchases (which is what makes the 7-day regret right apply).

## Policy manual inconsistencies (resolved in `data/policies.md`)

- Phone: (67) 3341-4444 kept as the general "Telefone / WhatsApp" (section 1.2's label); (67) 3321-4500 as the
  customer service WhatsApp (section 7), the one the agent gives. First transcribed as landline vs. WhatsApp, which
  dropped the manual's label; corrected in the review of 2026-11-03.
- "Mais de 300 instrumentos" left out: the catalog data has 65 products.
- Mission: transcribed in full (the first version had cut its last clause).
- E-mail: `contato@emporiodamusica.com.br` (the accented variant is treated as a typo).
- Credit card minimum installment: the detailed ranges of section 3.1 prevail over the summary table.
