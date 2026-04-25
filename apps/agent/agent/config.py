"""LLM factories + tunables.

All LLMs are OpenAI-compatible. Three roles:
  - LLM_SMALL  — cheap utility (plan validation, summarization)
  - LLM_WRITER — supervisor + lesson writer (best instruction following)
  - LLM_CRITIC — different model family from WRITER to avoid self-critique blindspots

Env reads are lazy so tests can stub.
"""
from __future__ import annotations
import os
import warnings
from functools import lru_cache
from langchain_openai import ChatOpenAI


# ── tunables ────────────────────────────────────────────────────────────────
MAX_WRITER_ATTEMPTS = int(os.environ.get("MAX_WRITER_ATTEMPTS", "3"))
MAX_SEARCH_RESULTS_PER_QUERY = int(os.environ.get("MAX_SEARCH_RESULTS_PER_QUERY", "6"))
MAX_SCRAPE_PER_STEP = int(os.environ.get("MAX_SCRAPE_PER_STEP", "3"))
MESSAGE_TAIL_CAP = int(os.environ.get("MESSAGE_TAIL_CAP", "40"))
SCRAPE_TIMEOUT_S = float(os.environ.get("SCRAPE_TIMEOUT_S", "20"))
SUPERVISOR_MAX_TURNS = int(os.environ.get("SUPERVISOR_MAX_TURNS", "30"))


def _build(prefix: str, *, temperature: float, json_mode: bool = False) -> ChatOpenAI:
    base = os.environ[f"{prefix}_BASE_URL"]
    key = os.environ[f"{prefix}_API_KEY"]
    model = os.environ[f"{prefix}_MODEL"]
    kwargs: dict = dict(
        base_url=base,
        api_key=key,
        model=model,
        temperature=temperature,
        timeout=120,
        max_retries=2,
        # LangSmith stays useful but we don't need partial-token streaming for
        # the supervisor — it slows tool-calling decisions on some providers.
        disable_streaming=True,
    )
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=1)
def small_llm() -> ChatOpenAI:
    return _build("LLM_SMALL", temperature=0.0)


@lru_cache(maxsize=1)
def writer_llm() -> ChatOpenAI:
    return _build("LLM_WRITER", temperature=0.4)


@lru_cache(maxsize=1)
def supervisor_llm() -> ChatOpenAI:
    # Slightly cooler than writer — we want decisive routing, not creativity.
    return _build("LLM_WRITER", temperature=0.1)


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


def serper_api_key() -> str | None:
    return os.environ.get("SERPER_API_KEY") or os.environ.get("SERPR_API_KEY")
