"""Supervisor node + tool-handling nodes + router.

Topology piece (top-level graph):

   START ──► supervisor ──┬──► END (no tool calls)
                          ├──► ask_user_node (interrupt) ──► supervisor
                          ├──► apply_search_plan ──► search_subgraph ──► supervisor
                          ├──► apply_todo_plan   ──► writer_subgraph ──► supervisor
                          └──► db_tools_node ──► supervisor
"""
from __future__ import annotations
from typing import Any
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage,
)
from langgraph.types import interrupt
from langgraph.store.base import BaseStore

from .config import SUPERVISOR_MAX_TURNS, supervisor_llm
from .events import emit_awaiting_input, emit_chapter_committed, emit_error, emit_phase
from .prompts import SUPERVISOR_CONTEXT_TEMPLATE, SUPERVISOR_PERSONA
from .state import SearchPlan, TodoPlan
from .store_keys import ns_search_summary, purge_namespace
from .tools import ALL_TOOLS
from .tools.db_tools import (
    exec_create_chapters, exec_create_syllabus, exec_list_thread_syllabi, exec_set_phase,
)


# ── system prompt builder (the "middleware") ───────────────────────────────
def _format_chapter_aliases(amap: dict[str, str]) -> str:
    if not amap:
        return "  (none yet)"
    return "\n".join(f"  {ref} → {uuid[:8]}…" for ref, uuid in sorted(amap.items()))


def _format_search_plan(plan_dict: dict | None) -> str:
    if not plan_dict:
        return "  (none yet)"
    out = [f"  goal: {plan_dict.get('global_goal', '')}"]
    for s in plan_dict.get("steps") or []:
        out.append(f"  - {s['id']} [{s.get('status', 'pending')}] {s['title']}")
    return "\n".join(out)


def _format_todo_plan(plan_dict: dict | None) -> str:
    if not plan_dict:
        return "  (none yet)"
    out = []
    for s in plan_dict.get("steps") or []:
        deps = ",".join(s.get("depends_on") or []) or "-"
        kind = s.get("kind") or "lesson"
        out.append(
            f"  - {s['id']} <{kind}> [{s.get('status', 'pending')}] "
            f"{s['chapter_ref']} {s['name']} "
            f"(deps: {deps}, attempts: {s.get('attempts', 0)})"
        )
    return "\n".join(out) or "  (none yet)"


def _next_action_hint(state: dict) -> str:
    """Compute the deterministic NEXT_ACTION the supervisor should take.

    This collapses ambiguity for the LLM — when state is in a known shape,
    we tell it exactly which tool to call next.
    """
    has_summary = bool(state.get("search_summary"))
    syllabus_id = state.get("syllabus_id")
    cmap = state.get("chapter_alias_map") or {}
    todo_plan = state.get("todo_plan") or {}
    todo_steps = todo_plan.get("steps") or []
    pending = [s for s in todo_steps if s.get("status") == "pending"]
    failed = [s for s in todo_steps if s.get("status") == "failed"]
    accepted = [s for s in todo_steps if s.get("status") == "accepted"]

    if has_summary and not syllabus_id:
        return "Call `create_syllabus` with a classroom-ready title and the requirements."
    if syllabus_id and not cmap:
        return ("Call `create_chapters` with the chapter list; use the search summary to "
                "decide chapter ordering and titles.")
    if syllabus_id and cmap and not todo_steps:
        return (
            "Call `set_todo_plan` with one TodoStep per lesson AND a final "
            "activity-kind step per chapter (`kind: \"activity\"`) evaluating "
            "its lessons. Use chapter aliases "
            f"({sorted(cmap.keys())}). Add `depends_on` (prior lesson Tn ids) "
            "for any lesson that builds on earlier ones, and each activity "
            "MUST depend on the lessons it tests."
        )
    if todo_steps and not pending and not failed and accepted:
        return ("All lessons committed. Reply ONCE in plain text summarizing what was "
                "created. Do NOT call any more tools.")
    if failed:
        return ("Some todo steps failed. You may issue a tighter `set_todo_plan` for the "
                "failed steps only, or end with a plain-text summary explaining what was "
                "produced.")
    if not has_summary and not syllabus_id and not cmap and not todo_steps:
        return ("If the teacher is asking to build a syllabus and provided enough info, "
                "call `set_search_plan`. If they are just chatting, reply in plain text.")
    return "Proceed."


def _build_system_prompt(state: dict) -> str:
    summary = (state.get("search_summary") or "")[:1500] or "  (none yet)"
    hint = _next_action_hint(state)
    return (
        SUPERVISOR_PERSONA
        + "\n\n"
        + SUPERVISOR_CONTEXT_TEMPLATE.format(
            thread_id=state.get("thread_id", "?"),
            phase=state.get("phase", "idle"),
            syllabus_id=state.get("syllabus_id") or "(none)",
            prefs=state.get("teacher_preferences") or "(none)",
            chapter_alias_lines=_format_chapter_aliases(state.get("chapter_alias_map") or {}),
            search_plan_lines=_format_search_plan(state.get("search_plan")),
            search_summary=summary,
            todo_plan_lines=_format_todo_plan(state.get("todo_plan")),
        )
        + f"\n\n=== NEXT ACTION (deterministic hint) ===\n{hint}\n"
    )


