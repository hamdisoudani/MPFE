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


## Execution environment — E2B sandbox

**All code execution for this project (tests, builds, lints, migrations, pushes, one-off scripts) runs inside an E2B sandbox.** The local/agent VM is only used to orchestrate; the sandbox is the real workspace.

- **Template:** `desktop` — 8 vCPU, 8 GB RAM, Ubuntu-based, has Python 3.10, git, curl. Node/pnpm installed on demand per project.
- **Reuse policy (in order):**
  1. Call `Sandbox.list()` — if any RUNNING sandbox on the account has template `desktop`, reuse it. This is the authoritative check because the sandbox id in the repo can be stale.
  2. Else try the id in `.e2b_sandbox.json` via `Sandbox.connect(sandbox_id)`.
  3. Else `Sandbox.create(template="desktop", timeout=3600)`.
- **Persistence:** `.e2b_sandbox.json` (committed — the id is useless without `E2B_API_KEY`) records `{sandbox_id, created_at, template}`. Acts as a hint across sessions; the `list()` call is the ground truth.
- **Timeout:** default 1 h, bump per-job via `sbx.set_timeout(seconds)`. Max is whatever your E2B plan allows.
- **Helper:** `scripts/e2b_sandbox.py` — `get_sandbox()` reconnects or creates, `python scripts/e2b_sandbox.py kill` tears it down.
- **Credentials:** `E2B_API_KEY` and `GITHUB_PAT` are passed in per session, never committed. The agent will request them when needed.
- **Verified SDK surface** (tested 2026-04-22 against `e2b` Python SDK):
  - `Sandbox.create(template="desktop", timeout=3600)` → new VM.
  - `Sandbox.connect(sandbox_id)` → reattach.
  - `sbx.commands.run(cmd, timeout=...)` → exec with stdout/stderr/exit code.
  - `sbx.files.write(path, contents)` / `sbx.files.read(path)` → FS access.
  - `sbx.set_timeout(sec)` → extend auto-kill timer.
  - `sbx.get_info()` → `{cpu_count, memory_mb, state, started_at, end_at}`.
  - `sbx.kill()` → shutdown (idempotent).
- **Workflow:** `pnpm install`, `pnpm test`, `pnpm build`, `supabase db push`, `git push` — all run via `sbx.commands.run(...)`. Artifacts stay inside the sandbox FS between steps of the same session.
