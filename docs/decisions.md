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

## Policy manual inconsistencies (resolved in `data/policies.md`)

- Phone: (67) 3341-4444 used as landline, (67) 3321-4500 as WhatsApp (as section 7 names it).
- E-mail: `contato@emporiodamusica.com.br` (the accented variant is treated as a typo).
- Credit card minimum installment: the detailed ranges of section 3.1 prevail over the summary table.
