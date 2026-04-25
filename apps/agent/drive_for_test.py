"""Drive the agent end-to-end against a caller-specified thread_id so the
frontend (keyed on that same threadId query param) observes the syllabus
populate live via Supabase Realtime.

Usage:
  source ~/.env_mpfe_test
  THREAD_ID=<uuid-or-string> python drive_for_test.py
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from agent.graph import build_compiled_memory


def _short(s, n=100):
    if not s:
        return ""
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


async def stream_run(graph, payload, config):
    async for ns, mode, chunk in graph.astream(
        payload, config=config, stream_mode=["custom", "updates"], subgraphs=True
    ):
        if mode == "custom":
            t = chunk.get("type", "?")
            extras = " ".join(f"{k}={_short(v, 60)}" for k, v in chunk.items() if k != "type")
            ns_str = "/".join(ns) if ns else "(root)"
            print(f"[evt {ns_str}] {t}  {extras}", flush=True)
        elif mode == "updates" and isinstance(chunk, dict):
            for node, upd in chunk.items():
                if not isinstance(upd, dict):
                    continue
                if "phase" in upd:
                    print(f"[upd {node}] phase -> {upd['phase']}", flush=True)
                if "syllabus_id" in upd:
                    print(f"[upd {node}] syllabus_id -> {upd['syllabus_id']}", flush=True)
                if "chapter_alias_map" in upd:
                    print(f"[upd {node}] chapters -> {list((upd['chapter_alias_map'] or {}).keys())}", flush=True)
                msgs = upd.get("messages") or []
                for m in msgs:
                    role = m.__class__.__name__
                    tcs = getattr(m, "tool_calls", None) or []
                    if tcs:
                        names = ", ".join(c.get("name", "?") for c in tcs)
                        print(f"[upd {node}] {role}: tools=[{names}]", flush=True)
                    else:
                        print(f"[upd {node}] {role}: {_short(getattr(m, 'content', ''), 160)}", flush=True)
    return await graph.aget_state(config)


async def main():
    thread = os.environ.get("THREAD_ID")
    if not thread:
        print("ERROR: THREAD_ID env var required", file=sys.stderr)
        return 2

    print(f"thread_id = {thread}")
    graph = build_compiled_memory()
    config = {"configurable": {"thread_id": thread}}

    print("\n===== TURN 1: build syllabus =====")
    state = await stream_run(graph, {
        "thread_id": thread,
        "messages": [HumanMessage(
            "Build me a short syllabus for Intro to HTML, 2 chapters, "
            "audience: absolute beginners. Include 1 quiz activity per chapter."
        )],
        "phase": "idle",
    }, config)

    interrupts = list((await graph.aget_state(config)).interrupts or [])
    canned = [
        "Audience: absolute beginners, no prior coding. Two chapters, "
        "two lessons each, and one multiple-choice quiz per chapter. "
        "Plain HTML only (no CSS/JS in this course). Proceed.",
        "That structure is fine, proceed.",
        "Proceed; your judgement is fine.",
        "Proceed; your judgement is fine.",
    ]
    rounds = 0
    while interrupts and rounds < 4:
        q = interrupts[0].value.get("question", "")
        print(f"\n[interrupt #{rounds+1}] {_short(q, 240)}")
        ans = canned[min(rounds, len(canned) - 1)]
        rounds += 1
        print(f"[resume]  {_short(ans, 120)}")
        state = await stream_run(graph, Command(resume=ans), config)
        interrupts = list((await graph.aget_state(config)).interrupts or [])

    final = await graph.aget_state(config)
    v = final.values
    print("\n===== DONE =====")
    print("phase:       ", v.get("phase"))
    print("syllabus_id: ", v.get("syllabus_id"))
    tp = v.get("todo_plan") or {}
    print("todo_plan:   ", [(s["id"], s.get("chapter_ref"), s.get("kind"), s.get("status")) for s in tp.get("steps", [])])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
