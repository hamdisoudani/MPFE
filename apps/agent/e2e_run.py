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
            if not isinstance(chunk, dict):
                # interrupt updates come through as tuples — skip pretty-print
                continue
            for node, upd in chunk.items():
                if not isinstance(upd, dict):
                    continue
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

    # ── Step 2: ask for a syllabus (very vague — should trigger ask_user) ──
    print("\n========= TURN 2: build syllabus (very vague request) =========")
    state = await stream_run(graph, {
        "messages": [HumanMessage(
            "Hey can you build me a syllabus about Python? Thanks."
        )],
    }, config)

    # If the run was interrupted by ask_user, resume with a canned answer.
    interrupts = list((await graph.aget_state(config)).interrupts or [])
    rounds = 0
    canned_answers = [
        # First clarifying round — provide audience + format.
        "Audience: high-school seniors, no prior programming experience. "
        "Hands-on format, with code examples in every lesson and one "
        "graded quiz per chapter. ~3 weeks, ~2 hours/week. Please include "
        "activities (multiple-choice quizzes) at the end of each chapter "
        "so students can self-assess.",
        # Second clarifying round — structural confirmation.
        "Three chapters with two lessons and one quiz-activity each is "
        "fine. Please proceed.",
        "Whatever you judge best is fine; proceed.",
        "Whatever you judge best is fine; proceed.",
    ]
    while interrupts and rounds < 4:
        question = interrupts[0].value.get("question", "")
        print(f"\n[interrupt #{rounds+1}] {question}")
        canned = canned_answers[min(rounds, len(canned_answers) - 1)]
        rounds += 1
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
        ls = sb.table("lessons").select("id,chapter_id,position,title,content_markdown").eq("syllabus_id", v["syllabus_id"]).order("position").execute().data
        acts = sb.table("activities").select("id,chapter_id,lesson_id,position,title,payload").eq("syllabus_id", v["syllabus_id"]).order("position").execute().data
        print(f"DB chapters ({len(ch)}):")
        for c in ch:
            print(f"  pos={c['position']} status={c['status']} title={c['title']}")
        print(f"DB lessons ({len(ls)}):")
        for l in ls:
            print(f"  pos={l['position']} title={l['title']} md_bytes={len(l.get('content_markdown') or '')}")
        print(f"DB activities ({len(acts)}):")
        for a in acts:
            pl = a.get("payload") or {}
            qs = pl.get("questions") or []
            print(f"  pos={a['position']} title={a['title']} questions={len(qs)} lesson_id={a.get('lesson_id')}")
            for i, q in enumerate(qs[:2]):
                print(f"    Q{i+1}: {_short(q.get('prompt',''), 100)}  correct_idx={q.get('correct_index')}")

    # ── State size audit ──
    print("\n========= STATE SIZE AUDIT =========")
    import sys as _sys
    for key, val in v.items():
        try:
            size = len(json.dumps(val, default=str))
        except Exception:
            size = _sys.getsizeof(val)
        if key == "messages":
            msg_count = len(val or [])
            total = sum(len(str(getattr(m, 'content', '') or '')) for m in (val or []))
            print(f"  messages: count={msg_count}, content_chars={total}")
        else:
            print(f"  {key}: ~{size} chars")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
