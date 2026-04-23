import { describe, it, expect } from "vitest";
import { reduceEvent } from "./useAgentProgress";
import type { AgentEvent } from "@/lib/types";

const empty = {
  phase: null, searchProgress: null, activeChapter: null, activeLesson: null,
  lastCommitted: null, lastActivity: null, errors: [], eventCount: 0,
} as any;

describe("reduceEvent", () => {
  it("sets phase on phase_changed", () => {
    const out = reduceEvent(empty, { type: "phase_changed", phase: "writing" } as AgentEvent);
    expect(out.phase).toBe("writing");
    expect(out.eventCount).toBe(1);
  });

  it("tracks search_progress", () => {
    const out = reduceEvent(empty, { type: "search_progress", queries_done: 2, queries_total: 5, findings: 8 } as AgentEvent);
    expect(out.searchProgress).toEqual({ done: 2, total: 5, findings: 8 });
  });

  it("merges lesson_attempt with critic_verdict", () => {
    let s = reduceEvent(empty, { type: "lesson_attempt", lesson_substep_id: "s::ch1::l1",
      chapter_pos: 1, position: 1, attempt: 1, status: "drafting" } as AgentEvent);
    s = reduceEvent(s, { type: "lesson_attempt", lesson_substep_id: "s::ch1::l1",
      chapter_pos: 1, position: 1, attempt: 1, status: "critiquing" } as AgentEvent);
    s = reduceEvent(s, { type: "critic_verdict", lesson_substep_id: "s::ch1::l1",
      attempt: 1, passes: false, score: 4, weaknesses: ["w"] } as AgentEvent);
    expect(s.activeLesson?.status).toBe("critiquing");
    expect(s.activeLesson?.lastPassed).toBe(false);
    expect(s.activeLesson?.lastScore).toBe(4);
  });

  it("clears activeLesson on lesson_committed", () => {
    let s = reduceEvent(empty, { type: "lesson_attempt", lesson_substep_id: "s::ch1::l1",
      chapter_pos: 1, position: 1, attempt: 2, status: "drafting" } as AgentEvent);
    s = reduceEvent(s, { type: "lesson_committed", lesson_id: "l-1", lesson_substep_id: "s::ch1::l1",
      chapter_id: "ch-1", position: 1, needs_review: true, attempts: 2 } as AgentEvent);
    expect(s.activeLesson).toBeNull();
    expect(s.lastCommitted?.needsReview).toBe(true);
    expect(s.lastCommitted?.attempts).toBe(2);
  });

  it("caps errors at 20 and records node/message", () => {
    let s: any = empty;
    for (let i = 0; i < 25; i++) {
      s = reduceEvent(s, { type: "error", node: "n", message: `m${i}` } as AgentEvent);
    }
    expect(s.errors.length).toBe(20);
    expect(s.errors[0].message).toBe("m5");
    expect(s.errors.at(-1).message).toBe("m24");
  });

  it("ignores unknown event shapes without throwing", () => {
    const out = reduceEvent(empty, { type: "unknown" } as any);
    expect(out.eventCount).toBe(1);
  });
});
