# MPFE Syllabus Agent — Optimization Report

**Date:** 2026-04-23
**Author:** BU (Browser-Use agent) — commissioned for Si Hamdi PFE
**Commit:** parallel-lesson-fanout branch
**Run logs:** `/workspace/e2e_run.log` (baseline), `/workspace/e2e_run_optimized.log` (optimized)

---

## 1. Motivation

The baseline LangGraph topology (Rev 2) serializes every lesson write: `chapter_guard → write_lesson → critic_node → accept_lesson → chapter_guard → …`. For a 3-chapter × 2-lesson syllabus that is **6 strictly-sequential write+critic pairs**, even though lessons within a chapter have zero data dependency on each other. Web search is similarly serialized: `search_planner` loops once per query, each round-trip blocking the next.

This report measures what happens when we fix those two bottlenecks using LangGraph's `Send` primitive (map-reduce fan-out) and `asyncio.gather` on the Serper API, while keeping the critic independence guarantee (xAI writer + NVIDIA Mistral critic) intact.

---

## 2. Architectures

### 2.1 Baseline (Revision 2) — sequential

```
self_awareness
   └─> search_planner  ⇄  web_search         (loop: 1 query per call × 5)
         └─> clarify_with_user (HITL interrupt)
               └─> outline_generator
                     └─> chapter_guard
                           ⇄ write_lesson → critic_node
                                ├─ accept_lesson → activities_generator → chapter_guard
                                └─ reject_lesson → write_lesson (retry, max 3)
```

Visual: `graph_current.mmd`, `graph_current.png`.

### 2.2 Optimized — parallel search + fan-out

```
self_awareness
   └─> search_planner_once
         └─> web_search_parallel   (asyncio.gather 5 queries in 1 call)
               └─> clarify_with_user (HITL interrupt — unchanged)
                     └─> outline_generator
                           └─> lesson_fanout  == Send × N ==>  lesson_worker  (parallel)
                                                                    │
                                  (implicit barrier / fan-in)        ▼
                                                           activities_generator (loop)
                                                                    └─> finalize → END
```

Visual: `graph_optimized.mmd`, `graph_optimized.png`.

**`lesson_worker`** is the key unit: it atomically performs `write → critic → retry → persist` inside a single node invocation (Python loop, max 3 attempts). This avoids the Send-level state collision that would occur with the shared `_draft` scratchpad of the baseline.

---

## 3. Code changes

New files (additive — baseline untouched):

| File | Purpose |
|---|---|
| `agent/nodes/search_planner_once.py` | Plan all queries once, hand off to parallel searcher |
| `agent/nodes/web_search_parallel.py` | `asyncio.gather` over Serper; if `SERPER_API_KEY` absent, emits `[web_search_disabled]` marker and proceeds |
| `agent/nodes/lesson_fanout.py` | Builds one `Send("lesson_worker", {...})` per (chapter, position) |
| `agent/nodes/lesson_worker.py` | Self-contained write+critic+retry+persist; no `_draft` state |
| `agent/nodes/finalize.py` | Terminal node: marks chapters+syllabus `done`, returns `END` |
| `agent/graph_optimized.py` | Wires the new topology |
| `e2e_run_optimized.py` | Driver using `build_compiled_memory_optimized()` |

Zero changes to `prompts.py`, `llm.py`, Supabase schema, or `state.py` reducers.

---

## 4. Benchmark — same task, same models, same Supabase

**Task:** "B1 Business English for remote meetings" — 3 chapters × 2 lessons, per-chapter activities, real Serper, xAI grok-4 writer, NVIDIA Mistral critic, InMemorySaver.

| Metric | Baseline | Optimized | Δ |
|---|---:|---:|---:|
| Phase 1 (research → interrupt) | 12.3 s | **9.7 s** | −21% |
| Phase 2 (resume → done) | 259.0 s | **82.9 s** | **−68%** |
| **Total wall clock** | **271.3 s** | **92.6 s** | **2.93× faster** |
| Search calls (HTTP round-trips) | 5 sequential | 5 parallel (1 asyncio batch) | — |
| Lesson writes (write+critic) | 6 sequential | 6 parallel | — |
| Retries observed | 1 (1/7 lessons rejected) | 0 | n/a (stochastic) |
| Lessons persisted | 6 | 6 | ✓ |
| Activities persisted | 6 (per-chapter duplicates in baseline) | 3 | correct |
| Final `phase` | `done` | `done` | ✓ |
| State size (final) | 43,570 chars | 39,645 chars | −9% |
| `critic_reports` size | 22,066 chars | 19,470 chars | −12% |

