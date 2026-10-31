# Data exploration notes

Findings from reading the raw files and running `scripts/explore_data.py`.
Each finding lists the decision it leads to (or "open" if not decided yet).

## Overview

| File | Rows | Notes |
|---|---|---|
| products.csv | 65 | ids 81–145 (not sorted: 145 appears before 131) |
| categories.csv | 9 | 3 categories have **no products** (see below) |
| customers.csv | 50 | only customers 1–18 have orders |
| orders.csv | 20 | dates 2025-10-15 → 2026-03-22 |
| order_items.csv | 22 | no price column; orders 15 and 20 have 2 items |
| promotions.csv | 25 | only `is_active` flag, **no start/end dates** |

Types load cleanly: prices are floats (no "R$" strings), stock is int, dates are ISO `YYYY-MM-DD`.
No nulls except the expected ones in `orders` (tracking/ETA empty for non-shipped orders, `notes` only on cancelled ones).

## Products

- **Status values:** `active` (62), `discontinued` (2: ids 113, 136), `coming_soon` (1: id 130).
  → Search tool returns status so the agent can say "discontinued" / "coming soon" instead of "available".
- **Out of stock:** id 96 (active, stock 0) and id 113 (discontinued, stock 0).
  → Good edge case: agent must say "temporarily unavailable" and suggest alternatives (policy rule).
- **`specs` is always valid JSON**, but the keys depend on the category:
  - Violões / Ukuleles: `top, back_sides, neck, strings (nylon|steel), scale, electronics (yes|no), color`
  - Guitarras / Baixos: `body, neck, strings ("6"/"4"), color`
  - Baterias: `shells, pieces, hardware, color`
  - Teclados: `keys, type, polyphony, color`
  → Parse specs into a dict once at load time; filters like "nylon" or "with electronics" work on violões/ukuleles.
- **Name vs description mismatches** (categories 2–4 look auto-generated):
  - 135 "Music Man Bass 1X" — description says Fender Jazz Bass
  - 136 "Ibanez Bass 2X" — description says Precision
  - 137 "Yamaha Bass 3X" — description says 5-string Ibanez, specs say 4 strings
  - 139 "Yamaha Kit 1" — description says Pearl Export with Poplar shells, specs say Maple
  - 140 "Pearl Kit 2" — description says Tama, Birch shells, specs say Maple
  - 142 "Korg Synth 1" — description says Roland with 88 keys, specs say 61 keys
  - 144 "Roland Synth 3" — description says Yamaha arranger
  → Decision (open): treat **`name` + `specs` as the source of truth** and use the description only as flavour text. Document in README.
- Typo: id 84 "Giannini GN-15 Nylon **Cedr**" (cedro). Names use "Elétrico" for electro-acoustic guitars.
  → Search should be accent/case-insensitive and match on name + description.
- **Empty categories:** Sopros (Madeiras), Sopros (Metais), Cordas Orquestrais have 0 products, although the policy manual says the store sells them.
  → Agent should say the category exists but no item is in the catalog right now (suggest contacting the store), never invent products.

## Promotions

- Only 4 are active: product 127 (10%), 121 (20%), 90 (18%), 94 (8%).
- Products 93, 96 and 99 have **two** promotion rows each (all inactive).
- **Takamine GD20 (id 95)** has only an **inactive** 12% promotion → perfect "expired promotion" scenario: show current price, do not promise the discount.
- No dates on promotions, so "active" means `is_active == 1`.
  → If more than one active promo existed for a product, apply only one (policy: promotions are not cumulative). Not the case in the current data.
- PIX 5% discount applies to list price only, not to promotional prices (policy).

## Orders

- Statuses: `delivered` 7, `confirmed` 4, `pending` 4, `cancelled` 4, `shipped` 1.
- Payment methods: `pix`, `debit`, `boleto`, `credit_3x`, `credit_6x`, `credit_12x`.
- Tracking codes all match `BR` + 9 alphanumeric + `BR`.
- **Totals that don't match item prices:**
  - Order 3: 2 × product 130 (1,749) = 3,498, but total is 3,450
  - Order 20: 799 + 689 = 1,488, but total is 1,400
  → Use `orders.total_brl` as the truth (it is what the customer paid; catalog prices may have changed). Document.
- Orders 3 and 14 contain product 130, which is `coming_soon` (order 3 is even delivered).
  → Data quirk; just document it.
- Some historical installments break today's minimums (e.g. order 16: 6× of R$ 71.65 < R$ 80).
  → Ignore: the agent only applies installment rules to new purchases.
- Order 8 is still `shipped` months after its ETA (2026-02-28); order 18's note says "out of stock" but product 85 now has stock.
  → Agent reports the stored status as-is; no inference.
- **No real delivery date** — only `estimated_delivery`.
  → Use `estimated_delivery` as the approximate receipt date for the 7-day return window. Document as assumption.

### Important: dates vs "today"

Today is 2026-10-31, but the most recent order is from 2026-03-22. With the real date, **every delivered order is outside** the 7-day return window, the 30-day defect exchange window and the 90-day legal warranty.

→ Decision (open): add an optional `STORE_TODAY` env var that overrides the current date for policy checks.
Default = real date (honest behaviour); for the example conversations we can set e.g. `STORE_TODAY=2026-03-20` so the return-window logic shows both an eligible and a non-eligible case.

## Customers

- Customers 11 "Bruno Carvalho Martins" and 43 "Bruno Martins" share the **same email** (`bruno.martins@jmail.com`).
  → Order lookup is keyed by `order_id` and then verified against the order's customer, so a shared email can't leak another customer's order.
- Near-duplicate names with different emails (13 "Diego Fernandes Castro" / 47 "Diego Castro"); 31 "Joao" without accent.
- No duplicate phones. Phones are formatted `(67) 9XXXX-XXXX`.
  → When verifying identity, compare phones by digits only, emails case-insensitively.
