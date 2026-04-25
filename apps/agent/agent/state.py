"""Lightweight LangGraph state.

Design rule: anything large lives in the LangGraph Store, NOT in state.
State only carries identifiers, cursors, plans, and a capped message tail.
"""
from __future__ import annotations
from typing import Annotated, Any, Literal, Optional, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph.message import add_messages

from .config import MESSAGE_TAIL_CAP


# ─── plan contracts ────────────────────────────────────────────────────────
StepStatus = Literal["pending", "searching", "scraping", "done"]


class SearchStep(BaseModel):
    """A single research step. The agent supplies the queries; we run them."""
    id: str = Field(description="Stable id like S1, S2, …")
    title: str = Field(description="Short human-readable goal of this step.")
    queries: list[str] = Field(min_length=1, max_length=5)
    status: StepStatus = "pending"


class SearchPlan(BaseModel):
    """Plan emitted by the supervisor's set_search_plan tool."""
    global_goal: str = Field(description="What the *whole* search is for. Used at summarize time.")
    steps: list[SearchStep] = Field(min_length=1, max_length=8)


TodoStatus = Literal[
    "pending", "writing", "critiquing", "accepted", "rejected", "failed"
]


TodoKind = Literal["lesson", "activity"]


class TodoStep(BaseModel):
    id: str = Field(description="Stable id like T1, T2, …")
    kind: TodoKind = Field(
        default="lesson",
        description="'lesson' = classroom-ready Markdown. 'activity' = JSON "
                    "quiz (multiple-choice, graded). Activities SHOULD declare "
                    "depends_on pointing at the lesson(s) they test.",
    )
    chapter_ref: str = Field(description="Alias like CH1 — never a UUID.")
    name: str = Field(description="Lesson/activity title or working title.")
    description: str = Field(
        description="Acceptance criteria — what MUST be covered / tested, written in detail."
    )
    must_cover: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(
        default_factory=list,
        description="Other TodoStep ids whose summaries this step reads. "
                    "For an activity, at least one dep SHOULD be a lesson this "
                    "activity evaluates.",
    )
    status: TodoStatus = "pending"
    attempts: int = 0
    final_lesson_id: Optional[str] = None
    final_activity_id: Optional[str] = None


class TodoPlan(BaseModel):
    steps: list[TodoStep] = Field(min_length=1, max_length=40)


# ─── reducers ──────────────────────────────────────────────────────────────
def capped_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    """Append-then-tail-cap. Pinned: SystemMessage at index 0 if present."""
    merged = add_messages(left, right)
    if len(merged) <= MESSAGE_TAIL_CAP:
        return merged
    head: list[BaseMessage] = []
    rest: list[BaseMessage] = []
    for m in merged:
        if isinstance(m, SystemMessage) and not head:
            head.append(m)
        else:
            rest.append(m)
    return head + rest[-(MESSAGE_TAIL_CAP - len(head)):]


def merge_dict(left: Optional[dict], right: Optional[dict]) -> dict:
    out = dict(left or {})
    out.update(right or {})
    return out


def replace(_left, right):
    return right


# ─── candidate scratch (in-state for one step at a time, cleared by reducer) ─
class SearchCandidate(TypedDict, total=False):
    step_id: str
    url: str
    title: str
    snippet: str
    score: float


_CLEAR_CANDIDATES_SENTINEL = {"__clear_search_candidates__": True}


def merge_candidates(
    left: list[SearchCandidate], right: list[SearchCandidate] | None
) -> list[SearchCandidate]:
    """De-dup by (step_id, url), keep highest score.

    GC: if `right` contains the sentinel candidate
    `{"__clear_search_candidates__": True}`, the scratch is CLEARED (and
    any other elements in the same update are ignored — callers should
    emit only the sentinel). Normal empty-list updates are a no-op
    (a zero-result search must not wipe peers' results during fan-out).
    """
    if right and any(
        isinstance(c, dict) and c.get("__clear_search_candidates__") for c in right
    ):
        return []
    by_key: dict[tuple[str, str], SearchCandidate] = {}
    for c in (left or []) + (right or []):
        if not c:
            continue
        k = (c.get("step_id", ""), c.get("url", ""))
        prev = by_key.get(k)
        if not prev or (c.get("score", 0) > prev.get("score", 0)):
            by_key[k] = c
    return list(by_key.values())


Phase = Literal[
    "idle", "awaiting_input", "searching", "summarizing",
    "outlining", "writing", "done", "failed",
]


class State(TypedDict, total=False):
    # Conversation — capped reducer keeps state lightweight.
    messages: Annotated[list[BaseMessage], capped_messages]

    # Identity / context
    thread_id: str
    syllabus_id: Optional[str]
    requirements: Optional[str]
    teacher_preferences: Annotated[Optional[dict], merge_dict]

    # Plans (full-replace)
    search_plan: Annotated[Optional[dict], replace]   # serialized SearchPlan
    search_summary: Annotated[Optional[str], replace]
    todo_plan: Annotated[Optional[dict], replace]    # serialized TodoPlan

    # Chapter alias map — agent only ever sees CH1/CH2 aliases.
    chapter_alias_map: Annotated[dict[str, str], merge_dict]

    # Subgraph cursors
    search_step_idx: int
    todo_step_idx: int

    # Search scratch (cleared at end of each step)
    _search_candidates: Annotated[list[SearchCandidate], merge_candidates]

    # Phase mirror for FE streaming
    phase: Annotated[Phase, replace]
