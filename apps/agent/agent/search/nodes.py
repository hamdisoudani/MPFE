"""Search subgraph nodes.

Topology (one outer iteration per search step):

   plan_step ─► [Send] search_query × N
                    ▼
             collect_candidates
                    ▼
            [Send] scrape_one × M
                    ▼
              step_done
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   advance_step           summarize_search
   (more steps)              (terminal)
"""
from __future__ import annotations
import asyncio
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Send
from langgraph.store.base import BaseStore

from ..config import (
    MAX_SCRAPE_PER_STEP,
    MAX_SEARCH_RESULTS_PER_QUERY,
)
from ..events import (
    emit_phase, emit_search_progress, emit_search_step,
    emit_search_summary_ready, emit_error,
)
from ..state import SearchPlan
from ..store_keys import (
    ns_scrape, ns_search_summary, purge_all_scrapes, purge_namespace,
)
from . import serper


# ── helpers ────────────────────────────────────────────────────────────────
def _plan_from_state(state: dict) -> SearchPlan | None:
    raw = state.get("search_plan")
    if not raw:
        return None
    return SearchPlan.model_validate(raw)


def _plan_to_state(plan: SearchPlan) -> dict:
    return plan.model_dump()


# ── plan_step: dispatch this step's queries in parallel ────────────────────
def plan_step(state: dict) -> dict:
    plan = _plan_from_state(state)
    if not plan:
        return {"phase": "idle"}
    idx = state.get("search_step_idx", 0)
    if idx >= len(plan.steps):
        return {"phase": "summarizing"}
    step = plan.steps[idx]
    step.status = "searching"
    plan.steps[idx] = step
    emit_phase("searching")
    emit_search_step(step.id, step.title, idx + 1, len(plan.steps))
    return {
        "search_plan": _plan_to_state(plan),
        "_search_candidates": [],   # reset scratch for this step
        "phase": "searching",
    }


def fanout_queries(state: dict) -> list[Send]:
    """Conditional edge — produces Sends in parallel."""
    plan = _plan_from_state(state)
    idx = state.get("search_step_idx", 0)
    if not plan or idx >= len(plan.steps):
        return []
    step = plan.steps[idx]
    return [
        Send("search_query", {
            "step_id": step.id,
            "step_title": step.title,
            "query": q,
            "_thread_id": state.get("thread_id", ""),
        })
        for q in step.queries
    ]


# ── search_query: a single Send-task ───────────────────────────────────────
async def search_query(payload: dict) -> dict:
    """Executes one query, returns reducer-merged candidates."""
    q = payload["query"]
    step_id = payload["step_id"]
    try:
        results = await serper.serper_search(q, num=MAX_SEARCH_RESULTS_PER_QUERY)
    except Exception as e:
        emit_error("search_query", f"{q}: {e}")
        results = []
    candidates = []
    for r in results:
        # naive confidence: prefer .edu, .org, recent-looking; penalize aggregator domains
        url = r.get("link", "")
        score = 1.0
        ll = url.lower()
        if any(d in ll for d in (".edu", "wikipedia.org", ".gov")):
            score += 0.5
        if any(d in ll for d in ("pinterest.", "quora.", "facebook.", "tiktok.")):
            score -= 0.5
        if r.get("position", 99) <= 3:
            score += 0.2
        candidates.append({
            "step_id": step_id, "url": url,
            "title": r.get("title", "")[:200],
            "snippet": r.get("snippet", "")[:300],
            "score": score,
        })
    return {"_search_candidates": candidates}


# ── pick_to_scrape: deterministic — picks top-K of this step's candidates ─
def pick_to_scrape(state: dict) -> dict:
    """Just emits a progress event; the actual fan-out is via the conditional edge."""
    plan = _plan_from_state(state)
    idx = state.get("search_step_idx", 0)
    if not plan or idx >= len(plan.steps):
        return {}
    step = plan.steps[idx]
    cands = [c for c in (state.get("_search_candidates") or []) if c.get("step_id") == step.id]
    step.status = "scraping"
    plan.steps[idx] = step
    emit_search_progress(step.id, candidates=len(cands), scraped=0)
    return {"search_plan": _plan_to_state(plan)}


