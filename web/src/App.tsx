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
  const scrollAreaRef = useRef<HTMLElement>(null);

  // Follow the conversation as new messages arrive. Only the messages area scrolls, to its very end
  // (scrollIntoView would also move the page itself and align the last element to the top).
  useEffect(() => {
    const area = scrollAreaRef.current;
    area?.scrollTo({ top: area.scrollHeight, behavior: "smooth" });
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
    <div className="flex h-dvh flex-col bg-neutral-100">
      <header className="border-b-2 border-red-600 bg-neutral-950 text-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">
              Empório da Música<span className="text-red-500">.</span>
            </h1>
            <p className="text-sm text-neutral-400">Converse com a melodIA, nossa assistente virtual</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-neutral-300">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showTools}
                onChange={(event) => setShowTools(event.target.checked)}
                className="size-4 accent-red-600"
              />
              Mostrar consultas
            </label>
            <label className="flex items-center gap-2" title="Vazio = data real. Os exemplos usam 20/02/2026.">
              Data simulada
              <input
                type="date"
                value={today}
                onChange={(event) => setToday(event.target.value)}
                className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-white [color-scheme:dark] focus:border-red-500 focus:outline-none"
              />
            </label>
            <button
              type="button"
              onClick={handleNewConversation}
              disabled={loading}
              className="rounded-md border border-neutral-600 px-3 py-1 text-white hover:border-red-500 hover:text-red-400 disabled:opacity-40"
            >
              Nova conversa
            </button>
          </div>
        </div>
      </header>

      <main ref={scrollAreaRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6" aria-live="polite">
          {messages.length === 0 && (
            <section className="rounded-2xl bg-white p-6 text-center shadow-sm ring-1 ring-neutral-200">
              <p className="text-3xl" aria-hidden="true">🎸</p>
              <h2 className="mt-2 text-lg font-semibold text-neutral-900">Oi! Eu sou a melodIA.</h2>
              <p className="mt-1 text-neutral-600">
                Posso te ajudar com instrumentos, preços, pedidos, trocas e informações da loja.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSend(suggestion)}
                    className="rounded-full bg-white px-3 py-1.5 text-sm text-neutral-800 ring-1 ring-neutral-300 hover:text-red-700 hover:ring-red-500"
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
        </div>
      </main>

      <footer className="border-t border-neutral-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <Composer disabled={loading} onSend={handleSend} />
        </div>
      </footer>
    </div>
  );
}