def _strip_system(messages: list[BaseMessage]) -> list[BaseMessage]:
    return [m for m in messages if not isinstance(m, SystemMessage)]


# ── supervisor ─────────────────────────────────────────────────────────────
async def supervisor_node(state: dict) -> dict:
    """Single LLM turn with tools bound. The router reads tool_calls."""
    turn = state.get("_supervisor_turn", 0) + 1
    if turn > SUPERVISOR_MAX_TURNS:
        return {
            "messages": [AIMessage(
                "I've reached the maximum reasoning turns for this run. "
                "Please review the partial result or ask me to continue."
            )],
            "_supervisor_turn": turn,
            "phase": "failed",
        }

    sys = _build_system_prompt(state)
    convo = _strip_system(state.get("messages") or [])
    if not convo:
        # No user message yet — bail with a stub. Should not happen in normal use.
        convo = [HumanMessage("Hi.")]

    llm = supervisor_llm().bind_tools(ALL_TOOLS, tool_choice="auto")
    try:
        ai = await llm.ainvoke([SystemMessage(sys), *convo])
    except Exception as e:
        emit_error("supervisor", str(e))
        ai = AIMessage(f"(supervisor error: {e})")

    return {"messages": [ai], "_supervisor_turn": turn}


# ── router ─────────────────────────────────────────────────────────────────
PLAN_TOOL_SEARCH = "set_search_plan"
PLAN_TOOL_TODO = "set_todo_plan"
TOOL_ASK = "ask_user"


def _last_ai(state: dict) -> AIMessage | None:
    for m in reversed(state.get("messages") or []):
        if isinstance(m, AIMessage):
            return m
    return None


def route_after_supervisor(state: dict) -> str:
    ai = _last_ai(state)
    if not ai:
        return "__end__"
    calls = ai.tool_calls or []
    if not calls:
        return "__end__"
    names = {c["name"] for c in calls}
    if TOOL_ASK in names:
        return "ask_user_node"
    if PLAN_TOOL_SEARCH in names:
        return "apply_search_plan"
    if PLAN_TOOL_TODO in names:
        return "apply_todo_plan"
    return "db_tools_node"


# ── ask_user (interrupt) ───────────────────────────────────────────────────
async def ask_user_node(state: dict) -> dict:
    ai = _last_ai(state)
    if not ai:
        return {}
    call = next((c for c in (ai.tool_calls or []) if c["name"] == TOOL_ASK), None)
    if not call:
        return {}
    question = (call.get("args") or {}).get("question") or "(no question)"
    emit_awaiting_input(question=question)
    answer = interrupt({"question": question, "tool_call_id": call["id"]})
    # Pair the tool call with a ToolMessage and inject the human message.
    tool_msg = ToolMessage(content=str(answer), tool_call_id=call["id"])
    human = HumanMessage(str(answer))
    # Also satisfy any *other* tool calls on the same AI message with stub
    # ToolMessages so the LLM doesn't see dangling calls.
    extras: list[BaseMessage] = []
    for c in ai.tool_calls or []:
        if c["id"] == call["id"]:
            continue
        extras.append(ToolMessage(content="(deferred — only ask_user was processed)", tool_call_id=c["id"]))
    return {"messages": [tool_msg, *extras, human], "phase": "idle"}


# ── apply_search_plan → leads into search subgraph ────────────────────────
async def apply_search_plan(state: dict, *, store: BaseStore) -> dict:
    ai = _last_ai(state)
    if not ai:
        return {}
    call = next((c for c in (ai.tool_calls or []) if c["name"] == PLAN_TOOL_SEARCH), None)
    if not call:
        return {}
    args = call.get("args") or {}
    try:
        plan = SearchPlan.model_validate(args)
    except Exception as e:
        return {"messages": [ToolMessage(
            content=f"Invalid search plan: {e}", tool_call_id=call["id"]
        )]}

    # Stub the OTHER tool calls on the same AI message.
    extras: list[BaseMessage] = []
    for c in ai.tool_calls or []:
        if c["id"] == call["id"]:
            continue
        extras.append(ToolMessage(content="(deferred — only set_search_plan was processed this turn)", tool_call_id=c["id"]))

    # Reset previous search artifacts (from a possible earlier search round).
    thread_id = state.get("thread_id", "")
    if thread_id:
        try:
            await purge_namespace(store, ns_search_summary(thread_id))
        except Exception:
            pass

    emit_phase("searching")
    # Note: by the time the supervisor next reads this message, the search
    # subgraph has already run and `state.search_summary` is populated.
    # Phrase accordingly so the LLM doesn't think the search is still going.
    msg = ToolMessage(
        content=(
            f"Search plan accepted with {len(plan.steps)} steps. The system "
            "ran the queries, scraped the top results, and synthesized a single "
            "summary which is now visible to you under 'Search summary' in "
            "the CURRENT CONTEXT. Proceed to the NEXT ACTION."
        ),
        tool_call_id=call["id"],
    )
    return {
        "messages": [msg, *extras],
        "search_plan": plan.model_dump(),
        "search_step_idx": 0,
        "search_summary": None,
        "phase": "searching",
    }


