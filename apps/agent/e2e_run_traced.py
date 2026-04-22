"""E2E with full tool-call tracing.

Run:
  cd apps/agent
  AGENT_TRACE=1 AGENT_TRACE_STDOUT=1 AGENT_TRACE_FILE=agent_trace.jsonl \
      python e2e_run_traced.py

Emits a JSONL trace of every:
  - node entry/exit
  - LLM request/response (model, base_url, prompt bytes, output bytes, elapsed)
  - Supabase call (method, path, rows, elapsed, sample)
  - HTTP call (Serper: URL, body, status, elapsed)

After the run it prints a per-node summary, an activity-generation focus dump for
any plan whose deps include lessons [1,2], and the final Supabase verification."""
import os, json, uuid, time, asyncio, sys
from collections import Counter, defaultdict

os.environ.setdefault("AGENT_TRACE", "1")
os.environ.setdefault("AGENT_TRACE_STDOUT", "1")
os.environ.setdefault("AGENT_TRACE_FILE", "agent_trace.jsonl")

from agent.tracing import install as install_tracer
install_tracer()

from langgraph.types import Command
from agent.graph import build_compiled_memory
from agent.db.supabase_client import supabase
from agent.tracing import _emit  # noqa

THREAD_ID = f"e2e-trace-{uuid.uuid4().hex[:6]}"
REQ = (
    "Design a B1-level Business English course for working professionals (non-native speakers) "
    "who attend remote meetings. Cover: opening/closing a meeting, interrupting politely, "
    "clarifying, disagreeing diplomatically, technical issues, and summarizing action items."
)

def _emit_node(name, kind, extra=None):
    _emit({"kind": f"node_{kind}", "node": name, "summary": json.dumps(extra or {}, default=str)[:300]})

