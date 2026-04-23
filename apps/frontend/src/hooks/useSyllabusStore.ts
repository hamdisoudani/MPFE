"use client";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabase";
import type { Activity, Chapter, Lesson, Syllabus } from "@/lib/types";

export interface SyllabusStore {
  syllabus: Syllabus | null;
  chapters: Chapter[];
  lessons: Lesson[];
  activities: Activity[];
  loading: boolean;
  error: string | null;
}

/**
 * Live view of syllabus/chapters/lessons/activities for a given threadId.
 * Combines a one-shot fetch + Supabase Realtime subscription. Works across
 * reloads because Postgres is the source of truth (no missed events).
 */
export function useSyllabusStore(threadId: string | undefined): SyllabusStore {
  const [store, setStore] = useState<SyllabusStore>({
    syllabus: null, chapters: [], lessons: [], activities: [],
    loading: Boolean(threadId), error: null,
  });

  useEffect(() => {
    if (!threadId) {
      setStore({ syllabus: null, chapters: [], lessons: [], activities: [], loading: false, error: null });
      return;
    }
    let cancelled = false;
    const sb = supabase();

    (async () => {
      try {
        const { data: syllabus } = await sb.from("syllabuses").select("*").eq("thread_id", threadId).maybeSingle();
        if (cancelled || !syllabus) {
          if (!cancelled) setStore((s) => ({ ...s, loading: false }));
          return;
        }
        const [{ data: chapters }, { data: lessons }, { data: activities }] = await Promise.all([
          sb.from("chapters").select("*").eq("syllabus_id", syllabus.id).order("position"),
          sb.from("lessons").select("*").eq("syllabus_id", syllabus.id).order("position"),
          sb.from("activities").select("*").eq("syllabus_id", syllabus.id).order("position"),
        ]);
        if (cancelled) return;
        setStore({
          syllabus: syllabus as Syllabus,
          chapters: (chapters ?? []) as Chapter[],
          lessons:  (lessons  ?? []) as Lesson[],
          activities: (activities ?? []) as Activity[],
          loading: false, error: null,
        });
      } catch (e: any) {
        if (!cancelled) setStore((s) => ({ ...s, loading: false, error: e?.message ?? "Failed to load" }));
      }
    })();

    return () => { cancelled = true; };
  }, [threadId]);

  // Realtime subscription (scoped to this syllabus_id once we know it)
  useEffect(() => {
    const syllabusId = store.syllabus?.id;
    if (!syllabusId) return;
    const sb = supabase();
    const channel = sb
      .channel(`syllabus:${syllabusId}`)
      .on("postgres_changes",
          { event: "*", schema: "public", table: "syllabuses", filter: `id=eq.${syllabusId}` },
          (p) => setStore((s) => ({ ...s, syllabus: (p.new as Syllabus) ?? s.syllabus })))
      .on("postgres_changes",
          { event: "*", schema: "public", table: "chapters", filter: `syllabus_id=eq.${syllabusId}` },
          (p) => setStore((s) => ({ ...s, chapters: upsertById(s.chapters, p.new as Chapter, p.eventType) })))
      .on("postgres_changes",
          { event: "*", schema: "public", table: "lessons", filter: `syllabus_id=eq.${syllabusId}` },
          (p) => setStore((s) => ({ ...s, lessons: upsertById(s.lessons, p.new as Lesson, p.eventType) })))
      .on("postgres_changes",
          { event: "*", schema: "public", table: "activities", filter: `syllabus_id=eq.${syllabusId}` },
          (p) => setStore((s) => ({ ...s, activities: upsertById(s.activities, p.new as Activity, p.eventType) })))
      .subscribe();
    return () => { sb.removeChannel(channel); };
  }, [store.syllabus?.id]);

  return store;
}

function upsertById<T extends { id: string; position?: number }>(list: T[], next: T | undefined,
                                                                  kind: string): T[] {
  if (!next || !next.id) return list;
  if (kind === "DELETE") return list.filter((x) => x.id !== next.id);
  const idx = list.findIndex((x) => x.id === next.id);
  const out = idx === -1 ? [...list, next] : list.map((x) => (x.id === next.id ? { ...x, ...next } : x));
  return out.sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
}
