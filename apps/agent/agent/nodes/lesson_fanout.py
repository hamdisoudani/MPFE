"""lesson_fanout — after outline, Send one lesson_worker per planned lesson (parallel)."""
from __future__ import annotations
from langgraph.types import Send, Command

def lesson_fanout(state: dict) -> Command:
    sid = state["syllabus_id"]
    prefs = state.get("teacher_preferences") or {}
    lpc = int(prefs.get("lessons_per_chapter", 3))
    chapters = state.get("chapters") or []
    lesson_plans = state.get("lesson_plans") or []
    sends = []
    for ch in sorted(chapters, key=lambda c: c.get("position", 0)):
        for pos in range(1, lpc + 1):
            substep_id = f"{sid}::ch{ch['position']}::l{pos}"
            plan = next((p for p in lesson_plans if p.get("substep_id") == substep_id), {})
            sends.append(Send("lesson_worker", {
                "syllabus_id": sid,
                "teacher_preferences": prefs,
                "_w_substep_id": substep_id,
                "_w_chapter_id": ch["id"],
                "_w_chapter_pos": ch["position"],
                "_w_chapter_goal": ch.get("goal") or "",
                "_w_position": pos,
                "_w_plan": plan,
            }))
    if not sends:
        return Command(goto="activities_generator")
    return Command(goto=sends)
