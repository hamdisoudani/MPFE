"""E2E driver: English A1, 2 chapters, 1 lesson/chapter, with activities."""
import asyncio, json, uuid, sys, os, time
from langgraph.types import Command
from agent.graph import build_compiled_memory
from agent.db.supabase_client import supabase

THREAD_ID = f"e2e-{uuid.uuid4().hex[:8]}"
REQ = "Build an English A1 level course for adult absolute beginners. Teach greetings, introductions, basic present simple, numbers 1-20, and common classroom vocabulary."

async def main():
    compiled = build_compiled_memory()
    config = {"configurable": {"thread_id": THREAD_ID}}
    init = {
        "thread_id": THREAD_ID,
        "requirements": REQ,
        "title": "English A1 — Beginners",
    }

    print(f"[driver] thread_id={THREAD_ID}")
    print("[driver] --- phase 1: run until interrupt ---")
    t0 = time.time()
    interrupt_payload = None
    async for event in compiled.astream(init, config=config, stream_mode="updates"):
        for node, upd in event.items():
            if node == "__interrupt__":
                interrupt_payload = upd[0].value if isinstance(upd, tuple) else upd
                print(f"[driver] INTERRUPT from graph: {json.dumps(interrupt_payload, default=str)[:500]}")
            else:
                keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
                print(f"[driver] node={node} updated keys={keys}")

    state = compiled.get_state(config)
    print(f"[driver] after phase1: next={state.next} elapsed={time.time()-t0:.1f}s")

    if "clarify_with_user" not in (state.next or ()):
        print("[driver] ERROR: expected interrupt at clarify_with_user")
        print("[driver] full state values keys:", list(state.values.keys()))
        return

    answers = {
        "target_audience": "Adult absolute beginners",
        "num_chapters": 2,
        "lessons_per_chapter": 1,
        "pedagogical_approach": "communicative",
        "activity_granularity": "per_lesson",
        "include_activities": True,
        "special_focus": ["speaking", "greetings", "present simple"],
        "must_cover": ["numbers 1-20", "classroom vocabulary"],
        "must_avoid": ["advanced grammar"],
        "language_of_instruction": "English",
    }
    print(f"[driver] --- phase 2: resume with TeacherPreferences ---")
    print(f"[driver] answers={json.dumps(answers)}")
    t1 = time.time()
    async for event in compiled.astream(Command(resume=answers), config=config, stream_mode="updates"):
        for node, upd in event.items():
            keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
            print(f"[driver] node={node} keys={keys}")
    print(f"[driver] phase2 elapsed={time.time()-t1:.1f}s")

    final = compiled.get_state(config)
    sid = final.values.get("syllabus_id")
    print(f"[driver] final phase={final.values.get('phase')} syllabus_id={sid} next={final.next}")

    print("[driver] --- Supabase verification ---")
    sb = supabase()
    syl = sb.table("syllabuses").select("*").eq("id", sid).single().execute().data
    chs = sb.table("chapters").select("*").eq("syllabus_id", sid).order("position").execute().data
    lss = sb.table("lessons").select("*").eq("syllabus_id", sid).order("position").execute().data
    acts = sb.table("activities").select("*").eq("syllabus_id", sid).execute().data
    print(f"[db] syllabus phase={syl['phase']} prefs={bool(syl.get('teacher_preferences'))}")
    print(f"[db] chapters={len(chs)}")
    for c in chs:
        print(f"  ch{c['position']} status={c['status']} title={c['title']!r}")
    print(f"[db] lessons={len(lss)}")
    for l in lss:
        cm = (l.get("content_markdown") or "")
        print(f"  pos={l['position']} title={l['title']!r} needs_review={l['needs_review']} md_len={len(cm)}")
    print(f"[db] activities={len(acts)}")
    for a in acts:
        p = a.get("payload") or {}
        qs = p.get("questions", [])
        print(f"  kind={p.get('kind')} title={p.get('title')!r} questions={len(qs)}")

    ok = (
        syl["phase"] == "done" and
        len(chs) == 2 and all(c["status"] == "done" for c in chs) and
        len(lss) == 2 and all(not l["needs_review"] for l in lss) and
        len(acts) == 2
    )
    print(f"[driver] === {'SUCCESS' if ok else 'FAILED'} ===")

asyncio.run(main())
