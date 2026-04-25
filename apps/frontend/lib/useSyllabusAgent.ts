"use client";
import { useMemo } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import {
  LANGGRAPH_API_URL,
  langgraphHeaders,
  assistantIdFor,
  type AgentVariant,
} from "@/providers/client";
import { useThreadMessagesCache } from "@/stores/thread-messages-cache";

type StreamOpts = {
  threadId?: string | null;
  onThreadId?: (id: string) => void;
  /**
   * Picked at thread creation and stored in `thread.metadata.variant`.
   * Cannot change for an existing thread.
   */
  variant?: AgentVariant | null;
};

export function useSyllabusAgent({ threadId, onThreadId, variant }: StreamOpts = {}) {
  const assistantId = assistantIdFor(variant ?? "classic");

  // If we have a cached messages snapshot for this thread, seed the stream
  // with it via `initialValues` so the transcript paints immediately on
  // reload — `useStream` will then rejoin the live SSE stream and overlay
  // any deltas on top. This avoids the "blank chat on reload" behavior.
  const cachedEntry = useThreadMessagesCache((s) =>
    threadId ? s.entries[threadId] : undefined
  );
  const cachedMessages = cachedEntry?.messages;

  const options = useMemo(() => {
    const base: any = {
      apiUrl: LANGGRAPH_API_URL,
      assistantId,
      messagesKey: "messages" as const,
      reconnectOnMount: true,
      // Always fetch state history — this is what populates `stream.messages`
      // for the existing thread on mount. Setting it false and relying only
      // on `initialValues` leaves the hook with an empty messages array
      // once the live stream swaps in, which was causing reloads to paint
      // blank until the next supervisor turn.
      fetchStateHistory: true,
      defaultHeaders: langgraphHeaders(),
      onThreadId,
      initialValues: cachedMessages
        ? { messages: cachedMessages }
        : undefined,
    };
    return threadId ? { ...base, threadId } : base;
  }, [assistantId, cachedMessages, threadId, onThreadId]);

  return useStream<{ messages: any[] }>(options as any);
}
