"use client";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import type { AgentProgress } from "@/hooks/useAgentProgress";
import { PhaseBanner } from "../plan/PhaseBanner";
import { ChapterList } from "../plan/ChapterList";
import { SearchStatus } from "../plan/SearchStatus";
import { AgentTimeline } from "../plan/AgentTimeline";

export function CenterPlan({
  store, progress, threadId, streaming = false,
}: { store: SyllabusStore; progress: AgentProgress; threadId: string | undefined; streaming?: boolean }) {
  if (store.loading) return <p className="px-6 py-8 text-sm text-fg-muted">Loading syllabus…</p>;
  if (!store.syllabus) {
    return (
      <div className="flex h-full min-h-[50vh] flex-col items-center justify-center px-6 text-center">
        <h2 className="text-base font-semibold">
          {threadId ? "Working on it…" : "No syllabus yet"}
        </h2>
        <p className="mt-1 max-w-sm text-sm text-fg-muted">
          {threadId
            ? "The agent is setting up this thread. The plan will appear here once research starts."
            : "Start a new syllabus using the prompt on the right."}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-4 md:px-6 md:py-6">
      <h1 className="truncate text-lg font-semibold md:text-xl">
        {store.syllabus.title || "Untitled syllabus"}
      </h1>
      <p className="mt-1 line-clamp-3 text-sm text-fg-muted">{store.syllabus.requirements}</p>

      <div className="mt-4">
        <PhaseBanner phase={progress.phase ?? store.syllabus.phase} />
      </div>

      <SearchStatus progress={progress} />

      <div className="mt-4">
        <AgentTimeline progress={progress} streaming={streaming} />
      </div>

      <div className="mt-6">
        <ChapterList store={store} progress={progress} />
      </div>
    </div>
  );
}
