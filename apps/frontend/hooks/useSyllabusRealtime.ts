"use client";
import { useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";
import {
  fetchSyllabusByThread,
  fetchChaptersForSyllabus,
  fetchLessonsForSyllabus,
  fetchActivitiesForSyllabus,
} from "@/lib/curriculumApi";
import { useSyllabusStore } from "@/store/syllabusStore";

/**
 * Subscribe the browser to realtime updates for a single thread's curriculum.
 *
 * Flow:
 *  1. Build one Supabase channel and register all `postgres_changes` handlers
 *     BEFORE calling `.subscribe()` (Supabase rejects late handler adds).
 *  2. Fetch the syllabus row for this thread -> hydrate store.
 *  3. Fetch chapters / lessons / activities for that syllabus -> hydrate.
 *  4. `.subscribe()` once hydration resolves (or is cancelled).
 *
 * Topic uses a per-mount random suffix so rapid remounts (StrictMode double-
 * invoke, HMR, threadId flips) never reuse a still-subscribed channel.
 */
export function useSyllabusRealtime(threadId: string | null | undefined) {
  const applyRemoteSyllabus = useSyllabusStore((s) => s.applyRemoteSyllabus);
  const removeSyllabusById = useSyllabusStore((s) => s.removeSyllabusById);
  const applyRemoteChapter = useSyllabusStore((s) => s.applyRemoteChapter);
  const removeChapterById = useSyllabusStore((s) => s.removeChapterById);
  const applyRemoteLesson = useSyllabusStore((s) => s.applyRemoteLesson);
  const removeLessonById = useSyllabusStore((s) => s.removeLessonById);
  const applyRemoteActivity = useSyllabusStore((s) => s.applyRemoteActivity);
  const removeActivityById = useSyllabusStore((s) => s.removeActivityById);
  const hydrate = useSyllabusStore((s) => s.hydrate);
  const setCurrentThread = useSyllabusStore((s) => s.setCurrentThread);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const syllabusIdRef = useRef<string | null>(null);

  useEffect(() => {
    setCurrentThread(threadId ?? null);
    if (!threadId) return;
    const supa = getSupabase();
    if (!supa) return;

    let cancelled = false;
    const topicSuffix =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2);
    const topic = `curriculum:${threadId}:${topicSuffix}`;

    const channel = supa
      .channel(topic)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "syllabuses",
          filter: `thread_id=eq.${threadId}`,
        },
        (payload) => {
          if (payload.eventType === "DELETE") {
            const old = payload.old as { id?: string };
            if (old?.id) removeSyllabusById(old.id);
          } else {
            const row = payload.new as any;
            if (row?.id) {
              syllabusIdRef.current = row.id;
              applyRemoteSyllabus(row);
            }
          }
        }
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "chapters" },
        (payload) => {
          const synId = syllabusIdRef.current;
          const newRow = payload.new as any;
          const oldRow = payload.old as any;
          const belongs = (r: any) => r && synId && r.syllabus_id === synId;
          if (payload.eventType === "DELETE") {
            if (belongs(oldRow) && oldRow.id) removeChapterById(oldRow.id);
          } else if (belongs(newRow)) {
            applyRemoteChapter(newRow);
          }
        }
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "lessons" },
        (payload) => {
          const synId = syllabusIdRef.current;
          const newRow = payload.new as any;
          const oldRow = payload.old as any;
          const belongs = (r: any) => r && synId && r.syllabus_id === synId;
          if (payload.eventType === "DELETE") {
            if (belongs(oldRow) && oldRow.id) removeLessonById(oldRow.id);
          } else if (belongs(newRow)) {
            applyRemoteLesson(newRow);
          }
        }
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "activities" },
        (payload) => {
          const synId = syllabusIdRef.current;
          const newRow = payload.new as any;
          const oldRow = payload.old as any;
          const belongs = (r: any) => r && synId && r.syllabus_id === synId;
          if (payload.eventType === "DELETE") {
            if (belongs(oldRow) && oldRow.id) removeActivityById(oldRow.id);
          } else if (belongs(newRow)) {
            applyRemoteActivity(newRow);
          }
        }
      );

    channelRef.current = channel;

    (async () => {
      try {
        const syl = await fetchSyllabusByThread(threadId);
        if (cancelled) return;
        if (!syl) {
          hydrate({ syllabus: null, chapters: [], lessons: [], activities: [] });
        } else {
          syllabusIdRef.current = syl.id;
          const [chapters, lessons, activities] = await Promise.all([
            fetchChaptersForSyllabus(syl.id),
            fetchLessonsForSyllabus(syl.id),
            fetchActivitiesForSyllabus(syl.id),
          ]);
          if (cancelled) return;
          hydrate({ syllabus: syl, chapters, lessons, activities });
        }
      } catch (err) {
        // swallow — realtime still works, next poke will repair the tree
        // eslint-disable-next-line no-console
        console.warn("[useSyllabusRealtime] hydrate failed", err);
      } finally {
        if (!cancelled) channel.subscribe();
      }
    })();

    return () => {
      cancelled = true;
      if (channelRef.current) {
        supa.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [threadId, applyRemoteSyllabus, removeSyllabusById, applyRemoteChapter, removeChapterById, applyRemoteLesson, removeLessonById, applyRemoteActivity, removeActivityById, hydrate, setCurrentThread]);
}