def fanout_scrapes(state: dict) -> list[Send]:
    plan = _plan_from_state(state)
    idx = state.get("search_step_idx", 0)
    if not plan or idx >= len(plan.steps):
        return []
    step = plan.steps[idx]
    cands = [c for c in (state.get("_search_candidates") or []) if c.get("step_id") == step.id]
    cands.sort(key=lambda c: c.get("score", 0), reverse=True)
    top = cands[:MAX_SCRAPE_PER_STEP]
    return [
        Send("scrape_one", {
            "step_id": step.id,
            "url": c["url"],
            "title": c.get("title", ""),
            "_thread_id": state.get("thread_id", ""),
        })
        for c in top if c.get("url")
    ]


# ── scrape_one: one URL fetch ──────────────────────────────────────────────
async def scrape_one(payload: dict, *, store: BaseStore) -> dict:
    step_id = payload["step_id"]
    thread_id = payload["_thread_id"]
    url = payload["url"]
    try:
        r = await serper.scrape_url(url)
    except Exception as e:
        emit_error("scrape_one", f"{url}: {e}")
        return {}
    md = r.get("markdown", "")
    if not md.strip():
        return {}
    md = serper.truncate_markdown(md)
    key = url
    try:
        await store.aput(
            ns_scrape(thread_id, step_id),
            key,
            {"url": url, "title": r.get("title", url), "markdown": md},
        )
    except Exception as e:
        emit_error("scrape_one_store", str(e))
    return {}


# ── advance_step: bump cursor, mark current done ───────────────────────────
async def advance_step(state: dict, *, store: BaseStore) -> dict:
    plan = _plan_from_state(state)
    idx = state.get("search_step_idx", 0)
    if plan and idx < len(plan.steps):
        thread_id = state.get("thread_id", "")
        step = plan.steps[idx]
        # tally what we actually scraped for visibility
        try:
            items = await store.asearch(ns_scrape(thread_id, step.id), limit=50)
            scraped = len(items)
        except Exception:
            scraped = 0
        step.status = "done"
        plan.steps[idx] = step
        emit_search_progress(step.id, candidates=0, scraped=scraped)
    return {
        "search_plan": _plan_to_state(plan) if plan else None,
        "search_step_idx": idx + 1,
        "_search_candidates": [],   # GC scratch between steps (replaced by reducer)
    }


# ── summarize_search: terminal — synthesize, write summary, GC scrapes ────
async def summarize_search(state: dict, *, store: BaseStore) -> dict:
    from ..config import small_llm

    plan = _plan_from_state(state)
    thread_id = state.get("thread_id", "")
    if not plan:
        return {"phase": "idle"}

    emit_phase("summarizing")

    # Pull all scraped sources from the store.
    sources_blocks: list[str] = []
    step_ids = [s.id for s in plan.steps]
    for sid in step_ids:
        try:
            items = await store.asearch(ns_scrape(thread_id, sid), limit=50)
        except Exception:
            items = []
        for it in items:
            v = it.value or {}
            block = (
                f"### {v.get('title', '(untitled)')}\n"
                f"Step: {sid}\n\n"
                f"{v.get('markdown', '')}\n"
            )
            sources_blocks.append(block)

    if not sources_blocks:
        # Either no scrapes succeeded or no key — still produce a summary
        # from snippets so we don't fully stall.
        sources_blocks.append("(no sources scraped — proceed from general knowledge)")

    from ..prompts import SEARCH_SUMMARY_PROMPT
    prompt = SEARCH_SUMMARY_PROMPT.format(
        global_goal=plan.global_goal,
        sources="\n\n---\n\n".join(sources_blocks)[:60_000],
    )
    try:
        resp = await small_llm().ainvoke([
            SystemMessage("You write tight pedagogical research briefs."),
            HumanMessage(prompt),
        ])
        summary = (resp.content or "").strip() if hasattr(resp, "content") else str(resp)
    except Exception as e:
        emit_error("summarize_search", str(e))
        summary = f"(summary unavailable due to model error: {e})"

    # Persist the summary in the Store too (for reference) and GC scrapes.
    try:
        await store.aput(ns_search_summary(thread_id), "current",
                         {"summary": summary, "global_goal": plan.global_goal})
    except Exception:
        pass

    # GC: drop all scrape data for this thread.
    purged = await purge_all_scrapes(store, thread_id, step_ids)

    emit_search_summary_ready(length=len(summary))
    return {
        "search_summary": summary,
        "phase": "outlining",
        # Reset cursor + plan retained for visibility in supervisor context.
    }
