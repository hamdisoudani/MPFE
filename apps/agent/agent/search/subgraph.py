"""Wires the search subgraph and exposes a `build_search_subgraph()` factory."""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from ..state import State
from .nodes import (
    plan_step, fanout_queries, search_query,
    pick_to_scrape, fanout_scrapes, scrape_one,
    advance_step, summarize_search,
)


def _route_after_advance(state: dict) -> str:
    plan_dict = state.get("search_plan") or {}
    idx = state.get("search_step_idx", 0)
    steps = (plan_dict.get("steps") or [])
    if idx < len(steps):
        return "plan_step"
    return "summarize_search"


def build_search_subgraph():
    g = StateGraph(State)
    g.add_node("plan_step", plan_step)
    g.add_node("search_query", search_query)
    g.add_node("pick_to_scrape", pick_to_scrape)
    g.add_node("scrape_one", scrape_one)
    g.add_node("advance_step", advance_step)
    g.add_node("summarize_search", summarize_search)

    g.add_edge(START, "plan_step")
    g.add_conditional_edges("plan_step", fanout_queries, ["search_query"])
    g.add_edge("search_query", "pick_to_scrape")
    g.add_conditional_edges("pick_to_scrape", fanout_scrapes, ["scrape_one"])
    g.add_edge("scrape_one", "advance_step")
    g.add_conditional_edges(
        "advance_step",
        _route_after_advance,
        {"plan_step": "plan_step", "summarize_search": "summarize_search"},
    )
    g.add_edge("summarize_search", END)
    return g
