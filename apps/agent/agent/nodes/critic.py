"""critic_node — strict pass/fail with a rewritten-brief."""
from __future__ import annotations
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import critic_llm


class CriticVerdict(BaseModel):
    passes: bool
    critique: str


def critic_node(state: dict) -> Command:
    draft = state["_draft"]
    prefs = state.get("teacher_preferences") or {}
    llm = critic_llm().with_structured_output(CriticVerdict)
    v: CriticVerdict = llm.invoke(
        "You are a strict pedagogy critic. Must_cover=" + str(prefs.get("must_cover", [])) +
        " must_avoid=" + str(prefs.get("must_avoid", [])) +
        " approach=" + str(prefs.get("pedagogical_approach")) +
        "\nLesson:\n" + draft["content_markdown"][:4000]
    )
    if v.passes:
        return Command(goto="accept_lesson")
    return Command(goto="reject_lesson", update={"_critique": v.critique})
