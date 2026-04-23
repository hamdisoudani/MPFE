"""finalize — mark all chapters + syllabus as done at end of optimized run."""
from langgraph.types import Command
from ..db.supabase_client import supabase

def finalize(state: dict) -> Command:
    sb = supabase()
    sid = state.get("syllabus_id")
    if sid:
        try:
            sb.table("chapters").update({"status": "done"}).eq("syllabus_id", sid).execute()
            sb.table("syllabuses").update({"phase": "done"}).eq("id", sid).execute()
        except Exception as e:
            print(f"[finalize] warn: {e}")
    chapters = [{"id": c["id"], "status": "done"} for c in (state.get("chapters") or [])]
    return Command(goto="__end__", update={"phase": "done", "chapters": chapters})
