"""LangGraph state — IDs, cursors, small metadata only."""
from __future__ import annotations
from typing import Annotated, Any, Optional, Literal, TypedDict
from operator import add
from langgraph.graph.message import add_messages

Phase = Literal["searching", "awaiting_input", "outlining", "writing", "done", "failed"]

class ChapterRef(TypedDict, total=False):
    id: str
    position: int
    title: str
    status: Literal["pending", "writing", "done"]

class LessonRef(TypedDict, total=False):
    id: str
    substep_id: str
    chapter_id: str
    position: int
    title: str
    draft_attempts: int
    needs_review: bool

def upsert_by_id(left: list, right: list) -> list:
    by_id = {r["id"]: r for r in left}
    for r in right:
        by_id[r["id"]] = {**by_id.get(r["id"], {}), **r}
    return list(by_id.values())

class SyllabusState(TypedDict, total=False):
    thread_id: str
    syllabus_id: Optional[str]
    requirements: str
    title: Optional[str]
    phase: Phase
    teacher_preferences: Optional[dict]
    search_queries: list[str]
    search_cursor: int
    findings: Annotated[list[str], add]
    chapters: Annotated[list[ChapterRef], upsert_by_id]
    lessons: Annotated[list[LessonRef], upsert_by_id]
    active_chapter_id: Optional[str]
    active_lesson_id: Optional[str]
    messages: Annotated[list, add_messages]
    _draft: Optional[dict]
    _draft_chapter_pos: Optional[int]
    _draft_position: Optional[int]
    _draft_substep_id: Optional[str]
    _draft_attempts: int
    _critique: Optional[str]
