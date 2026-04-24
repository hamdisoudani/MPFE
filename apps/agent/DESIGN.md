# Supervisor-Pattern Syllabus Agent — Design

This file is the canonical design for the rewrite that landed under
`devin/<ts>-supervisor-agent`. Reflects what's actually implemented;
update this and `plan.md` when you change the architecture.

## High-level

```
┌──────────────┐  tool_calls?
│ supervisor   │──────────► router ──► tool_executor ──► supervisor
└──────────────┘                  ├──► search_subgraph ──► supervisor
                                  ├──► writer_subgraph ──► supervisor
                                  ├──► ask_user (interrupt) ──► supervisor (resume)
                                  └──► END (no tool calls = final response)
```

The supervisor is the single LLM-driven decision maker. Everything else
is deterministic plumbing or a focused subgraph. The router NEVER calls
the LLM — it only inspects the latest assistant message's tool calls.

## State (lightweight on purpose)

```python
class State(TypedDict, total=False):
    # Conversation — capped reducer
    messages: Annotated[list[BaseMessage], capped_messages]

    # User intent / metadata
    thread_id: str
    syllabus_id: str | None
    requirements: str | None
    teacher_preferences: dict | None

    # Plans (structured, set via tools)
    search_plan: SearchPlan | None
    search_summary: str | None        # output of summarize
    todo_plan: TodoPlan | None

    # Chapter ref aliases — agent only ever sees CH1/CH2..., never UUIDs
    chapter_alias_map: dict[str, str]

    # Per-subgraph cursors (small ints, no payloads)
    search_step_idx: int
    todo_step_idx: int

    # Phase mirror for FE
    phase: Phase
```

**Out of state on purpose:** scraped markdown, lesson drafts, raw search
results, rendered system prompts. All live in the LangGraph Store
namespaced by `thread_id` and a stable subkey.

Reducers:
- `messages`: append + tail-cap (last 40, system pinned).
- `search_plan`/`todo_plan`: full replace (set by tool).
- `chapter_alias_map`: dict-merge.

## Store namespaces

| Namespace                                       | Value                              | Lifetime                                              |
|-------------------------------------------------|------------------------------------|-------------------------------------------------------|
| `("scrape", thread_id, search_step_id)`         | `{url, markdown, title}`           | until `summarize_search` finishes; then purged        |
| `("search_summary", thread_id)`                 | `{summary, sources}`                | until `set_search_plan` is called again or thread ends|
| `("draft", thread_id, todo_step_id)`            | `{title, content_md, attempt, critique?}` | until lesson committed; then purged                |
| `("dep_summary", thread_id, todo_step_id)`      | `{title, summary, chapter_ref}`    | until thread ends — read by dependents               |

## Plans

```python
class SearchStep(BaseModel):
    id: str             # S1, S2…
    title: str
    queries: list[str]
    status: Literal["pending","searching","scraping","done"] = "pending"

class SearchPlan(BaseModel):
    global_goal: str
    steps: list[SearchStep]

class TodoStep(BaseModel):
    id: str             # T1, T2…
    chapter_ref: str    # CH1, CH2…
    name: str
    description: str    # acceptance criteria, what must be covered
    must_cover: list[str]
    depends_on: list[str] = []     # other TodoStep ids — writer/critic gets the dep summaries from Store
    status: Literal["pending","writing","critiquing","accepted","rejected","failed"] = "pending"
    attempts: int = 0
    final_lesson_id: str | None = None

class TodoPlan(BaseModel):
    steps: list[TodoStep]
```

## Tools (LLM-facing)

| Tool                  | Effect                                                                |
|-----------------------|-----------------------------------------------------------------------|
| `ask_user(question)`  | LangGraph `interrupt()` — frontend resumes via `Command(resume=...)`. |
| `set_search_plan(...)`| Validates + stores plan in state, routes to search subgraph.          |
| `set_todo_plan(...)`  | Validates + stores plan in state, routes to writer subgraph.          |
| `create_syllabus(title)` | Inserts row in Supabase, sets `state.syllabus_id`.                |
| `create_chapters(items)` | Inserts chapters in Supabase, returns alias map (CH1→uuid).       |
| `list_thread_syllabi()`  | Returns existing syllabi for the thread.                          |

