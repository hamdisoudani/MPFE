"""outline_generator — chapters + per-lesson plans + per-activity plans with deps."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase

class ChapterDraft(BaseModel):
    title: str
    summary: str

class LessonPlanDraft(BaseModel):
    chapter_pos: int
    position: int
    title: str
    learning_objective: str
    must_cover: list[str] = Field(default_factory=list)
    grammar_point: str = ""
    vocab_targets: list[str] = Field(default_factory=list)

class ActivityPlanDraft(BaseModel):
    scope: str = Field(description="lesson or chapter")
    chapter_pos: int
    depends_on_lesson_positions: list[int] = Field(
        description="1-based lesson positions within the chapter this activity consolidates"
    )
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
    prompt = (
        f"You are producing a rigorous teaching plan for this requirement:\n{state['requirements']}\n\n"
        f"Teacher preferences: {prefs}\n\n"
        f"Web findings (use these to ground real-world relevance, cite naturally in lessons):\n"
        + "\n---\n".join(state.get("findings", [])[-15:])
        + f"\n\nOutput EXACTLY:\n"
        f"- {n} chapters with title+summary\n"
        f"- {n*lpc} lesson_plans (every chapter {lpc} lessons), each with learning_objective, must_cover (3-5 concrete skills/facts), grammar_point, vocab_targets (6-12 items)\n"
        f"- activity_plans: scope={granularity} (lesson => one activity per lesson covering that lesson; chapter => one activity per chapter consolidating ALL its lessons). "
        f"depends_on_lesson_positions must list every lesson the activity covers. include_activities={include_activities}\n"
        f"All positions are 1-based within their chapter."
    )
    plan: FullPlan = llm.invoke(prompt)

    sb = supabase()
    rows = [{"syllabus_id": state["syllabus_id"], "position": i+1,
             "title": c.title, "summary": c.summary, "status": "pending"}
            for i, c in enumerate(plan.chapters[:n])]
    resp = sb.table("chapters").upsert(rows, on_conflict="syllabus_id,position").execute()
    sb.table("syllabuses").update({"phase": "writing"}).eq("id", state["syllabus_id"]).execute()
    chapters = [{"id": r["id"], "position": r["position"], "title": r["title"], "status": "pending"}
                for r in resp.data]

    sid = state["syllabus_id"]
    lesson_plans = []
    for lp in plan.lesson_plans:
        if lp.chapter_pos < 1 or lp.chapter_pos > n or lp.position < 1 or lp.position > lpc:
            continue
        lesson_plans.append({
            "substep_id": f"{sid}::ch{lp.chapter_pos}::l{lp.position}",
            "chapter_pos": lp.chapter_pos, "position": lp.position, "title": lp.title,
            "learning_objective": lp.learning_objective, "must_cover": lp.must_cover,
            "grammar_point": lp.grammar_point, "vocab_targets": lp.vocab_targets,
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
