# Project plan — session checkpoint 2026-04-23

## Landed this session (branch: feat/frontend-and-streaming-v2)

### Agent
- `agent/events.py` — typed helper wrapping `langgraph.config.get_stream_writer`. Safe no-op outside a run; swallows writer exceptions. Documented event contract in `src/lib/types.ts (AgentEvent)`.
- Emitters plumbed into: `self_awareness`, `web_search`, `clarify_with_user`,
  `syllabus_outline`*, `chapter_guard`, `write_lesson`, `critic_node`,
  `accept_lesson`, `reject_lesson`, `activities_generator`, `finalize`.
  (*outline_generator kept lean — phase change already emitted by clarify_with_user.)
- **Bug fix:** `reject_lesson` force-accept path now respects
  `teacher_preferences.include_activities` and routes to `activities_generator`
  (previously always `chapter_guard`).
- **State sync:** `accept_lesson` + `reject_lesson` force-accept mirror the
  upserted row into `state.lessons` so the reducer matches Supabase.
- Tests (pytest, 10 passing):
  - `tests/test_events.py` — no-writer no-op, routed emit, error truncation,
    writer exception swallow.
  - `tests/test_nodes_accept_reject.py` — accept routing + mirror, reject
    routing both branches, sub-3-attempt retry.

### Frontend (apps/frontend — new)
- Next.js 16.2.4 (App Router, React 19, Turbopack), Tailwind v3 with
  open-swe-inspired palette (zinc neutrals + emerald accent, Inter UI font).
- Mobile-first three-pane shell: Sidebar (drawer on mobile), CenterPlan,
  AgentPane. Flex column on < md, three columns on md+.
- Hooks (ported + custom):
  - `useSyllabusStream` — wraps `@langchain/langgraph-sdk/react::useStream`
    with `reconnectOnMount: true`, `fetchStateHistory: false`, onCustomEvent.
  - `useAgentProgress` — pure reducer over `AgentEvent`; tracks phase,
    search progress, active chapter, active lesson attempt, last critic
    verdict, committed lessons, activities, capped error log.
  - `useSyllabusStore` — Supabase Realtime subscription on
    `syllabuses/chapters/lessons/activities` scoped by `syllabus_id`, with
    one-shot hydration + upsert-by-id live merge.
  - `useCancelStream` — server-side run cancel via
    `client.runs.cancel(threadId, runId, true)`.
  - `useThreadsSWR` — SWR-backed thread list, 15s refresh, keepPreviousData.
  - `useDraftStorage` — per-thread localStorage composer draft.
- Components: `AppShell`, `Sidebar`, `CenterPlan`, `ChapterList`, `PhaseBanner`,
  `SearchStatus`, `AgentPane`, `MessageList`, `Composer`, `ClarifyForm` (full
  widget support: text/number/boolean/single_choice/multi_choice chips).
- Tests (vitest + jsdom + testing-library, 14 passing):
  - `useAgentProgress.test.ts` — phase, search progress, attempt+verdict merge,
    commit clears activeLesson, error cap (20), unknown events.
  - `useDraftStorage.test.ts` — persistence + per-thread scoping + clear.
  - `ClarifyForm.test.tsx` — renders all kinds, submits defaults, multi_choice toggle.
  - `cn.test.ts` — tailwind-merge + falsy drop.
- `Dockerfile` (standalone Next output) + `railway.json`; mirrors agent
  Railway pattern. `typecheck` + `build` both green locally in sandbox.

## Deferred (not in this session)
- BlockNote readonly viewer for clicked lesson rows.
- Virtualization (`@tanstack/react-virtual`) for long chapter lists.
- Human-review interrupt UX (same `ClarifyForm` pattern, different schema).
- `PostgresStore` wiring for scrapes / serper namespaces in agent.
- Consolidating `graph.py` and `graph_optimized.py` into one graph.
- Live end-to-end test against deployed Railway agent (needs Railway token).
- LangGraph version bump to latest 0.6.x — currently pinned at 0.6.0 in
  pyproject; still compiles. Deferred to when we touch the graph topology.

## Next session priorities (suggested)
1. BlockNote readonly + lesson detail drawer on row click.
2. Human-review interrupt (`needs_review: true` lessons).
3. E2E happy-path test hitting the live agent with a short syllabus.
4. Graph consolidation + PostgresStore.
