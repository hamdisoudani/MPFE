"""critic_node — plan-aware rubric; JSON-mode with manual fallback (NVIDIA/Mistral safe)."""
from __future__ import annotations
import json, re
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import critic_llm

class CriticVerdict(BaseModel):
    passes: bool
    critique: str

def _find_plan(state: dict, substep_id: str):
    for p in state.get("lesson_plans") or []:
        if p.get("substep_id") == substep_id:
            return p
    return None

def _parse_verdict(text: str) -> CriticVerdict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try:
            obj = json.loads(m.group(0))
            return CriticVerdict(passes=bool(obj.get("passes", False)), critique=str(obj.get("critique","")))
        except Exception:
            pass
    low = text.lower()
    passes = "\"passes\": true" in low.replace(" ", "\"passes\":true") or ("accept" in low[:200] and "reject" not in low[:200])
    return CriticVerdict(passes=passes, critique=text[:1500])

def critic_node(state: dict) -> Command:
    draft = state["_draft"]
    prefs = state.get("teacher_preferences") or {}
    plan = _find_plan(state, state.get("_draft_substep_id","")) or {}

    plan_block = ""
    if plan:
        plan_block = (
            f"\nPLAN CONTRACT to verify:\n"
            f"- objective: {plan.get('learning_objective')}\n"
            f"- must_cover: {plan.get('must_cover')}\n"
            f"- grammar_point: {plan.get('grammar_point')}\n"
            f"- vocab_targets: {plan.get('vocab_targets')}\n"
        )

    rubric = (
        "You are a strict pedagogy reviewer. Score the lesson on 6 criteria:\n"
        "1. Level-appropriate for target audience and CEFR level\n"
        "2. Stated learning objective matches the plan objective\n"
        "3. EVERY item in must_cover appears in the lesson\n"
        "4. Grammar point is explained with >=2 examples\n"
        "5. >=80% of vocab_targets appear in the vocabulary section\n"
        "6. Respects must_avoid; contains a practice section\n\n"
        "ACCEPT (passes=true) if >=5 of 6 are satisfied.\n"
        "REJECT if 2+ are missing or wrong.\n"
        "Reply with ONLY a JSON object:\n"
        "{\"passes\": <true|false>, \"critique\": \"per-criterion OK or specific fix (1-2 sentences each)\"}\n"
    )
    prompt = (
        rubric + plan_block
        + f"\nmust_cover_pref={prefs.get('must_cover', [])} must_avoid={prefs.get('must_avoid', [])}"
        + "\n---LESSON---\n" + (draft.get("content_markdown") or "")[:4500]
    )
    llm = critic_llm()
    try:
        resp = llm.invoke(prompt, response_format={"type":"json_object"})
    except Exception:
        resp = llm.invoke(prompt)
    text = getattr(resp, "content", None) or str(resp)
    v = _parse_verdict(text if isinstance(text, str) else str(text))
    if v.passes:
        return Command(goto="accept_lesson", update={"_critique": v.critique})
    return Command(goto="reject_lesson", update={"_critique": v.critique})
