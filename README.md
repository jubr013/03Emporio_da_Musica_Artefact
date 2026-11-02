# Empório da Música — Customer Service Agent (melodIA)

Prototype of a text-based customer service agent for **Empório da Música**, a fictional musical instrument store in
Campo Grande/MS. Built for the Artefact AI Engineer technical challenge.

The agent, **melodIA**, talks to customers in Portuguese (pt-BR) with the store's tone ("informal but professional,
like a friend who knows about music"). It decides on its own when to **look up data** (products, prices, stock,
orders) and when to **look up store policies** (returns, hours, payment, shipping), and it handles out-of-scope
requests politely.

```
Cliente: Quanto custa o Takamine GD20?
   🔧 search_products(query='Takamine GD20')
melodIA: O Takamine GD20 Dreadnought Natural custa R$ 2.199,00. No PIX, ele sai com 5% de desconto por R$ 2.089,05! ...
```

## Contents

- [Requirements](#requirements) · [How to run](#how-to-run)
- [How it works](#how-it-works) · [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Assumptions](#assumptions)
- [Example conversations](#example-conversations)
- [Known limitations](#known-limitations) · [What I would do with more time](#what-i-would-do-with-more-time)
- [Use of AI coding assistants](#use-of-ai-coding-assistants)

## Requirements

- Python 3.12 (developed and tested with 3.12.10)
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) (no credit card needed)

## How to run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the API key
cp .env.example .env            # Windows cmd: copy .env.example .env
                                # then paste your key after GEMINI_API_KEY=

# 4. (Optional) check that the key and model work
python scripts/check_gemini.py

# 5. Chat with the agent
python -m src.main
```

CLI options:

| Option | What it does |
|---|---|
| `--show-tools` | Prints every tool call, so you can see when the agent looks up data or policies |
| `--today YYYY-MM-DD` | Pretends today is this date for return/warranty deadlines (same as `STORE_TODAY` in `.env`). The example conversations use `--today 2026-02-20` (see [Assumptions](#assumptions)) |

Type `sair` (or press Ctrl+C) to end the chat. The conversation is saved to `history/` as JSON and Markdown.

To reproduce the return scenarios of the examples:

```bash
python -m src.main --show-tools --today 2026-02-20
```

Run the tests (no API key needed: the tools are tested directly and the agent loop with a fake model):

```bash
python -m pytest -q
```

Environment variables (`.env`):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Your Gemini API key (required) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model name. `python scripts/check_gemini.py` lists the models your key can use |
| `STORE_TODAY` | empty (real date) | Overrides "today" for deadline checks |

## How it works

A single agent with **function calling**. Each customer message goes through a loop written by hand:

```
customer message
      │
      ▼
 Gemini (system prompt + conversation + tool declarations)
      │
      ├── asks for tool(s) ──► Python runs them (pandas / policies file) ──► results go back to Gemini ──┐
      │                                                                                                    │
      │◄───────────────────────────────────────────────────────────────────────────────────────────────────┘
      │                                         (up to 6 rounds)
      ▼
 text answer to the customer
```

The tools the model can call:

| Tool | Source | Used for |
|---|---|---|
| `search_products` | CSVs (pandas) | Catalog search by keywords, category, price range and availability. Returns list price, active promotion and PIX price |
| `get_product_details` | CSVs (pandas) | Description, specs, stock, availability label and prices of one product |
| `get_order_status` | CSVs (pandas) | Order status for a **verified** customer; for delivered orders, return/exchange/warranty deadlines computed in code |
| `create_support_ticket` | `history/tickets.jsonl` | Registers a return, exchange, warranty request or complaint for the human team and returns a protocol number |
| `get_policy` | `data/policies.md` | One section of the store policies: store info, hours, payment, returns, shipping, promotions, service, warranty, privacy, partner stores |

**Data vs. policies:** facts that change (price, stock, order status) always come from the data tools; rules
(how returns work, opening hours, payment conditions) always come from `get_policy`. The system prompt forbids
answering either from memory. The examples show the agent combining both in one turn (e.g. order status +
return policy).

## Project structure

```
├── data/
│   ├── *.csv                  # store data provided with the challenge
│   ├── politicas_da_loja.pdf  # policy manual provided with the challenge (file renamed without accent)
│   └── policies.md            # the manual transcribed to Markdown, one section per topic
├── src/
│   ├── main.py                # CLI: chat loop, saves the conversation to history/
│   ├── agent.py               # function-calling loop, tool declarations, error handling
│   ├── prompts.py             # system prompt: melodIA persona, when to use each tool, store rules
│   ├── tools.py               # data tools (products, orders, tickets) over pandas
│   ├── policies.py            # policy lookup by topic
│   └── data_loader.py         # loads and cleans the CSVs once
├── tests/                     # pytest: every tool, plus the agent loop with a fake model (no API calls)
├── examples/                  # 5 example conversations recorded from real runs
├── scripts/
│   ├── check_gemini.py        # smoke test for the API key and model
│   └── explore_data.py        # data exploration checks
└── docs/
    ├── data_exploration.md    # data quirks found and how each one is handled
    ├── decisions.md           # design decisions taken during development
    └── ai_usage_log.md        # what I asked the AI vs. what I decided
```

## Design decisions

### Agent approach: single agent + function calling, no framework

The problem is a small set of well-defined lookups (products, orders, policies), so the model only needs to pick
the right tool and phrase the answer. Function calling fits that exactly. I did not use LangChain/LlamaIndex or a
multi-agent setup: they would add abstractions without solving a real problem here, and a hand-written loop
(~40 lines in `src/agent.py`) is easy to debug and explain. The SDK's automatic function calling is **disabled on
purpose**, so every step (tool requested → executed → result returned) is explicit and loggable (`--show-tools`).

### Model and provider: Gemini free tier, `gemini-3.5-flash-lite`

- **Zero cost** for me and for anyone evaluating the project: a Gemini key is free and needs no credit card.
- The official **`google-genai`** SDK (`from google import genai`), not the deprecated `google-generativeai`
  package that many tutorials still use.
- I started with `gemini-3.5-flash`, but its free tier allows only **20 requests per day**, and each agent turn
  takes 2–3 requests. The quota ran out while recording the examples, so I switched the default to
  `gemini-3.5-flash-lite`, which has its own quota, handled the tool calls and policy rules correctly in my tests
  and is faster. Switching models is one line in `.env`.
- Temperature 0.3: customer service needs consistent, factual answers more than creativity.

### Retrieval: pandas for data, sectioned Markdown for policies (no RAG)

- **CSVs → pandas in memory.** Under 200 rows in total; a database or a SQL agent would be overkill. Data is
  loaded and cleaned once (`src/data_loader.py`): JSON specs parsed, accent-free search text, normalized e-mails and
  phones, parsed dates.
- **Keyword search tuned on the real data.** I measured which customer-style queries failed and fixed only those:
  words that exist only in the specs are added to the search text (3 steel-string guitars never say "aço", 2 with a
  pickup never say "eletroacústico"); words match at the **start** of a word, so "aço" no longer matches "braço"
  ("braco" without accents) while "baixo" still matches "baixos"; "-ões" plurals match "-ão"; spelled-out numbers
  become digits ("sete cordas" → "7 cordas"); filler words ("de", "com", "até", "cordas") are ignored.
- **Policies → `get_policy(topic)` over a Markdown file split by topic.** The manual is 8 pages. Embeddings and a
  vector store would add moving parts and make retrieval fuzzy, while a fixed list of topics (sent to the model as
  an `enum`) makes it explicit **when** the agent consults policies, which is one of the challenge's goals.
  I transcribed the PDF by hand instead of extracting it with code because automatic extraction broke the tables
  (hours, payment, shipping).

### Business rules live in code, not in the prompt

LLMs are unreliable at date arithmetic and at applying discount rules consistently. So the tools return
ready-made values and the model only explains them:

- **Prices:** final price with the active promotion; PIX price (5% off) only when there is **no** promotion
  (promotions are not cumulative, policy 6.2). Price filters use the final price, since that is what the customer pays.
- **Availability labels:** `disponivel`, `esgotado`, `descontinuado`, `em breve`, so the agent follows the policy
  for each case (suggest alternatives, offer equivalents, etc.).
- **Deadlines:** for delivered orders, `get_order_status` returns the start date, deadline, whether it is still
  valid and the days left for the 7-day return window, the 30-day defect exchange and the 90-day legal warranty.
  In one test the model mixed up a start date with a deadline, so each deadline now carries an explicit `starts_on`.

### Prompt strategy

The system prompt (`src/prompts.py`) is organized in sections: persona and tone, current context, when to use each
tool, product/price rules, order and privacy rules, returns and warranty, out-of-scope handling, and what to do when
unsure. Key points:

- **Grounding:** never give prices, stock, deadlines or rules without calling the matching tool; never invent products.
- **No fake actions:** in an early test the agent said it had "forwarded" a request it had no way to forward. The
  prompt now forbids claiming any action without calling the matching tool, and `create_support_ticket` gives it a
  real way to register requests.
- **Current date and time** are injected every turn, so the agent knows if the store is open (policy 7.1: outside
  business hours, tell the customer when the team is back). They use the **store's time zone**
  (`America/Campo_Grande`, UTC-4), not the clock of whatever machine runs the agent.
- **Escalation:** complaints, unclear cases or anything needing a human decision → offer a support ticket
  (reply within 24 business hours) and the WhatsApp number.
- **Out of scope:** the store sells instruments only. For accessories the agent explains this and **asks** if the
  customer wants partner store suggestions before listing them; unrelated topics get a friendly one-line refusal.

### Privacy (LGPD)

- Order details are only revealed with the **order number + the e-mail or phone of the customer who placed it**.
  E-mail is case-insensitive; phone works in any format, with or without the area code.
- "Order does not exist" and "contact does not match" return **the same message**, so nobody can discover which order
  numbers exist by trying numbers.
- The tool returns only the customer's **first name** (enough for a greeting).

### Interface and conversation history

- **CLI**: the challenge focuses on the agent, not the UI.
- **History in memory** during the session (the model needs it to follow the conversation). When the chat ends, it
  is saved to `history/` as JSON (full, with tool results) and Markdown (readable). The example conversations come
  straight from these files.

### Error handling

- Tool errors become a dict returned to the model, so it can explain instead of crashing.
- The free tier sometimes answers **503 (high demand)**: the client retries with exponential backoff (5 attempts).
  If it still fails, the customer gets a polite fallback message, the unfinished turn is removed from the history,
  and the real error (e.g. `429 RESOURCE_EXHAUSTED`) is printed to stderr for the operator.

More details and the reasoning behind each choice: [`docs/decisions.md`](docs/decisions.md) and
[`docs/data_exploration.md`](docs/data_exploration.md).

## Assumptions

The challenge says to make reasonable assumptions when something is ambiguous. These are mine:

**Dates**
- **"Today" for deadlines.** The data ends in March 2026; with the real date, every delivered order is outside every
  deadline. The agent uses the real date by default, and `STORE_TODAY` / `--today` overrides it. The examples use
  **2026-02-20**: order 7 is inside the 7-day return window and order 6 is outside it but under the legal warranty.
  Side effect: with that date, orders placed after 2026-02-20 look like they are in the future.
- **Receipt date.** There is no real delivery date, only `estimated_delivery`. The agent uses it as the receipt date,
  says it is an estimate and confirms it with the customer. If the customer gives another date between the purchase
  and today, it is used; if it is *later* than the estimate (which extends the deadline), the result is flagged for
  staff confirmation, and the agent neither denies nor promises the refund.
- **Deadline start dates follow the manual literally:** return window and legal warranty count from **receipt**;
  defect exchange (30 days) counts from **purchase**. For online orders, transit time uses part of those 30 days.

**Policy manual inconsistencies**
- Phone: (67) 3341-4444 (cover/company data) vs. (67) 3321-4500 (WhatsApp section) → treated as landline and
  WhatsApp, respectively.
- E-mail: `contato@emporiodamusica.com.br` vs. `contato@empóriodamusica.com.br` → the accented one is treated as a typo.
- Credit card minimum installment: the summary table says R$ 100; section 3.1 gives ranges (no minimum up to 3x,
  R$ 80 for 4–6x, R$ 100 for 7–12x) → the more specific section 3.1 prevails.
- The manual is an internal document: the agent uses it but never refers to it as "the internal manual".
- **Partner stores** for accessories are mentioned but not listed in the manual. I added two **fictional** partner
  stores to `data/policies.md`, marked as an addition that is not in the original manual.

**Data**
- **Order total:** `orders.total_brl` is the source of truth. Orders 3 and 20 don't match the sum of item prices
  (prices may have changed since).
- **Product name + specs are the source of truth** when the description contradicts them. In the bass, drum and
  keyboard categories, several descriptions mention another brand or model (e.g. "Korg Synth 1" described as a
  Roland with 88 keys while specs say 61).
- **Empty categories:** wind instruments and orchestral strings exist as categories but have no products. The agent
  says nothing is available instead of inventing items.
- **Promotions** have no dates, only `is_active`. If a product ever had two active promotions, the biggest discount
  would apply (they are not cumulative); this doesn't happen in the current data.
- **Order lookup identity:** customers 11 and 43 share the same e-mail. Since lookup is by order number and then
  checked against that order's customer, this can't leak another customer's order.

All data quirks and how each is handled: [`docs/data_exploration.md`](docs/data_exploration.md).

## Example conversations

Five conversations recorded with the real CLI (`--show-tools --today 2026-02-20`), unedited. Each file starts
with a short context line in English; the conversation itself is in Portuguese.

| File | Scenario |
|---|---|
| [`01_catalog_guitars_up_to_1000.md`](examples/01_catalog_guitars_up_to_1000.md) | Acoustic guitars up to R$ 1000, then a nylon recommendation for a beginner |
| [`02_price_expired_promotion.md`](examples/02_price_expired_promotion.md) | Price of the Takamine GD20; the customer asks about a 12% discount that is no longer active; installments |
| [`03_return_within_window.md`](examples/03_return_within_window.md) | **Non-trivial:** regret return inside the 7-day window → identity check, deadlines, support ticket with protocol |
| [`04_return_outside_window.md`](examples/04_return_outside_window.md) | **Non-trivial:** wrong e-mail rejected, right phone accepted; window expired → legal warranty explained |
| [`05_store_info_and_out_of_scope.md`](examples/05_store_info_and_out_of_scope.md) | Address and Saturday hours; accessory request (asks before suggesting partners); off-topic football question |

## Known limitations

- **Free tier quotas.** `gemini-3.5-flash` allows 20 requests/day and each turn takes 2–3 requests. I did not confirm
  the exact daily limit of `gemini-3.5-flash-lite`. The free tier also returns occasional 503 errors at peak times.
- **LLM variability.** Even with tools and a low temperature, the lite model sometimes phrases things imprecisely
  (e.g. it occasionally says "o sistema" although the prompt asks it not to). Business rules are protected by
  computing them in code, but wording is not deterministic.
- **No automated evaluation of the agent's answers.** There are 53 tests (every tool, plus the function-calling loop
  with a fake model: tool results sent back, API errors rolled back, round limit), but what the real model *says*
  was checked by running scenarios and reading the transcripts.
- **Keyword search, not semantic search.** Every meaningful word of the query must start a word in the product's
  text. There is no typo tolerance and only the few normalizations described above; for anything else the model has
  to rephrase the query or filter by category.
- **Support tickets are a local file** (`history/tickets.jsonl`), not a real helpdesk. Nobody actually receives them.
- **Holidays are unknown:** opening hours follow Campo Grande's time zone, but the agent doesn't know which days are
  holidays (when the store is closed).
- **Conversation history is saved but not reloaded:** each run starts a new conversation.
- **Identity check is basic** (no limit on attempts, no one-time code).
- **Policies were transcribed by hand:** if the manual changes, `data/policies.md` must be updated.

## What I would do with more time

- **Evaluation set:** scripted scenarios (prices, promotions, returns, out of scope) run automatically against the
  agent, with assertions on which tools were called plus an LLM-as-judge for tone and grounding.
- **Real channel:** WhatsApp or web chat integration, and tickets going to a real helpdesk with human handoff.
- **Better search:** typo tolerance, a real synonym list, or embeddings if the catalog grows to the
  "300+ instruments" the manual mentions.
- **Policies:** if the manual grew large or changed often, chunk it and use embeddings (RAG) instead of fixed topics.
- **Data layer:** SQLite or a real database instead of CSVs, with real delivery dates and dated promotions.
- **Operations:** structured logging of tool calls and latency, a holiday calendar, rate limiting for
  identity checks, resuming conversations from `history/`.

## Use of AI coding assistants

I used **Claude Code** (desktop app, Claude Opus 5.5) throughout the project. My main stack is React/TypeScript and
Python is newer to me, so I used it as a pair programmer that also explained Python by analogy to the JS ecosystem
(venv ≈ `node_modules`, `pytest` fixtures ≈ Jest's `beforeAll`, `@dataclass` ≈ a TypeScript interface with a
constructor).

How I worked with it:

- **Planning first.** Before writing code I summarized the challenge, the data and the policy manual in a handoff file
  (requirements, schedule, architecture options) and started the coding sessions from it.
- **Small steps, one commit each.** The AI wrote code in small pieces (data loader → product tools → policies →
  order tool → agent → CLI → examples), each with tests. I reviewed each step, and the AI proposed the files and the
  commit message, but only committed after my approval. Commits carry a `Co-Authored-By` trailer.
- **I made the decisions; the AI laid out the options.** For each ambiguous point it presented options with a
  recommendation, and I chose: e.g. the identity check, the "today" override, combining the delivery estimate with
  the customer's confirmation (my idea), the persona name, fictional partner stores that are only offered after
  asking the customer, and the support ticket tool.
- **It also corrected me.** I first read the 30-day defect exchange as counting from delivery; the AI checked the
  manual ("30 dias corridos após a compra") and the code follows the manual.
- **Testing with the real model surfaced real problems**, which we fixed in code rather than by editing transcripts:
  the agent inventing a "forwarding" step (→ ticket tool + prompt rule), a mixed-up date (→ explicit `starts_on`),
  and the free tier quota running out (→ model switch, clearer error logging).

The full log of what I asked the AI vs. what I decided is in [`docs/ai_usage_log.md`](docs/ai_usage_log.md).
