from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from ..state import State
from .nodes import (
    pick_next, write_node, critic_node, decide_node, commit_node, give_up_node,
)


def _route_pick(state: dict) -> str:
    if state.get("_writer_done"):
        return END
    return "write"


def build_writer_subgraph():
    g = StateGraph(State)
    g.add_node("pick_next", pick_next)
    g.add_node("write", write_node)
    g.add_node("critic", critic_node)
    g.add_node("commit", commit_node)
    g.add_node("give_up", give_up_node)

    g.add_edge(START, "pick_next")
    g.add_conditional_edges("pick_next", _route_pick, {END: END, "write": "write"})
    g.add_edge("write", "critic")
    g.add_conditional_edges(
        "critic", decide_node,
        {"commit": "commit", "write": "write", "give_up": "give_up"},
    )
    g.add_edge("commit", "pick_next")
    g.add_edge("give_up", "pick_next")
    return g
