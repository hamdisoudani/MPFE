"""self_awareness — entry. Seed syllabus row + infer phase from DB."""
from __future__ import annotations
from typing import Any
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from ..db.supabase_client import supabase
from ..events import emit_phase, emit


def _thread_id(state: dict, config) -> str:
    cfg = (config or {}).get("configurable") or {}
    tid = cfg.get("thread_id") or state.get("thread_id")
    if not tid:
        raise ValueError("thread_id missing from both config.configurable and state")
    return tid


def self_awareness(state: dict, config: RunnableConfig = None) -> Command:  # type: ignore[assignment]
    sb = supabase()
    thread_id = _thread_id(state, config)
    row = sb.table("syllabuses").select("*").eq("thread_id", thread_id).maybe_single().execute()
    if not row or not row.data:
        ins = sb.table("syllabuses").upsert({
            "thread_id": thread_id,
            "title": state.get("title") or "Untitled",
            "requirements": state["requirements"],
            "phase": "searching",
        }, on_conflict="thread_id").execute()
        data = ins.data[0]
        emit("syllabus_created", syllabus_id=data["id"], title=data["title"])
        emit_phase("searching")
        return Command(goto="search_planner", update={"thread_id": thread_id, "syllabus_id": data["id"], "phase": "searching"})
    data = row.data
    phase = data["phase"]
    emit_phase(phase)
    upd: dict[str, Any] = {"thread_id": thread_id, "syllabus_id": data["id"], "phase": phase,
                           "teacher_preferences": data.get("teacher_preferences")}
    if phase in ("searching", "awaiting_input"):
        return Command(goto="search_planner", update=upd)
    if phase == "outlining":
        return Command(goto="clarify_with_user", update=upd)
    if phase == "writing":
        return Command(goto="chapter_guard", update=upd)
    return Command(goto="__end__", update=upd)
