export function TypingIndicator() {
  return (
    <div className="flex items-center gap-3" role="status">
      <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-amber-100 text-base">
        🎸
      </span>
      <span className="flex gap-1 rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ring-stone-200">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-2 animate-bounce rounded-full bg-stone-400"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
        <span className="sr-only">melodIA está digitando…</span>
      </span>
    </div>
  );
}
