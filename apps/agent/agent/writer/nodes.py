"""Writer/Critic subgraph nodes.

Each iteration handles one TodoStep:
   pick_next ─► write ─► critic ─► decide ──accept──► commit ─► pick_next
                              ↑          ──reject──► write (≤MAX)
                              │          ──fail────► pick_next

`pick_next` exits the subgraph when no pending steps remain (or all
remaining are blocked by failed deps).
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.store.base import BaseStore

from ..config import (
    MAX_WRITER_ATTEMPTS, writer_llm, critic_llm,
)
from ..events import (
    emit_phase, emit_todo_started, emit_todo_step,
    emit_critic, emit_lesson_committed, emit_error,
)
from ..prompts import (
    WRITER_PERSONA, WRITER_TASK_TEMPLATE, WRITER_RETRY_TEMPLATE,
    CRITIC_PERSONA, CRITIC_TASK_TEMPLATE,
)
from ..state import TodoPlan, TodoStep
from ..store_keys import ns_dep_summary, ns_draft, purge_namespace
from ..tools.db_tools import (
    exec_commit_lesson, exec_set_chapter_status, exec_set_phase,
)


# ── pydantic models for structured outputs ────────────────────────────────
class LessonOut(BaseModel):
    title: str
    content_markdown: str = Field(description="GitHub-flavored markdown.")
    summary: str = Field(description="1-2 sentence summary for downstream lessons.")


class PerCriterion(BaseModel):
    item: str
    present: bool
    note: Optional[str] = None


class CriticOut(BaseModel):
    score: int = Field(ge=0, le=100)
    passes: bool
    weaknesses: list[str] = Field(default_factory=list)
    per_must_cover: list[PerCriterion] = Field(default_factory=list)
    critique: str


# ── helpers ───────────────────────────────────────────────────────────────
def _plan_from_state(state: dict) -> TodoPlan | None:
    raw = state.get("todo_plan")
    if not raw:
        return None
    return TodoPlan.model_validate(raw)


def _to_state(plan: TodoPlan) -> dict:
    return plan.model_dump()


def _eligible_idx(plan: TodoPlan) -> int | None:
    """First pending step whose dependencies are all accepted. -1 if blocked."""
    accepted = {s.id for s in plan.steps if s.status == "accepted"}
    failed = {s.id for s in plan.steps if s.status == "failed"}
    for i, s in enumerate(plan.steps):
        if s.status not in ("pending",):
            continue
        deps = set(s.depends_on or [])
        if deps & failed:
            # mark as failed too (cannot satisfy)
            s.status = "failed"
            plan.steps[i] = s
            continue
        if deps - accepted:
            continue
        return i
    return None


async def _read_dep_summaries(store: BaseStore, thread_id: str, deps: list[str]) -> str:
    blocks = []
    for did in deps or []:
        try:
            it = await store.aget(ns_dep_summary(thread_id, did), "current")
        except Exception:
            it = None
        if it and it.value:
            v = it.value
            blocks.append(
                f"- **{v.get('chapter_ref', '?')} / {did} — {v.get('title', '')}**: {v.get('summary', '')}"
            )
    return "\n".join(blocks) if blocks else "(none)"


# ── pick_next ─────────────────────────────────────────────────────────────
async def pick_next(state: dict) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {"phase": "idle", "_writer_done": True}

    started_total = state.get("_todo_started_emitted")
    if not started_total:
        emit_todo_started(steps_total=len(plan.steps))

    idx = _eligible_idx(plan)
    if idx is None:
        all_done = all(s.status in ("accepted", "failed") for s in plan.steps)
        any_failed = any(s.status == "failed" for s in plan.steps)
        # Mark syllabus phase + emit phase event
        if all_done:
            from ..tools.db_tools import exec_set_phase
            exec_set_phase(state.get("syllabus_id"), "failed" if any_failed else "done")
        return {
            "todo_plan": _to_state(plan),
            "phase": ("failed" if any_failed else "done") if all_done else "outlining",
            "_writer_done": True,
            "_todo_started_emitted": True,
        }
    step = plan.steps[idx]
    step.status = "writing"
    step.attempts = (step.attempts or 0) + 1
    plan.steps[idx] = step
    emit_phase("writing")
    emit_todo_step(step.id, step.chapter_ref, step.name, step.attempts, "writing")

    # Set chapter to "writing" status in supabase
    cmap = state.get("chapter_alias_map") or {}
    cid = cmap.get(step.chapter_ref)
    if cid:
        exec_set_chapter_status(cid, "writing")

    return {
        "todo_plan": _to_state(plan),
        "todo_step_idx": idx,
        "phase": "writing",
        "_todo_started_emitted": True,
        "_writer_done": False,
    }


# ── write ─────────────────────────────────────────────────────────────────
async def write_node(state: dict, *, store: BaseStore) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {}
    idx = state.get("todo_step_idx", 0)
    step = plan.steps[idx]
    thread_id = state.get("thread_id", "")
    dep_block = await _read_dep_summaries(store, thread_id, step.depends_on or [])

    # Retry block (read previous critique from draft store if present)
    retry_block = ""
    prev_attempt = step.attempts - 1
    if prev_attempt >= 1:
        try:
            it = await store.aget(ns_draft(thread_id, step.id), "current")
        except Exception:
            it = None
        if it and it.value and it.value.get("critique"):
            retry_block = WRITER_RETRY_TEMPLATE.format(
                prev_attempt=prev_attempt,
                critique=(it.value.get("critique") or "")[:2000],
                weaknesses="\n".join(f"- {w}" for w in (it.value.get("weaknesses") or [])[:8]),
            )

    user = WRITER_TASK_TEMPLATE.format(
        step_id=step.id,
        chapter_ref=step.chapter_ref,
        name=step.name,
        description=step.description,
        must_cover="\n".join(f"- {x}" for x in (step.must_cover or [])) or "(none)",
        dep_block=dep_block,
        search_summary=(state.get("search_summary") or "")[:6000],
        retry_block=retry_block,
    )

    try:
        llm = writer_llm().with_structured_output(LessonOut, method="function_calling")
        out: LessonOut = await llm.ainvoke([
            SystemMessage(WRITER_PERSONA),
            HumanMessage(user),
        ])
    except Exception as e:
        emit_error("writer", str(e))
        # save a minimal failure marker so critic can reject cleanly
        try:
            await store.aput(ns_draft(thread_id, step.id), "current", {
                "title": step.name,
                "content_md": f"# {step.name}\n\n*(writer failed: {e})*",
                "summary": "",
                "attempt": step.attempts,
                "critique": None,
                "weaknesses": [],
            })
        except Exception:
            pass
        return {}

    try:
        await store.aput(ns_draft(thread_id, step.id), "current", {
            "title": out.title,
            "content_md": out.content_markdown,
            "summary": out.summary,
            "attempt": step.attempts,
            "critique": None,
            "weaknesses": [],
        })
    except Exception as e:
        emit_error("writer_store", str(e))

    return {}


# ── critic ────────────────────────────────────────────────────────────────
async def critic_node(state: dict, *, store: BaseStore) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {}
    idx = state.get("todo_step_idx", 0)
    step = plan.steps[idx]
    thread_id = state.get("thread_id", "")

    try:
        it = await store.aget(ns_draft(thread_id, step.id), "current")
    except Exception:
        it = None
    if not it or not it.value:
        # no draft to evaluate — synthesize a fail
        report = CriticOut(score=0, passes=False, weaknesses=["no draft"], critique="No draft was produced.")
    else:
        v = it.value
        dep_block = await _read_dep_summaries(store, thread_id, step.depends_on or [])
        user = CRITIC_TASK_TEMPLATE.format(
            step_id=step.id,
            chapter_ref=step.chapter_ref,
            attempt=v.get("attempt", step.attempts),
            description=step.description,
            must_cover="\n".join(f"- {x}" for x in (step.must_cover or [])) or "(none)",
            dep_block=dep_block,
            draft=(v.get("content_md") or "")[:14000],
        )
        try:
            llm = critic_llm().with_structured_output(CriticOut, method="function_calling")
            report = await llm.ainvoke([
                SystemMessage(CRITIC_PERSONA),
                HumanMessage(user),
            ])
        except Exception as e:
            emit_error("critic", str(e))
            report = CriticOut(
                score=0, passes=False,
                weaknesses=[f"critic error: {e}"],
                critique="Critic LLM failed; treating as reject.",
            )

    # Persist critique back into draft so writer can read on retry.
    try:
        cur = (await store.aget(ns_draft(thread_id, step.id), "current")).value or {}
    except Exception:
        cur = {}
    cur.update({
        "critique": report.critique,
        "weaknesses": report.weaknesses,
        "score": report.score,
        "passes": report.passes,
    })
    try:
        await store.aput(ns_draft(thread_id, step.id), "current", cur)
    except Exception:
        pass

    emit_critic(step.id, step.attempts, report.passes, report.score, report.weaknesses)

    return {"_critic_passes": bool(report.passes), "_critic_score": int(report.score)}


# ── decide ────────────────────────────────────────────────────────────────
def decide_node(state: dict) -> str:
    """Conditional edge — accept / retry / fail."""
    plan = _plan_from_state(state)
    if not plan:
        return "pick_next"
    idx = state.get("todo_step_idx", 0)
    step = plan.steps[idx]
    if state.get("_critic_passes"):
        return "commit"
    if step.attempts >= MAX_WRITER_ATTEMPTS:
        return "give_up"
    return "write"


# ── commit ────────────────────────────────────────────────────────────────
async def commit_node(state: dict, *, store: BaseStore) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {}
    idx = state.get("todo_step_idx", 0)
    step = plan.steps[idx]
    thread_id = state.get("thread_id", "")
    syllabus_id = state.get("syllabus_id")
    cmap = state.get("chapter_alias_map") or {}
    cid = cmap.get(step.chapter_ref)
    if not (syllabus_id and cid):
        emit_error("commit", f"missing syllabus_id ({syllabus_id}) or chapter_id for {step.chapter_ref}")
        step.status = "failed"
        plan.steps[idx] = step
        return {"todo_plan": _to_state(plan)}

    try:
        it = await store.aget(ns_draft(thread_id, step.id), "current")
    except Exception:
        it = None
    if not it or not it.value:
        step.status = "failed"
        plan.steps[idx] = step
        return {"todo_plan": _to_state(plan)}

    draft = it.value
    # Position within chapter — count accepted lessons in this chapter so far + 1.
    pos = 1 + sum(
        1 for s in plan.steps
        if s.chapter_ref == step.chapter_ref and s.status == "accepted"
    )

    try:
        row = exec_commit_lesson(
            syllabus_id=syllabus_id,
            chapter_id=cid,
            substep_id=step.id,
            position=pos,
            title=draft.get("title", step.name),
            content_md=draft.get("content_md", ""),
            summary=draft.get("summary"),
            draft_attempts=int(draft.get("attempt", step.attempts) or 1),
            needs_review=False,
        )
    except Exception as e:
        emit_error("commit_lesson", str(e))
        step.status = "failed"
        plan.steps[idx] = step
        return {"todo_plan": _to_state(plan)}

    lesson_id = row.get("id")
    step.status = "accepted"
    step.final_lesson_id = lesson_id
    plan.steps[idx] = step
    emit_lesson_committed(step.id, lesson_id or "", cid, draft.get("title", step.name))

    # If this was the last lesson in the chapter, mark chapter as done.
    chapter_steps = [s for s in plan.steps if s.chapter_ref == step.chapter_ref]
    if chapter_steps and all(s.status == "accepted" for s in chapter_steps):
        exec_set_chapter_status(cid, "done")

    # Save dep summary for downstream lessons.
    try:
        await store.aput(ns_dep_summary(thread_id, step.id), "current", {
            "title": draft.get("title", step.name),
            "summary": draft.get("summary") or "",
            "chapter_ref": step.chapter_ref,
        })
    except Exception:
        pass

    # GC draft.
    try:
        await purge_namespace(store, ns_draft(thread_id, step.id))
    except Exception:
        pass

    return {"todo_plan": _to_state(plan)}


async def give_up_node(state: dict, *, store: BaseStore) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {}
    idx = state.get("todo_step_idx", 0)
    step = plan.steps[idx]
    step.status = "failed"
    plan.steps[idx] = step
    emit_todo_step(step.id, step.chapter_ref, step.name, step.attempts, "failed")
    # GC draft for the failed step too.
    try:
        await purge_namespace(store, ns_draft(state.get("thread_id", ""), step.id))
    except Exception:
        pass
    return {"todo_plan": _to_state(plan)}
