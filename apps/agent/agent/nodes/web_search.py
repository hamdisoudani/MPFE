"""web_search — real Serper API; falls back to stub if key missing."""
from __future__ import annotations
import os, json, httpx
from langgraph.types import Command

def web_search(state: dict) -> Command:
    queries = state.get("search_queries", [])
    cursor = state.get("search_cursor", 0)
    if cursor >= len(queries):
        return Command(goto="search_planner")
    q = queries[cursor]
    key = os.getenv("SERPER_API_KEY")
    findings: list[str] = []
    if key:
        try:
            r = httpx.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": q, "num": 5},
                timeout=20.0,
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
    else:
        findings.append(f"Q: {q}\n[stub] no SERPER_API_KEY set")
    return Command(goto="search_planner", update={
        "search_cursor": cursor + 1,
        "findings": findings,
    })
