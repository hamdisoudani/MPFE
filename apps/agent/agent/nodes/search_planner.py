"""Plan 3–5 web search queries with structured output."""
from __future__ import annotations
from pydantic import BaseModel, Field
from langgraph.types import Command
from ..llm import small_llm


class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=3, max_length=5)


def search_planner(state: dict) -> Command:
    if state.get("search_queries") and state.get("search_cursor", 0) >= len(state["search_queries"]):
        return Command(goto="clarify_with_user")
    if state.get("search_queries"):
        return Command(goto="web_search")
    llm = small_llm().with_structured_output(SearchPlan)
    plan: SearchPlan = llm.invoke(
        f"You are planning web searches to research this teaching requirement:\n{state['requirements']}\n"
        "Return 3–5 diverse queries."
    )
    return Command(goto="web_search", update={"search_queries": plan.queries, "search_cursor": 0})
