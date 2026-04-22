"""reject_lesson — bump attempts, reroute."""
from langgraph.types import Command
from ..db.supabase_client import supabase


def reject_lesson(state: dict) -> Command:
    attempts = state.get("_draft_attempts", 0) + 1
    if attempts >= 3:
        draft = state["_draft"]
        sb = supabase()
        sb.table("lessons").upsert({
            "chapter_id": state["active_chapter_id"],
            "syllabus_id": state["syllabus_id"],
            "substep_id": state["_draft_substep_id"],
            "position": state["_draft_position"],
            "title": draft["title"],
            "content_markdown": draft["content_markdown"],
            "summary": draft["summary"],
            "draft_attempts": attempts,
            "needs_review": True,
        }, on_conflict="substep_id").execute()
        return Command(goto="chapter_guard", update={"_draft_attempts": 0})
    return Command(goto="write_lesson", update={"_draft_attempts": attempts})
