"""Pure import / graph-construction smoke test — no LLM calls, no DB."""
import importlib
import os


def _stub_env() -> None:
    defaults = {
        "LLM_SMALL_BASE_URL": "https://api.x.ai/v1",
        "LLM_SMALL_API_KEY": "dummy",
        "LLM_SMALL_MODEL": "dummy",
        "LLM_WRITER_BASE_URL": "https://api.x.ai/v1",
        "LLM_WRITER_API_KEY": "dummy",
        "LLM_WRITER_MODEL": "dummy",
        "LLM_CRITIC_BASE_URL": "https://api.x.ai/v1",
        "LLM_CRITIC_API_KEY": "dummy",
        "LLM_CRITIC_MODEL": "dummy",
        "SUPABASE_URL": "http://localhost",
        "SUPABASE_SERVICE_ROLE_KEY": "dummy",
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)


def test_imports_and_topology():
    _stub_env()
    mod = importlib.import_module("agent.graph")
    assert mod.graph is not None
    expected = {
        "supervisor",
        "ask_user_node",
        "apply_search_plan",
        "apply_todo_plan",
        "db_tools_node",
        "search_subgraph",
        "writer_subgraph",
    }
    assert expected.issubset(set(mod.graph.nodes))


def test_state_reducers():
    _stub_env()
    from agent.state import merge_candidates, merge_dict, capped_messages
    from langchain_core.messages import HumanMessage, AIMessage

    a = [{"step_id": "S1", "url": "u", "score": 0.8}]
    b = [{"step_id": "S1", "url": "u", "score": 0.9}, {"step_id": "S1", "url": "v", "score": 0.5}]
    out = {(c["step_id"], c["url"]): c for c in merge_candidates(a, b)}
    assert out[("S1", "u")]["score"] == 0.9
    assert out[("S1", "v")]["score"] == 0.5

    assert merge_dict({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert merge_dict(None, {"b": 2}) == {"b": 2}

    msgs = capped_messages([HumanMessage("hi")], [AIMessage("hello")])
    assert len(msgs) == 2


def test_plan_validation():
    _stub_env()
    from agent.state import SearchPlan, TodoPlan
    sp = SearchPlan.model_validate({
        "global_goal": "x",
        "steps": [{"id": "S1", "title": "t", "queries": ["q"]}],
    })
    assert sp.steps[0].id == "S1"
    tp = TodoPlan.model_validate({
        "steps": [{
            "id": "T1", "chapter_ref": "CH1", "name": "Lesson",
            "description": "must teach", "must_cover": ["x"],
        }]
    })
    assert tp.steps[0].chapter_ref == "CH1"
