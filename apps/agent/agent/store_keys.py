"""Conventions for LangGraph Store namespaces. Centralized so GC is honest."""
from __future__ import annotations
from typing import Iterable
from langgraph.store.base import BaseStore


def ns_scrape(thread_id: str, step_id: str) -> tuple[str, str, str]:
    return ("scrape", thread_id, step_id)


def ns_search_summary(thread_id: str) -> tuple[str, str]:
    return ("search_summary", thread_id)


def ns_draft(thread_id: str, todo_step_id: str) -> tuple[str, str, str]:
    return ("draft", thread_id, todo_step_id)


def ns_dep_summary(thread_id: str, todo_step_id: str) -> tuple[str, str, str]:
    return ("dep_summary", thread_id, todo_step_id)


async def purge_namespace(store: BaseStore, namespace: tuple[str, ...]) -> int:
    """Delete every item under `namespace`. Returns count deleted."""
    n = 0
    try:
        items = await store.asearch(namespace, limit=1000)
    except Exception:
        return 0
    for it in items:
        try:
            await store.adelete(namespace, it.key)
            n += 1
        except Exception:
            continue
    return n


async def purge_all_scrapes(store: BaseStore, thread_id: str, step_ids: Iterable[str]) -> int:
    n = 0
    for sid in step_ids:
        n += await purge_namespace(store, ns_scrape(thread_id, sid))
    return n
