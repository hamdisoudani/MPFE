"""write_lesson — markdown output; honors special_focus + pedagogical_approach."""
from __future__ import annotations
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase

class LessonDraft(BaseModel):
    title: str
    content_markdown: str
    summary: str

def write_lesson(state: dict) -> Command:
    sb = supabase()
    ch_id = state["active_chapter_id"]
    prefs = state.get("teacher_preferences") or {}
    lpc = prefs.get("lessons_per_chapter", 3)

    existing = sb.table("lessons").select("position").eq("chapter_id", ch_id).order("position").execute()
    next_pos = (max([r["position"] for r in existing.data], default=0)) + 1
    if next_pos > lpc:
        sb.table("chapters").update({"status": "done"}).eq("id", ch_id).execute()
        return Command(goto="chapter_guard", update={
            "chapters": [{"id": ch_id, "status": "done"}],
            "active_chapter_id": None,
        })

    chapter = sb.table("chapters").select("*").eq("id", ch_id).single().execute().data
    substep_id = f"{state['syllabus_id']}::ch{chapter['position']}::l{next_pos}"

    llm = writer_llm().with_structured_output(LessonDraft)
    draft: LessonDraft = llm.invoke(
        f"Write lesson {next_pos} of chapter '{chapter['title']}' — {chapter['summary']}.\n"
        f"Approach: {prefs.get('pedagogical_approach','mixed')}. "
        f"Focus: {prefs.get('special_focus', [])}. Language: {prefs.get('language_of_instruction','English')}.\n"
        "Return markdown."
    )
    return Command(goto="critic_node", update={
        "_draft": draft.model_dump(),
        "_draft_chapter_pos": chapter["position"],
        "_draft_position": next_pos,
        "_draft_substep_id": substep_id,
    })
