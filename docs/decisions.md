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

## Policy manual inconsistencies (resolved in `data/policies.md`)

- Phone: (67) 3341-4444 used as landline, (67) 3321-4500 as WhatsApp (as section 7 names it).
- E-mail: `contato@emporiodamusica.com.br` (the accented variant is treated as a typo).
- Credit card minimum installment: the detailed ranges of section 3.1 prevail over the summary table.
