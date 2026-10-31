"""Policy lookup tool. The manual is short (8 pages), so instead of embeddings/RAG
the agent asks for one topic by name and gets the whole section back.
"""
from functools import lru_cache
from pathlib import Path

POLICIES_FILE = Path(__file__).resolve().parent.parent / "data" / "policies.md"


@lru_cache(maxsize=1)
def _sections() -> dict:
    """Splits policies.md on '## <topic>' headings -> {topic: section text}."""
    sections = {}
    current_topic = None
    for line in POLICIES_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_topic = line[3:].strip()
            sections[current_topic] = []
        elif current_topic:
            sections[current_topic].append(line)
    return {topic: "\n".join(lines).strip() for topic, lines in sections.items()}


def list_policy_topics() -> list:
    return list(_sections())


def get_policy(topic: str) -> dict:
    """Returns the policy text for one topic, or the list of valid topics if it doesn't exist."""
    sections = _sections()
    if topic not in sections:
        return {"found": False, "message": f"Tópico '{topic}' não existe.", "valid_topics": list(sections)}
    return {"found": True, "topic": topic, "content": sections[topic]}
