"""lesson_worker — atomic write→critic→retry→persist per lesson."""
from __future__ import annotations
import json, time
from langgraph.types import Command
from ..llm import writer_llm, critic_llm
from ..db.supabase_client import supabase
from ..prompts import writer_prompt, critic_prompt
from .lesson_writer import LessonDraft
from .critic import _parse, _enforce

MAX_ATTEMPTS = 3

def lesson_worker(state: dict) -> Command:
    substep_id = state["_w_substep_id"]
    chapter_id = state["_w_chapter_id"]
    chapter_pos = state["_w_chapter_pos"]
    chapter_goal = state.get("_w_chapter_goal") or ""
    position = state["_w_position"]
    syllabus_id = state["syllabus_id"]
    prefs = state.get("teacher_preferences") or {}
    plan = state.get("_w_plan") or {}
    sb = supabase()
    chapter = sb.table("chapters").select("*").eq("id", chapter_id).single().execute().data

    prior_critique = None
    reports_out = []
    accepted_draft = None
    attempts = 0
    draft = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts = attempt
        t0 = time.time()
        llm_w = writer_llm().with_structured_output(LessonDraft)
        draft = llm_w.invoke(writer_prompt(
            chapter=chapter, lesson_pos=position, prefs=prefs, plan=plan,
            chapter_goal=chapter_goal, prior_critique=prior_critique, attempt_num=attempt,
        ))
        t_write = time.time() - t0
        t0 = time.time()
        prompt = critic_prompt(
            lesson_markdown=draft.content_markdown, plan=plan,
            chapter_goal=chapter_goal, prefs=prefs,
        )
        llm_c = critic_llm()
        try:
            resp = llm_c.invoke(prompt, response_format={"type": "json_object"})
        except Exception:
            resp = llm_c.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        verdict = _enforce(_parse(text if isinstance(text, str) else str(text)), plan)
        t_crit = time.time() - t0
        report = {
            "substep_id": substep_id, "attempt": attempt,
            "score": int(verdict.get("score") or 0),
            "passes": bool(verdict.get("passes")),
            "per_criterion": verdict.get("per_criterion") or [],
            "weaknesses": verdict.get("weaknesses") or [],
            "critique": verdict.get("critique") or "",
            "_t_write": round(t_write, 2), "_t_crit": round(t_crit, 2),
        }
        reports_out.append(report)
        if report["passes"]:
            accepted_draft = draft
            break
        prior_critique = json.dumps({
            "score": report["score"], "per_criterion": report["per_criterion"],
            "weaknesses": report["weaknesses"], "critique": report["critique"],
        }, ensure_ascii=False)[:4000]

    needs_review = accepted_draft is None
    final = accepted_draft or draft
    row = sb.table("lessons").upsert({
        "chapter_id": chapter_id, "syllabus_id": syllabus_id,
        "substep_id": substep_id, "position": position,
        "title": final.title, "content_markdown": final.content_markdown,
        "summary": final.summary, "needs_review": needs_review,
        "draft_attempts": attempts,
    }, on_conflict="substep_id").execute().data[0]

    return Command(update={
        "lessons": [{"id": row["id"], "substep_id": substep_id, "chapter_id": chapter_id,
                     "position": position, "title": final.title,
                     "draft_attempts": attempts, "needs_review": needs_review}],
        "critic_reports": reports_out,
    })
