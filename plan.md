# Project plan — progress log (keyed to `syllabus_agent_spec.md`)

> Canonical running log. Last updated 2026-04-24.
> Status legend: ✅ landed · 🟡 partial · ⏭️ deferred · ❌ not started

---

## 2026-04-24 — REWRITE: supervisor-pattern agent (`devin/<ts>-supervisor-agent`)

The R1/R2 linear pipeline (self_awareness → search_planner → web_search → clarify → outline → chapter_guard → writer/critic → activities → finalize) was replaced by a **supervisor-pattern agent**. The motivation came from the latest spec from the user: a central LLM-driven router that decides the next move, dynamic plan tools (`set_search_plan` / `set_todo_plan`), `ask_user` clarifications via `interrupt()`, parallel fan-out search/scrape via `Send`, and aggressive use of LangGraph Store for ephemeral data with explicit GC.

### What landed

- **Architecture** (see `apps/agent/DESIGN.md`):
  ```
  supervisor ──► tool_calls? ──┬──► END (no calls)
                               ├──► ask_user (interrupt)
                               ├──► apply_search_plan ──► search_subgraph ──► supervisor
                               ├──► apply_todo_plan   ──► writer_subgraph ──► supervisor
                               └──► db_tools_node     ──► supervisor
  ```
- **Lightweight state** (`agent/state.py`): only ids, cursors, plans, capped messages, alias map, phase. No payloads. `messages` capped via custom reducer; candidates de-duped by `(step_id, url)`; plans full-replaced.
- **LangGraph Store namespaces** + GC discipline (`agent/store_keys.py`): `("scrape", thread, step_id)` purged after `summarize_search`; `("draft", thread, todo_id)` purged after lesson commit or give-up; `("dep_summary", thread, todo_id)` retained for downstream lessons; `("search_summary", thread)` retained until next `set_search_plan`.
- **Search subgraph** (`agent/search/`): `plan_step` → parallel `Send` fan-out to `search_query × N` → `pick_to_scrape` → parallel `Send` fan-out to `scrape_one × M` → `advance_step` (loop) → `summarize_search` (purge + write summary).
  - Search via Serper.dev `/search`. Scrape via Serper `/scrape` with **`r.jina.ai` markdown fallback** (free, no key).
- **Writer/Critic subgraph** (`agent/writer/`): `pick_next` (DAG-aware via `depends_on`) → `write` → `critic` → `decide` (accept/retry/give_up) with `MAX_WRITER_ATTEMPTS=3`. Reads dep summaries from Store. Commits lesson, marks chapter done if its last, saves `dep_summary`, GCs draft.
- **Supervisor + middleware** (`agent/supervisor.py`): system prompt is built per-turn from persona + dynamic context block + a deterministic NEXT_ACTION hint computed from state shape. Tool messages are phrased to reflect the *post-subgraph* state so the LLM doesn't think searches are still running.
- **Tools** (`agent/tools/`): `ask_user`, `set_search_plan`, `set_todo_plan`, `create_syllabus`, `create_chapters`, `list_thread_syllabi`. Plan tools are intent stubs — execution lives in `apply_*` nodes. DB tools execute Supabase writes idempotently (upsert-on-conflict by `thread_id` and `(syllabus_id, position)`).
- **Chapter alias contract**: agent only sees `CH1`/`CH2`/… aliases. The supabase UUIDs live in `state.chapter_alias_map` and are resolved by the writer subgraph at commit time. Prevents UUID hallucination.
- **Streaming events** (`agent/events.py`): `phase_changed`, `search_step_started`, `search_progress`, `search_summary_ready`, `todo_started`, `todo_step`, `critic_verdict`, `lesson_committed`, `chapter_committed`, `awaiting_input`, `error`. Frontend can stream these via `stream_mode=["custom", "updates"]`.
- **LLM assignments**: supervisor + writer = `LLM_WRITER` (`stepfun-ai/step-3.5-flash` in test); critic = `LLM_CRITIC` (`mistralai/mistral-small-4-119b-2603`); summarizer = `LLM_SMALL` (`stepfun-ai/step-3.5-flash`). The user-supplied `nicoboss/DeepSeek-R1-Distill-Qwen-32B-Uncensored` is not in NVIDIA's catalog and `nim.api.nvidia.com` 403s — switched to step-3.5-flash for writer/small (verified tool calling + structured output).

### Removed (legacy R1/R2 nodes)

`self_awareness, search_planner, search_planner_once, web_search, web_search_parallel, clarify_with_user, syllabus_outline, chapter_guard, lesson_writer, lesson_worker, lesson_fanout, write_lesson, critic_node, accept_lesson, reject_lesson, activities_generator, finalize, init_node, graph_optimized.py, e2e_run*.py, agent/memory/store.py, tracing.py, prompts.py, llm.py, events.py, state.py, graph.py` — all gone. Tests reduced to a single import/topology smoke test plus state-reducer/plan-validation unit tests.

### Verified end-to-end

`apps/agent/e2e_run.py` runs a fresh thread through:
1. Greeting → plain reply, no tools, no DB writes ✅
2. "Build me a 4-week Intro to C++ syllabus..." → supervisor calls `set_search_plan` (3 steps × 2-3 queries × 3 scrapes parallel) → summarize → `create_syllabus` → `create_chapters` (CH1, CH2, CH3) → `set_todo_plan` (6 lessons with `depends_on` chain T1→T2→…→T6) → writer/critic loop, all 6 lessons critic-passed on attempt 1 (scores 90-95) → final plain-text reply. Supabase: 1 syllabus, 3 chapters, 6 lessons committed. Lesson content is classroom-ready markdown (~1000 words each, code blocks with language tags, "Check your understanding" sections, dependency-aware (T2 explicitly builds on T1's Hello World)). ✅

### Schema

Recreated minimally: `syllabuses`, `chapters`, `lessons`, `activities` (kept the activities table per user instruction even though the new agent doesn't write to it yet — easy to re-enable later via a `set_activities_plan` tool). Realtime publication: all 4 tables.

### Deferred from the previous architecture

- Activities generator (table exists; tool not yet defined for the supervisor — straightforward to add)
- BlockNote readonly viewer (frontend, R1.6)
- Human-review interrupt UI (frontend) — backend supports `ask_user` interrupt natively
- `PostgresStore` swap-in (currently `InMemoryStore` — fine since Store data is thread-scoped and purged at run boundaries)
- Token/cost instrumentation
- Eval harness

### Known limitations

- Default writer model `stepfun-ai/step-3.5-flash` works well for ~6-lesson syllabi but timing depends on NVIDIA NIM availability. Configurable via env.
- Search depends on `SERPER_API_KEY`; without it the search degrades to stub URLs but the rest of the pipeline still runs.
- The frontend is unchanged; it consumes Supabase Realtime so chapter/lesson rows show up live, but the *typed event stream* now uses different event names — frontend `useAgentProgress` reducer needs a small adapter pass to handle new event types (deferred, separate PR).
