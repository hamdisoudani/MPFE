"""End-to-end smoke runner for the supervisor-pattern syllabus agent.

Drives a fresh thread through:
  1. Greeting → expected: plain reply, no tools.
  2. "Build me a syllabus for Introduction to C++"
     → expected: ask_user → resume → set_search_plan → search → set_todo_plan
       → writer/critic loop → committed lessons in Supabase.

Run with:
    source ~/.env_mpfe_test      # LLM creds
    # SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SERPER_API_KEY already in env
    python e2e_run.py
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from agent.graph import build_compiled_memory


def _short(s: str, n: int = 100) -> str:
    if not s:
        return ""
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


async def stream_run(graph, payload, config) -> dict:
    """Stream the run, print typed events, return final state."""
    async for ns, mode, chunk in graph.astream(
        payload, config=config, stream_mode=["custom", "updates"], subgraphs=True
    ):
        if mode == "custom":
            t = chunk.get("type", "?")
            extras = " ".join(f"{k}={_short(v, 60)}" for k, v in chunk.items() if k != "type")
            ns_str = "/".join(ns) if ns else "(root)"
            print(f"[evt {ns_str}] {t}  {extras}")
        elif mode == "updates":
            for node, upd in chunk.items():
                msgs = (upd or {}).get("messages") or []
                for m in msgs:
                    role = m.__class__.__name__
                    content = getattr(m, "content", "")
                    tcs = getattr(m, "tool_calls", None) or []
                    tcs_str = ", ".join(f"{c['name']}({_short(json.dumps(c.get('args', {})), 80)})" for c in tcs)
                    if tcs_str:
                        print(f"[upd {node}] {role}: tools=[{tcs_str}]")
                    else:
                        print(f"[upd {node}] {role}: {_short(content, 200)}")
                if "phase" in (upd or {}):
                    print(f"[upd {node}] phase -> {upd['phase']}")
                if "search_plan" in (upd or {}) and (upd or {}).get("search_plan"):
                    plan = upd["search_plan"]
                    print(f"[upd {node}] search_plan goal={_short(plan.get('global_goal'), 60)} "
                          f"steps={[s['id'] for s in plan.get('steps', [])]}")
                if "todo_plan" in (upd or {}) and (upd or {}).get("todo_plan"):
                    plan = upd["todo_plan"]
                    print(f"[upd {node}] todo_plan steps={[(s['id'], s.get('chapter_ref'), s.get('status')) for s in plan.get('steps', [])]}")
                if "syllabus_id" in (upd or {}):
                    print(f"[upd {node}] syllabus_id -> {upd['syllabus_id']}")
                if "chapter_alias_map" in (upd or {}):
                    print(f"[upd {node}] chapter_alias_map -> {list((upd['chapter_alias_map'] or {}).keys())}")
    return await graph.aget_state(config)


async def main():
    graph = build_compiled_memory()
    thread = f"e2e-{int(time.time())}"
    config = {"configurable": {"thread_id": thread}}

    # ── Step 1: greeting (should NOT call tools) ──
    print("\n========= TURN 1: greeting =========")
    state = await stream_run(graph, {
        "thread_id": thread,
        "messages": [HumanMessage("Hi! Are you online?")],
        "phase": "idle",
    }, config)
    last = state.values.get("messages") or []
    print(f"\nfinal turn-1 message count={len(last)}")

    # ── Step 2: ask for a syllabus ──
    print("\n========= TURN 2: build syllabus =========")
    state = await stream_run(graph, {
        "messages": [HumanMessage(
            "I'd like to build a short Introduction to C++ syllabus for "
            "first-year CS students with no prior programming experience. "
            "Aim for 3 chapters with 2 lessons each, 4 weeks total."
        )],
    }, config)

    # If the run was interrupted by ask_user, resume with a canned answer.
    interrupts = list((await graph.aget_state(config)).interrupts or [])
    rounds = 0
    while interrupts and rounds < 4:
        rounds += 1
        question = interrupts[0].value.get("question", "")
        print(f"\n[interrupt] {question}")
        canned = (
            "First-year CS students, no prior programming experience. "
            "Hands-on, exam-prep oriented, 4 weeks of study, ~3 hours/week. "
            "Include code examples in every lesson. 3 chapters with 2 lessons each is fine. "
            "Yes please proceed with that chapter shape."
        )
        print(f"[resume w/] {canned[:100]}…")
        state = await stream_run(graph, Command(resume=canned), config)
        interrupts = list((await graph.aget_state(config)).interrupts or [])

    final = await graph.aget_state(config)
    v = final.values
    print("\n========= FINAL STATE SUMMARY =========")
    print("phase:        ", v.get("phase"))
    print("syllabus_id:  ", v.get("syllabus_id"))
    print("chapter_aliases:", list((v.get("chapter_alias_map") or {}).keys()))
    sp = v.get("search_plan") or {}
    print("search_plan:  ", sp.get("global_goal"), [(s["id"], s.get("status")) for s in sp.get("steps", [])])
    tp = v.get("todo_plan") or {}
    print("todo_plan:    ", [(s["id"], s.get("chapter_ref"), s.get("status"), s.get("attempts")) for s in tp.get("steps", [])])

    # Show what landed in Supabase
    if v.get("syllabus_id"):
        from agent.db.supabase_client import supabase
        sb = supabase()
        ch = sb.table("chapters").select("id,position,title,status").eq("syllabus_id", v["syllabus_id"]).order("position").execute().data
        ls = sb.table("lessons").select("id,chapter_id,position,title").eq("syllabus_id", v["syllabus_id"]).order("position").execute().data
        print(f"DB chapters ({len(ch)}):")
        for c in ch:
            print(f"  pos={c['position']} status={c['status']} title={c['title']}")
        print(f"DB lessons ({len(ls)}):")
        for l in ls:
            print(f"  pos={l['position']} title={l['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
