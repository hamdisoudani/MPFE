"""Three OpenAI-compatible endpoints: small / writer / critic.

All via langchain-openai, all `.with_structured_output()`-ready.
"""
from __future__ import annotations
import os
import warnings
from functools import lru_cache
from langchain_openai import ChatOpenAI


def _build(prefix: str, **kw) -> ChatOpenAI:
    base = os.environ[f"{prefix}_BASE_URL"]
    key = os.environ[f"{prefix}_API_KEY"]
    model = os.environ[f"{prefix}_MODEL"]
    return ChatOpenAI(
        base_url=base, api_key=key, model=model,
        temperature=kw.get("temperature", 0.2), timeout=60, max_retries=2,
    )


@lru_cache(maxsize=1)
def small_llm() -> ChatOpenAI:
    return _build("LLM_SMALL", temperature=0.0)


@lru_cache(maxsize=1)
def writer_llm() -> ChatOpenAI:
    return _build("LLM_WRITER", temperature=0.3)


@lru_cache(maxsize=1)
def critic_llm() -> ChatOpenAI:
    llm = _build("LLM_CRITIC", temperature=0.0)
    if os.environ.get("LLM_WRITER_MODEL") == os.environ.get("LLM_CRITIC_MODEL"):
        warnings.warn(
            "LLM_WRITER_MODEL == LLM_CRITIC_MODEL — self-critique is weak. "
            "Point critic at a different model family in production.",
            stacklevel=2,
        )
    return llm
