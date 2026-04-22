"""E2E harder: B1 Business English for remote meetings — 3 ch × 2 lessons, per_chapter activities."""
import asyncio, json, uuid, time, sys
from langgraph.types import Command
from agent.graph import build_compiled_memory
from agent.db.supabase_client import supabase

THREAD_ID = f"e2e-{uuid.uuid4().hex[:8]}"
REQ = (
    "Design a B1-level Business English course for working professionals (non-native speakers) "
    "who attend remote meetings on Zoom / Google Meet. Cover: opening and closing a meeting, "
    "interrupting politely, clarifying and paraphrasing, disagreeing diplomatically, "
    "handling technical issues ('you\'re on mute', 'can you share your screen'), and "
    "summarizing action items. Use recent real-world phrasing from business-English sources."
)

def _state_size(values: dict) -> dict:
    payload = json.dumps(values, default=str)
    keys_sz = {k: len(json.dumps(v, default=str)) for k, v in values.items()}
    return {"total_chars": len(payload), "by_key": dict(sorted(keys_sz.items(), key=lambda x: -x[1])[:8])}

async def main():
    compiled = build_compiled_memory()
    config = {"configurable": {"thread_id": THREAD_ID}}
    init = {"thread_id": THREAD_ID, "requirements": REQ, "title": "Business English B1 — Remote Meetings"}

    print(f"[driver] thread_id={THREAD_ID}")
    print("[driver] --- phase 1: run until interrupt (real Serper search) ---")
    t0 = time.time()
    critic_calls = 0; reject_count = 0; accept_count = 0
    async for event in compiled.astream(init, config=config, stream_mode="updates"):
        for node, upd in event.items():
            if node == "__interrupt__":
                payload = upd[0].value if isinstance(upd, tuple) else upd
                print(f"[driver] INTERRUPT: {json.dumps(payload, default=str)[:600]}")
            else:
                keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
                print(f"[driver] node={node} keys={keys}")

    state = compiled.get_state(config)
    findings = state.values.get("findings") or []
    print(f"[driver] phase1 done in {time.time()-t0:.1f}s; findings={len(findings)}")
    for i, f in enumerate(findings[:3]):
        print(f"  finding[{i}]: {f[:200]!r}")
    print(f"[driver] state size pre-resume: {_state_size(state.values)}")

    if "clarify_with_user" not in (state.next or ()):
        print("[driver] ERROR expected interrupt"); return

    answers = {
        "target_audience": "Working professionals attending daily remote meetings",
        "num_chapters": 3,
        "lessons_per_chapter": 2,
        "pedagogical_approach": "communicative",
        "activity_granularity": "per_chapter",
        "include_activities": True,
        "special_focus": ["remote meeting phrases", "diplomatic disagreement", "summarizing"],
        "must_cover": ["opening/closing a meeting", "interrupting politely", "clarifying", "action items"],
        "must_avoid": ["C1+ idioms", "slang"],
        "language_of_instruction": "English",
    }
    print(f"[driver] --- phase 2: resume ---")
    t1 = time.time()
    async for event in compiled.astream(Command(resume=answers), config=config, stream_mode="updates"):
        for node, upd in event.items():
            keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
            print(f"[driver] node={node} keys={keys}")
            if node == "critic_node": critic_calls += 1
            if node == "reject_lesson": reject_count += 1
            if node == "accept_lesson": accept_count += 1
    print(f"[driver] phase2 in {time.time()-t1:.1f}s; critic_calls={critic_calls} accepts={accept_count} rejects={reject_count}")

    final = compiled.get_state(config)
    sid = final.values.get("syllabus_id")
    print(f"[driver] final phase={final.values.get('phase')} next={final.next}")
    print(f"[driver] state size FINAL: {_state_size(final.values)}")
    print(f"[driver] scratchpad after run: _draft={final.values.get('_draft')} _critique={final.values.get('_critique')} _draft_attempts={final.values.get('_draft_attempts')}")
    aps = final.values.get("activity_plans") or []
    print(f"[driver] activity_plans total={len(aps)} done={sum(1 for p in aps if p.get('status')=='done')}")
    for p in aps:
        print(f"  plan ch{p.get('chapter_pos')} scope={p.get('scope')} deps={p.get('depends_on_lesson_positions')} status={p.get('status')} title={p.get('title')!r}")

    print("[driver] --- Supabase verification ---")
    sb = supabase()
    syl = sb.table("syllabuses").select("*").eq("id", sid).single().execute().data
    chs = sb.table("chapters").select("*").eq("syllabus_id", sid).order("position").execute().data
    lss = sb.table("lessons").select("*").eq("syllabus_id", sid).order("position").execute().data
    acts = sb.table("activities").select("*").eq("syllabus_id", sid).execute().data
    print(f"[db] syllabus phase={syl['phase']} prefs={bool(syl.get('teacher_preferences'))}")
    print(f"[db] chapters={len(chs)}")
    for c in chs: print(f"  ch{c['position']} {c['status']} {c['title']!r}")
    print(f"[db] lessons={len(lss)}")
    for l in lss:
        cm = (l.get("content_markdown") or "")
        print(f"  ch={l['chapter_id'][:8]} pos={l['position']} attempts={l.get('draft_attempts')} needs_review={l['needs_review']} md_len={len(cm)} title={l['title']!r}")
    print(f"[db] activities={len(acts)}")
    for a in acts:
        p = a.get("payload") or {}
        qs = p.get("questions", [])
        print(f"  lesson_id={(a.get('lesson_id') or 'NULL')[:8]} kind={p.get('kind')} q#={len(qs)} title={p.get('title')!r}")
        if qs: print(f"    q1: {qs[0].get('question','')[:160]}")

    expected_lessons = 3*2
    ok = (
        syl["phase"] == "done"
        and len(chs) == 3 and all(c["status"]=="done" for c in chs)
        and len(lss) == expected_lessons
        and len(acts) >= 3
    )
    print(f"[driver] === {'SUCCESS' if ok else 'FAILED'} ===")

asyncio.run(main())
