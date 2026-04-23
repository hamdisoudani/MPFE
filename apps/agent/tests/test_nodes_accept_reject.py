"""Node-level tests for accept/reject routing + state.lessons mirroring."""
from __future__ import annotations
import importlib
from unittest.mock import patch, MagicMock

accept_mod = importlib.import_module("agent.nodes.accept_lesson")
reject_mod = importlib.import_module("agent.nodes.reject_lesson")


def _mk_sb(row_id="lesson-xyz"):
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": row_id}]
    return sb


def test_reject_force_accept_routes_to_activities_when_enabled():
    sb = _mk_sb("l-force")
    state = {
        "_draft": {"title": "T", "content_markdown": "# T", "summary": "s"},
        "_draft_substep_id": "sid::ch1::l1",
        "_draft_position": 1, "_draft_attempts": 2,
        "active_chapter_id": "ch-1", "syllabus_id": "syl-1",
        "teacher_preferences": {"include_activities": True},
    }
    with patch.object(reject_mod, "supabase", return_value=sb):
        cmd = reject_mod.reject_lesson(state)
    assert cmd.goto == "activities_generator"
    assert cmd.update["active_lesson_id"] == "l-force"
    assert cmd.update["lessons"][0]["needs_review"] is True
    assert cmd.update["lessons"][0]["id"] == "l-force"
    assert cmd.update["_draft"] is None


def test_reject_force_accept_routes_to_chapter_guard_when_activities_disabled():
    sb = _mk_sb("l-force")
    state = {
        "_draft": {"title": "T", "content_markdown": "# T", "summary": "s"},
        "_draft_substep_id": "sid::ch1::l1",
        "_draft_position": 1, "_draft_attempts": 2,
        "active_chapter_id": "ch-1", "syllabus_id": "syl-1",
        "teacher_preferences": {"include_activities": False},
    }
    with patch.object(reject_mod, "supabase", return_value=sb):
        cmd = reject_mod.reject_lesson(state)
    assert cmd.goto == "chapter_guard"


def test_reject_under_three_attempts_retries_write_lesson():
    cmd = reject_mod.reject_lesson({"_draft_attempts": 0})
    assert cmd.goto == "write_lesson"
    assert cmd.update["_draft_attempts"] == 1


def test_accept_lesson_mirrors_into_state_lessons():
    sb = _mk_sb("l-ok")
    state = {
        "_draft": {"title": "T", "content_markdown": "# T", "summary": "s"},
        "_draft_substep_id": "sid::ch1::l1",
        "_draft_position": 1, "_draft_attempts": 0,
        "active_chapter_id": "ch-1", "syllabus_id": "syl-1",
        "teacher_preferences": {"include_activities": True},
    }
    with patch.object(accept_mod, "supabase", return_value=sb):
        cmd = accept_mod.accept_lesson(state)
    assert cmd.goto == "activities_generator"
    assert cmd.update["lessons"][0]["id"] == "l-ok"
    assert cmd.update["lessons"][0]["needs_review"] is False
    assert cmd.update["_draft"] is None
