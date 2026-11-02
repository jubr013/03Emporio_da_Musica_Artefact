import type { ToolCall } from "../api";
import { toolLabel, type ToolKind } from "../toolLabels";

const STYLES: Record<ToolKind, string> = {
  data: "bg-sky-50 text-sky-800 ring-sky-200",
  policy: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  action: "bg-violet-50 text-violet-800 ring-violet-200",
};

const ICONS: Record<ToolKind, string> = { data: "🔎", policy: "📋", action: "📝" };

export function ToolBadges({ calls }: { calls: ToolCall[] }) {
  if (calls.length === 0) {
    return <p className="mt-2 text-xs text-stone-400">Respondeu sem consultar dados ou políticas</p>;
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
