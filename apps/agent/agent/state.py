"""LangGraph state — IDs, cursors, small metadata only. Production-ready with plans + GC."""
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

class LessonPlan(TypedDict, total=False):
    substep_id: str
    chapter_pos: int
    position: int
    title: str
    learning_objective: str
    must_cover: list[str]
    grammar_point: str
    vocab_targets: list[str]

class ActivityPlan(TypedDict, total=False):
    substep_id: str
    scope: Literal["lesson", "chapter"]
    chapter_pos: int
    depends_on_lesson_positions: list[int]
    kind: str
    title: str
    instructions: str
    requirements: list[str]
    status: Literal["pending", "done"]

def upsert_by_id(left: list, right: list) -> list:
    by_id = {r.get("id") or r.get("substep_id"): r for r in left}
    for r in right:
        k = r.get("id") or r.get("substep_id")
        by_id[k] = {**by_id.get(k, {}), **r}
    return list(by_id.values())

def capped_findings(left: list[str], right: list[str]) -> list[str]:
    merged = list(left) + list(right)
    seen = set(); out = []
    for f in merged:
        if f in seen: continue
        seen.add(f); out.append(f)
    return out[-20:]

class SyllabusState(TypedDict, total=False):
    thread_id: str
    syllabus_id: Optional[str]
    requirements: str
    title: Optional[str]
    phase: Phase
    teacher_preferences: Optional[dict]
    search_queries: list[str]
    search_cursor: int
    findings: Annotated[list[str], capped_findings]
    chapters: Annotated[list[ChapterRef], upsert_by_id]
    lessons: Annotated[list[LessonRef], upsert_by_id]
    lesson_plans: Annotated[list[LessonPlan], upsert_by_id]
    activity_plans: Annotated[list[ActivityPlan], upsert_by_id]
    active_chapter_id: Optional[str]
    active_lesson_id: Optional[str]
    messages: Annotated[list, add_messages]
    _draft: Optional[dict]
    _draft_chapter_pos: Optional[int]
    _draft_position: Optional[int]
    _draft_substep_id: Optional[str]
    _draft_attempts: int
    _critique: Optional[str]
