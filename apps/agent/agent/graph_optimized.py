"""Optimized graph: parallel search + parallel lesson fan-out via Send."""
from __future__ import annotations
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .state import SyllabusState
from .nodes import (
    self_awareness, clarify_with_user, outline_generator as _outline,
    activities_generator,
)
from .nodes.search_planner_once import search_planner_once
from .nodes.web_search_parallel import web_search_parallel
from .nodes.lesson_fanout import lesson_fanout
from .nodes.lesson_worker import lesson_worker
from .nodes.finalize import finalize


def outline_to_fanout(state):
    cmd = _outline(state)
    return Command(goto="lesson_fanout", update=getattr(cmd, "update", None))


def activities_then_finalize(state):
    cmd = activities_generator(state)
    if getattr(cmd, "goto", None) == "chapter_guard":
        return Command(goto="finalize", update=getattr(cmd, "update", None))
    return cmd


def build_graph_optimized():
    g = StateGraph(SyllabusState)
    g.add_node("self_awareness", self_awareness)
    g.add_node("search_planner", search_planner_once)
    g.add_node("web_search_parallel", web_search_parallel)
    g.add_node("clarify_with_user", clarify_with_user)
    g.add_node("outline_generator", outline_to_fanout)
    g.add_node("lesson_fanout", lesson_fanout)
    g.add_node("lesson_worker", lesson_worker)
    g.add_node("activities_generator", activities_then_finalize)
    g.add_node("finalize", finalize)
    g.add_edge(START, "self_awareness")
    g.add_edge("lesson_worker", "activities_generator")
    return g


def build_compiled_memory_optimized():
    return build_graph_optimized().compile(checkpointer=InMemorySaver())
