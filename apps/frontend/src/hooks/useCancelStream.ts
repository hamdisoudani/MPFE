"use client";
import { useCallback, useState } from "react";
import { langgraph } from "@/lib/langgraph";

/** Actually cancels the run server-side (stream.stop() only closes the socket). */
export function useCancelStream() {
  const [cancelling, setCancelling] = useState(false);
  const cancel = useCallback(async (threadId: string, runId: string) => {
    if (!runId) return;
    setCancelling(true);
    try {
      await langgraph().runs.cancel(threadId, runId, true);
    } finally {
      setCancelling(false);
    }
  }, []);
  return { cancel, cancelling };
}
