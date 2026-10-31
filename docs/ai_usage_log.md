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
