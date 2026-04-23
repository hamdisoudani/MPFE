"""reject_lesson — bump attempts; force-accept w/ needs_review after 3; still runs activities."""
from langgraph.types import Command
from ..db.supabase_client import supabase
from ..events import emit_lesson_committed

def reject_lesson(state: dict) -> Command:
    attempts = int(state.get("_draft_attempts", 0)) + 1
    if attempts >= 3:
        draft = state["_draft"]
        substep_id = state["_draft_substep_id"]
        position = state["_draft_position"]
        chapter_id = state["active_chapter_id"]
        sb = supabase()
        row = sb.table("lessons").upsert({
            "chapter_id": chapter_id,
            "syllabus_id": state["syllabus_id"],
            "substep_id": substep_id,
            "position": position,
            "title": draft["title"],
            "content_markdown": draft["content_markdown"],
            "summary": draft["summary"],
            "draft_attempts": attempts,
            "needs_review": True,
        }, on_conflict="substep_id").execute().data[0]

        emit_lesson_committed(
            lesson_id=row["id"], lesson_substep_id=substep_id, chapter_id=chapter_id,
            position=position, needs_review=True, attempts=attempts,
        )

        gc = {"_draft": None, "_draft_chapter_pos": None, "_draft_position": None,
              "_draft_substep_id": None, "_draft_attempts": 0, "_critique": None}
        state_lesson_mirror = [{
            "id": row["id"], "substep_id": substep_id, "chapter_id": chapter_id,
            "position": position, "title": draft["title"],
            "draft_attempts": attempts, "needs_review": True,
        }]
        prefs = state.get("teacher_preferences") or {}
        goto = "activities_generator" if prefs.get("include_activities", True) else "chapter_guard"
        return Command(goto=goto, update={**gc,
                                          "active_lesson_id": row["id"],
                                          "lessons": state_lesson_mirror})
    return Command(goto="write_lesson", update={"_draft_attempts": attempts})
