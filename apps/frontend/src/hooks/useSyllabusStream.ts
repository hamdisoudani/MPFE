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
 */
export function useSyllabusStream(threadId: string | undefined) {
  const { progress, onCustomEvent, reset } = useAgentProgress();

  const stream = useStream<any, { InterruptType: ClarificationInterrupt }>({
    apiUrl: LANGGRAPH_API_URL,
    assistantId: LANGGRAPH_ASSISTANT,
    threadId: threadId ?? null,
    reconnectOnMount: true,
    fetchStateHistory: false,
    onCustomEvent,
  } as any);

  return { stream, progress, resetProgress: reset };
}
