"use client";
import { useState } from "react";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { ChevronRight, Folder, FolderOpen, FileText, Sparkles, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export function SyllabusTree({ store, progress, onOpenLesson, onOpenActivity }: {
  store: SyllabusStore;
  progress: AgentProgress;
  onOpenLesson: (id: string) => void;
  onOpenActivity: (id: string) => void;
}) {
  const chapters = [...store.chapters].sort((a, b) => a.position - b.position);
  const activeChapterId = progress.activeChapter?.id ?? null;

  if (chapters.length === 0) {
    return <div className="rounded-xl border border-dashed border-border dark:border-border-dark p-6 text-center text-sm text-fg-muted">The outline will appear here as soon as it's drafted.</div>;
  }
  return (
    <ul className="space-y-1">
      {chapters.map((c) => (
        <ChapterRow key={c.id} chapter={c} store={store}
          active={c.id === activeChapterId}
          onOpenLesson={onOpenLesson} onOpenActivity={onOpenActivity} />
      ))}
    </ul>
  );
}

function ChapterRow({ chapter, store, active, onOpenLesson, onOpenActivity }: any) {
  const [open, setOpen] = useState(true);
  const lessons = store.lessons.filter((l: any) => l.chapter_id === chapter.id).sort((a: any, b: any) => a.position - b.position);
  const activities = store.activities.filter((a: any) => a.chapter_id === chapter.id).sort((a: any, b: any) => (a.position ?? 0) - (b.position ?? 0));
  const writing = chapter.status === "writing";
  return (
    <li>
      <button onClick={() => setOpen((o) => !o)}
        className={cn(
          "group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors",
          "hover:bg-panel dark:hover:bg-panel-dark",
          active && "ring-1 ring-accent/40 bg-accent/5",
        )}>
        <ChevronRight className={cn("h-3.5 w-3.5 text-fg-muted transition-transform", open && "rotate-90")} />
        {open ? <FolderOpen className="h-4 w-4 text-accent" /> : <Folder className="h-4 w-4 text-fg-muted" />}
        <span className="text-xs tabular-nums text-fg-muted w-6">{String(chapter.position).padStart(2, "0")}</span>
        <span className="truncate text-sm font-medium">{chapter.title}</span>
        {writing && <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-accent" />}
        {!writing && <span className="ml-auto text-[10px] uppercase tracking-wide text-fg-muted">{chapter.status}</span>}
      </button>
      {open && (
        <ul className="ml-6 mt-0.5 space-y-0.5 border-l border-border dark:border-border-dark pl-3">
          {lessons.length === 0 && <li className="py-1 text-xs text-fg-muted italic">No lessons yet</li>}
          {lessons.map((l: any) => (
            <li key={l.id}>
              <button onClick={() => onOpenLesson(l.id)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-panel dark:hover:bg-panel-dark">
                <FileText className="h-3.5 w-3.5 text-fg-muted" />
                <span className="text-xs tabular-nums text-fg-muted w-6">{String(l.position).padStart(2, "0")}</span>
                <span className="truncate text-sm">{l.title}</span>
                {l.needs_review && <span className="ml-auto text-[10px] text-warn">review</span>}
              </button>
            </li>
          ))}
          {activities.map((a: any) => (
            <li key={a.id}>
              <button onClick={() => onOpenActivity(a.id)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-panel dark:hover:bg-panel-dark">
                <Sparkles className="h-3.5 w-3.5 text-accent" />
                <span className="truncate text-sm">{a.payload?.title ?? a.kind ?? "Activity"}</span>
                <span className="ml-auto text-[10px] uppercase tracking-wide text-fg-muted">{a.kind ?? "quiz"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
