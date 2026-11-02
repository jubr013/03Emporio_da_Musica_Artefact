import Markdown from "react-markdown";

import type { ToolCall } from "../api";
import { ToolBadges } from "./ToolBadges";

export interface ChatMessage {
  id: number;
  role: "customer" | "assistant" | "error";
  text: string;
  toolCalls?: ToolCall[];
}

export function MessageBubble({ message, showTools }: { message: ChatMessage; showTools: boolean }) {
  if (message.role === "customer") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-amber-700 px-4 py-2.5 whitespace-pre-wrap text-white shadow-sm">
          {message.text}
        </p>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
        {message.text}
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <span aria-hidden="true" className="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-amber-100 text-base">
        🎸
      </span>
      <div className="max-w-[85%]">
        <div className="answer rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-stone-800 shadow-sm ring-1 ring-stone-200">
          <Markdown>{message.text}</Markdown>
        </div>
        {showTools && message.toolCalls && <ToolBadges calls={message.toolCalls} />}
      </div>
    </div>
  );
}
