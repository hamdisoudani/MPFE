# Plan & Progress Log

> **Rule:** this file is the source of truth for what has been done and what decisions override the spec.
> Update it at the **end of every work session**. Do not ask someone to re-read the 2 000-line spec to figure out where we are.

## Status
- Phase: **0 — Spec review & scaffolding**
- Spec version: `syllabus_agent_spec.md` with **Revision 1** prepended (2026-04-22)
- Last updated: 2026-04-22

---

## Decisions that override the spec (most recent first)

### 2026-04-22 — Revision 1 (ratified with user)

**Frontend / streaming**
- Frontend does **not** consume LangGraph SSE. Only **Supabase Realtime** is used.
- Frontend is view-only for content; creation happens via a simple form that kicks off an agent run.
- Remove `@langchain/langgraph-sdk` from `frontend/package.json`.

**Frontend framework**
- **Next.js 16.x** (App Router, React 19, Turbopack) — not Next.js 14. Pin `"next": "^16.2.0"`.
- Bump peers to latest: `@supabase/supabase-js`, `@blocknote/core|react|mantine`, `zustand` v5, `typescript` 5.7+.

**Content format**
- Lessons are stored as **markdown** in `lessons.content_markdown`, NOT BlockNote JSON.
- Frontend maps markdown → BlockNote blocks at render time using `editor.tryParseMarkdownToBlocks(md)` from `@blocknote/core`.
- This keeps the DB editor-agnostic and lets us export to PDF / HTML trivially later.

**LLMs (3 endpoints, OpenAI-compatible)**
- Three independent endpoints in `.env`, all via `langchain-openai`:
  - `LLM_SMALL_*` — summarization / small classification (cheap).
  - `LLM_WRITER_*` — syllabus outline + lesson writer + activities generator.
  - `LLM_CRITIC_*` — critic only. **MUST be a different model family than the writer.**
- Runtime warning if writer and critic point at the same model.

**Database**
- Tables: `syllabuses`, `chapters`, `lessons`, `activities`.
- Hierarchy: syllabus 1→N chapters 1→N lessons, chapters also 1→N activities, lessons 1→N activities (activity.lesson_id nullable for chapter-level quizzes).
- **All** child rows use `ON DELETE CASCADE` — delete syllabus removes everything beneath it; delete chapter removes its lessons and activities; delete lesson removes its activities.
- **Realtime enabled** on all four tables (`alter publication supabase_realtime add table …`).
- **No RLS, no auth** for v1. Anon key is localhost-only. Service role key for the agent.
- Activities payload is validated JSON: `{ kind, title, questions: [{ question, options[], correct_indices[], explanation? }] }`.

**Agent (LangGraph)**
- Require `langgraph >= 0.6`.
- Checkpointer: `AsyncPostgresSaver` backed by the same Supabase Postgres (`SUPABASE_DB_URL` in `.env`). No `MemorySaver` in production.
- Routing: use `Command(goto=..., update=...)` from inside nodes. **Delete the `_critic_result` temp state key** and the `route_after_critic` function.
- Delete the `search_router` passthrough node — attach conditional edges directly.
- `get_stream_writer` / `StreamWriter`: used **server-side only** for structured events. A runner consumer writes them to a `logs` table / `syllabuses.phase_history` → frontend reads via Realtime. Frontend never subscribes to the LangGraph stream.
- `BaseStore`: stub with `InMemoryStore` in `agent/memory/store.py` now; swap to `PostgresStore` against Supabase later. Namespaces planned: `("scrapes", url_hash)`, `("serper", query_hash)`.
- `interrupt()`: reserved for the human-review flow on lessons flagged `needs_review: true`. Leave a TODO at the accept node, do not wire yet.
- New node: **activities generator** runs after `accept_lesson`. Uses `writer_llm.with_structured_output(list[ActivityPayload])`. Upsert on `(lesson_id, position)`. Max 2 attempts, then flag lesson and move on.

**Idempotency / upserts**
- `syllabuses` on `thread_id`, `chapters` on `(syllabus_id, position)`, `lessons` on `substep_id`, `activities` on `(lesson_id, position)`.

**Security posture**
- No RLS, no auth — anon key **must not** leave localhost / dev. Agent uses service role key only.
- Before any public deploy: enable RLS, add auth (Supabase Auth or Clerk), scope everything by `owner_id`.

---

## Completed
- [x] Repo cloned and spec reviewed (2026-04-22).
- [x] Revision 1 agreed and documented in README + this file + spec header.

## In progress
- [ ] Supabase SQL migration file implementing the new schema + realtime + cascades.
- [ ] `agent/` package skeleton (`llm.py`, `memory/store.py`, `nodes/`, `graph.py`, `langgraph.json`).
- [ ] `frontend/` Next.js 16 scaffold with Supabase client + markdown→BlockNote renderer.

## Backlog (not started)
- [ ] Token/cost accounting on `syllabuses` (input_tokens, output_tokens, usd_cost).
- [ ] `evaluations` table (lesson_id, critic_model, pass, critique, attempt) for drift tracking.
- [ ] `logs` table or `phase_history jsonb[]` on syllabus for live timeline via Realtime.
- [ ] Human review UI for lessons with `needs_review = true` (wire `interrupt()`).
- [ ] Swap `InMemoryStore` → `PostgresStore` once scraping volume justifies it.
- [ ] Eval harness: golden (requirements, objectives) → known-good lessons.

