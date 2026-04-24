"""Supabase-backed tools the supervisor can call directly.

These DO execute side effects — they're not no-ops. The router treats
them as "execute then return to supervisor".
"""
from __future__ import annotations
from typing import Any
from langchain_core.tools import tool

from .plan_tools import (
    CreateSyllabusArgs, CreateChaptersArgs, ListThreadSyllabiArgs
)
from ..db.supabase_client import supabase


@tool("create_syllabus", args_schema=CreateSyllabusArgs)
def create_syllabus_tool(title: str, requirements: str | None = None) -> dict[str, Any]:
    """Insert the syllabus row in Supabase (or update if it already exists)."""
    # Implementation lives in the executor — kept here only for the schema.
    # The router/executor reads tool name + args from the AIMessage and
    # performs the actual work with thread context.
    return {"_pending": True, "title": title, "requirements": requirements}


@tool("create_chapters", args_schema=CreateChaptersArgs)
def create_chapters_tool(chapters: list[dict]) -> dict[str, Any]:
    """Insert every chapter in Supabase. Returns CHn alias→uuid map."""
    return {"_pending": True, "chapters": chapters}


@tool("list_thread_syllabi", args_schema=ListThreadSyllabiArgs)
def list_thread_syllabi_tool() -> list[dict[str, Any]]:
    """List existing syllabi for the current thread."""
    return [{"_pending": True}]


# ── concrete executors (called by the tool_executor node) ──────────────────
def exec_create_syllabus(thread_id: str, title: str, requirements: str | None) -> dict:
    """Idempotent on (thread_id). Inserts or updates the row."""
    sb = supabase()
    payload = {
        "thread_id": thread_id,
        "title": title,
        "requirements": requirements or "",
        "phase": "outlining",
    }
    # upsert by thread_id (unique)
    res = (
        sb.table("syllabuses")
        .upsert(payload, on_conflict="thread_id")
        .execute()
    )
    row = (res.data or [{}])[0]
    return {"id": row.get("id"), "title": row.get("title")}


def exec_create_chapters(syllabus_id: str, chapters: list[dict]) -> dict[str, str]:
    """Inserts each chapter, returns alias map {CH1: uuid, …}."""
    sb = supabase()
    rows = [
        {
            "syllabus_id": syllabus_id,
            "position": i + 1,
            "title": ch.get("title", f"Chapter {i+1}"),
            "summary": ch.get("summary"),
            "status": "pending",
        }
        for i, ch in enumerate(chapters)
    ]
    res = sb.table("chapters").upsert(rows, on_conflict="syllabus_id,position").execute()
    out: dict[str, str] = {}
    for row in res.data or []:
        out[f"CH{row['position']}"] = row["id"]
    return out


def exec_list_thread_syllabi(thread_id: str) -> list[dict]:
    sb = supabase()
    res = (
        sb.table("syllabuses")
        .select("id,title,phase,requirements,created_at")
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def exec_commit_lesson(
    *, syllabus_id: str, chapter_id: str, substep_id: str, position: int,
    title: str, content_md: str, summary: str | None,
    draft_attempts: int, needs_review: bool,
) -> dict:
    sb = supabase()
    row = {
        "syllabus_id": syllabus_id,
        "chapter_id": chapter_id,
        "substep_id": substep_id,
        "position": position,
        "title": title,
        "content_markdown": content_md,
        "summary": summary,
        "draft_attempts": draft_attempts,
        "needs_review": needs_review,
    }
    res = sb.table("lessons").upsert(row, on_conflict="substep_id").execute()
    return (res.data or [{}])[0]


def exec_set_phase(syllabus_id: str | None, phase: str) -> None:
    if not syllabus_id:
        return
    try:
        supabase().table("syllabuses").update({"phase": phase}).eq("id", syllabus_id).execute()
    except Exception:
        pass


def exec_set_chapter_status(chapter_id: str, status: str) -> None:
    try:
        supabase().table("chapters").update({"status": status}).eq("id", chapter_id).execute()
    except Exception:
        pass
