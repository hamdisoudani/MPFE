"use client";
import { memo, useMemo } from "react";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { Markdown } from "./Markdown";
import { cn } from "@/lib/cn";

export function MessageList({ messages }: { messages: any[] }) {
  const visible = useMemo(() => filterConversational(messages), [messages]);
  if (visible.length === 0) return null;
  return (
    <ul className="space-y-3">
      {visible.map((m) => <Bubble key={m.id} role={m.role} content={m.content} />)}
    </ul>
  );
}

const Bubble = memo(function Bubble({ role, content }: { role: "user" | "agent"; content: string }) {
  const isUser = role === "user";
  return (
    <li className={cn("flex animate-fade-in", isUser ? "justify-end" : "justify-start")}>
      <div className={cn(
        "max-w-[92%] rounded-2xl px-3 py-2 text-sm leading-relaxed",
        isUser
          ? "bg-accent text-accent-fg dark:bg-fg-dark dark:text-bg-dark"
          : "bg-panel dark:bg-panel-dark border border-border dark:border-border-dark",
      )}>
        {isUser ? <p className="whitespace-pre-wrap">{content}</p> : <Markdown>{content}</Markdown>}
      </div>
    </li>
  );
});

function filterConversational(messages: any[]): Array<{ id: string; role: "user" | "agent"; content: string }> {
  const out: Array<{ id: string; role: "user" | "agent"; content: string }> = [];
  messages.forEach((m, i) => {
    const role = normalizeRole(m);
    if (role === "tool") return;
    const hasToolCalls = Boolean(
      (Array.isArray(m?.tool_calls) && m.tool_calls.length) ||
      (Array.isArray(m?.additional_kwargs?.tool_calls) && m.additional_kwargs.tool_calls.length)
    );
    if (role === "agent" && hasToolCalls) return;
    const content = normalizeContent(m).trim();
    if (!content) return;
    if (role === "agent" && looksStructured(content)) return;
    out.push({ id: m.id ?? String(i), role, content });
  });
  return out;
}

function normalizeRole(m: any): "user" | "agent" | "tool" {
  const r = (m?.type ?? m?.role ?? "ai").toString().toLowerCase();
  if (r === "human" || r === "user") return "user";
  if (r === "tool") return "tool";
  return "agent";
}

function normalizeContent(m: any): string {
  const c = m?.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) return c.map((b: any) => (typeof b === "string" ? b : b?.text ?? "")).filter(Boolean).join("");
  return "";
}

function looksStructured(content: string): boolean {
  const t = content.trimStart();
  if (!t) return true;
  if (t[0] === "{" || t[0] === "[") return true;
  if (/"(chapters|lessons|activities|findings_summary|questions|title|goal|summary|learning_objective)"\s*:/.test(content)) return true;
  if (/^```json/i.test(t)) return true;
  return false;
}
