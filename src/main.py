"""Command-line chat with melodIA.

Run from the repo root:
    python -m src.main                     # normal chat
    python -m src.main --show-tools        # also print each tool call (useful to see the agent's decisions)
    python -m src.main --today 2026-02-20  # pretend today is this date (same as STORE_TODAY in .env)

When the chat ends, the conversation is saved to history/ as JSON and as Markdown.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HISTORY_DIR = Path(__file__).resolve().parent.parent / "history"
EXIT_WORDS = {"sair", "exit", "quit", "tchau"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat with melodIA, Empório da Música's assistant.")
    parser.add_argument("--show-tools", action="store_true", help="print every tool call the agent makes")
    parser.add_argument("--today", help="date used for deadline checks (YYYY-MM-DD), overrides STORE_TODAY")
    return parser.parse_args()


def format_args(args: dict) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in args.items())


def save_transcript(transcript: list, model: str) -> Path:
    """Writes the conversation as JSON (for machines) and Markdown (for people). Returns the Markdown path."""
    HISTORY_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = HISTORY_DIR / f"conversation_{stamp}"
    store_today = os.getenv("STORE_TODAY") or "real date"

    base.with_suffix(".json").write_text(
        json.dumps({"model": model, "store_today": store_today, "messages": transcript}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [f"<!-- model: {model} | STORE_TODAY: {store_today} | saved: {stamp} -->", ""]
    for entry in transcript:
        if entry["role"] == "customer":
            lines += [f"**Cliente:** {entry['text']}", ""]
        elif entry["role"] == "tool":
            lines += [f"> 🔧 `{entry['name']}({format_args(entry['args'])})`", ""]
        else:
            lines += [f"**melodIA:** {entry['text']}", ""]
    markdown_path = base.with_suffix(".md")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_path


def main() -> None:
    # Windows terminals may default to a legacy encoding; force UTF-8 so accents and emojis print correctly
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    args = parse_args()
    if args.today:
        os.environ["STORE_TODAY"] = args.today
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is missing. Copy .env.example to .env and add your key (see README).")

    from src.agent import Agent  # imported after load_dotenv so the SDK sees the key

    transcript = []

    def on_tool_call(name: str, call_args: dict, result: dict) -> None:
        transcript.append({"role": "tool", "name": name, "args": call_args, "result": result})
        if args.show_tools:
            print(f"   🔧 {name}({format_args(call_args)})")

    agent = Agent(on_tool_call=on_tool_call)
    print("🎸 Empório da Música — converse com a melodIA. Digite 'sair' para encerrar.\n")

    while True:
        try:
            # lstrip removes the invisible BOM some Windows shells add when text is piped in
            message = input("Você: ").strip().lstrip("﻿")
        except (EOFError, KeyboardInterrupt):  # Ctrl+D / Ctrl+C end the chat gracefully
            print()
            break
        if not message:
            continue
        if message.lower() in EXIT_WORDS:
            break

        transcript.append({"role": "customer", "text": message})
        answer = agent.send(message)
        transcript.append({"role": "assistant", "text": answer})
        print(f"\nmelodIA: {answer}\n")

    if transcript:
        path = save_transcript(transcript, agent.model)
        print(f"Conversa salva em {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    print("Até mais! 🎶")


if __name__ == "__main__":
    main()
