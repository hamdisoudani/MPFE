"""Search + scrape clients.

Search:  Serper.dev /search endpoint, JSON.
Scrape:  Try Serper /scrape; if unavailable, fall back to r.jina.ai which
         returns clean markdown without a key.
"""
from __future__ import annotations
import asyncio
import os
from typing import Any
import httpx

from ..config import (
    MAX_SEARCH_RESULTS_PER_QUERY,
    SCRAPE_TIMEOUT_S,
    serper_api_key,
)


SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_SCRAPE_URL = "https://scrape.serper.dev"
JINA_READER_URL = "https://r.jina.ai/"


async def serper_search(query: str, *, num: int | None = None) -> list[dict[str, Any]]:
    """Returns a list of {title, link, snippet, position} dicts."""
    key = serper_api_key()
    n = num or MAX_SEARCH_RESULTS_PER_QUERY
    if not key:
        # Graceful degrade for tests / no-key envs: return a synthetic stub.
        return [
            {
                "title": f"[stub] {query}",
                "link": f"https://example.com/?q={query.replace(' ', '+')}",
                "snippet": f"Stub search result for {query}",
                "position": 1,
            }
        ]
    payload = {"q": query, "num": n, "gl": "us", "hl": "en"}
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(SERPER_SEARCH_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    organic = data.get("organic") or []
    out: list[dict[str, Any]] = []
    for i, o in enumerate(organic[:n]):
        out.append({
            "title": o.get("title", "") or "",
            "link": o.get("link", "") or "",
            "snippet": o.get("snippet", "") or "",
            "position": o.get("position", i + 1),
        })
    return out


async def scrape_url(url: str) -> dict[str, str]:
    """Returns {url, title, markdown}. Markdown may be empty on failure."""
    if not url:
        return {"url": "", "title": "", "markdown": ""}
    key = serper_api_key()
    # Try Serper /scrape first if we have a key.
    if key:
        try:
            async with httpx.AsyncClient(timeout=SCRAPE_TIMEOUT_S) as c:
                r = await c.post(
                    SERPER_SCRAPE_URL,
                    json={"url": url, "includeMarkdown": True},
                    headers={"X-API-KEY": key, "Content-Type": "application/json"},
                )
                if r.status_code == 200:
                    data = r.json()
                    md = data.get("markdown") or data.get("text") or ""
                    title = (data.get("metadata") or {}).get("title") or url
                    if md.strip():
                        return {"url": url, "title": title, "markdown": md}
        except Exception:
            pass
    # Fallback: r.jina.ai — free, no key, returns markdown.
    try:
        async with httpx.AsyncClient(timeout=SCRAPE_TIMEOUT_S, follow_redirects=True) as c:
            r = await c.get(
                JINA_READER_URL + url,
                headers={"Accept": "text/markdown", "User-Agent": "syllabus-agent/1.0"},
            )
            if r.status_code == 200 and r.text.strip():
                # r.jina.ai prepends "Title: ..." then "URL Source: ..." then content.
                lines = r.text.splitlines()
                title = url
                for ln in lines[:5]:
                    if ln.lower().startswith("title:"):
                        title = ln.split(":", 1)[1].strip() or url
                        break
                return {"url": url, "title": title, "markdown": r.text}
    except Exception:
        pass
    return {"url": url, "title": url, "markdown": ""}


def truncate_markdown(md: str, *, max_chars: int = 8000) -> str:
    if not md:
        return ""
    if len(md) <= max_chars:
        return md
    return md[: max_chars] + "\n\n[…truncated…]"
