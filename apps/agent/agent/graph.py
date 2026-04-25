"""Top-level graph assembly.

Compiles a default graph with InMemorySaver + InMemoryStore for tests/dev.
For production, call `build_compiled_with_postgres()` to attach an
AsyncPostgresSaver against Supabase.
"""
from __future__ import annotations
import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from .state import State
from .search import build_search_subgraph
from .writer import build_writer_subgraph
from .supervisor import (
    supervisor_node, route_after_supervisor,
    ask_user_node, apply_search_plan, apply_todo_plan, db_tools_node,
)


def build_graph() -> StateGraph:
    g = StateGraph(State)

    # nodes
    g.add_node("supervisor", supervisor_node)
    g.add_node("ask_user_node", ask_user_node)
    g.add_node("apply_search_plan", apply_search_plan)
    g.add_node("apply_todo_plan", apply_todo_plan)
    g.add_node("db_tools_node", db_tools_node)
    g.add_node("search_subgraph", build_search_subgraph().compile())
    g.add_node("writer_subgraph", build_writer_subgraph().compile())

    # edges
    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "__end__": END,
            "ask_user_node": "ask_user_node",
            "apply_search_plan": "apply_search_plan",
            "apply_todo_plan": "apply_todo_plan",
            "db_tools_node": "db_tools_node",
        },
    )
    g.add_edge("ask_user_node", "supervisor")
    g.add_edge("apply_search_plan", "search_subgraph")
    g.add_edge("search_subgraph", "supervisor")
    g.add_edge("apply_todo_plan", "writer_subgraph")
    g.add_edge("writer_subgraph", "supervisor")
    g.add_edge("db_tools_node", "supervisor")
    return g


def build_compiled_memory():
    """Dev/smoke compile with in-memory checkpoint and store."""
    return build_graph().compile(
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )


async def build_compiled_with_postgres():
    """Production compile: AsyncPostgresSaver + InMemoryStore (good enough
    for thread-scoped Store data — it's all purged at run boundaries)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    db_url = os.environ["SUPABASE_DB_URL"]
    saver_ctx = AsyncPostgresSaver.from_conn_string(db_url)
    return build_graph(), saver_ctx, InMemoryStore()


# Default export — for `langgraph dev` / langgraph.json.
# The LangGraph platform (and `langgraph dev`) injects its own checkpointer +
# store at runtime, so the exported graph must NOT ship with custom ones.
# For standalone scripts / tests, use `build_compiled_memory()` instead.
graph = build_graph().compile()
