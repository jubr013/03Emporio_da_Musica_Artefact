# Empório da Música — Customer Service Agent

Prototype of a text-based customer service agent for Empório da Música, a fictional musical
instrument store in Campo Grande/MS. Built for the Artefact AI Engineer technical challenge.

> Work in progress. Full instructions, design decisions and limitations will be added here.

## Requirements

- Python 3.12 (developed and tested with 3.12.10)
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## How to run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the API key
cp .env.example .env            # then paste your key after GEMINI_API_KEY=

# 4. (Optional) check that the key and model work
python scripts/check_gemini.py

# 5. Chat with the agent
python -m src.main
```

CLI options:

| Option | What it does |
|---|---|
| `--show-tools` | Prints every tool call, so you can see when the agent looks up data or policies |
| `--today YYYY-MM-DD` | Pretends today is this date for return/warranty deadlines (same as `STORE_TODAY` in `.env`). The example conversations use `--today 2026-02-20` |

Type `sair` (or press Ctrl+C) to end the chat. The conversation is saved to `history/` as JSON and Markdown.

Run the tests (no API key needed):

```bash
python -m pytest -q
```
