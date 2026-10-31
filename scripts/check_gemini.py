"""Smoke test for the Gemini setup: is the key valid, which models can it use, does the chosen model answer?

Run from the repo root:  python scripts/check_gemini.py
"""
import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()  # reads .env into os.environ (like dotenv in Node)

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")

client = genai.Client()  # picks up GEMINI_API_KEY from the environment

print("Models available to this key that can generate text:")
for model in client.models.list():
    if "generateContent" in (model.supported_actions or []):
        print(" -", model.name.replace("models/", ""))

model_name = os.getenv("GEMINI_MODEL")
if not model_name:
    sys.exit("\nGEMINI_MODEL is empty. Pick one from the list above and set it in .env.")

print(f"\nSending a test message to {model_name}...")
response = client.models.generate_content(model=model_name, contents="Responda apenas: ok")
print("Answer:", response.text)
