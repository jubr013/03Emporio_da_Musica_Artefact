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

- [Requirements](#requirements) · [How to run](#how-to-run) · [Optional web UI](#optional-web-ui)
- [How it works](#how-it-works) · [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Assumptions](#assumptions)
- [Example conversations](#example-conversations) · [Evaluation](#evaluation)
- [Known limitations](#known-limitations) · [What I would do with more time](#what-i-would-do-with-more-time)
- [Use of AI coding assistants](#use-of-ai-coding-assistants)

## Requirements

- Python 3.12 (developed and tested with 3.12.10). Python 3.9 does **not** work: the `google-genai` 2.x SDK
  doesn't support it.
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) (no credit card needed)
- Only for the optional web UI: Node.js 22.12+ (tested with 26.13)

## How to run

```bash
# 1. Create and activate a virtual environment with Python 3.12
#    (if `python --version` shows another version, create the venv with the launcher below)
py -3.12 -m venv .venv          # Windows
# python3.12 -m venv .venv      # macOS / Linux
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

> If PowerShell refuses to run `activate` (execution policy), you can skip activation and call the venv's Python
> directly: `.venv\Scripts\python -m src.main`.

To reproduce the return scenarios of the examples:

```bash
python -m src.main --show-tools --today 2026-02-20
```

Run the tests (no API key needed: the tools are tested directly, the agent loop and the web API with a fake model):

```bash
python -m pytest -q
```

Evaluate the agent against the real model (15 scripted scenarios, ~40 requests of the free quota per run; see
[Evaluation](#evaluation)):

```bash
python scripts/evaluate_agent.py            # 1 run
python scripts/evaluate_agent.py --runs 3   # 3 runs per scenario, reports a pass rate (~120 requests)
```

Environment variables (`.env`):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Your Gemini API key (required) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model name. `python scripts/check_gemini.py` lists the models your key can use |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.1-flash-lite` | Used automatically if the main model's daily quota runs out (empty disables it) |
| `STORE_TODAY` | empty (real date) | Overrides "today" for deadline checks |

### Optional: web UI

A small React + TypeScript + Tailwind chat on top of the same agent, for local use. The CLI above is all the challenge
needs; this is an extra. It shows, under each answer, **which lookups the agent made** (🔎 data, 📋 policy,
📝 support ticket), and has a "Data simulada" field that does the same as `--today`.

Requires Node.js 22.12+ (tested with 26.13; Vitest, used by the frontend tests, needs 22.12+). Run in two terminals,
from the repo root:

```bash
# Terminal 1: Python API (same venv as above)
python -m uvicorn src.api:app --port 8000

# Terminal 2: web app
cd web
npm install
npm run dev                     # then open http://localhost:5173
```

The web app forwards `/api` to the Python API (`web/vite.config.ts`). Frontend tests: `npm test` inside `web/`.
Conversations in the web UI live in the API's memory only (they are not saved to `history/` like the CLI's).

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
│   ├── api.py                 # small FastAPI app for the optional web UI (same Agent)
│   ├── agent.py               # function-calling loop, tool declarations, error handling
│   ├── prompts.py             # system prompt: melodIA persona, when to use each tool, store rules
│   ├── tools.py               # data tools (products, orders, tickets) over pandas
│   ├── policies.py            # policy lookup by topic
│   ├── store_calendar.py      # holidays (store closed): national, MS state and Campo Grande
│   └── data_loader.py         # loads and cleans the CSVs once
├── tests/                     # pytest: every tool, the agent loop and the web API with a fake model (no API
│                              # calls), and the policy transcription checked against the original PDF
├── examples/                  # 5 example conversations recorded from real runs
├── scripts/
│   ├── evaluate_agent.py      # scripted scenarios against the real model -> docs/evaluation.md
│   ├── check_gemini.py        # smoke test for the API key and model
│   └── explore_data.py        # data exploration checks
├── web/                       # optional React + TypeScript + Tailwind chat UI (Vite, Vitest)
└── docs/
    ├── evaluation.md          # latest evaluation report
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
- Temperature 0: customer service needs consistent, factual answers, not creative ones.
- **Fallback model:** if the main model's daily quota runs out (429 even after the SDK's retries), the agent switches
  to `gemini-3.1-flash-lite`, which has its own free quota, for the rest of the conversation, so an evaluator
  doesn't hit a dead end.

### Retrieval: pandas for data, sectioned Markdown for policies (no RAG)

- **CSVs → pandas in memory.** Under 200 rows in total; a database or a SQL agent would be overkill. Data is
  loaded and cleaned once (`src/data_loader.py`): JSON specs parsed, accent-free search text, normalized e-mails and
  phones, parsed dates.
- **Keyword search tuned on the real data.** I measured which customer-style queries failed and fixed only those:
  words that exist only in the specs are added to the search text (3 steel-string guitars never say "aço", 2 with a
  pickup never say "eletroacústico"); words match at the **start** of a word, so "aço" no longer matches "braço"
  ("braco" without accents) while "baixo" still matches "baixos"; "-ões" plurals match "-ão"; spelled-out numbers
  become digits ("sete cordas" → "7 cordas"); filler words ("de", "com", "até", "cordas") are ignored; model codes are
  glued together, so "GD 20", "GD-20" and "GD20" all find the Takamine GD20. I did not add typo tolerance: the LLM
  writes the search query, so it already fixes customer typos ("takamini" → "takamine"); what it doesn't fix is how
  a model code is formatted.
- **Policies → `get_policy(topic)` over a Markdown file split by topic.** The manual is 8 pages. Embeddings and a
  vector store would add moving parts and make retrieval fuzzy, while a fixed list of topics (sent to the model as
  an `enum`) makes it explicit **when** the agent consults policies, which is one of the challenge's goals.
  I transcribed the PDF by hand instead of extracting it with code because plain-text extraction flattens the tables
  (hours, payment, shipping) into run-on lines; a test checks the transcription against the PDF (see
  [Known limitations](#known-limitations)).

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
  (`America/Campo_Grande`, UTC-4), not the clock of whatever machine runs the agent. **Holidays** (store closed) are
  computed in code (`src/store_calendar.py`: national, Mato Grosso do Sul and Campo Grande holidays, with Good Friday
  derived from Easter) and the prompt says whether today is a holiday and which ones are coming in the next two weeks.
  Optional days ("ponto facultativo", e.g. Carnival, Corpus Christi) are treated as regular days.
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
- After **3 failed verifications** in the same conversation, order lookups are blocked and the customer is sent to the
  team's WhatsApp, so contact details can't be guessed by trial and error. The counter lives in the agent (the
  conversation), because the tool itself is stateless.

### Interface and conversation history

- **CLI** as the main interface: the challenge focuses on the agent, not the UI.
- **Optional web UI** (`web/`), because the role is full-stack and React/TypeScript is my main stack. It is
  deliberately thin: a FastAPI endpoint (`src/api.py`) reuses the same `Agent`, keeps one conversation per browser
  session in memory and handles one request at a time (it's meant for local use by one person). The UI's main
  feature is showing the agent's decisions, i.e. which data or policy lookups each answer is based on.
- **History in memory** during the session (the model needs it to follow the conversation). When a CLI chat ends, it
  is saved to `history/` as JSON (full, with tool results) and Markdown (readable). The example conversations come
  straight from these files. Web UI conversations stay in the API's memory only.

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
- Refund "em até 10 dias úteis": the manual doesn't say from when the 10 business days count. The agent states the
  10 days and doesn't specify the start, instead of guessing (an early version said "after the product arrives back
  at the store", which is not in the policy).
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
| [`01_catalog_guitars_up_to_1000.md`](examples/01_catalog_guitars_up_to_1000.md) | Acoustic guitars up to R$ 1000 (shows 10 of 12 and says so), then a nylon recommendation for a beginner grounded in the product descriptions |
| [`02_price_expired_promotion.md`](examples/02_price_expired_promotion.md) | Price of the Takamine GD20; the customer asks about a 12% discount that is no longer active; installments |
| [`03_return_within_window.md`](examples/03_return_within_window.md) | **Non-trivial:** regret return inside the 7-day window → identity check, deadlines, support ticket with protocol |
| [`04_return_outside_window.md`](examples/04_return_outside_window.md) | **Non-trivial:** wrong e-mail rejected, right phone accepted; window expired → legal warranty explained |
| [`05_store_info_and_out_of_scope.md`](examples/05_store_info_and_out_of_scope.md) | Address and Saturday hours; accessory request (asks before suggesting partners); off-topic football question |

## Evaluation

Two layers of tests:

1. **Unit tests (`python -m pytest -q`, 119 tests, no API key; plus 11 frontend tests with `npm test` in `web/`).**
   Every tool (search, prices and promotions, order lookup and deadlines, tickets, policies, holidays, time zone),
   the policy transcription against the original PDF, the web API, and the function-calling loop itself, using a fake
   model built from the SDK's real types: tool results go back with the right id, API errors roll back the turn, the
   round limit holds, order lookups are blocked after 3 failed verifications, and the fallback model takes over when
   the quota runs out. The frontend tests mock the API (messages, lookup labels, session, simulated date, errors).
2. **Scenario evaluation against the real model (`python scripts/evaluate_agent.py`).** 15 scripted customer
   messages. For each one the script checks **which tools were called** (data vs. policy vs. none), key **tool
   arguments** (e.g. the price filter), text that **must** appear (correct price, PIX price, deadline, tracking code)
   and text that **must not** appear (a discount that isn't active, an invented price for a product the store doesn't
   have, another customer's data, partner stores before the customer asks). The report goes to
   [`docs/evaluation.md`](docs/evaluation.md).

The first run passed 13/14: in the return scenario the agent applied the rule correctly but didn't say the deadline
date and added a condition that is not in the policy ("after the product arrives and is inspected"). I fixed the
prompt (always state the deadline; never add conditions the policy doesn't have), not the test, and the next run
passed **14/14**.

Re-recording the example conversations with that prompt showed two more issues, both fixed: the agent presented
10 of 12 search results as the full list (the search tool now returns `showing` / `more_available`, and the prompt
requires saying when there are more), and it still guessed when the refund period starts (see
[Assumptions](#assumptions)). Its recommendations also included sales talk not supported by the data ("recommended
by music teachers"); the prompt now requires recommendations grounded in the product data, temperature went to 0,
and a 15th scenario checks for that.

Since the model is not deterministic, the final evaluation runs **every scenario 3 times**:
**45/45 runs passed** (report in [`docs/evaluation.md`](docs/evaluation.md)). That is good evidence the agent behaves
as intended, not a guarantee that it always will.

## Known limitations

- **Free tier quotas.** On my account's AI Studio rate-limit page (checked 2026-11-02), `gemini-3.5-flash-lite` allows
  **15 requests/minute and 500/day**; `gemini-3.5-flash` (served as Gemini 3.6 Flash) only 5/minute and 20/day.
  Each agent turn takes 2–3 requests, so the default model allows roughly 200 turns a day; when its daily quota runs
  out, the agent falls back to `gemini-3.1-flash-lite` (another 500/day). Limits can differ per account and change
  over time. The free tier also returns occasional 503 errors at peak times (retried automatically).
- **LLM variability.** Wording is not deterministic. During development the lite model said "o sistema" and added
  sales talk not in the data ("recommended by music teachers"); prompt rules, temperature 0 and a dedicated evaluation
  scenario now cover these, and the last evaluation passed 45/45 runs, but a rare unsupported phrase can still slip
  through. Business rules (prices, deadlines, identity) don't depend on wording: they are computed in code.
- **The evaluation is small and string-based.** 15 scenarios × 3 runs, checked with tool names, key arguments and
  required / forbidden text. It catches wrong tools, wrong numbers, leaks and known bad phrases, but not tone or new
  kinds of wording problems.
- **Keyword search, not semantic search.** Every meaningful word of the query must start a word in the product's
  text. There is no typo tolerance and only the few normalizations described above; for anything else the model has
  to rephrase the query or filter by category.
- **Support tickets are a local file** (`history/tickets.jsonl`), not a real helpdesk. Nobody actually receives them.
- **Holiday list is maintained by hand.** It covers national, MS state and Campo Grande holidays from official and
  local calendars; a change in the law, or the store's "extended hours" on special dates (policy 2), would need an
  update.
- **Conversation history is saved but not reloaded:** each CLI run starts a new conversation.
- **The web UI is a local extra:** one person, one request at a time, conversations kept in the API's memory (lost
  when it restarts and not saved to `history/`), no authentication, no deployment.
- **Identity check is basic:** order number + e-mail or phone, at most 3 failed attempts per conversation; there is
  no one-time code, and a new conversation resets the counter. I deliberately did not lock the **order** after failed
  attempts: anyone could then block another customer's order just by typing wrong e-mails. In a real channel the
  limit would be per origin (the customer's WhatsApp number), which a CLI doesn't have.
- **Policies were transcribed by hand.** A test reads the original PDF and checks that 26 key facts (deadlines,
  amounts, hours, contacts) appear identically in `data/policies.md`, so a changed manual makes the test fail; but
  rewording that keeps the numbers would not be detected.

## What I would do with more time

- **Stronger evaluation:** more scenarios (multi-turn ones included), an LLM-as-judge for tone and grounding, and
  running it in CI on every prompt change.
- **Answer self-check:** a second, cheap model call that checks each answer against the tool results before it is
  sent (catches unsupported claims), at the cost of double the requests and latency.
- **Real channel:** WhatsApp integration or a deployed web chat (the current UI runs locally only), and tickets going
  to a real helpdesk with human handoff.
- **Better search:** typo tolerance, a real synonym list, or embeddings if the catalog grows to the
  "300+ instruments" the manual mentions.
- **Policies:** if the manual grew large or changed often, chunk it and use embeddings (RAG) instead of fixed topics.
- **Data layer:** SQLite or a real database instead of CSVs, with real delivery dates and dated promotions.
- **Operations:** structured logging of tool calls and latency, identity checks limited per customer rather than per
  conversation, resuming conversations from `history/`.

## Use of AI coding assistants

I used **Claude Code** (desktop app, Claude Opus 5.5) throughout the project. My main stack is React/TypeScript and
Python is newer to me, so I used it as a pair programmer that also explained Python by analogy to the JS ecosystem
(venv ≈ `node_modules`, `pytest` fixtures ≈ Jest's `beforeAll`, `@dataclass` ≈ a TypeScript interface with a
constructor).

How I worked with it:

- **Planning first.** Before writing code I summarized the challenge, the data and the policy manual in a handoff file
  (requirements, schedule, architecture options) and started the coding sessions from it.
- **Small steps, one commit each.** The AI wrote code in small pieces (data loader → product tools → policies →
  order tool → agent → CLI → examples → evaluation → optional web UI), each with tests. I reviewed each step, and the
  AI proposed the files and the commit message, but only committed after my approval. Commits carry a
  `Co-Authored-By` trailer. The web UI was built on a separate branch and merged only after I tested and approved it.
- **It weighed costs, I chose scope.** When I had extra time, it listed each known limitation with cost, risk and a
  recommendation; I picked what to fix and what to leave documented (e.g. it argued against fuzzy search and against
  locking an order after failed attempts, and I agreed).
- **I made the decisions; the AI laid out the options.** For each ambiguous point it presented options with a
  recommendation, and I chose: e.g. the identity check, the "today" override, combining the delivery estimate with
  the customer's confirmation (my idea), the persona name, fictional partner stores that are only offered after
  asking the customer, and the support ticket tool.
- **It also corrected me.** I first read the 30-day defect exchange as counting from delivery; the AI checked the
  manual ("30 dias corridos após a compra") and the code follows the manual.
- **Testing with the real model surfaced real problems**, which we fixed in code rather than by editing transcripts:
  the agent inventing a "forwarding" step (→ ticket tool + prompt rule), a mixed-up date (→ explicit `starts_on`),
  the free tier quota running out (→ model switch, fallback model, clearer error logging), a missing deadline plus an
  invented condition caught by the scenario evaluation (→ prompt rules), a partial list presented as complete
  (→ `more_available`), and recommendations not grounded in the data (→ prompt rule + evaluation scenario).
- **A clean-clone test** following only the README found that `python` on my machine is 3.9, which breaks the
  install; the README now creates the venv with Python 3.12 explicitly.

The full log of what I asked the AI vs. what I decided is in [`docs/ai_usage_log.md`](docs/ai_usage_log.md).
