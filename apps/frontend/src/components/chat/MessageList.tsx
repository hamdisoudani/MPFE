"use client";
import type { AgentProgress } from "@/hooks/useAgentProgress";

export function MessageList({
  messages, progress,
}: { messages: any[]; progress: AgentProgress }) {
  if (messages.length === 0 && progress.eventCount === 0) {
    return (
      <div className="py-8 text-center text-sm text-fg-muted">
        Describe what you want to teach below to start.
      </div>
    );
  }
  return (
    <ul className="space-y-3">
      {messages.map((m: any, i: number) => {
        const role = m.type ?? m.role ?? "ai";
        const content = typeof m.content === "string"
          ? m.content
          : Array.isArray(m.content)
            ? m.content.map((b: any) => (typeof b === "string" ? b : b.text ?? "")).join("")
            : "";
        if (!content) return null;
        return (
          <li key={m.id ?? i} className="animate-fade-in">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-fg-muted">{roleLabel(role)}</div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{content}</div>
          </li>
        );
      })}
    </ul>
  );
}

function roleLabel(role: string) {
  if (role === "human" || role === "user") return "You";
  if (role === "tool") return "Tool";
  return "Agent";
}
