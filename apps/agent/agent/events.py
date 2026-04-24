"""Typed helpers around langgraph.config.get_stream_writer.

Every event is a dict with a `type` discriminant; the frontend keys off that.
Safe to call outside a stream context (no-op).
"""
from __future__ import annotations
from typing import Any

try:
    from langgraph.config import get_stream_writer as _get_writer
except Exception:  # pragma: no cover
    _get_writer = None  # type: ignore


def emit(event_type: str, **fields: Any) -> None:
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


def emit_search_step(step_id: str, title: str, idx: int, total: int) -> None:
    emit("search_step_started", step_id=step_id, title=title, idx=idx, total=total)


def emit_search_progress(step_id: str, candidates: int, scraped: int) -> None:
    emit("search_progress", step_id=step_id, candidates=candidates, scraped=scraped)


def emit_search_summary_ready(length: int) -> None:
    emit("search_summary_ready", length=length)


def emit_todo_started(steps_total: int) -> None:
    emit("todo_started", steps_total=steps_total)


def emit_todo_step(step_id: str, chapter_ref: str, name: str, attempt: int, status: str) -> None:
    emit(
        "todo_step",
        step_id=step_id, chapter_ref=chapter_ref, name=name,
        attempt=attempt, status=status,
    )


def emit_critic(step_id: str, attempt: int, passes: bool, score: int, weaknesses: list[str]) -> None:
    emit(
        "critic_verdict",
        step_id=step_id, attempt=attempt, passes=passes, score=score,
        weaknesses=(weaknesses or [])[:5],
    )


def emit_lesson_committed(step_id: str, lesson_id: str, chapter_id: str, title: str) -> None:
    emit(
        "lesson_committed",
        step_id=step_id, lesson_id=lesson_id, chapter_id=chapter_id, title=title,
    )


def emit_chapter_committed(chapter_ref: str, chapter_id: str, title: str, position: int) -> None:
    emit(
        "chapter_committed",
        chapter_ref=chapter_ref, chapter_id=chapter_id, title=title, position=position,
    )


def emit_awaiting_input(question: str) -> None:
    emit("awaiting_input", question=question)


def emit_error(node: str, message: str) -> None:
    emit("error", node=node, message=str(message)[:500])
