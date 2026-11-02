import type { ToolCall } from "../api";
import { toolLabel, type ToolKind } from "../toolLabels";

// Kept within the palette (black, white, gray, red); the icon also tells the kinds apart
const STYLES: Record<ToolKind, string> = {
  data: "bg-white text-neutral-800 ring-neutral-300",
  policy: "bg-neutral-800 text-white ring-neutral-800",
  action: "bg-red-50 text-red-700 ring-red-200",
};

const ICONS: Record<ToolKind, string> = { data: "🔎", policy: "📋", action: "📝" };

export function ToolBadges({ calls }: { calls: ToolCall[] }) {
  if (calls.length === 0) {
    return <p className="mt-2 text-xs text-neutral-400">Respondeu sem consultar dados ou políticas</p>;
  }
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Consultas feitas pela melodIA">
      {calls.map((call, index) => {
        const label = toolLabel(call);
        return (
          <li key={index} className={`rounded-full px-2 py-0.5 text-xs ring-1 ring-inset ${STYLES[label.kind]}`}>
            <span aria-hidden="true">{ICONS[label.kind]} </span>
            {label.text}
          </li>
        );
      })}
    </ul>
  );
}
