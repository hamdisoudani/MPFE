"use client";
import { useCallback, useRef, useState } from "react";
import type { AgentEvent, Phase } from "@/lib/types";

export interface AgentProgress {
  phase: Phase | null;
  searchProgress: { done: number; total: number; findings: number } | null;
  activeChapter: { id: string; position: number; title: string } | null;
  activeLesson: {
    substepId: string; chapterPos: number; position: number;
    attempt: number; status: "drafting" | "critiquing";
    lastScore?: number; lastPassed?: boolean; weaknesses?: string[];
  } | null;
  lastCommitted: { lessonId: string; needsReview: boolean; attempts: number } | null;
  lastActivity: { chapterId: string; lessonId: string | null; count: number } | null;
  errors: Array<{ node: string; message: string; at: number }>;
  eventCount: number;
}

const initial: AgentProgress = {
  phase: null, searchProgress: null, activeChapter: null, activeLesson: null,
  lastCommitted: null, lastActivity: null, errors: [], eventCount: 0,
};

export function reduceEvent(prev: AgentProgress, evt: AgentEvent): AgentProgress {
  const next = { ...prev, eventCount: prev.eventCount + 1 };
  switch (evt.type) {
    case "phase_changed":
      return { ...next, phase: evt.phase };
    case "search_progress":
      return { ...next, searchProgress: { done: evt.queries_done, total: evt.queries_total, findings: evt.findings } };
    case "chapter_started":
      return { ...next, activeChapter: { id: evt.chapter_id, position: evt.position, title: evt.title } };
    case "lesson_attempt":
      return {
        ...next,
        activeLesson: {
          ...(prev.activeLesson && prev.activeLesson.substepId === evt.lesson_substep_id ? prev.activeLesson : {}),
          substepId: evt.lesson_substep_id, chapterPos: evt.chapter_pos,
          position: evt.position, attempt: evt.attempt, status: evt.status,
        },
      };
    case "critic_verdict":
      return {
        ...next,
        activeLesson: prev.activeLesson
          ? { ...prev.activeLesson, lastScore: evt.score, lastPassed: evt.passes, weaknesses: evt.weaknesses }
          : prev.activeLesson,
      };
    case "lesson_committed":
      return {
        ...next,
        lastCommitted: { lessonId: evt.lesson_id, needsReview: evt.needs_review, attempts: evt.attempts },
        activeLesson: null,
      };
    case "activities_generated":
      return { ...next, lastActivity: { chapterId: evt.chapter_id, lessonId: evt.lesson_id, count: evt.count } };
    case "error":
      return { ...next, errors: [...prev.errors, { node: evt.node, message: evt.message, at: Date.now() }].slice(-20) };
    case "syllabus_created":
      return next;
    default:
      return next;
  }
}

/** Reducer-style hook fed by useStream onCustomEvent. */
export function useAgentProgress() {
  const [progress, setProgress] = useState<AgentProgress>(initial);
  const ref = useRef(progress);
  ref.current = progress;

  const onCustomEvent = useCallback((evt: unknown) => {
    if (!evt || typeof evt !== "object" || !("type" in evt)) return;
    setProgress((p) => reduceEvent(p, evt as AgentEvent));
  }, []);

  const reset = useCallback(() => setProgress(initial), []);

  return { progress, onCustomEvent, reset };
}
