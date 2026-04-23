"use client";
import { useState } from "react";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { cn } from "@/lib/cn";
import { Check, Loader2, CircleDashed, AlertTriangle, ChevronDown } from "lucide-react";
import { LessonBlock } from "./LessonBlock";
import { ActivityCard } from "./ActivityCard";

export function ChapterList({ store, progress }: { store: SyllabusStore; progress: AgentProgress }) {
  const { chapters, lessons, activities } = store;
  if (chapters.length === 0) {
    return <p className="text-sm text-fg-muted">Chapters will appear here once the outline is ready.</p>;
  }
  const lessonsByChapter = groupBy(lessons, (l) => l.chapter_id);
  const activitiesByChapter = groupBy(activities, (a) => a.chapter_id);

  return (
    <ul className="space-y-3">
      {chapters.map((ch) => {
        const chLessons = (lessonsByChapter.get(ch.id) ?? []).slice().sort((a, b) => a.position - b.position);
        const chActs    = (activitiesByChapter.get(ch.id) ?? []).slice().sort((a, b) => a.position - b.position);
        const isActive  = progress.activeChapter?.id === ch.id;
        return (
          <li key={ch.id} className="panel p-3 md:p-4">
            <div className="flex items-center gap-2">
              <StatusIcon status={ch.status} active={isActive} />
              <h3 className="min-w-0 truncate text-sm font-semibold md:text-base">
                {ch.position}. {ch.title}
              </h3>
              {chActs.length > 0 && (
                <span className="chip-accent ml-auto shrink-0">{chActs.length} activity</span>
              )}
            </div>
            {ch.summary && <p className="mt-1 line-clamp-2 text-xs text-fg-muted">{ch.summary}</p>}

            <ul className="mt-3 space-y-2">
              {chLessons.map((l) => {
                const activeAttempt =
                  progress.activeLesson &&
                  progress.activeLesson.chapterPos === ch.position &&
                  progress.activeLesson.position === l.position
                    ? progress.activeLesson
                    : null;
                return (
                  <LessonItem
                    key={l.id}
                    position={l.position}
                    title={l.title}
                    markdown={l.content_markdown}
                    needsReview={l.needs_review}
                    activeAttempt={activeAttempt ? { attempt: activeAttempt.attempt, status: activeAttempt.status } : null}
                  />
                );
              })}
              {isActive && progress.activeLesson &&
                !chLessons.some((l) => l.position === progress.activeLesson!.position) && (
                <li className="flex items-center gap-2 text-sm text-fg-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
                  L{progress.activeLesson.position} · {progress.activeLesson.status} · attempt {progress.activeLesson.attempt}
                </li>
              )}
            </ul>

            {chActs.length > 0 && (
              <div className="mt-3 space-y-2">
                {chActs.map((a) => <ActivityCard key={a.id} activity={a} />)}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function LessonItem({
  position, title, markdown, needsReview, activeAttempt,
}: {
  position: number; title: string; markdown: string; needsReview: boolean;
  activeAttempt: { attempt: number; status: string } | null;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-border dark:border-border-dark">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm">
        <Check className="h-3.5 w-3.5 text-accent" />
        <span className="min-w-0 truncate">L{position} · {title}</span>
        {needsReview && (
          <span className="chip-warn ml-auto shrink-0"><AlertTriangle className="h-3 w-3" /> review</span>
        )}
        {activeAttempt && (
          <span className="chip ml-auto shrink-0">attempt {activeAttempt.attempt} · {activeAttempt.status}</span>
        )}
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-fg-muted transition-transform", open && "rotate-180", needsReview || activeAttempt ? "" : "ml-auto")} />
      </button>
      {open && (
        <div className="border-t border-border dark:border-border-dark px-3 py-3">
          {markdown ? <LessonBlock markdown={markdown} /> : <p className="text-xs text-fg-muted">No content yet.</p>}
        </div>
      )}
    </li>
  );
}

function StatusIcon({ status, active }: { status: string; active: boolean }) {
  if (status === "done") return <Check className="h-4 w-4 text-accent" />;
  if (active) return <Loader2 className="h-4 w-4 animate-spin text-accent" />;
  return <CircleDashed className="h-4 w-4 text-fg-muted" />;
}

function groupBy<T, K>(arr: T[], key: (x: T) => K): Map<K, T[]> {
  const m = new Map<K, T[]>();
  for (const x of arr) {
    const k = key(x);
    (m.get(k) ?? m.set(k, []).get(k)!).push(x);
  }
  return m;
}
