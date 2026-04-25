"use client";
import { getSupabase } from "./supabase";
import type { Activity, Chapter, Lesson, Syllabus } from "@/store/syllabusStore";

/**
 * Read helpers for the MPFE curriculum tables.
 * All writes go through the agent (curriculum-mcp / exec_commit_*) — the
 * frontend is read-only except for learner-driven navigation state.
 * Realtime subscriptions stream changes via `useSyllabusRealtime`.
 */

function sb() {
  const c = getSupabase();
  if (!c) throw new Error("Supabase client unavailable (missing env vars).");
  return c;
}

export async function fetchSyllabusByThread(threadId: string): Promise<Syllabus | null> {
  const { data, error } = await sb()
    .from("syllabuses")
    .select("id, thread_id, title, description")
    .eq("thread_id", threadId)
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return (data as Syllabus) ?? null;
}

export async function fetchChaptersForSyllabus(syllabusId: string): Promise<Chapter[]> {
  const { data, error } = await sb()
    .from("chapters")
    .select("id, syllabus_id, title, summary, position, status")
    .eq("syllabus_id", syllabusId)
    .order("position", { ascending: true });
  if (error) throw error;
  return (data as Chapter[]) ?? [];
}

export async function fetchLessonsForSyllabus(syllabusId: string): Promise<Lesson[]> {
  const { data, error } = await sb()
    .from("lessons")
    .select(
      "id, chapter_id, syllabus_id, title, position, content_markdown, substep_id, needs_review, draft_attempts"
    )
    .eq("syllabus_id", syllabusId)
    .order("position", { ascending: true });
  if (error) throw error;
  return (data as Lesson[]) ?? [];
}

export async function fetchActivitiesForSyllabus(syllabusId: string): Promise<Activity[]> {
  const { data, error } = await sb()
    .from("activities")
    .select(
      "id, chapter_id, syllabus_id, lesson_id, title, position, payload, substep_id, draft_attempts"
    )
    .eq("syllabus_id", syllabusId)
    .order("position", { ascending: true });
  if (error) throw error;
  return (data as Activity[]) ?? [];
}

export async function fetchLessonById(lessonId: string): Promise<Lesson | null> {
  const { data, error } = await sb()
    .from("lessons")
    .select(
      "id, chapter_id, syllabus_id, title, position, content_markdown, substep_id, needs_review, draft_attempts"
    )
    .eq("id", lessonId)
    .maybeSingle();
  if (error) throw error;
  return (data as Lesson) ?? null;
}
