# Project plan — progress log (keyed to `syllabus_agent_spec.md`)

> Canonical running log per spec §R1 intro. Last updated 2026-04-23.
> Status legend: ✅ landed · 🟡 partial · ⏭️ deferred · ❌ not started

---

## Spec alignment snapshot

### R1 — Authoritative overrides

| Area | Spec (R1) | Status | Notes |
|---|---|---|---|
| Frontend: Next.js 16.x + React 19 + Turbopack | R1.1 | ✅ | `apps/frontend` scaffolded at 16.2.4 / React 19. |
| 3 OpenAI-compatible LLM endpoints (small/writer/critic) | R1.2 | ✅ | `agent/llm.py` with `_mk()` + same-model warning. |
| Serper via `SERPER_API_KEY` | R1.2 | ✅ | wired in `web_search` + `web_search_parallel`. |
| Supabase schema: syllabuses/chapters/lessons/activities + ON DELETE CASCADE | R1.3 | ✅ | applied; includes `teacher_preferences jsonb` per R2.9. |
| Realtime enabled on all 4 tables | R1.3 | ✅ | consumed by `useSyllabusStore`. |
| Activities Pydantic contract | R1.4 | ✅ | `activities_generator` node writes rows. |
| Lesson stored as **markdown** (not BlockNote JSON) | R1.5 | ✅ | writer emits markdown; DB column `content_md`. |
| Frontend renders markdown → BlockNote at view time | R1.6 | ⏭️ | viewer deferred this session (see Deferred). |
| **Supabase Realtime is the only stream** for syllabus data | R1.7 | ✅ | `useSyllabusStore` hydrate-then-subscribe; LangGraph SSE used only for agent progress / chat. |
| `Command(goto=…, update=…)` routing from `critic_node` | R1.8a | ✅ | `_critic_result` removed. |
| `get_stream_writer` server-side typed events | R1.8b | ✅ | `agent/events.py` (this session); emitters in all phase nodes. |
| `AsyncPostgresSaver` checkpointer on Supabase | R1.8c | ✅ | configured in `graph.py`. |
| `BaseStore` cross-thread memory | R1.8d | 🟡 | `InMemoryStore` stub; `PostgresStore` upgrade deferred. |
| `interrupt()` for human review on `needs_review: true` lessons | R1.8e | ⏭️ | reserved; no UI yet. |
| Activities generator node | R1.9 | ✅ | plus reject-force-accept now routes through it via `include_activities` pref (bug fix this session). |
| Graph topology: no `search_router` passthrough | R1.10 | ✅ | direct conditional edges. |
| Security: no RLS / no auth, localhost-only | R1.11 | ✅ | documented in README. |

### R1.12 backlog

| Item | Status |
|---|---|
| Token / cost columns on `syllabuses` (`input_tokens`, `output_tokens`, `usd_cost`) | ❌ |
| `evaluations` table for critic pass-rate | ❌ |
| `logs` / `phase_history` timeline end-to-end (writer → runner → Supabase → FE) | 🟡 — typed events exist; persistence layer not wired. |
| Human review UI + `interrupt()` resume | ❌ |
| Eval harness (golden reqs → golden lessons) | ❌ |
| `PostgresStore` swap-in for scrape/search caches | ❌ |

### R2 — Clarification phase

| Area | Spec (R2) | Status |
|---|---|---|
| `clarify_with_user` node after web_search, before outline | R2.1/R2.4 | ✅ |
| `TeacherPreferences` / `ClarificationQuestions` Pydantic contracts | R2.2/R2.3 | ✅ |
| State channel additions (`teacher_preferences`, `clarification_questions`) | R2.5 | ✅ |
| Graph topology update (web_search → clarify → outline) | R2.6 | ✅ |
| Frontend clarification form (text / number / boolean / single_choice / multi_choice) | R2.7 | ✅ — `ClarifyForm` component + vitest. |
| Bypass path for pre-filled `teacher_preferences` at submit | R2.8 | ✅ — short-circuit in `clarify_with_user`. |
| SQL migration: `teacher_preferences jsonb` + `awaiting_input` phase | R2.9 | ✅ |

---

## Landed this session (branch `feat/frontend-and-streaming-v2`)

### Agent
- `agent/events.py` — typed helper wrapping `langgraph.config.get_stream_writer`. No-op outside a run; swallows writer exceptions. Event contract mirrored in frontend `src/lib/types.ts (AgentEvent)`.
- Emitters plumbed into: `init_node` (self_awareness), `web_search`, `clarify_with_user`, `chapter_guard`, `lesson_writer`, `critic`, `accept_lesson`, `reject_lesson`, `activities_generator`, `finalize`.
- **Bug fix:** `reject_lesson` force-accept path now respects `teacher_preferences.include_activities` and routes to `activities_generator` (previously hard-coded to `chapter_guard`, skipping activities on 3rd-attempt force-accept).
- **State sync:** `accept_lesson` + `reject_lesson` force-accept mirror the upserted row into `state.lessons` so the reducer matches Supabase.
- Tests (pytest, 10 green): `test_events.py`, `test_nodes_accept_reject.py`.

### Frontend — `apps/frontend/` (new)
- Next.js 16.2.4, Tailwind v3, zinc + emerald palette, Inter.
- Mobile-first three-pane shell (Sidebar drawer / CenterPlan / AgentPane).
- Hooks: `useSyllabusStream`, `useAgentProgress` (pure reducer over `AgentEvent`), `useSyllabusStore` (Realtime + upsert-by-id), `useCancelStream`, `useThreadsSWR`, `useDraftStorage`.
- Components: `AppShell`, `Sidebar`, `CenterPlan`, `ChapterList`, `PhaseBanner`, `SearchStatus`, `AgentPane`, `MessageList`, `Composer`, `ClarifyForm`.
- Dockerfile (standalone output) + `railway.json`.
- Tests (vitest + jsdom + testing-library, 14 green): `useAgentProgress`, `useDraftStorage`, `ClarifyForm`, `cn`.
- `next build` + `tsc --noEmit` both green.

---

## Deferred (tracked, not done)

1. **BlockNote readonly viewer** (R1.6) — markdown → BlockNote blocks on lesson row click.
2. **Human-review interrupt UI** (R1.8e / R1.12) — reuse `ClarifyForm` pattern with a review schema.
3. **`PostgresStore` swap-in** (R1.8d / R1.12) — replaces `InMemoryStore` for scrape/search caches.
4. **Token + cost columns on `syllabuses`** (R1.12) — instrument LLM clients, write after `finalize`.
5. **`evaluations` table** (R1.12) — critic pass-rate tracking.
6. **`phase_history` persistence** (R1.12) — consume typed events into a DB timeline.
7. **Eval harness** (R1.12) — golden requirements → golden lessons regression set.
8. **Virtualization** (`@tanstack/react-virtual`) for long chapter lists.
9. **Graph consolidation** — fold `graph_optimized.py` back into `graph.py` (parallel fan-out is stable).
10. **Live E2E against deployed Railway agent** — smoke test hitting real agent with short syllabus.
11. **LangGraph bump** — currently pinned `>= 0.6.0`; revisit when topology changes.

---

## Next session — suggested priorities

1. BlockNote readonly viewer + lesson detail drawer (unblocks R1.6 end-to-end).
2. Human-review `interrupt()` wiring (closes R1.8e).
3. Token/cost instrumentation + `phase_history` table (closes two R1.12 items together since both consume the stream).
4. Graph consolidation + `PostgresStore`.
5. E2E happy-path test against Railway.
