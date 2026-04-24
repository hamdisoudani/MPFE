"""Plan-setting tools.

These are *intent* tools: when the supervisor calls them, the router
detects the call and routes the run into the relevant subgraph. The
"execution" of the tool itself is just to acknowledge & validate.
"""
from __future__ import annotations
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..state import SearchPlan, TodoPlan


# ── pydantic args (gives us tool-call structured output for free) ──────────
class SearchStepArg(BaseModel):
    id: str = Field(description="Stable id like S1, S2, …")
    title: str = Field(description="Short human-readable goal of this step.")
    queries: list[str] = Field(min_length=1, max_length=5, description="2–4 web search queries.")


class SetSearchPlanArgs(BaseModel):
    """Use this when you have decided the next move is to run web research.

    The system will execute every step's queries in parallel, scrape the
    top results, and feed you a single synthesized summary. Do NOT call
    this for chitchat or trivial questions.
    """
    global_goal: str = Field(description="What ALL the searches together are meant to answer. The summarizer keys off this.")
    steps: list[SearchStepArg] = Field(min_length=1, max_length=4)


class TodoStepArg(BaseModel):
    id: str = Field(description="Stable id like T1, T2, …")
    chapter_ref: str = Field(description="Alias such as CH1, CH2 — never a UUID.")
    name: str = Field(description="Lesson title.")
    description: str = Field(description="Acceptance criteria — what MUST be covered, in detail.")
    must_cover: list[str] = Field(default_factory=list, description="Concrete, atomic items that must appear.")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Other todo step ids whose summaries the writer should read."
    )


class SetTodoPlanArgs(BaseModel):
    """Use this when you have decided the chapter list and want to write
    the lessons. One TodoStep per lesson. Reference chapters by their
    alias (CH1...). Use `depends_on` when a lesson builds on previous
    lessons in the same syllabus.
    """
    steps: list[TodoStepArg] = Field(min_length=1, max_length=40)


class AskUserArgs(BaseModel):
    """Use this when you GENUINELY need information you cannot infer.
    Asks the teacher exactly one question, then waits for their answer.
    The system uses LangGraph's `interrupt()` so the run pauses cleanly.
    Do NOT use this for chitchat or to confirm obvious things.
    """
    question: str = Field(description="A single, specific question the teacher will read verbatim.")


class CreateSyllabusArgs(BaseModel):
    """Insert the syllabus row in the database. Call this exactly once,
    after clarifications and before `create_chapters`.
    """
    title: str = Field(description="Final syllabus title, classroom-ready.")
    requirements: Optional[str] = Field(default=None, description="Optional 1-2 sentence framing.")


class ChapterArg(BaseModel):
    title: str = Field(description="Chapter title.")
    summary: Optional[str] = Field(default=None)


class CreateChaptersArgs(BaseModel):
    """Insert all chapters at once. Returns a CHn alias map you must use
    in `set_todo_plan`.
    """
    chapters: list[ChapterArg] = Field(min_length=1, max_length=20)


class ListThreadSyllabiArgs(BaseModel):
    """List existing syllabi in this thread (for context if user mentions
    'the previous one'). No args.
    """
    pass


# ── tool stubs (executed only as no-ops; the router does the routing) ──────
@tool("ask_user", args_schema=AskUserArgs)
def ask_user_tool(question: str) -> str:
    """Ask the teacher one targeted question and wait for their answer."""
    return f"(ask_user dispatched: {question})"


@tool("set_search_plan", args_schema=SetSearchPlanArgs)
def set_search_plan_tool(global_goal: str, steps: list[dict]) -> str:
    """Stage a research plan. The system will run it and return a summary."""
    plan = SearchPlan(global_goal=global_goal, steps=steps)
    return f"Search plan staged with {len(plan.steps)} steps."


@tool("set_todo_plan", args_schema=SetTodoPlanArgs)
def set_todo_plan_tool(steps: list[dict]) -> str:
    """Stage a writing plan. The system will run a writer/critic loop."""
    plan = TodoPlan(steps=steps)
    return f"Todo plan staged with {len(plan.steps)} steps."
