"use client";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { useCancelStream } from "@/hooks/useCancelStream";
import { useDraftStorage } from "@/hooks/useDraftStorage";
import { ClarifyForm } from "../forms/ClarifyForm";
import { MessageList } from "../chat/MessageList";
import { Composer } from "../chat/Composer";
import { AgentStepCard } from "../chat/AgentStepCard";
import { StopCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { useEffect, useMemo, useRef } from "react";

export function AgentPane({ stream, progress, threadId }: {
  stream: any; progress: AgentProgress; threadId: string | undefined;
}) {
  const { draft, setDraft, clearDraft } = useDraftStorage(threadId);
  const { cancel, cancelling } = useCancelStream();
  const isStreaming = Boolean(stream?.isLoading);
  const interrupt = stream?.interrupt?.value;
  const activeRunId = stream?.run?.run_id ?? stream?.values?._run_id;
  const rawMessages: any[] = stream?.messages ?? [];

  const feed = useMemo(() => buildFeed(rawMessages, progress), [rawMessages, progress.timeline, progress.eventCount]);
  const activeStepId = progress.timeline.length ? progress.timeline[progress.timeline.length - 1].id : null;

  const scrollerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollerRef.current; if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [feed.length, isStreaming, interrupt]);

  const submitFollowup = async () => {
    const text = draft.trim(); if (!text) return;
    clearDraft();
    try {
      await stream.submit({ messages: [{ type: "human", content: text }] }, { streamMode: ["values", "custom"] });
    } catch (e) { console.error(e); }
  };
  const submitClarify = async (answers: Record<string, unknown>) => {
    await stream.submit(undefined, { command: { resume: answers }, streamMode: ["values", "custom"] });
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-panel dark:bg-panel-dark border-l border-border dark:border-border-dark">
      <header className="flex items-center justify-between border-b border-border dark:border-border-dark px-3 py-2">
        <div className="flex items-center gap-2 text-xs">
          <span className={cn("h-2 w-2 rounded-full", isStreaming ? "bg-accent animate-pulse" : interrupt ? "bg-warn" : "bg-fg-muted/40")} />
          <span className="text-fg-muted">
            {interrupt ? "waiting for input" : isStreaming ? "agent working" : "idle"} · {progress.eventCount} events
          </span>
        </div>
        {isStreaming && activeRunId && threadId && (
          <button className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-err" disabled={cancelling}
                  onClick={() => cancel(threadId, activeRunId)}>
            <StopCircle className="h-3.5 w-3.5" /> Stop
          </button>
        )}
      </header>

      <div ref={scrollerRef} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {feed.length === 0 && !isStreaming && (
          <p className="py-8 text-center text-xs text-fg-muted">The conversation will appear here.</p>
        )}
        {feed.map((item) => {
          if (item.kind === "message") {
            return <MessageList key={item.key} messages={[item.message]} />;
          }
          return <AgentStepCard key={item.key} step={item.step} active={item.step.id === activeStepId && isStreaming} />;
        })}

        {isStreaming && (
          <div className="flex items-center gap-2 rounded-xl border border-border dark:border-border-dark bg-bg dark:bg-bg-dark px-3 py-2 text-xs text-fg-muted animate-fade-in">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> streaming…
          </div>
        )}

        {interrupt?.kind === "clarification" && (
          <div className="animate-slide-in"><ClarifyForm interrupt={interrupt} onSubmit={submitClarify} /></div>
        )}

        {progress.errors.length > 0 && (
          <div className="rounded-xl border border-err/40 bg-err-soft dark:bg-err/10 p-2 text-xs text-err">
            {progress.errors.slice(-1).map((e, i) => (<div key={i}><strong>{e.node}:</strong> {e.message}</div>))}
          </div>
        )}
      </div>

      {!interrupt && threadId && (
        <Composer draft={draft} setDraft={setDraft} disabled={isStreaming} onSubmit={submitFollowup} variant="inline" />
      )}
    </div>
  );
}

type FeedItem =
  | { kind: "message"; key: string; at: number; message: any }
  | { kind: "step"; key: string; at: number; step: any };

function buildFeed(messages: any[], progress: AgentProgress): FeedItem[] {
  const userMsgs = messages.filter((m: any) => {
    const r = (m?.type ?? m?.role ?? "").toString().toLowerCase();
    return r === "human" || r === "user";
  }).map((m: any, i: number): FeedItem => ({
    kind: "message", key: `m-${m.id ?? i}`, at: messageAt(m, i), message: m,
  }));
  const steps: FeedItem[] = progress.timeline.map((s): FeedItem => ({ kind: "step", key: `s-${s.id}`, at: s.at, step: s }));
  return [...userMsgs, ...steps].sort((a, b) => a.at - b.at);
}
function messageAt(m: any, i: number): number {
  const t = m?.created_at ?? m?.createdAt;
  if (t) { const v = new Date(t).getTime(); if (!Number.isNaN(v)) return v; }
  return Date.now() - (1e9 - i);
}
