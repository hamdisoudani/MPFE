"use client";
import { memo, useMemo } from "react";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { Markdown } from "./Markdown";
import { cn } from "@/lib/cn";
import { Loader2 } from "lucide-react";

const QUIET_PHASES = new Set(["done", "awaiting_input", "failed"]);

export function MessageList({
  messages, progress, streaming,
}: { messages: any[]; progress: AgentProgress; streaming: boolean }) {
  const agentQuiet = !progress.phase || QUIET_PHASES.has(progress.phase) || !streaming;

  const visible = useMemo(() => {
    const out: Array<{ id: string; role: "user" | "agent"; content: string }> = [];
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      const role = normalizeRole(m);
      const content = normalizeContent(m).trim();
      if (!content) continue;
      if (role === "agent" && !agentQuiet) continue;
      out.push({ id: m.id ?? String(i), role: role === "user" ? "user" : "agent", content });
    }
    return out;
  }, [messages, agentQuiet]);

  if (visible.length === 0 && progress.eventCount === 0 && !streaming) {
    return (
      <div className="py-8 text-center text-sm text-fg-muted">
        The conversation will appear here.
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {visible.map((m) => (
        <Bubble key={m.id} role={m.role} content={m.content} />
      ))}
      {streaming && !agentQuiet && (
        <li className="flex justify-start animate-fade-in">
          <div className="flex items-center gap-2 rounded-2xl border border-border dark:border-border-dark bg-panel dark:bg-panel-dark px-3 py-2 text-xs text-fg-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> working…
          </div>
        </li>
      )}
    </ul>
  );
}

const Bubble = memo(function Bubble({ role, content }: { role: "user" | "agent"; content: string }) {
  const isUser = role === "user";
  return (
    <li className={cn("flex animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-relaxed",
          isUser
            ? "bg-accent text-accent-fg dark:bg-fg-dark dark:text-bg-dark"
            : "bg-panel dark:bg-panel-dark border border-border dark:border-border-dark"
        )}
      >
        {isUser ? <p className="whitespace-pre-wrap">{content}</p> : <Markdown>{content}</Markdown>}
      </div>
    </li>
  );
});

function normalizeRole(m: any): "user" | "agent" | "tool" {
  const r = (m.type ?? m.role ?? "ai").toString().toLowerCase();
  if (r === "human" || r === "user") return "user";
  if (r === "tool") return "tool";
  return "agent";
}

function normalizeContent(m: any): string {
  if (typeof m.content === "string") return m.content;
  if (Array.isArray(m.content)) {
    return m.content
      .map((b: any) => (typeof b === "string" ? b : b?.text ?? b?.content ?? ""))
      .filter(Boolean)
      .join("");
  }
  return "";
}
