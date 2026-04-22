"""chapter_guard — picks next pending chapter or routes to END."""
from langgraph.types import Command


def chapter_guard(state: dict) -> Command:
    for ch in state.get("chapters", []):
        if ch["status"] != "done":
            return Command(goto="write_lesson", update={"active_chapter_id": ch["id"]})
    return Command(goto="__end__", update={"phase": "done"})
