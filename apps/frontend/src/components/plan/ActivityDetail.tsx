"use client";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import { ActivityCard } from "./ActivityCard";

export function ActivityDetail({ activityId, store }: { activityId: string; store: SyllabusStore }) {
  const activity = store.activities.find((a) => a.id === activityId);
  if (!activity) return <p className="text-sm text-fg-muted">Activity not found.</p>;
  const chapter = store.chapters.find((c) => c.id === activity.chapter_id);
  return (
    <article className="flex-1 overflow-y-auto">
      <header className="mb-4">
        {chapter && <p className="text-xs uppercase tracking-wide text-fg-muted">Chapter {chapter.position} · {chapter.title}</p>}
        <h2 className="mt-1 text-xl font-semibold">{activity.payload?.title ?? activity.payload?.kind ?? "Activity"}</h2>
      </header>
      <ActivityCard activity={activity} />
    </article>
  );
}
