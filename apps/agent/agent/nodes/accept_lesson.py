"""accept_lesson — upsert lesson row, maybe run activities."""
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
    }, on_conflict="substep_id").execute().data[0]

    prefs = state.get("teacher_preferences") or {}
    if not prefs.get("include_activities", True):
        return Command(goto="chapter_guard", update={"active_lesson_id": row["id"]})
    granularity = prefs.get("activity_granularity", "per_lesson")
    if granularity == "per_lesson":
        return Command(goto="activities_generator", update={"active_lesson_id": row["id"]})
    if granularity == "per_chapter" and state["_draft_position"] >= prefs.get("lessons_per_chapter", 3):
        return Command(goto="activities_generator", update={"active_lesson_id": None})
    return Command(goto="chapter_guard", update={"active_lesson_id": row["id"]})
