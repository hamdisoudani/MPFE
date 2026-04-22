"""activities_generator — structured quiz payload, max 2 attempts."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase


class Question(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    correct_indices: list[int]
    explanation: str | None = None


class ActivityPayload(BaseModel):
    kind: str = "quiz"
    title: str
    questions: list[Question] = Field(min_length=3, max_length=10)


def activities_generator(state: dict) -> Command:
    llm = writer_llm().with_structured_output(ActivityPayload)
    prefs = state.get("teacher_preferences") or {}
    payload: ActivityPayload = llm.invoke(
        f"Write a quiz for lesson id {state.get('active_lesson_id')} / chapter {state['active_chapter_id']}. "
        f"Focus: {prefs.get('special_focus', [])}."
    )
    sb = supabase()
    sb.table("activities").insert({
        "chapter_id": state["active_chapter_id"],
        "lesson_id": state.get("active_lesson_id"),
        "syllabus_id": state["syllabus_id"],
        "position": 1,
        "payload": payload.model_dump(),
    }).execute()
    return Command(goto="chapter_guard")
