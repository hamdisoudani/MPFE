"""self_awareness — entry. Seed syllabus row + infer phase from DB."""
from __future__ import annotations
from typing import Any
from langgraph.types import Command
from ..db.supabase_client import supabase
from ..events import emit_phase, emit

def self_awareness(state: dict) -> Command:
    sb = supabase()
    thread_id = state["thread_id"]
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
        return Command(goto="search_planner", update={"syllabus_id": data["id"], "phase": "searching"})
    data = row.data
    phase = data["phase"]
    emit_phase(phase)
    upd: dict[str, Any] = {"syllabus_id": data["id"], "phase": phase,
                           "teacher_preferences": data.get("teacher_preferences")}
    if phase in ("searching", "awaiting_input"):
        return Command(goto="search_planner", update=upd)
    if phase == "outlining":
        return Command(goto="clarify_with_user", update=upd)
    if phase == "writing":
        return Command(goto="chapter_guard", update=upd)
    return Command(goto="__end__", update=upd)