async def main():
    compiled = build_compiled_memory()
    config = {"configurable": {"thread_id": THREAD_ID}}
    init = {"thread_id": THREAD_ID, "requirements": REQ,
            "title": "B1 Business English — Remote Meetings"}

    print(f"[driver] thread_id={THREAD_ID}")
    print("[driver] === phase 1: run until interrupt ===")
    t0 = time.time()
    async for event in compiled.astream(init, config=config, stream_mode="updates"):
        for node, upd in event.items():
            if node == "__interrupt__":
                payload = upd[0].value if isinstance(upd, tuple) else upd
                _emit_node("interrupt", "interrupt", {"head": str(payload)[:200]})
                print(f"[driver] INTERRUPT fired")
            else:
                keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
                _emit_node(node, "update", {"keys": keys})
                print(f"[driver] ← {node} updates keys={keys}")
    print(f"[driver] phase1 {time.time()-t0:.1f}s")

    answers = {
        "target_audience": "Working professionals attending daily remote meetings",
        "num_chapters": 2,
        "lessons_per_chapter": 2,
        "pedagogical_approach": "communicative",
        "activity_granularity": "per_chapter",
        "include_activities": True,
        "special_focus": ["remote meeting phrases", "diplomatic disagreement"],
        "must_cover": ["opening/closing meeting", "interrupting politely", "action items"],
        "must_avoid": ["C1+ idioms"],
        "language_of_instruction": "English",
    }
    print("[driver] === phase 2: resume ===")
    t1 = time.time()
    async for event in compiled.astream(Command(resume=answers), config=config, stream_mode="updates"):
        for node, upd in event.items():
            keys = list(upd.keys()) if isinstance(upd, dict) else type(upd).__name__
            _emit_node(node, "update", {"keys": keys})
            print(f"[driver] ← {node} keys={keys}")
    print(f"[driver] phase2 {time.time()-t1:.1f}s")

    final = compiled.get_state(config)
    sid = final.values.get("syllabus_id")
    print(f"[driver] final phase={final.values.get('phase')} next={final.next} syllabus_id={sid}")

    print()
    print("=" * 70)
    print("TRACE SUMMARY")
    print("=" * 70)
    with open(os.environ["AGENT_TRACE_FILE"]) as f:
        events = [json.loads(l) for l in f if l.strip()]

    kinds = Counter(e["kind"] for e in events)
    print("\nEvent counts:")
    for k, v in kinds.most_common():
        print(f"  {k:16s} {v}")

    llm_by_model = defaultdict(lambda: {"n":0, "s":0.0, "chars_in":0})
    for e in events:
        if e["kind"] == "llm_response":
            m = e.get("model","?")
            llm_by_model[m]["n"] += 1
            llm_by_model[m]["s"] += e.get("elapsed_s", 0) or 0
        if e["kind"] == "llm_request":
            m = e.get("model","?")
            llm_by_model[m]["chars_in"] += e.get("prompt_chars", 0)
    print("\nLLM usage:")
    for m, d in llm_by_model.items():
        print(f"  {m:50s} calls={d['n']:3d} total_s={d['s']:6.1f} prompt_chars={d['chars_in']}")

    http = [e for e in events if e["kind"] == "http"]
    print(f"\nHTTP calls (Serper etc): {len(http)}")
    for e in http[:10]:
        print(f"  {e.get('url','?')[:70]:70s} {e.get('status')} {e.get('elapsed_s')}s")

    db = [e for e in events if e["kind"] in ("db_call","db_error")]
    by_method = Counter(e.get("method","?") for e in db)
    print(f"\nSupabase calls: {len(db)} methods={dict(by_method)}")

    print()
    print("=" * 70)
    print("ACTIVITY GENERATION FOCUS — what tools ran per activity plan")
    print("=" * 70)
    plans = final.values.get("activity_plans") or []
    print(f"\n{len(plans)} activity_plans total\n")

    # Rebuild the order activities_generator fired by scanning trace events
    # surrounding each 'activities' table insert.
    activity_inserts = [i for i,e in enumerate(events)
                        if e["kind"]=="db_call" and "activities" in (e.get("path") or "") and e.get("method","").upper() in ("POST","PUT","PATCH")]
    print(f"Activity INSERT events at trace #: {[events[i]['seq'] for i in activity_inserts]}\n")

    for idx, ins_i in enumerate(activity_inserts):
        ins = events[ins_i]
        # Walk BACK from the insert to find: lesson fetches (deps), the activity LLM call
        window = []
        j = ins_i - 1
        steps_back = 0
        while j >= 0 and steps_back < 60:
            ev = events[j]
            if ev["kind"] == "db_call" and "activities" in (ev.get("path") or "") and ev.get("method","").upper() in ("POST","PUT","PATCH"):
                break
            window.append(ev); j -= 1; steps_back += 1
        window.reverse()
        lesson_fetches = [e for e in window if e["kind"]=="db_call" and "lessons" in (e.get("path") or "") and e.get("method","").upper()=="GET"]
        chapter_fetches = [e for e in window if e["kind"]=="db_call" and "chapters" in (e.get("path") or "") and e.get("method","").upper()=="GET"]
        llm_calls = [e for e in window if e["kind"] in ("llm_request","llm_response")]
        plan_ref = plans[idx] if idx < len(plans) else {}
        deps = plan_ref.get("depends_on_lesson_positions")
        scope = plan_ref.get("scope")

        print(f"--- Activity #{idx+1} (plan scope={scope} deps={deps} title={plan_ref.get('title','?')!r}) ---")
        print("  Supabase reads before LLM:")
        for f in chapter_fetches: print(f"    GET {f.get('path')[:80]} -> {f.get('rows')} rows")
        for f in lesson_fetches: print(f"    GET {f.get('path')[:80]} -> {f.get('rows')} rows")
        llm_req = next((e for e in llm_calls if e["kind"]=="llm_request"), None)
        llm_resp = next((e for e in llm_calls if e["kind"]=="llm_response"), None)
        if llm_req:
            print(f"  LLM request: model={llm_req.get('model')} prompt={llm_req.get('prompt_chars')}B "
                  f"(contains deps lesson markdown)")
            print(f"    prompt head: {llm_req.get('prompt_head','')[:260]!r}")
        if llm_resp:
            print(f"  LLM response: {llm_resp.get('elapsed_s')}s head: {llm_resp.get('out_head','')[:220]!r}")
        print(f"  Supabase write: POST /activities  payload bytes≈{len(ins.get('sample',''))}")
        print()

    print("=" * 70)
    print("SUPABASE FINAL STATE")
    print("=" * 70)
    sb = supabase()
    syl = sb.table("syllabuses").select("*").eq("id", sid).single().execute().data
    chs = sb.table("chapters").select("*").eq("syllabus_id", sid).order("position").execute().data
    lss = sb.table("lessons").select("*").eq("syllabus_id", sid).order("position").execute().data
    acts = sb.table("activities").select("*").eq("syllabus_id", sid).execute().data
    print(f"syllabus.phase={syl['phase']}")
    print(f"chapters={len(chs)}, lessons={len(lss)}, activities={len(acts)}")
    for a in acts:
        p = a.get("payload") or {}
        print(f"  activity lesson_id={(a.get('lesson_id') or 'NULL')[:8]} "
              f"kind={p.get('kind')} Q#={len(p.get('questions',[]))} title={p.get('title')!r}")

    reports = final.values.get("critic_reports") or []
    print(f"\ncritic_reports={len(reports)}")
    for r in reports[:8]:
        print(f"  attempt={r.get('attempt')} score={r.get('score')}/6 passes={r.get('passes')} "
              f"weaknesses={r.get('weaknesses',[])[:2]}")
    print(f"\ntrace file: {os.environ['AGENT_TRACE_FILE']}")

asyncio.run(main())
