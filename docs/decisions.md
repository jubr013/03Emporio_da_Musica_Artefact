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

## Policy manual inconsistencies (resolved in `data/policies.md`)

- Phone: (67) 3341-4444 used as landline, (67) 3321-4500 as WhatsApp (as section 7 names it).
- E-mail: `contato@emporiodamusica.com.br` (the accented variant is treated as a typo).
- Credit card minimum installment: the detailed ranges of section 3.1 prevail over the summary table.
