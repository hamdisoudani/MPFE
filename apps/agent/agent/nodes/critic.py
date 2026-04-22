"""critic_node — rubric-based pass/fail; JSON-mode with manual fallback (NVIDIA/Mistral safe)."""
from __future__ import annotations
import json, re
from pydantic import BaseModel
from langgraph.types import Command
from ..llm import critic_llm

class CriticVerdict(BaseModel):
    passes: bool
    critique: str

RUBRIC = """You are a CEFR A1 pedagogy reviewer. Score the lesson on 5 criteria:
1. Level-appropriate: very short sentences, A1 vocabulary only
2. Clear single learning objective, explicitly stated
3. Contains concrete examples or dialogues (>=3)
4. Contains a vocabulary section (>=6 items) or a practice section
5. Respects must_cover and must_avoid constraints

ACCEPT (passes=true) if at least 4 of 5 are satisfied, even partially.
REJECT (passes=false) only if 2+ criteria are clearly missing or wrong.

Reply with ONLY a JSON object, no prose, no markdown fences:
{"passes": <true|false>, "critique": "<per-criterion OK or specific fix>"}
"""

def _parse_verdict(text: str) -> CriticVerdict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.DOTALL)
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try:
            obj = json.loads(m.group(0))
            return CriticVerdict(
                passes=bool(obj.get("passes", False)),
                critique=str(obj.get("critique", "")),
            )
        except Exception:
            pass
    low = text.lower()
    passes = ("passes\": true" in low) or ("\"passes\":true" in low.replace(" ", "")) or ("accept" in low and "reject" not in low[:80])
    return CriticVerdict(passes=passes, critique=text[:1200])

def critic_node(state: dict) -> Command:
    draft = state["_draft"]
    prefs = state.get("teacher_preferences") or {}
    prompt = (
        RUBRIC
        + "\nmust_cover=" + str(prefs.get("must_cover", []))
        + " must_avoid=" + str(prefs.get("must_avoid", []))
        + " approach=" + str(prefs.get("pedagogical_approach"))
        + "\n---LESSON---\n" + (draft.get("content_markdown") or "")[:4000]
    )
    llm = critic_llm()
    try:
        resp = llm.invoke(prompt, response_format={"type": "json_object"})
    except Exception:
        resp = llm.invoke(prompt)
    text = getattr(resp, "content", None) or str(resp)
    v = _parse_verdict(text if isinstance(text, str) else str(text))
    if v.passes:
        return Command(goto="accept_lesson", update={"_critique": v.critique})
    return Command(goto="reject_lesson", update={"_critique": v.critique})
