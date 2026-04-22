"""write_lesson — plan-contract aware; carries chapter.goal; injects critic report on retries."""
from __future__ import annotations
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase
from ..prompts import writer_prompt

class LessonDraft(BaseModel):
    title: str
    content_markdown: str
    summary: str

def _find_plan(state: dict, substep_id: str):
    for p in state.get("lesson_plans") or []:
        if p.get("substep_id") == substep_id:
            return p
    return None

def _find_chapter_goal(state: dict, chapter_pos: int) -> str:
    for c in state.get("chapters") or []:
        if c.get("position") == chapter_pos:
            return c.get("goal") or ""
    return ""

def write_lesson(state: dict) -> Command:
    sb = supabase()
    ch_id = state["active_chapter_id"]
    prefs = state.get("teacher_preferences") or {}
    lpc = prefs.get("lessons_per_chapter", 3)

    existing = sb.table("lessons").select("position").eq("chapter_id", ch_id).order("position").execute()
    next_pos = (max([r["position"] for r in existing.data], default=0)) + 1
    if next_pos > lpc:
        sb.table("chapters").update({"status": "done"}).eq("id", ch_id).execute()
        return Command(goto="activities_generator", update={
            "chapters": [{"id": ch_id, "status": "done"}],
        })

    chapter = sb.table("chapters").select("*").eq("id", ch_id).single().execute().data
    substep_id = f"{state['syllabus_id']}::ch{chapter['position']}::l{next_pos}"
    plan = _find_plan(state, substep_id) or {}
    chapter_goal = _find_chapter_goal(state, chapter["position"])

    prior_attempts = int(state.get("_draft_attempts") or 0)
    same = state.get("_draft_substep_id") == substep_id
    prior_critique = state.get("_critique") if (same and prior_attempts > 0) else None

    llm = writer_llm().with_structured_output(LessonDraft)
    draft: LessonDraft = llm.invoke(writer_prompt(
        chapter=chapter, lesson_pos=next_pos, prefs=prefs, plan=plan,
        chapter_goal=chapter_goal, prior_critique=prior_critique,
        attempt_num=prior_attempts + 1,
    ))
    return Command(goto="critic_node", update={
        "_draft": draft.model_dump(),
        "_draft_chapter_pos": chapter["position"],
        "_draft_position": next_pos,
        "_draft_substep_id": substep_id,
    })
