"""activities_generator — substep loop with custom stream events."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import writer_llm
from ..db.supabase_client import supabase
from ..events import emit_activities_generated, emit_phase

class Question(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    correct_indices: list[int]
    explanation: str | None = None

class ActivityPayload(BaseModel):
    kind: str = "quiz"
    title: str
    questions: list[Question] = Field(min_length=3, max_length=10)

def _lesson_row(sb, syllabus_id: str, chapter_pos: int, position: int):
    ch = sb.table("chapters").select("id").eq("syllabus_id", syllabus_id).eq("position", chapter_pos).single().execute().data
    if not ch: return None
    r = sb.table("lessons").select("id,title,content_markdown,summary,position,substep_id") \
          .eq("chapter_id", ch["id"]).eq("position", position).limit(1).execute().data
    return r[0] if r else None

def _next_ready_plan(state, sb):
    plans = state.get("activity_plans") or []
    sid = state["syllabus_id"]
    for p in plans:
        if p.get("status") == "done": continue
        deps = p.get("depends_on_lesson_positions") or []
        rows = [_lesson_row(sb, sid, p["chapter_pos"], pos) for pos in deps]
        if all(rows) and all(r for r in rows):
            return p, rows
    return None, None

def activities_generator(state: dict) -> Command:
    sb = supabase()
    plan, dep_lessons = _next_ready_plan(state, sb)
    if not plan:
        return Command(goto="chapter_guard")

    emit_phase("activities")
    prefs = state.get("teacher_preferences") or {}
    ch = sb.table("chapters").select("id,title,summary,position") \
           .eq("syllabus_id", state["syllabus_id"]).eq("position", plan["chapter_pos"]).single().execute().data

    deps_block = "\n".join(
        f"### Lesson {l['position']}: {l['title']}\nSummary: {l.get('summary','')}\n{l['content_markdown'][:2000]}"
        for l in dep_lessons
    )

    llm = writer_llm().with_structured_output(ActivityPayload)
    payload: ActivityPayload = llm.invoke(
        f"Design a {plan['kind']} activity for chapter {ch['position']}: {ch['title']}.\n"
        f"Scope: {plan['scope']}. Consolidates lessons at positions {plan['depends_on_lesson_positions']}.\n"
        f"Title hint: {plan['title']}\n"
        f"Instructions: {plan['instructions']}\n"
        f"Requirements (each must be assessed by >=1 question): {plan['requirements']}\n"
        f"Teacher focus: {prefs.get('special_focus', [])}. must_cover={prefs.get('must_cover',[])}\n"
        f"Generate 6-10 questions drawn DIRECTLY from the lesson content below. "
        f"Questions must reference concrete phrases/vocab from the lessons.\n"
        f"---LESSONS---\n{deps_block}"
    )
    lesson_id_for_activity = dep_lessons[0]["id"] if plan["scope"] == "lesson" else None
    sb.table("activities").insert({
        "chapter_id": ch["id"],
        "lesson_id": lesson_id_for_activity,
        "syllabus_id": state["syllabus_id"],
        "position": len([p for p in state.get("activity_plans",[]) if p.get("status")=="done"]) + 1,
        "payload": payload.model_dump(),
    }).execute()

    emit_activities_generated(chapter_id=ch["id"], lesson_id=lesson_id_for_activity,
                              count=len(payload.questions))

    return Command(goto="activities_generator", update={
        "activity_plans": [{"substep_id": plan["substep_id"], "status": "done"}],
    })
