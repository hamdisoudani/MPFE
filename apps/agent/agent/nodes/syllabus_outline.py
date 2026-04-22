"""outline_generator — builds chapters respecting teacher preferences."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase


class ChapterDraft(BaseModel):
    title: str
    summary: str


class OutlineDraft(BaseModel):
    chapters: list[ChapterDraft]


def outline_generator(state: dict) -> Command:
    prefs = state.get("teacher_preferences") or {}
    n = prefs.get("num_chapters", 10)
    llm = writer_llm().with_structured_output(OutlineDraft)
    outline: OutlineDraft = llm.invoke(
        f"Build an outline of exactly {n} chapters for:\n{state['requirements']}\n"
        f"Preferences: {prefs}\nFindings:\n" + "\n".join(state.get("findings", []))
    )
    sb = supabase()
    rows = [{"syllabus_id": state["syllabus_id"], "position": i+1,
             "title": c.title, "summary": c.summary, "status": "pending"}
            for i, c in enumerate(outline.chapters[:n])]
    resp = sb.table("chapters").upsert(rows, on_conflict="syllabus_id,position").execute()
    sb.table("syllabuses").update({"phase": "writing"}).eq("id", state["syllabus_id"]).execute()
    chapters = [{"id": r["id"], "position": r["position"], "title": r["title"], "status": "pending"}
                for r in resp.data]
    return Command(goto="chapter_guard", update={"chapters": chapters, "phase": "writing"})
