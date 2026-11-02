import { useState, type FormEvent, type KeyboardEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  onSend: (message: string) => void;
}

const MAX_LENGTH = 2000; // same limit as the API

export function Composer({ disabled, onSend }: ComposerProps) {
  const [text, setText] = useState("");
  const canSend = !disabled && text.trim().length > 0;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line (like most chat apps)
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <label htmlFor="message" className="sr-only">
        Sua mensagem
      </label>
      <textarea
        id="message"
        rows={1}
        value={text}
        maxLength={MAX_LENGTH}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escreva sua mensagem…"
        className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-neutral-300 bg-white px-4 py-2.5 text-neutral-800 shadow-sm outline-none focus:border-red-600 focus:ring-2 focus:ring-red-100"
      />
      <button
        type="submit"
        disabled={!canSend}
        className="h-11 rounded-xl bg-red-600 px-5 font-medium text-white shadow-sm transition hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
      >
        Enviar
      </button>
    </form>
  );
}
