"""outline_generator — chapters with explicit GOAL + per-lesson plans + per-activity plans."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase
from ..prompts import outline_prompt

class ChapterDraft(BaseModel):
    title: str
    goal: str = Field(description="By the end of this chapter, the learner can …")
    summary: str

class LessonPlanDraft(BaseModel):
    chapter_pos: int
    position: int
    title: str
    serves_chapter_goal: str = ""
    learning_objective: str
    must_cover: list[str] = Field(default_factory=list)
    grammar_point: str = ""
    vocab_targets: list[str] = Field(default_factory=list)

class ActivityPlanDraft(BaseModel):
    scope: str = Field(description="lesson or chapter")
    chapter_pos: int
    depends_on_lesson_positions: list[int]
    kind: str = "quiz"
    title: str
    instructions: str
    requirements: list[str] = Field(default_factory=list)

class FullPlan(BaseModel):
    chapters: list[ChapterDraft]
    lesson_plans: list[LessonPlanDraft]
    activity_plans: list[ActivityPlanDraft]


def outline_generator(state: dict) -> Command:
    prefs = state.get("teacher_preferences") or {}
    n = prefs.get("num_chapters", 10)
    lpc = prefs.get("lessons_per_chapter", 3)
    granularity = prefs.get("activity_granularity", "per_lesson")
    include_activities = prefs.get("include_activities", True)

    llm = writer_llm().with_structured_output(FullPlan)
    plan: FullPlan = llm.invoke(outline_prompt(
        state["requirements"], prefs, state.get("findings", []),
        n, lpc, granularity, include_activities,
    ))

    sb = supabase()
    rows = [{
        "syllabus_id": state["syllabus_id"], "position": i+1,
        "title": c.title,
        "summary": f"Goal: {c.goal}\n\n{c.summary}",
        "status": "pending",
    } for i, c in enumerate(plan.chapters[:n])]
    resp = sb.table("chapters").upsert(rows, on_conflict="syllabus_id,position").execute()
    sb.table("syllabuses").update({"phase": "writing"}).eq("id", state["syllabus_id"]).execute()

    goals_by_pos = {i+1: c.goal for i, c in enumerate(plan.chapters[:n])}
    chapters = [{"id": r["id"], "position": r["position"], "title": r["title"],
                 "goal": goals_by_pos.get(r["position"], ""), "status": "pending"}
                for r in resp.data]

    sid = state["syllabus_id"]
    lesson_plans = []
    for lp in plan.lesson_plans:
        if lp.chapter_pos < 1 or lp.chapter_pos > n or lp.position < 1 or lp.position > lpc:
            continue
        lesson_plans.append({
            "substep_id": f"{sid}::ch{lp.chapter_pos}::l{lp.position}",
            "chapter_pos": lp.chapter_pos, "position": lp.position, "title": lp.title,
            "serves_chapter_goal": lp.serves_chapter_goal or goals_by_pos.get(lp.chapter_pos, ""),
            "learning_objective": lp.learning_objective,
            "must_cover": lp.must_cover,
            "grammar_point": lp.grammar_point,
            "vocab_targets": lp.vocab_targets,
        })

    activity_plans = []
    if include_activities:
        for i, ap in enumerate(plan.activity_plans):
            if ap.chapter_pos < 1 or ap.chapter_pos > n: continue
            deps = [p for p in ap.depends_on_lesson_positions if 1 <= p <= lpc]
            if not deps: continue
            deps_tag = "-".join(str(p) for p in sorted(set(deps)))
            activity_plans.append({
                "substep_id": f"{sid}::ch{ap.chapter_pos}::act{i+1}-{deps_tag}",
                "scope": ap.scope if ap.scope in ("lesson","chapter") else granularity,
                "chapter_pos": ap.chapter_pos,
                "depends_on_lesson_positions": sorted(set(deps)),
                "kind": ap.kind or "quiz",
                "title": ap.title,
                "instructions": ap.instructions,
                "requirements": ap.requirements,
                "status": "pending",
            })

    return Command(goto="chapter_guard", update={
        "chapters": chapters,
        "lesson_plans": lesson_plans,
        "activity_plans": activity_plans,
        "phase": "writing",
        "findings": [],
    })
