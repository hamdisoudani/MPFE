"""clarify_with_user — Revision 2 node. Only blocking point in the graph."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langgraph.types import Command, interrupt
from ..llm import small_llm
from ..db.supabase_client import supabase

class TeacherPreferences(BaseModel):
    target_audience: str = "Adult beginners"
    num_chapters: int = Field(default=10, ge=1, le=50)
    lessons_per_chapter: int = Field(default=3, ge=1, le=10)
    pedagogical_approach: Literal["communicative","grammar_translation","task_based","mixed","project_based","direct_instruction"] = "mixed"
    activity_granularity: Literal["per_lesson","per_chapter","end_of_course","none"] = "per_lesson"
    include_activities: bool = True
    special_focus: list[str] = []
    must_cover: list[str] = []
    must_avoid: list[str] = []
    language_of_instruction: str = "English"
    total_duration_hours: Optional[int] = None

class ClarificationQuestion(BaseModel):
    key: str
    kind: Literal["text","number","single_choice","multi_choice","boolean"]
    prompt: str
    options: list[str] = []
    default: object = None
    rationale: Optional[str] = None

class ClarificationQuestions(BaseModel):
    findings_summary: str
    questions: list[ClarificationQuestion] = Field(max_length=6)

async def clarify_with_user(state: dict) -> Command:
    if state.get("teacher_preferences"):
        return Command(goto="outline_generator", update={"phase": "outlining"})

    llm = small_llm().with_structured_output(ClarificationQuestions)
    prompt = (
        "Teacher requirements:\n" + state["requirements"] +
        "\n\nFindings so far:\n" + "\n".join(state.get("findings", [])) +
        "\n\nPropose up to 6 clarifying questions with sensible defaults. "
        "Keys must be fields of TeacherPreferences."
    )
    qs: ClarificationQuestions = await llm.ainvoke(prompt)

    sb = supabase()
    sb.table("syllabuses").update({"phase": "awaiting_input"}).eq("id", state["syllabus_id"]).execute()

    answers = interrupt({
        "kind": "clarification",
        "findings_summary": qs.findings_summary,
        "questions": [q.model_dump() for q in qs.questions],
    })

    prefs = TeacherPreferences(**(answers or {}))
    sb.table("syllabuses").update({
        "phase": "outlining",
        "teacher_preferences": prefs.model_dump(),
    }).eq("id", state["syllabus_id"]).execute()

    return Command(goto="outline_generator", update={
        "teacher_preferences": prefs.model_dump(),
        "phase": "outlining",
    })
