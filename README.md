# MPFE — Syllabus Agent

> ## 🛑 AGENT / CONTRIBUTOR DIRECTIVE — READ FIRST
>
> Before starting **any** work in this repository:
>
> 1. **Read [`plan.md`](./plan.md)** — it tracks what has already been built from [`syllabus_agent_spec.md`](./syllabus_agent_spec.md), what is in progress, and what decisions/mistakes we do NOT want to repeat.
> 2. **Update `plan.md`** at the end of every work session with:
>    - ✅ What was completed (link commits / files).
>    - 🚧 What is in progress and where you left off.
>    - 🧠 Any lessons learned, pitfalls, or design decisions that override the spec.
> 3. **Never re-read the full spec to figure out progress.** `plan.md` is the single source of truth for "where are we".
> 4. If `plan.md` and `syllabus_agent_spec.md` disagree, **`plan.md` wins** (it reflects decisions made after the spec was frozen). Only update the spec for large, intentional changes.

---

## What this is

An autonomous **Syllabus Agent**: a LangGraph (Python) orchestrator that, given a topic + requirements, performs web research, drafts a chapter outline, writes lessons with a writer/critic loop, generates quiz activities, and persists everything to Supabase. A Next.js 16 frontend subscribes to Supabase Realtime and renders the syllabus as it is built — no polling, no SSE.

## Repo layout

```
.
├── README.md                    # this file
├── plan.md                      # progress + decisions log  ← READ / UPDATE EVERY SESSION
├── syllabus_agent_spec.md       # full implementation spec (v1 + Revision 1 overrides on top)
├── LICENSE
├── agent/                       # Python LangGraph agent        (to be built)
└── frontend/                    # Next.js 16 app                (to be built)
```

## Quick links

- Spec: [`syllabus_agent_spec.md`](./syllabus_agent_spec.md) — start by reading **§ Revision 1** at the top, it supersedes conflicting content below.
- Progress log: [`plan.md`](./plan.md).
- License: MIT.
