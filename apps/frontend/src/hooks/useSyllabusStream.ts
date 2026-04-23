"use client";
import { useStream } from "@langchain/langgraph-sdk/react";
import { LANGGRAPH_API_URL, LANGGRAPH_ASSISTANT } from "@/lib/env";
import { useAgentProgress } from "./useAgentProgress";
import type { ClarificationInterrupt } from "@/lib/types";

/**
 * Wraps @langchain/langgraph-sdk useStream with:
 *  - reconnectOnMount: true  → rejoins active run on page reload
 *  - fetchStateHistory: false → no expensive history fetch on mount
 *  - onCustomEvent → feeds the useAgentProgress reducer
 *  - onError      → swallow 404s (stale thread ids from URL) and surface other errors
 */
export function useSyllabusStream(
  threadId: string | undefined,
  onMissingThread?: () => void,
) {
  const { progress, onCustomEvent, reset } = useAgentProgress();

  const stream = useStream<any, { InterruptType: ClarificationInterrupt }>({
    apiUrl: LANGGRAPH_API_URL,
    assistantId: LANGGRAPH_ASSISTANT,
    threadId: threadId ?? null,
    reconnectOnMount: true,
    fetchStateHistory: false,
    onCustomEvent,
    onError: (err: unknown) => {
      const msg = (err as any)?.message ?? String(err);
      if (/404|not.*found/i.test(msg) && onMissingThread) {
        onMissingThread();
        return;
      }
      console.error("[syllabus-stream]", err);
    },
  } as any);

  return { stream, progress, resetProgress: reset };
}
