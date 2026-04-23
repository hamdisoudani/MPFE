"use client";
import { useEffect, useState } from "react";

const KEY = (threadId: string | undefined) => `mpfe:draft:${threadId ?? "new"}`;

/** Persists the composer draft across reloads. Ported from open-swe. */
export function useDraftStorage(threadId: string | undefined) {
  const storageKey = KEY(threadId);
  const [draft, setDraft] = useState<string>("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    try { setDraft(window.localStorage.getItem(storageKey) ?? ""); }
    catch { /* ignore */ }
  }, [storageKey]);

  const update = (v: string) => {
    setDraft(v);
    try { window.localStorage.setItem(storageKey, v); } catch { /* ignore */ }
  };
  const clear = () => {
    setDraft("");
    try { window.localStorage.removeItem(storageKey); } catch { /* ignore */ }
  };
  return { draft, setDraft: update, clearDraft: clear };
}
