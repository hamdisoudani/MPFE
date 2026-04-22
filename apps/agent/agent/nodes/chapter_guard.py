"""chapter_guard — picks next pending chapter or routes to END."""
from langgraph.types import Command
from ..db.supabase_client import supabase

def chapter_guard(state: dict) -> Command:
    for ch in state.get("chapters", []):
        if ch["status"] != "done":
            return Command(goto="write_lesson", update={"active_chapter_id": ch["id"]})
    sid = state.get("syllabus_id")
    if sid:
        try:
            supabase().table("syllabuses").update({"phase": "done"}).eq("id", sid).execute()
        except Exception:
            pass
    return Command(goto="__end__", update={"phase": "done"})
