"""Live LLM smoke test against xAI — skipped unless LIVE_LLM=1."""
import os
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("LIVE_LLM") != "1",
                                reason="set LIVE_LLM=1 to run")


def test_xai_structured_output():
    from pydantic import BaseModel
    from agent.llm import small_llm

    class Ping(BaseModel):
        pong: str

    out = small_llm().with_structured_output(Ping).invoke(
        "Return JSON {\"pong\": \"ok\"}"
    )
    assert isinstance(out, Ping)
    assert isinstance(out.pong, str) and len(out.pong) > 0
