"""Small HTTP API so the optional web UI (web/) can talk to the same agent the CLI uses.

Run from the repo root:
    uvicorn src.api:app --port 8000

Endpoints:
    GET  /api/health -> {"status": "ok", "model": ...}
    POST /api/chat   -> body {"message": "...", "session_id": optional, "today": optional "YYYY-MM-DD"}
                        returns {"session_id", "answer", "tool_calls": [{"name", "args"}]}
    DELETE /api/chat/{session_id} -> ends a conversation

Designed for local use by one person: conversations live in memory and requests are handled one at a time.
"""
import os
import threading
import uuid
from datetime import date
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()  # before creating any Agent, so the SDK sees GEMINI_API_KEY

from src.agent import Agent  # noqa: E402

MAX_SESSIONS = 50  # oldest conversation is dropped beyond this (memory guard for a long-running server)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None
    today: Optional[date] = None  # same as STORE_TODAY / --today in the CLI


class ToolCall(BaseModel):
    name: str
    args: dict


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_calls: list[ToolCall]


def create_app(agent_factory: Callable[..., Agent] = Agent) -> FastAPI:
    """Builds the app. Tests pass an `agent_factory` that returns agents with a fake model."""
    app = FastAPI(title="Empório da Música - melodIA API")
    sessions: dict[str, Agent] = {}  # session_id -> Agent (insertion order = age)
    env_today = os.getenv("STORE_TODAY")  # value from .env, used when the UI doesn't send a date
    # STORE_TODAY is a process-wide setting and the agent keeps per-conversation state, so one request at a time
    lock = threading.Lock()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")}

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="Mensagem vazia.")

        with lock:
            session_id = request.session_id if request.session_id in sessions else str(uuid.uuid4())
            if session_id not in sessions:
                if len(sessions) >= MAX_SESSIONS:
                    sessions.pop(next(iter(sessions)))  # drop the oldest conversation
                sessions[session_id] = agent_factory()
            agent = sessions[session_id]

            tool_calls: list[ToolCall] = []
            agent.on_tool_call = lambda name, args, result: tool_calls.append(ToolCall(name=name, args=args))

            today = request.today.isoformat() if request.today else env_today
            if today:
                os.environ["STORE_TODAY"] = today
            else:
                os.environ.pop("STORE_TODAY", None)
            answer = agent.send(message)

        return ChatResponse(session_id=session_id, answer=answer, tool_calls=tool_calls)

    @app.delete("/api/chat/{session_id}")
    def end_chat(session_id: str) -> dict:
        with lock:
            removed = sessions.pop(session_id, None) is not None
        return {"removed": removed}

    return app


app = create_app()
