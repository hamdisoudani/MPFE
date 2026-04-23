export type Phase =
  | "searching" | "awaiting_input" | "outlining" | "writing"
  | "activities" | "done" | "failed";

export interface Syllabus {
  id: string;
  thread_id: string;
  title: string | null;
  requirements: string;
  phase: Phase;
  teacher_preferences: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

export interface Chapter {
  id: string;
  syllabus_id: string;
  position: number;
  title: string;
  summary: string | null;
  status: "pending" | "writing" | "done";
}

export interface Lesson {
  id: string;
  chapter_id: string;
  syllabus_id: string;
  substep_id: string | null;
  position: number;
  title: string;
  content_markdown: string;
  summary: string | null;
  needs_review: boolean;
  draft_attempts: number | null;
  created_at?: string;
}

export interface Activity {
  id: string;
  chapter_id: string;
  lesson_id: string | null;
  syllabus_id: string;
  position: number;
  payload: { kind: string; title: string; questions: unknown[] };
}

// Custom events emitted by the agent via get_stream_writer().
export type AgentEvent =
  | { type: "phase_changed"; phase: Phase }
  | { type: "syllabus_created"; syllabus_id: string; title: string }
  | { type: "search_progress"; queries_done: number; queries_total: number; findings: number }
  | { type: "chapter_started"; chapter_id: string; position: number; title: string }
  | { type: "lesson_attempt"; lesson_substep_id: string; chapter_pos: number; position: number; attempt: number; status: "drafting" | "critiquing" }
  | { type: "critic_verdict"; lesson_substep_id: string; attempt: number; passes: boolean; score: number; weaknesses: string[] }
  | { type: "lesson_committed"; lesson_id: string; lesson_substep_id: string; chapter_id: string; position: number; needs_review: boolean; attempts: number }
  | { type: "activities_generated"; chapter_id: string; lesson_id: string | null; count: number }
  | { type: "error"; node: string; message: string };

export interface ClarificationQuestion {
  key: string;
  kind: "text" | "number" | "single_choice" | "multi_choice" | "boolean";
  prompt: string;
  options?: string[];
  default?: unknown;
  rationale?: string;
}

export interface ClarificationInterrupt {
  kind: "clarification";
  findings_summary: string;
  questions: ClarificationQuestion[];
}
