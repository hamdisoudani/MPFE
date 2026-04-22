"""Graph assembly.

Topology (Revision 2):
  self_awareness -> search_planner <-> web_search -> clarify_with_user
    -> outline_generator -> chapter_guard <-> (write_lesson -> critic
       -> (accept -> [activities] -> chapter_guard | reject -> write_lesson))
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from .state import SyllabusState
from .nodes import (
    self_awareness, search_planner, web_search, clarify_with_user,
    outline_generator, chapter_guard, write_lesson, critic_node,
    accept_lesson, reject_lesson, activities_generator,
)


def build_graph():
    g = StateGraph(SyllabusState)
    g.add_node("self_awareness", self_awareness)
    g.add_node("search_planner", search_planner)
    g.add_node("web_search", web_search)
    g.add_node("clarify_with_user", clarify_with_user)
    g.add_node("outline_generator", outline_generator)
    g.add_node("chapter_guard", chapter_guard)
    g.add_node("write_lesson", write_lesson)
    g.add_node("critic_node", critic_node)
    g.add_node("accept_lesson", accept_lesson)
    g.add_node("reject_lesson", reject_lesson)
    g.add_node("activities_generator", activities_generator)
    g.add_edge(START, "self_awareness")
    return g


async def build_compiled_with_postgres():
    """Production compile: AsyncPostgresSaver against Supabase."""
    import os
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    db_url = os.environ["SUPABASE_DB_URL"]
    saver_ctx = AsyncPostgresSaver.from_conn_string(db_url)
    return build_graph(), saver_ctx


def build_compiled_memory():
    """Dev/smoke compile: InMemorySaver. Not for production."""
    return build_graph().compile(checkpointer=InMemorySaver())


graph = build_graph().compile()
