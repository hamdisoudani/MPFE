"""critic_node — evidence-based; per-criterion quotes; emits full report to state."""
from __future__ import annotations
import json, re
from langgraph.types import Command
from ..llm import critic_llm
from ..prompts import critic_prompt


def _find_plan(state: dict, substep_id: str):
    for p in state.get("lesson_plans") or []:
        if p.get("substep_id") == substep_id:
            return p
    return None

def _find_chapter_goal(state: dict, chapter_pos: int) -> str:
    for c in state.get("chapters") or []:
        if c.get("position") == chapter_pos:
            return c.get("goal") or ""
    return ""

def _parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.DOTALL)
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    return {"passes": False, "critique": "Critic returned unparseable output; rejecting for safety.",
            "per_criterion": [], "score": 0, "weaknesses": ["unparseable critic response"]}

def _enforce(verdict: dict, plan: dict) -> dict:
    """Re-verify hard rules client-side — model may still try to rubber-stamp."""
    pc = verdict.get("per_criterion") or []
    by_id = {c.get("id"): c for c in pc if isinstance(c, dict)}

    c3 = by_id.get("C3_must_cover_each") or {}
    per_item = c3.get("per_item") or []
    must_cover = plan.get("must_cover") or []
    if must_cover:
        covered = sum(1 for x in per_item if isinstance(x, dict) and x.get("pass")
                      and isinstance(x.get("evidence"), str)
                      and x.get("evidence") and "MISSING" not in x["evidence"].upper()
                      and len(x["evidence"].strip()) >= 8)
        c3_ok = covered == len(must_cover) and len(per_item) == len(must_cover)
    else:
        c3_ok = bool(c3.get("pass"))

    c5 = by_id.get("C5_vocab_coverage") or {}
    try:
        cov = float(c5.get("coverage_ratio") or 0.0)
    except Exception:
        cov = 0.0
    c5_ok = cov >= 0.8

    score = 0
    for cid in ["C1_objective_stated","C2_serves_chapter_goal","C4_grammar_examples","C6_practice_and_constraints"]:
        if (by_id.get(cid) or {}).get("pass"): score += 1
    if c3_ok: score += 1
    if c5_ok: score += 1
    verdict["score"] = score
    verdict["passes"] = bool(score >= 5 and c3_ok and c5_ok)
    return verdict


def critic_node(state: dict) -> Command:
    draft = state["_draft"]
    prefs = state.get("teacher_preferences") or {}
    plan = _find_plan(state, state.get("_draft_substep_id","")) or {}
    chapter_goal = _find_chapter_goal(state, state.get("_draft_chapter_pos") or 0)

    prompt = critic_prompt(
        lesson_markdown=draft.get("content_markdown") or "",
        plan=plan, chapter_goal=chapter_goal, prefs=prefs,
    )
    llm = critic_llm()
    try:
        resp = llm.invoke(prompt, response_format={"type": "json_object"})
    except Exception:
        resp = llm.invoke(prompt)
    text = getattr(resp, "content", None) or str(resp)
    verdict = _parse(text if isinstance(text, str) else str(text))
    verdict = _enforce(verdict, plan)

    report = {
        "substep_id": state.get("_draft_substep_id"),
        "attempt": int(state.get("_draft_attempts") or 0) + 1,
        "score": int(verdict.get("score") or 0),
        "passes": bool(verdict.get("passes")),
        "per_criterion": verdict.get("per_criterion") or [],
        "weaknesses": verdict.get("weaknesses") or [],
        "critique": verdict.get("critique") or "",
    }

    crit_for_writer = json.dumps({
        "score": report["score"],
        "per_criterion": report["per_criterion"],
        "weaknesses": report["weaknesses"],
        "critique": report["critique"],
    }, ensure_ascii=False)[:4000]

    goto = "accept_lesson" if report["passes"] else "reject_lesson"
    return Command(goto=goto, update={
        "_critique": crit_for_writer,
        "critic_reports": [report],
    })
