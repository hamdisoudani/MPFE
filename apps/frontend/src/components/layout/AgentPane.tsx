"use client";
import { useState } from "react";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { useCancelStream } from "@/hooks/useCancelStream";
import { useDraftStorage } from "@/hooks/useDraftStorage";
import { ClarifyForm } from "../forms/ClarifyForm";
import { MessageList } from "../chat/MessageList";
import { Composer } from "../chat/Composer";
import { StopCircle } from "lucide-react";
import { cn } from "@/lib/cn";

export function AgentPane({
  stream, progress, threadId, onThreadCreated,
}: {
  stream: any;
  progress: AgentProgress;
  threadId: string | undefined;
  onThreadCreated: (id: string) => void;
}) {
  const { draft, setDraft, clearDraft } = useDraftStorage(threadId);
  const { cancel, cancelling } = useCancelStream();
  const [title, setTitle] = useState("");

  const isStreaming = Boolean(stream?.isLoading);
  const interrupt = stream?.interrupt?.value;
  const activeRunId = stream?.run?.run_id ?? stream?.values?._run_id;

  const submitStart = async () => {
    const text = draft.trim();
    if (!text) return;
    clearDraft();
    try {
      await stream.submit(
        { requirements: text, title: title || undefined },
        { streamMode: ["values", "messages-tuple", "custom"] }
      );
      if (!threadId && stream.thread?.thread_id) onThreadCreated(stream.thread.thread_id);
    } catch (e) { console.error(e); }
  };

  const submitClarify = async (answers: Record<string, unknown>) => {
    await stream.submit(undefined, { command: { resume: answers }, streamMode: ["values","messages-tuple","custom"] });
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-panel dark:bg-panel-dark">
      <header className="flex items-center justify-between border-b border-border dark:border-border-dark px-3 py-2">
        <div className="flex items-center gap-2 text-sm">
          <span className={cn("dot", isStreaming ? "text-accent" : "text-fg-muted")} />
          <span className="text-fg-muted">
            {isStreaming ? "agent working" : "idle"} · {progress.eventCount} events
          </span>
        </div>
        {isStreaming && activeRunId && threadId && (
          <button className="btn-ghost text-xs" disabled={cancelling}
                  onClick={() => cancel(threadId, activeRunId)}>
            <StopCircle className="h-3.5 w-3.5" /> Stop
          </button>
        )}
      </header>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <MessageList messages={stream?.messages ?? []} progress={progress} />

        {interrupt?.kind === "clarification" && (
          <div className="mt-4 animate-slide-in">
            <ClarifyForm interrupt={interrupt} onSubmit={submitClarify} />
          </div>
        )}

        {progress.errors.length > 0 && (
          <div className="mt-3 rounded-xl border border-err/40 bg-err-soft dark:bg-err/10 p-2 text-xs text-err">
            {progress.errors.slice(-1).map((e, i) => (
              <div key={i}><strong>{e.node}:</strong> {e.message}</div>
            ))}
          </div>
        )}
      </div>

      {!interrupt && (
        <Composer
          draft={draft} setDraft={setDraft}
          title={title} setTitle={setTitle}
          showTitle={!threadId}
          disabled={isStreaming}
          onSubmit={submitStart}
        />
      )}
    </div>
  );
}
