"""web_search_parallel — fetch all queries in parallel with asyncio.gather."""
from __future__ import annotations
import os, asyncio, httpx
from langgraph.types import Command

async def _one(client, key, q):
    findings = []
    try:
        r = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": q, "num": 5}, timeout=20.0,
        )
        data = r.json()
        for item in (data.get("organic") or [])[:5]:
            title = item.get("title", "").strip()
            snip = item.get("snippet", "").strip()
            link = item.get("link", "").strip()
            if title or snip:
                findings.append(f"Q: {q}\nT: {title}\nS: {snip}\nU: {link}")
        if (kg := data.get("knowledgeGraph")) and kg.get("description"):
            findings.append(f"Q: {q}\nKG: {kg.get('title','')} — {kg['description']}")
    except Exception as e:
        findings.append(f"Q: {q}\n[search_error] {e}")
    return findings

async def _gather(queries, key):
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_one(client, key, q) for q in queries])
    return [f for batch in results for f in batch]

def web_search_parallel(state: dict) -> Command:
    queries = state.get("search_queries") or []
    key = os.getenv("SERPER_API_KEY")
    if not queries:
        return Command(goto="clarify_with_user")
    if not key:
        return Command(goto="clarify_with_user", update={
            "findings": ["[web_search_disabled] SERPER_API_KEY not set — proceeding without findings"],
            "search_cursor": len(queries),
        })
    findings = asyncio.run(_gather(queries, key))
    return Command(goto="clarify_with_user", update={
        "findings": findings, "search_cursor": len(queries),
    })
