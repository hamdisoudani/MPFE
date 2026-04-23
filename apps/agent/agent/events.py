"""Typed helper around langgraph custom stream events.

Frontend contract — every event is a dict with a "type" discriminant.
See frontend-streaming-design.md for the full list. Safe to call outside
a stream context (no-op).
"""
from __future__ import annotations
from typing import Any

try:
    from langgraph.config import get_stream_writer as _get_writer
except Exception:  # pragma: no cover
    _get_writer = None  # type: ignore


def emit(event_type: str, **fields: Any) -> None:
    """Emit a typed custom event on the active run's stream. No-op if no writer."""
    if _get_writer is None:
        return
    try:
        writer = _get_writer()
    except Exception:
        return
    if writer is None:
        return
    payload = {"type": event_type, **fields}
    try:
        writer(payload)
    except Exception:
        pass


def emit_phase(phase: str) -> None:
    emit("phase_changed", phase=phase)


def emit_search_progress(queries_done: int, queries_total: int, findings: int) -> None:
    emit("search_progress", queries_done=queries_done, queries_total=queries_total, findings=findings)


def emit_chapter_started(chapter_id: str, position: int, title: str) -> None:
    emit("chapter_started", chapter_id=chapter_id, position=position, title=title)


def emit_lesson_attempt(lesson_substep_id: str, chapter_pos: int, position: int,
                        attempt: int, status: str) -> None:
    emit("lesson_attempt", lesson_substep_id=lesson_substep_id,
         chapter_pos=chapter_pos, position=position, attempt=attempt, status=status)


def emit_critic_verdict(lesson_substep_id: str, attempt: int, passes: bool,
                        score: int, weaknesses: list[str]) -> None:
    emit("critic_verdict", lesson_substep_id=lesson_substep_id, attempt=attempt,
         passes=passes, score=score, weaknesses=weaknesses[:5])


def emit_lesson_committed(lesson_id: str, lesson_substep_id: str, chapter_id: str,
                          position: int, needs_review: bool, attempts: int) -> None:
    emit("lesson_committed", lesson_id=lesson_id, lesson_substep_id=lesson_substep_id,
         chapter_id=chapter_id, position=position, needs_review=needs_review, attempts=attempts)


def emit_activities_generated(chapter_id: str, lesson_id: str | None, count: int) -> None:
    emit("activities_generated", chapter_id=chapter_id, lesson_id=lesson_id, count=count)


def emit_error(node: str, message: str) -> None:
    emit("error", node=node, message=message[:500])
