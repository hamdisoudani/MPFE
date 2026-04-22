"""Pure import / graph-construction smoke test — no LLM calls, no DB."""
import importlib
import os


def test_imports():
    os.environ.setdefault("LLM_SMALL_BASE_URL", "https://api.x.ai/v1")
    os.environ.setdefault("LLM_SMALL_API_KEY", "dummy")
    os.environ.setdefault("LLM_SMALL_MODEL", "dummy")
    os.environ.setdefault("LLM_WRITER_BASE_URL", "https://api.x.ai/v1")
    os.environ.setdefault("LLM_WRITER_API_KEY", "dummy")
    os.environ.setdefault("LLM_WRITER_MODEL", "dummy")
    os.environ.setdefault("LLM_CRITIC_BASE_URL", "https://api.x.ai/v1")
    os.environ.setdefault("LLM_CRITIC_API_KEY", "dummy")
    os.environ.setdefault("LLM_CRITIC_MODEL", "dummy")
    os.environ.setdefault("SUPABASE_URL", "http://localhost")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy")
    mod = importlib.import_module("agent.graph")
    assert mod.graph is not None
    expected = {
        "self_awareness","search_planner","web_search","clarify_with_user",
        "outline_generator","chapter_guard","write_lesson","critic_node",
        "accept_lesson","reject_lesson","activities_generator",
    }
    assert expected.issubset(set(mod.graph.nodes))


def test_state_upsert_reducer():
    from agent.state import upsert_by_id
    a = [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]
    b = [{"id": "2", "title": "B2"}, {"id": "3", "title": "C"}]
    out = {r["id"]: r for r in upsert_by_id(a, b)}
    assert out["1"]["title"] == "A"
    assert out["2"]["title"] == "B2"
    assert out["3"]["title"] == "C"