## Search subgraph

```
todo_iter ─► [Send] search_query × N ─► scrape_picker ─► [Send] scrape_one × M ─► step_done
                                                                                    │
                                                                            (more steps?)
                                                                                    │
                                                                                    ▼
                                                                              summarize ─► out
```

- Parallel fan-out via `Send`. Reducer-merged `_search_candidates` is
  scratch state cleared each step.
- Scraping uses `r.jina.ai/<url>` for clean markdown — no JS rendering
  needed, free, no key.
- `summarize_search` reads all scraped markdown from Store, runs critic
  LLM (small temp) to produce a tight summary tied to `global_goal`,
  writes to `("search_summary", thread_id)` and to `state.search_summary`,
  then **purges all `("scrape", thread, *)` entries**.

## Writer/Critic subgraph

```
todo_iter ─► writer ─► critic ─► decide ──accept──► commit ─► todo_iter
                       ▲                  ──reject──► writer (≤ MAX_RETRIES)
                       │                  ──fail───► out (status=failed)
```

- Writer reads:
  - `state.search_summary`
  - The current `TodoStep` (must_cover, description)
  - For each dep id: `("dep_summary", thread, dep_id)` from Store
  - Draft (if retry)
- Critic reads:
  - The new draft from Store
  - The TodoStep acceptance criteria
  - Same dep summaries (consistency check)
- `MAX_WRITER_ATTEMPTS = 3`. On 3rd failure → mark step `failed`, continue
  to next non-blocked step. After loop, supervisor sees plan with mixed
  statuses and may set a new todo_plan.
- Commit: insert lesson row in Supabase, write
  `("dep_summary", thread, step.id) = {title, summary}`, **purge draft**.

## Topology of the dependency graph among todo steps

`depends_on` lets the agent express "Lesson 3 builds on Lesson 1+2".
The `todo_iter` is **strict**: a step is only eligible when all
depends_on are `accepted`. If a strongly connected component would
deadlock, those steps fail (no infinite loop).

## Phase / streaming events

| Phase           | When                                                  |
|-----------------|-------------------------------------------------------|
| `idle`          | Default                                                |
| `awaiting_input`| `ask_user` interrupt fired                             |
| `searching`     | Search subgraph running                                |
| `summarizing`   | Summarize node running                                 |
| `outlining`     | After summarize, before set_todo_plan                  |
| `writing`       | Writer subgraph running                                |
| `done`          | Supervisor returns with no tool call                   |
| `failed`        | Any step failed beyond retries (mirrored in plan)      |

Custom stream events (via `agent.events.emit`):
- `phase_changed { phase }`
- `search_step_started { step_id, title }`
- `search_progress { step_idx, steps_total, candidates, scraped }`
- `search_summary_ready { length }`
- `todo_started { steps_total }`
- `todo_step_started { step_id, chapter_ref, name, attempt }`
- `critic_verdict { step_id, attempt, passes, score, weaknesses }`
- `lesson_committed { step_id, lesson_id, chapter_id }`
- `awaiting_input { question }`
- `error { node, message }`

## LLM assignments

| Role             | Env prefix     | Why                                |
|------------------|----------------|-------------------------------------|
| Supervisor       | `LLM_WRITER`   | Strongest, tool calling             |
| Search summarizer| `LLM_SMALL`    | Fast, cheap, deterministic-ish      |
| Writer           | `LLM_WRITER`   | Long-form lesson content            |
| Critic           | `LLM_CRITIC`   | Different family — guards against self-critique |
| Plan validators  | `LLM_SMALL`    | Cheap structured output             |

## Out of scope (deferred)

- Activities generator (table exists; the new agent doesn't write
  activities yet — supervisor can be extended with a tool later).
- `interrupt()` resume from frontend — the contract is supported but
  the FE form for ad-hoc questions is not in this PR.
- PostgresStore swap-in (using InMemoryStore — fine for thread-scoped
  data which is purged at end of run).
