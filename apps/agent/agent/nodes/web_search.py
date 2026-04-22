"""Stub web search — no LLM. Real impl will call Serper/Tavily; for now synthesize a finding."""
from __future__ import annotations
from langgraph.types import Command


def web_search(state: dict) -> Command:
    queries = state.get("search_queries", [])
    cursor = state.get("search_cursor", 0)
    if cursor >= len(queries):
        return Command(goto="search_planner")
    q = queries[cursor]
    finding = f"[stub] Results for query: {q}"
    return Command(goto="search_planner", update={"search_cursor": cursor + 1, "findings": [finding]})
