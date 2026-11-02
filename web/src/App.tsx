import { useEffect, useRef, useState } from "react";

import { endConversation, sendMessage } from "./api";
import { Composer } from "./components/Composer";
import { MessageBubble, type ChatMessage } from "./components/MessageBubble";
import { TypingIndicator } from "./components/TypingIndicator";

// The challenge's suggested scenarios, as one-click starters
const SUGGESTIONS = [
  "Quais opções de violões disponíveis custando até R$1000?",
  "Qual o endereço da loja?",
  "Quanto custa o Takamine GD20?",
  "Me arrependi da minha compra, posso devolver meu pedido?",
];

const SERVER_ERROR =
  "Não consegui falar com o servidor da melodIA. Confira se a API está rodando " +
  "(uvicorn src.api:app --port 8000) e tente de novo.";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showTools, setShowTools] = useState(true);
  const [today, setToday] = useState(""); // empty = real date
  const nextId = useRef(1);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Follow the conversation as new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function addMessage(message: Omit<ChatMessage, "id">) {
    setMessages((current) => [...current, { ...message, id: nextId.current++ }]);
  }

  async function handleSend(text: string) {
    addMessage({ role: "customer", text });
    setLoading(true);
    try {
      const response = await sendMessage({ message: text, sessionId, today: today || null });
      setSessionId(response.session_id);
      addMessage({ role: "assistant", text: response.answer, toolCalls: response.tool_calls });
    } catch {
      addMessage({ role: "error", text: SERVER_ERROR });
    } finally {
      setLoading(false);
    }
  }

  function handleNewConversation() {
    if (sessionId) void endConversation(sessionId);
    setSessionId(null);
    setMessages([]);
  }

  return (
    <div className="flex h-dvh flex-col bg-stone-100">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold text-stone-900">Empório da Música</h1>
            <p className="text-sm text-stone-500">Converse com a melodIA, nossa assistente virtual</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label className="flex items-center gap-2 text-stone-600">
              <input
                type="checkbox"
                checked={showTools}
                onChange={(event) => setShowTools(event.target.checked)}
                className="size-4 accent-amber-700"
              />
              Mostrar consultas
            </label>
            <label className="flex items-center gap-2 text-stone-600" title="Vazio = data real. Os exemplos usam 20/02/2026.">
              Data simulada
              <input
                type="date"
                value={today}
                onChange={(event) => setToday(event.target.value)}
                className="rounded-md border border-stone-300 px-2 py-1 text-stone-800"
              />
            </label>
            <button
              type="button"
              onClick={handleNewConversation}
              disabled={loading}
              className="rounded-md border border-stone-300 px-3 py-1 text-stone-700 hover:bg-stone-50 disabled:opacity-40"
            >
              Nova conversa
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6" aria-live="polite">
          {messages.length === 0 && (
            <section className="rounded-2xl bg-white p-6 text-center shadow-sm ring-1 ring-stone-200">
              <p className="text-3xl" aria-hidden="true">🎸</p>
              <h2 className="mt-2 text-lg font-semibold text-stone-900">Oi! Eu sou a melodIA.</h2>
              <p className="mt-1 text-stone-600">
                Posso te ajudar com instrumentos, preços, pedidos, trocas e informações da loja.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSend(suggestion)}
                    className="rounded-full bg-amber-50 px-3 py-1.5 text-sm text-amber-900 ring-1 ring-amber-200 hover:bg-amber-100"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </section>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} showTools={showTools} />
          ))}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="border-t border-stone-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <Composer disabled={loading} onSend={handleSend} />
        </div>
      </footer>
    </div>
  );
}
