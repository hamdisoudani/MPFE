"""accept_lesson — persists lesson, clears draft scratchpad (GC), routes to activity scheduler."""
from langgraph.types import Command
from ..db.supabase_client import supabase

def accept_lesson(state: dict) -> Command:
    draft = state["_draft"]
    sb = supabase()
    row = sb.table("lessons").upsert({
        "chapter_id": state["active_chapter_id"],
        "syllabus_id": state["syllabus_id"],
        "substep_id": state["_draft_substep_id"],
        "position": state["_draft_position"],
        "title": draft["title"],
        "content_markdown": draft["content_markdown"],
        "summary": draft["summary"],
        "needs_review": False,
        "draft_attempts": int(state.get("_draft_attempts") or 0),
    }, on_conflict="substep_id").execute().data[0]

    gc = {"_draft": None, "_draft_chapter_pos": None, "_draft_position": None,
          "_draft_substep_id": None, "_draft_attempts": 0, "_critique": None}
    prefs = state.get("teacher_preferences") or {}
    if not prefs.get("include_activities", True):
        return Command(goto="chapter_guard", update={**gc, "active_lesson_id": row["id"]})
    return Command(goto="activities_generator", update={**gc, "active_lesson_id": row["id"]})
