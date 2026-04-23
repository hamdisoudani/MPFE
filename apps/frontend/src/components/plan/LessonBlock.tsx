"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Markdown } from "@/components/chat/Markdown";

const BlockNoteView = dynamic(() => import("./LessonBlockNoteView").then((m) => m.LessonBlockNoteView), {
  ssr: false,
  loading: () => <div className="py-3 text-xs text-fg-muted">Loading editor…</div>,
});

export function LessonBlock({ markdown }: { markdown: string }) {
  const [useBN, setUseBN] = useState(false);
  useEffect(() => { setUseBN(true); }, []);
  if (!useBN) return <Markdown>{markdown}</Markdown>;
  return <BlockNoteView markdown={markdown} />;
}
