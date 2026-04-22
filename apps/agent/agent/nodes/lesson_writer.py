"""write_lesson — markdown output; honors special_focus + pedagogical_approach + prior critique."""
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

    prior_critique = state.get("_critique") or {}
    prior_attempts = int(state.get("_draft_attempts") or 0)
    same_substep = state.get("_draft_substep_id") == substep_id
    revision_block = ""
    if same_substep and prior_attempts > 0 and prior_critique:
        issues = prior_critique.get("issues") or prior_critique.get("reasons") or prior_critique.get("feedback") or prior_critique
        revision_block = (
            f"\n\nThis is revision attempt #{prior_attempts + 1}. The previous draft was REJECTED by the critic.\n"
            f"Critic feedback to address: {issues}\n"
            "Explicitly fix every issue above. Keep what worked; rewrite what did not."
        )

    llm = writer_llm().with_structured_output(LessonDraft)
    draft: LessonDraft = llm.invoke(
        f"Write lesson {next_pos} of chapter '{chapter['title']}' — {chapter['summary']}.\n"
        f"Approach: {prefs.get('pedagogical_approach','mixed')}. "
        f"Focus: {prefs.get('special_focus', [])}. Language: {prefs.get('language_of_instruction','English')}.\n"
        "CEFR level A1: very short sentences, high-frequency vocabulary, present tense, 1 grammar point, "
        "3-5 example dialogues, a vocabulary list of 8-12 items, and a short practice section. "
        "Return markdown."
        + revision_block
    )
    return Command(goto="critic_node", update={
        "_draft": draft.model_dump(),
        "_draft_chapter_pos": chapter["position"],
        "_draft_position": next_pos,
        "_draft_substep_id": substep_id,
    })
