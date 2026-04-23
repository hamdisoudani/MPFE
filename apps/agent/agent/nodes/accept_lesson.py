"""accept_lesson — persists lesson, mirrors into state.lessons, GCs scratchpad, routes to activities."""
from langgraph.types import Command
from ..db.supabase_client import supabase
from ..events import emit_lesson_committed

def accept_lesson(state: dict) -> Command:
    draft = state["_draft"]
    sb = supabase()
    substep_id = state["_draft_substep_id"]
    position = state["_draft_position"]
    chapter_id = state["active_chapter_id"]
    attempts = int(state.get("_draft_attempts") or 0) + 1

    row = sb.table("lessons").upsert({
        "chapter_id": chapter_id,
        "syllabus_id": state["syllabus_id"],
        "substep_id": substep_id,
        "position": position,
        "title": draft["title"],
        "content_markdown": draft["content_markdown"],
        "summary": draft["summary"],
        "needs_review": False,
        "draft_attempts": attempts,
    }, on_conflict="substep_id").execute().data[0]

    emit_lesson_committed(
        lesson_id=row["id"], lesson_substep_id=substep_id, chapter_id=chapter_id,
        position=position, needs_review=False, attempts=attempts,
    )

    gc = {"_draft": None, "_draft_chapter_pos": None, "_draft_position": None,
          "_draft_substep_id": None, "_draft_attempts": 0, "_critique": None}
    state_lesson_mirror = [{
        "id": row["id"], "substep_id": substep_id, "chapter_id": chapter_id,
        "position": position, "title": draft["title"],
        "draft_attempts": attempts, "needs_review": False,
    }]
    prefs = state.get("teacher_preferences") or {}
    goto = "activities_generator" if prefs.get("include_activities", True) else "chapter_guard"
    return Command(goto=goto, update={**gc,
                                      "active_lesson_id": row["id"],
                                      "lessons": state_lesson_mirror})