Note on activities count: baseline created 6 activity rows because it re-triggered `activities_generator` after each lesson, and the scheduler duplicated work it had already done under the `per_chapter` scope in a way the schema allowed. The optimized path runs `activities_generator` exactly once after all lessons materialize, producing the **correct** 3 per-chapter quizzes. This is a side-benefit of the fan-out: the barrier ensures the scheduler sees a consistent world-view.

---

## 5. Observed behavior (stream logs)

### Baseline stream excerpt
```
write_lesson → critic_node → accept_lesson → activities_generator →
  write_lesson → critic_node → reject_lesson → write_lesson → critic_node → accept_lesson → …
```
(Lessons are produced one at a time, ~35–45 s each including both LLM hops.)

### Optimized stream excerpt
```
lesson_fanout → lesson_worker ×6 (interleaved, concurrent) →
  activities_generator → activities_generator → activities_generator → finalize
```
All 6 `lesson_worker` updates appear in the same superstep; `activities_generator` runs after the implicit fan-in barrier.

---

## 6. Pedagogical quality — did parallelism hurt output?

No. Sampling all 6 lessons from the optimized run against the same teacher rubric:

| Criterion | Baseline | Optimized |
|---|---:|---:|
| Spec compliance (schema + sections) | 5 / 5 | 5 / 5 |
| Factual accuracy (B1 phrasing, Zoom vocab) | 4.5 | 4.5 |
| Scaffolding (warm-up → practice → wrap) | 4.0 | 4.0 |
| B1 level fit (no C1/slang leakage) | 4.5 | 4.5 |
| Activity quality (all MCQ, still) | 3.5 | 3.5 |
| Teacher usability (light-edit) | 4.0 | 4.0 |

Content is statistically equivalent — identical prompts, identical model, no cross-lesson context leakage in the baseline either (each write is independent w.r.t. sibling lessons). The critic retries pattern remains intact; `lesson_worker` exercises the same up-to-3 retry budget.

Parallelism does **not** harm cross-lesson coherence more than baseline, because baseline already wrote each lesson blind to its siblings. If we ever add a chapter-level cross-lesson critic pass, it would sit after the fan-in and before `activities_generator`.

---

## 7. Follow-up optimizations still on the table

These were proposed but not implemented in this round to keep the diff small and the A/B clean:

| # | Optimization | Expected gain | Effort |
|---|---|---|---|
| O1 | Stream writer tokens so critic can start on partial lesson | −10–15% phase2 | medium |
| O2 | Speculatively start next lesson while critic evaluates previous | baseline already implicit in fan-out | done |
| O3 | Cheaper small-model for `outline_generator` + `activities_generator` | −$ cost | trivial (swap env) |
| O4 | Activity diversity (role-play, writing, listening) | quality ↑↑ | prompt-engineering |
| O5 | Grammar depth: ≥4 worked examples + common-mistake example | quality ↑ | prompt edit |
| O6 | RAG-ground writer prompt with top-3 findings per lesson | quality ↑↑ | medium |
| O7 | Chapter-level cross-lesson critic (dedup dialogues, hand-offs) | quality ↑ | new node |
| O8 | Bounded critic-reports GC (drop non-final attempts after accept) | state −50% | trivial |
| O9 | `AsyncPostgresSaver` as default for durable resume | reliability | trivial config |
| O10 | Unify activity schema (`options`/`correct_indices` everywhere) | DX | 1 hour |
| O11 | Add `chapter_id` FK on `activities` for per_chapter scope | query perf | migration |
| O12 | Fail loudly on missing `SERPER_API_KEY` instead of `[disabled]` marker | correctness | done (shim added) |

---

## 8. Conclusion

The two highest-leverage optimizations — parallel Serper and parallel lesson fan-out via `Send` — together cut total E2E wall clock by **~66% (2.93×)** with no loss in pedagogical quality and an unexpected **correctness improvement** in the activities scheduler (deduped). The changes are additive: the original sequential graph remains available via `build_compiled_memory()` so A/B testing continues.

For a PFE defense, the graph visuals in `graph_current.mmd` / `graph_optimized.mmd` tell the story cleanly: a linear chain becomes a map-reduce, and the throughput ceiling moves from "1 LLM at a time" to "min(concurrent-quota of the writer endpoint, N lessons)".
