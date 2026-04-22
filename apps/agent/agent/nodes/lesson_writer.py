"""write_lesson — honors lesson_plan requirements; injects prior critique on retries."""
from __future__ import annotations
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase

class LessonDraft(BaseModel):
    title: str
    content_markdown: str
    summary: str

def _find_plan(state: dict, substep_id: str):
    for p in state.get("lesson_plans") or []:
        if p.get("substep_id") == substep_id:
            return p
    return None

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

    prior_critique = state.get("_critique") or ""
    prior_attempts = int(state.get("_draft_attempts") or 0)
    same = state.get("_draft_substep_id") == substep_id
    revision_block = ""
    if same and prior_attempts > 0 and prior_critique:
        revision_block = (
            f"\n\n### REVISION #{prior_attempts+1} — previous draft was REJECTED\n"
            f"Critic feedback (address every item):\n{prior_critique}\n"
            "Explicitly fix each issue. Preserve what worked."
        )

    plan_block = ""
    if plan:
        plan_block = (
            f"\n\n### PLAN CONTRACT (you MUST satisfy all of these)\n"
            f"- Planned title: {plan.get('title')}\n"
            f"- Learning objective: {plan.get('learning_objective')}\n"
            f"- must_cover (each item appears in the lesson): {plan.get('must_cover')}\n"
            f"- Grammar focus: {plan.get('grammar_point')}\n"
            f"- Vocabulary targets (include every item in the vocab list): {plan.get('vocab_targets')}\n"
        )

    llm = writer_llm().with_structured_output(LessonDraft)
    draft: LessonDraft = llm.invoke(
        f"Write lesson {next_pos} of chapter '{chapter['title']}' — {chapter['summary']}.\n"
        f"Approach: {prefs.get('pedagogical_approach','mixed')}. "
        f"Focus: {prefs.get('special_focus', [])}. Language: {prefs.get('language_of_instruction','English')}.\n"
        f"Target audience: {prefs.get('target_audience','adult learners')}.\n"
        "Structure: explicit objective line, grammar explanation, 3-5 dialogues/examples, vocabulary list, practice section."
        + plan_block
        + revision_block
        + "\nReturn markdown."
    )
    return Command(goto="critic_node", update={
        "_draft": draft.model_dump(),
        "_draft_chapter_pos": chapter["position"],
        "_draft_position": next_pos,
        "_draft_substep_id": substep_id,
    })
