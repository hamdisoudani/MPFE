"use client";
import type { SyllabusStore } from "@/hooks/useSyllabusStore";
import { LessonBlock } from "./LessonBlock";

export function LessonDetail({ lessonId, store }: { lessonId: string; store: SyllabusStore }) {
  const lesson = store.lessons.find((l) => l.id === lessonId);
  if (!lesson) return <p className="text-sm text-fg-muted">Lesson not found.</p>;
  const chapter = store.chapters.find((c) => c.id === lesson.chapter_id);
  return (
    <article className="flex-1 overflow-y-auto">
      <header className="mb-4">
        {chapter && <p className="text-xs uppercase tracking-wide text-fg-muted">Chapter {chapter.position} · {chapter.title}</p>}
        <h2 className="mt-1 text-xl font-semibold">{lesson.title}</h2>
        {lesson.summary && <p className="mt-1 text-sm text-fg-muted">{lesson.summary}</p>}
      </header>
      <div className="rounded-2xl border border-border dark:border-border-dark bg-panel dark:bg-panel-dark p-4">
        <LessonBlock markdown={lesson.content_markdown ?? ""} />
      </div>
    </article>
  );
}
