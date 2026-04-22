"""LangGraph state — IDs, cursors, small metadata only.

Large content (markdown, scraped HTML, embeddings) lives in Supabase.
"""
from __future__ import annotations
from typing import Annotated, Optional, Literal, TypedDict
from operator import add
from langgraph.graph.message import add_messages


Phase = Literal["searching", "awaiting_input", "outlining", "writing", "done", "failed"]


class ChapterRef(TypedDict):
    id: str
    position: int
    title: str
    status: Literal["pending", "writing", "done"]


class LessonRef(TypedDict):
    id: str
    substep_id: str
    chapter_id: str
    position: int
    title: str
    draft_attempts: int
    needs_review: bool


def upsert_by_id(left: list, right: list) -> list:
    """Upsert-by-id reducer for chapters/lessons/activities in state."""
    by_id = {r["id"]: r for r in left}
    for r in right:
        by_id[r["id"]] = {**by_id.get(r["id"], {}), **r}
    return list(by_id.values())


class SyllabusState(TypedDict, total=False):
    # identity
    thread_id: str
    syllabus_id: Optional[str]
    requirements: str
    title: Optional[str]

    # phase machine
    phase: Phase

    # clarification (Revision 2)
    teacher_preferences: Optional[dict]

    # search loop
    search_queries: list[str]
    search_cursor: int
    findings: Annotated[list[str], add]

    # chapter/lesson tracking (IDs only)
    chapters: Annotated[list[ChapterRef], upsert_by_id]
    lessons: Annotated[list[LessonRef], upsert_by_id]

    # active chapter/lesson cursors
    active_chapter_id: Optional[str]
    active_lesson_id: Optional[str]

    # conversation surface (trimmed with RemoveMessage at phase boundaries)
    messages: Annotated[list, add_messages]