# ── apply_todo_plan → leads into writer subgraph ──────────────────────────
async def apply_todo_plan(state: dict) -> dict:
    ai = _last_ai(state)
    if not ai:
        return {}
    call = next((c for c in (ai.tool_calls or []) if c["name"] == PLAN_TOOL_TODO), None)
    if not call:
        return {}
    args = call.get("args") or {}
    # Validate every chapter_ref is in the alias map.
    cmap = state.get("chapter_alias_map") or {}
    raw_steps = args.get("steps") or []
    bad_refs = sorted({s.get("chapter_ref") for s in raw_steps} - set(cmap.keys()))
    if bad_refs:
        return {"messages": [ToolMessage(
            content=(
                f"Invalid chapter_refs: {bad_refs}. "
                f"Valid aliases: {sorted(cmap.keys())}. "
                "Call create_chapters first or fix the refs."
            ),
            tool_call_id=call["id"],
        )]}
    try:
        plan = TodoPlan.model_validate(args)
    except Exception as e:
        return {"messages": [ToolMessage(
            content=f"Invalid todo plan: {e}", tool_call_id=call["id"]
        )]}

    extras: list[BaseMessage] = []
    for c in ai.tool_calls or []:
        if c["id"] == call["id"]:
            continue
        extras.append(ToolMessage(content="(deferred — only set_todo_plan was processed this turn)", tool_call_id=c["id"]))

    emit_phase("writing")
    lessons = sum(1 for s in plan.steps if s.kind == "lesson")
    activities = sum(1 for s in plan.steps if s.kind == "activity")
    msg = ToolMessage(
        content=(
            f"Todo plan accepted: {lessons} lessons + {activities} activities. "
            "The system ran the writer/critic loop. Final per-step statuses "
            "are now visible under 'Todo plan steps' in the CURRENT CONTEXT. "
            "Proceed to the NEXT ACTION."
        ),
        tool_call_id=call["id"],
    )
    exec_set_phase(state.get("syllabus_id"), "writing")
    return {
        "messages": [msg, *extras],
        "todo_plan": plan.model_dump(),
        "todo_step_idx": 0,
        "_todo_started_emitted": False,
        "phase": "writing",
    }


# ── db_tools_node: executes create_syllabus / create_chapters / list ──────
async def db_tools_node(state: dict) -> dict:
    ai = _last_ai(state)
    if not ai:
        return {}
    out_msgs: list[BaseMessage] = []
    syllabus_update: dict[str, Any] = {}
    cmap_update: dict[str, str] = {}
    for c in ai.tool_calls or []:
        name = c["name"]
        cid = c["id"]
        args = c.get("args") or {}
        try:
            if name == "create_syllabus":
                title = args.get("title") or "(untitled)"
                req = args.get("requirements")
                row = exec_create_syllabus(state.get("thread_id", ""), title, req)
                syllabus_update["syllabus_id"] = row.get("id")
                syllabus_update["title"] = row.get("title")
                out_msgs.append(ToolMessage(
                    content=f"Created syllabus row id={row.get('id')} title={row.get('title')}.",
                    tool_call_id=cid,
                ))
            elif name == "create_chapters":
                if not state.get("syllabus_id") and not syllabus_update.get("syllabus_id"):
                    out_msgs.append(ToolMessage(
                        content="No syllabus_id yet. Call create_syllabus first.",
                        tool_call_id=cid,
                    ))
                    continue
                sid = syllabus_update.get("syllabus_id") or state.get("syllabus_id")
                amap = exec_create_chapters(sid, args.get("chapters") or [])
                cmap_update.update(amap)
                # emit per-chapter committed events
                for ref, uuid in amap.items():
                    pos = int(ref[2:]) if ref.startswith("CH") else 0
                    title = (args.get("chapters") or [])[max(pos-1, 0)].get("title") if args.get("chapters") else ref
                    emit_chapter_committed(ref, uuid, title or ref, pos)
                out_msgs.append(ToolMessage(
                    content=f"Inserted {len(amap)} chapters. Aliases: {amap}",
                    tool_call_id=cid,
                ))
            elif name == "list_thread_syllabi":
                rows = exec_list_thread_syllabi(state.get("thread_id", ""))
                out_msgs.append(ToolMessage(
                    content=f"{len(rows)} prior syllabi: {rows}",
                    tool_call_id=cid,
                ))
            else:
                out_msgs.append(ToolMessage(
                    content=f"Unknown tool {name}", tool_call_id=cid,
                ))
        except Exception as e:
            emit_error(f"tool:{name}", str(e))
            out_msgs.append(ToolMessage(
                content=f"Tool {name} failed: {e}", tool_call_id=cid,
            ))
    update = {"messages": out_msgs}
    if syllabus_update:
        update.update(syllabus_update)
    if cmap_update:
        update["chapter_alias_map"] = cmap_update
    return update
