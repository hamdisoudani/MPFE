# Frontend streaming design — lessons from open-swe + agent-chat-ui

> Research note produced 2026-04-22. Source repos:
> - `langchain-ai/open-swe` @ bd52e5e0~1 (last commit with `apps/web`, dropped in #1029)
> - `langchain-ai/agent-chat-ui` @ main
>
> Goal: decide how the Syllabus Agent frontend should consume the LangGraph stream so the UI feels real-time, reconnects are painless, and thread checkpoints never bloat.

---

## 1. Use `useStream` from `@langchain/langgraph-sdk/react` as the ONE source of truth for the chat pane

Both open-swe and agent-chat-ui consume the LangGraph server through `useStream`. You should too. It already gives us everything we would otherwise hand-roll:

- optimistic message appends (`messages` array is patched as tokens arrive)
- typed `UpdateType` / `CustomEventType` / `InterruptType` generics
- `submit()`, `stop()`, `joinStream(runId)`, `getMessagesMetadata()`, `setBranch()`, `client` escape hatch
- `interrupt` surface that pairs with LangGraph's `interrupt()` node
- automatic reconnect on remount

### 1.1 The exact options that matter for "super smooth + resumable"

From `apps/web/src/components/v2/thread-view.tsx` and `apps/web/src/app/(v2)/chat/[thread_id]/page.tsx`, open-swe always passes these:

```ts
const stream = useStream<SyllabusGraphState>({
  apiUrl: process.env.NEXT_PUBLIC_LANGGRAPH_URL,
  assistantId: "syllabus_agent",      // graph_id from langgraph.json
  threadId,                            // from the URL, nuqs-driven
  reconnectOnMount: true,              // <-- the "resume on refresh" switch
  fetchStateHistory: false,            // <-- the "don't block first paint" switch
  onCustomEvent: (evt) => { ... },     // custom stream writer events
  onThreadId: setThreadId,             // persist the new thread_id to the URL on first submit
});
```

The two flags to copy verbatim:

| Flag | Why it matters for us |
| --- | --- |
| `reconnectOnMount: true` | When the user reloads mid-generation, the SDK re-subscribes to the active run over SSE instead of showing a frozen transcript. This is the "resume on reconnect" you asked about. It also means we do NOT need our own reconnect logic. |
| `fetchStateHistory: false` | Skips the `GET /threads/{id}/history` call on mount. Thread history can be multi-MB for long syllabuses; fetching it blocks first paint. Load only `values` (current state) and lazy-load history only if the user opens a "previous versions" panel. |

### 1.2 Joining a run that was started outside the current component

Open-swe runs a Manager graph that spawns Planner + Programmer sub-runs. The manager stores `{ threadId, runId }` for each child in its state; the UI then calls `stream.joinStream(runId)` to attach its `useStream` instance to that already-running child. We need the same pattern because our pipeline has multiple phases (outline → chapters → lessons → activities), and the user may navigate away and come back while node N is still running.

```ts
useEffect(() => {
  if (activeRun?.runId && activeRun.runId !== joinedRef.current) {
    joinedRef.current = activeRun.runId;
    stream.joinStream(activeRun.runId).catch(console.error);
  }
}, [activeRun?.runId]);
```

### 1.3 Cancel button that actually kills the run server-side

`apps/web/src/hooks/useCancelStream.tsx`:

```ts
await stream.client.runs.cancel(threadId, runId, true /* wait */);
```

Not `stream.stop()` — that only detaches the SSE. `runs.cancel` is what actually halts token spend.

---

## 2. Two-track data plane: `useStream` for the active run, SWR for everything else

This is the single most important architectural idea in open-swe and it is where most naive LangGraph UIs go wrong.

```
┌──────────────────────── browser ─────────────────────────┐
│                                                          │
│  Active thread pane  ──►  useStream (SSE)   ◄── hot path │
│                                                          │
│  Thread list, status badges, task progress,              │
│  previous runs, "other tabs"    ──►  SWR polling         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Open-swe's `apps/web/src/lib/swr-config.ts` has a tiered polling policy — copy this pattern literally:

| Config | Interval | Used for |
| --- | --- | --- |
| `THREAD_SWR_CONFIG` | 15 s | Sidebar thread list |
| `THREAD_STATUS_SWR_CONFIG` | 15 s, revalidate on focus | Status badges ("running", "idle", "error") |
| `TASK_PLAN_SWR_CONFIG` | 3 s, revalidate on focus | The actively-viewed thread's task/progress tree |
| `THREAD_STATIC_SWR_CONFIG` | 0 (manual) | Archived runs |

Why not just use `useStream` for all of this? Because `useStream` opens an SSE connection per thread; polling 50 threads at once with SSE would crush both browser and server. SWR with a shared dedupe window is dramatically cheaper for "status-only" views.

### 2.1 For us specifically — Supabase Realtime replaces `TASK_PLAN_SWR_CONFIG`

Our current spec already says Supabase Realtime is the single frontend stream for structural updates (chapters/lessons/activities). That stays. The split becomes:

| Surface | Transport |
| --- | --- |
| **Chat-style log of the agent** (LLM messages, tool calls, "thinking…" chips) | `useStream` (SSE) |
| **Structural artifacts** (chapter cards, lesson blocks, activity lists) | Supabase Realtime on `syllabuses/chapters/lessons/activities` |
| **Thread list & status badges** in the sidebar | SWR polling `client.threads.search()` every 15 s |
| **Draft of the composer input** | `localStorage` via `useDraftStorage` pattern (see §5) |

This is the cleanest mapping: the LangGraph stream carries *token-level* UX, Supabase carries *row-level* UX. Neither layer ever contains the full lesson body blob — those live behind IDs in Supabase storage per our existing spec.

---

## 3. How to keep thread checkpoints from bloating

This is where the "state-as-index, not a store" principle we already have in `syllabus_agent_spec.md` pays off. Open-swe follows the same rule. Concrete techniques to lift:

### 3.1 Do NOT put long markdown/tool-output/file-content in graph state

- Open-swe stores sandbox file dumps and PR diffs in the **sandbox**, not in state. State holds a sandbox session ID.
- Our equivalent: lesson markdown → `lessons.content_md` in Supabase. The graph's `LessonState` holds only `lesson_id` and `status`. If a node needs the body, it reads Supabase; it never passes the full body to the next node via state.

### 3.2 Use `MessagesState` only for the *conversational* channel

`useStream` renders `state.messages`. Make this a *separate* channel that contains only:

- user turns,
- assistant "narration" turns (what the agent is doing next, in one sentence),
- tool call summaries (not full tool outputs),
- interrupts for human review.

Everything else (drafts, critic verdicts, raw LLM JSON, search snippets) lives in adjacent keys that are NOT `messages`, NOT rendered in chat, and get periodically compacted.

### 3.3 Trim the messages channel at every supernode boundary

LangGraph ships `RemoveMessage` for exactly this. Rule of thumb: when we transition phases (outline done → chapters start; chapters done → lessons start; lessons done → activities start), emit `RemoveMessage`s that collapse the prior phase into a single summary line like *"✔ Generated outline (12 chapters, 47 lessons)"*. The UI sees the collapse via `useStream`; the checkpoint shrinks on disk.

```python
from langchain_core.messages import RemoveMessage, AIMessage

def collapse_outline_phase(state):
    keep_ids = {m.id for m in state["messages"] if m.type == "human"}
    summary = AIMessage(content="✔ Generated outline (12 chapters, 47 lessons)")
    return {
        "messages": [RemoveMessage(id=m.id) for m in state["messages"] if m.id not in keep_ids]
                    + [summary],
    }
```

### 3.4 Use a separate "artifacts" channel with a custom reducer

Instead of `Annotated[list, add]` (which grows forever), use an upsert-by-id reducer so re-generating a chapter REPLACES the prior entry instead of appending:

```python
def upsert_by_id(left: list[dict], right: list[dict]) -> list[dict]:
    by_id = {x["id"]: x for x in left}
    for x in right:
        by_id[x["id"]] = x
    return list(by_id.values())

class SyllabusState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    chapters: Annotated[list[ChapterRef], upsert_by_id]   # list of {id, title, status}
    lessons:  Annotated[list[LessonRef],  upsert_by_id]   # list of {id, chapter_id, status, draft_count}
```

This is the state-as-index contract enforced at the reducer level. Draft count stays bounded because our "max 3 drafts" rule means the same `lesson_id` is upserted at most 3 times.

### 3.5 Prefer `AsyncPostgresSaver` with a TTL sweeper for old checkpoints

LangGraph 0.6 exposes `checkpointer.delete_thread(thread_id)` and checkpoint-version pruning. Add a nightly job that deletes checkpoints for threads `updated_at < now() - interval '30 days'` and keeps only the latest checkpoint for threads older than 7 days. The Supabase row for the syllabus survives; the graph replay history goes away. This is the single biggest disk-size win.

### 3.6 Store large tool outputs via the `BaseStore`, not in state

LangGraph's `Store` (e.g. `InMemoryStore`, `PostgresStore`) is namespaced KV. Pattern:

```python
# In a node that calls a search tool with a huge response:
store.put(("tool_cache", thread_id), key=tool_call_id, value=big_json)
return {"messages": [ToolMessage(content=f"[cached as {tool_call_id}]", tool_call_id=...)]}
```

The `messages` channel stays tiny; the downstream node reads the big payload from `store` only if it actually needs it. Open-swe uses this for web-search results.

---

## 4. Making the chat pane load **super fast**

In order of impact:

1. **`fetchStateHistory: false`** on mount. Already covered. This is free and shaves 300–1500 ms on cold loads.
2. **Server-render the thread shell, hydrate `useStream` in the client.** Next.js 16 App Router: the `app/c/[threadId]/page.tsx` is a Server Component that fetches `client.threads.get(threadId)` on the edge, renders the static header + message skeletons, and then mounts a Client Component that calls `useStream`. The user sees the thread before any SSE connects.
3. **Split the sidebar into its own Suspense boundary with SWR.** Don't block the chat pane on the thread list.
4. **Virtualize long transcripts.** For threads with > ~50 assistant messages, use `@tanstack/react-virtual` on the message list. Open-swe does not (their threads are shorter), but syllabus generation can easily hit hundreds of messages across all lessons; virtualization is the difference between smooth scroll and 200 ms jank.
5. **Debounced content flush.** `useStream` re-renders on every SSE chunk (~token). Wrap message bodies in `React.memo` keyed on `message.id` so only the currently-streaming bubble re-renders. Open-swe does this in `components/thread/messages/ai.tsx`.
6. **`nuqs` for `threadId` in the URL.** Keeps navigation instant and shareable without a router push storm.
7. **Prefetch on hover in the sidebar.** `onMouseEnter` → `client.threads.get(threadId)` → seed the SWR cache for that key. Click becomes instantaneous.
8. **Persist the composer draft** so "reload while typing" never loses anything. Copy `useDraftStorage` from open-swe verbatim (500 ms debounced localStorage write; restores on mount).
9. **`React.memo` + stable keys on chapter/lesson cards.** Supabase Realtime will fire a lot of row updates; without memoization the whole syllabus tree re-renders on every activity status change.
10. **Use `onCustomEvent` for progress chips instead of pushing them into `messages`.** E.g. a "Critic is reviewing lesson 3.2…" chip that appears and disappears. These are transient UI events — emit them with `get_stream_writer()` server-side and render them as ephemeral toasts/badges. They never touch the checkpoint, so they can't bloat it, and the UI gets fine-grained feedback without polluting the message log.

---

## 5. Concrete hook inventory we should build (mirrors open-swe)

| Hook | Purpose | Copy-from reference |
| --- | --- | --- |
| `useSyllabusStream(threadId)` | Thin wrapper around `useStream<SyllabusState>` with our generics, `reconnectOnMount: true`, `fetchStateHistory: false`. | `apps/web/src/app/(v2)/chat/[thread_id]/page.tsx` |
| `useSyllabusStore(syllabusId)` | Supabase Realtime subscription to `syllabuses/chapters/lessons/activities` for one syllabus. Returns a normalized tree + loading flags. | new, Supabase docs |
| `useThreadsSWR()` | Sidebar list via `client.threads.search({ metadata: { graph_id: "syllabus_agent" }, limit: 25 })` with SWR. | `hooks/useThreadsSWR.ts` (copy 1:1, drop GitHub installation filter) |
| `useThreadStatus(threadId)` | Lightweight status poll for a single thread's badge. | `hooks/useThreadStatus.ts` |
| `useCancelRun({ stream, threadId, runId })` | `stream.client.runs.cancel(...)` with toast. | `hooks/useCancelStream.tsx` |
| `useDraftStorage()` | localStorage-backed composer draft with 500 ms debounce. | `hooks/useDraftStorage.tsx` |
| `useJoinActiveRun(stream, runId)` | Reattaches to an already-running run on mount or when a sub-run starts. | inline in `components/v2/thread-view.tsx` lines 187–240 |

### 5.1 Zustand is used *only* for UI state

open-swe's `stores/thread-store.ts` holds two things: `activeThreadId`, `isGlobalPollingEnabled`. That is it. All server data goes through SWR or `useStream`. Follow the same discipline — do not replicate server state into Zustand, ever.

---

## 6. What we explicitly do NOT take from open-swe

- **Their dual Planner+Programmer thread split.** We don't need separate child graphs; our phases (outline/chapters/lessons/activities) should run as supernodes inside one graph so the user sees one continuous thread.
- **The GitHub/installation data model.** Irrelevant to us; strip all `installation_name` filtering from the SWR key.
- **Their "agent inbox" interrupt UI complexity.** We only have one interrupt point (the `needs_review` flag from our critic). A simple inline "review required" card on the lesson is enough — don't build a generic inbox.

---

## 7. Action items for the next session

These have been added to `plan.md` under a new "Frontend streaming — Revision 1" section:

1. Add `@langchain/langgraph-sdk` to the Next.js frontend; wire `useStream` with `reconnectOnMount: true`, `fetchStateHistory: false`.
2. Split state channels: `messages` (chat), `chapters`/`lessons` (upsert-by-id reducers, IDs only), `_private` (ephemeral).
3. Adopt the SWR tiered config (`THREAD_SWR_CONFIG` / `THREAD_STATUS_SWR_CONFIG`) for the sidebar and badges.
4. Use `get_stream_writer()` in nodes for transient progress events; never for data that needs to survive a reload.
5. Add a nightly Supabase job (or LangGraph scheduler) to prune old checkpoints via `checkpointer.delete_thread()`.
6. Port `useCancelStream`, `useDraftStorage`, `useThreadsSWR`, `useThreadStatus` from open-swe.
7. Server-render the thread shell in a Next.js Server Component; mount `useStream` in a Client Component child.
8. Virtualize the message list and memoize message bubbles.

When `needs_review` interrupts get wired, switch from a TODO to LangGraph's `interrupt()` + `stream.submit({ resume: ... })` pattern — `useStream` already exposes the `.interrupt` surface for it.
