"""Smoke tests for agent.events + event emission from critical nodes."""
from __future__ import annotations
from unittest.mock import patch
from agent import events as ev


def test_emit_no_writer_context_is_safe():
    ev.emit("phase_changed", phase="searching")
    ev.emit_phase("writing")
    ev.emit_search_progress(1, 3, 5)
    ev.emit_chapter_started("ch-1", 1, "Intro")
    ev.emit_lesson_attempt("ss::ch1::l1", 1, 1, 1, "drafting")
    ev.emit_critic_verdict("ss::ch1::l1", 1, True, 6, [])
    ev.emit_lesson_committed("l-1", "ss::ch1::l1", "ch-1", 1, False, 1)
    ev.emit_activities_generated("ch-1", "l-1", 5)
    ev.emit_error("node", "boom")


def test_emit_routes_to_writer_when_present():
    captured = []
    def fake_get_writer():
        return lambda payload: captured.append(payload)
    with patch.object(ev, "_get_writer", fake_get_writer):
        ev.emit_phase("writing")
        ev.emit_critic_verdict("ss::ch1::l1", 2, False, 4,
                               ["a","b","c","d","e","truncated"])
    assert captured[0] == {"type": "phase_changed", "phase": "writing"}
    assert captured[1]["type"] == "critic_verdict"
    assert captured[1]["attempt"] == 2
    assert captured[1]["passes"] is False
    assert captured[1]["score"] == 4
    assert len(captured[1]["weaknesses"]) == 5


def test_emit_error_truncates_long_messages():
    captured = []
    def fake_get_writer():
        return lambda p: captured.append(p)
    with patch.object(ev, "_get_writer", fake_get_writer):
        ev.emit_error("web_search", "x" * 5000)
    assert len(captured[0]["message"]) == 500


def test_emit_swallows_writer_exceptions():
    def fake_get_writer():
        def bad(_): raise RuntimeError("blew up")
        return bad
    with patch.object(ev, "_get_writer", fake_get_writer):
        ev.emit_phase("done")
