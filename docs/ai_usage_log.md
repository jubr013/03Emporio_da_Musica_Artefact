# AI assistant usage log

Running log for the README section "Use of coding assistants". Tool: Claude Code (Claude Opus).

| Date | Asked the AI | Decided by me |
|---|---|---|
| 2026-10-31 | Scaffold the repo (folders, `.gitignore`, `requirements.txt`, `.env.example`) | Repo layout, single-agent + function calling, pandas in memory |
| 2026-10-31 | Write an exploration script and summarize data quirks | Which quirks matter and how to handle them (see `docs/data_exploration.md`) |
| 2026-10-31 | Compare Gemini vs OpenAI; set up the SDK and a key smoke test | Gemini free tier (zero cost for me and reviewers), using the new `google-genai` SDK instead of the deprecated `google-generativeai` |
| 2026-10-31 | Write `src/data_loader.py` and its pytest tests | Load everything in memory with pandas; normalize text/phones/emails at load time |
| 2026-10-31 | Write product tools (`search_products`, `get_product_details`) and tests | Scope for the session (orders/policies left for Monday); price filters use the final price |
| 2026-10-31 | Transcribe the policy PDF into `data/policies.md` (one section per topic) and write `get_policy` | No RAG/embeddings for 8 pages; how to resolve the manual's inconsistencies (phone, e-mail, installments) |
| 2026-10-31 | Propose options for the order tool (today's date, identity check, receipt date, who computes deadlines) | All four choices; receipt date combining the estimate with the customer's confirmation was my idea (see `docs/decisions.md`) |
| 2026-11-02 | Implement `get_order_status` from those decisions, with tests | Reviewed the deadline rules against the policy manual |
| 2026-11-02 | Write the agent loop and system prompt; run real conversations against Gemini | Manual loop, persona name "melodIA", fictional partner stores offered only after asking the customer |
| 2026-11-02 | AI flagged that the agent invented a "forwarding" step in a test conversation | Add a support-ticket tool instead of just telling the customer to call the store |
| 2026-11-02 | Write the CLI (`src/main.py`) and the README run instructions | Save each conversation as JSON + Markdown so the example conversations come straight from real runs |
| 2026-11-02 | Run the 5 example scenarios through the real CLI, diagnose the 429 quota error, review each transcript | Switch to `gemini-3.5-flash-lite`; which scenarios to show |
| 2026-11-02 | AI caught a wrong purchase date in one transcript and traced it to the tool output | Add `starts_on` to each deadline and re-record that conversation instead of editing it |
| 2026-11-02 | Draft the full README from `docs/` (decisions, data notes, this log) | Reviewed the content; assumptions and limitations reflect my choices |
| 2026-11-02 | Suggest what to improve with the extra day, with cost and risk | Picked agent loop tests, store time zone and search improvements; skipped UI and RAG |
| 2026-11-02 | Measure failing searches and fix them; tests caught "aço" matching "braço" | Fix only measured failures, keep keyword search |
| 2026-11-02 | Review the known limitations and estimate which are worth fixing | Looked up the real quota in AI Studio myself; chose holidays, identity attempt limit and evaluation |
| 2026-11-02 | Verify Campo Grande holidays on the web, write the calendar, attempt limit and evaluation script | First evaluation failed 1/14: fix the prompt, not the test |
| 2026-11-02 | Re-record the 5 examples with the final prompt and review them | Re-record instead of keeping old ones; fix the partial-list and refund-start issues the review found |
| 2026-11-02 | Go through every known limitation with cost, risk and a recommendation | Do: grounded recommendations, fallback model, multi-run evaluation, PDF check, model codes in search. Don't: per-order lock, holiday library, conversation reload, real helpdesk |
| 2026-11-02 | AI argued against fuzzy search (the LLM already fixes typos) and against a per-order lock (lets anyone block someone else's order) | Accepted both: smaller search fix, lock left as a documented trade-off |
| 2026-11-02 | Assess whether a React UI is worth it with the remaining time | Build it as an optional extra on a separate branch, local only, merged only after my approval |
| 2026-11-02 | Write the FastAPI endpoint, the React/TS/Tailwind UI and their tests; test end to end in the browser | UI shows the agent's lookups as labels; simulated date field |
| 2026-11-02 | Clean-clone test following only the README | `python` on my machine is 3.9, so the README now creates the venv with `py -3.12` / `python3.12` and says 3.9 doesn't work |
| 2026-11-03 | Review the repo against the e-mail, the challenge and the job description | Fix the gaps found (fake "close the order" offer, tickets on unverified orders, history rollback) |
| 2026-11-03 | I went through the policy manual section by section; for each one the AI said what was covered, where, and what was missing | Decided each point: hours/next opening, installments, preference exchange (7 days from receipt), metro region = IBGE immediate region, free delivery from R$ 500,00 inclusive, warranty, privacy requests |
| 2026-11-03 | Ask if the Correios API could quote shipping | Not used: needs a Correios contract and the products have no weight/dimensions; documented as future work |
| 2026-11-03 | Full evaluation failed 73/81; a prompt-only fix made the agent invent products | Move alternatives, price formatting and a forbidden-phrase check into code; final full run 27/27 |
