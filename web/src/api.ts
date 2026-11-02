// Client for the Python API (src/api.py). In development Vite forwards /api to http://127.0.0.1:8000.

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  tool_calls: ToolCall[];
}

export interface ChatRequest {
  message: string;
  sessionId: string | null;
  today: string | null; // "YYYY-MM-DD" or null for the real date
}

export async function sendMessage({ message, sessionId, today }: ChatRequest): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, today }),
  });
  if (!response.ok) {
    throw new Error(`API respondeu ${response.status}`);
  }
  return response.json();
}

export async function endConversation(sessionId: string): Promise<void> {
  // Best effort: if the server is down there is nothing to clean up anyway
  await fetch(`/api/chat/${sessionId}`, { method: "DELETE" }).catch(() => undefined);
}
