"use client";
import { useState } from "react";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { PhaseBanner } from "../plan/PhaseBanner";
import { SearchStatus } from "../plan/SearchStatus";
import { SyllabusTree } from "../plan/SyllabusTree";
import { LessonDetail } from "../plan/LessonDetail";
import { ActivityDetail } from "../plan/ActivityDetail";
import { ArrowLeft } from "lucide-react";

type Selection =
  | { kind: "none" }
  | { kind: "lesson"; id: string }
  | { kind: "activity"; id: string };

export function CenterPlan({ store, progress, threadId }: {
  store: SyllabusStore; progress: AgentProgress; threadId: string | undefined; streaming?: boolean;
}) {
  const [sel, setSel] = useState<Selection>({ kind: "none" });

  if (store.loading) return <p className="px-6 py-8 text-sm text-fg-muted">Loading syllabus…</p>;
  if (!store.syllabus) {
    return (
      <div className="flex h-full min-h-[50vh] flex-col items-center justify-center px-6 text-center">
        <h2 className="text-base font-semibold">{threadId ? "Working on it…" : "No syllabus yet"}</h2>
        <p className="mt-1 max-w-sm text-sm text-fg-muted">
          {threadId ? "The agent is setting up this thread." : "Start a new syllabus using the prompt on the right."}
        </p>
      </div>
    );
  }

  if (sel.kind !== "none") {
    return (
      <div className="mx-auto flex h-full max-w-4xl flex-col px-4 py-4 md:px-6 md:py-6">
        <button onClick={() => setSel({ kind: "none" })}
                className="mb-3 inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to outline
        </button>
        {sel.kind === "lesson" && <LessonDetail lessonId={sel.id} store={store} />}
        {sel.kind === "activity" && <ActivityDetail activityId={sel.id} store={store} />}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-4 md:px-6 md:py-6">
      <h1 className="truncate text-lg font-semibold md:text-xl">{store.syllabus.title || "Untitled syllabus"}</h1>
      <p className="mt-1 line-clamp-3 text-sm text-fg-muted">{store.syllabus.requirements}</p>
      <div className="mt-4"><PhaseBanner phase={progress.phase ?? store.syllabus.phase} /></div>
      <SearchStatus progress={progress} />
      <div className="mt-6">
        <SyllabusTree store={store} progress={progress}
          onOpenLesson={(id) => setSel({ kind: "lesson", id })}
          onOpenActivity={(id) => setSel({ kind: "activity", id })}
        />
      </div>
    </div>
  );
}