## Lessons learned / do not repeat
- **Never** store large content (HTML, BlockNote JSON, scraped text) in LangGraph state — only IDs, cursors, and small metadata.
- **Never** let the LLM emit BlockNote JSON directly. Use markdown + a deterministic mapper.
- **Never** use the same model family for writer and critic — self-critique is weak.
- **Never** couple the frontend to the LangGraph stream when Supabase Realtime already covers it — one source of truth.
- **Never** use `MemorySaver` past the very first local smoke test — no resume, no durability.
- Temporary routing state (`_critic_result`) leaks across checkpoints — use `Command` instead.

---

## Frontend streaming — Revision 1 (added 2026-04-22)

Research source: `frontend-streaming-design.md` in this repo (distilled from `langchain-ai/open-swe` @ bd52e5e0~1 and `langchain-ai/agent-chat-ui`).

### Decisions (authoritative)
- Adopt `useStream` from `@langchain/langgraph-sdk/react` as the single SSE consumer for the active chat pane. Always pass `reconnectOnMount: true` and `fetchStateHistory: false`.
- Two-track data plane:
  - `useStream` for the active run's chat/messages + custom progress events.
  - Supabase Realtime for structural artifacts (chapters/lessons/activities rows).
  - SWR with tiered intervals (15 s sidebar / 3 s active-thread status) for thread list + status badges.
- State channels split:
  - `messages`: only user turns, one-sentence agent narration, tool-call summaries, interrupts. Trimmed with `RemoveMessage` at phase boundaries.
  - `chapters` / `lessons` / `activities`: IDs + status only, with an **upsert-by-id reducer** (NOT `add`). Max 3 drafts per lesson = bounded growth.
  - Everything large (lesson markdown, search snippets, tool payloads) lives in Supabase or LangGraph `BaseStore`, never in graph state.
- Emit transient progress via `get_stream_writer()` and render as ephemeral chips via `onCustomEvent` — these never hit the checkpoint.
- Nightly checkpoint pruning via `AsyncPostgresSaver.delete_thread()` for threads older than 30 days; keep only latest checkpoint for threads > 7 days.

### Hooks to port from open-swe (1:1 unless noted)
- [ ] `useThreadsSWR` (drop GitHub installation filter)
- [ ] `useThreadStatus`
- [ ] `useCancelStream`
- [ ] `useDraftStorage`
- [ ] thin `useSyllabusStream(threadId)` wrapper around `useStream<SyllabusState>`
- [ ] `useJoinActiveRun(stream, runId)` helper (pattern from `thread-view.tsx` L187–240)
- [ ] `useSyllabusStore(syllabusId)` Supabase Realtime subscription (new, not from open-swe)

### UI perf checklist
- [ ] Next.js 16 Server Component renders the thread shell; Client Component child mounts `useStream`.
- [ ] `nuqs` drives `threadId` from the URL.
- [ ] Prefetch `client.threads.get()` on sidebar hover.
- [ ] Virtualize message list with `@tanstack/react-virtual` above ~50 messages.
- [ ] `React.memo` on message bubbles + chapter/lesson cards with stable keys.
- [ ] Zustand is for UI-only state (`activeThreadId`, `isGlobalPollingEnabled`). No server data mirrored into Zustand.

### Explicitly out of scope for v1
- Dual-graph Planner/Programmer split (we keep one graph with supernodes).
- Agent-inbox interrupt UI (single inline "review required" card is enough).


## Revision 2 — Clarification phase (2026-04-22)

Inserted a `clarify_with_user` node between the search loop and `outline_generator`. Full contract in `syllabus_agent_spec.md` § R2.

**Why after search, not before:** the agent holds `findings` by the time it asks, so it can ask *informed* questions with sensible defaults instead of generic ones.

**How it works**
- New Pydantic contracts: `TeacherPreferences` (full shape) and `ClarificationQuestions` (the subset the agent actually asks, ≤ 6 items).
- Node uses LangGraph 0.6 `interrupt({...})`. `AsyncPostgresSaver` persists the pause durably — teacher can close the tab and resume later.
- Frontend reads `stream.interrupt.value.kind === "clarification"`, renders a form, resumes via `stream.submit(undefined, { command: { resume: answers } })`.
- Short-circuit: if the initial `stream.submit()` already carries `teacher_preferences`, the node skips the LLM + interrupt entirely. Lets a "Create syllabus" form bypass chat-style clarification.

**Downstream effects**
- `outline_generator` uses `num_chapters` / `lessons_per_chapter` / `must_cover` / `must_avoid` / `special_focus` / duration.
- `write_lesson` threads `language_of_instruction` + `pedagogical_approach` + `special_focus` into its system prompt.
- `critic_node` also checks `must_cover` / `must_avoid` / `pedagogical_approach`.
- `activities_generator` is now behind a conditional edge driven by `include_activities` + `activity_granularity`; `per_chapter` emits on the last lesson of the chapter only (and sets `lesson_id = NULL` on the activities row, which the schema already allows).

**New artifacts**
- `phase` enum gains `awaiting_input`.
- `syllabuses.teacher_preferences jsonb` column (audit + analytics).
- New frontend component `ClarifyForm` + Zod schema mirroring `TeacherPreferences`.

**Updated topology**
```
search_planner ⇄ web_search → clarify_with_user → outline_generator → chapter_guard ⇄ (write_lesson → critic → accept → activities?) → END
```
