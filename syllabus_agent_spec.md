# Syllabus Agent — Full Implementation Spec
> Feed this document to a coding agent. Follow every section in order. Do not skip ahead.

---

## 0. Guiding Principles

Before writing a single line of code, the agent must internalize these rules:

1. **State is an index, never a store.** The LangGraph checkpoint holds IDs, cursors, and small metadata only. All large content (lesson HTML, BlockNote JSON, scraped text) goes to Supabase immediately and is referenced by ID.
2. **Every LLM node is forced.** No node lets the LLM decide whether to call a tool. All LLM nodes use `.with_structured_output()`. The LLM's only job is to fill a Pydantic schema.
3. **Every write is an upsert.** Every Supabase insert uses `upsert` with a unique constraint so the graph can crash and resume without creating duplicates.
4. **Self-awareness runs first.** Before doing anything, the graph checks Supabase for existing work and resumes exactly from the right point. The agent never blindly re-runs completed work.
5. **The critic is the sole gatekeeper.** No lesson enters the database without `pass: true` from the critic. The writer cannot approve its own output.
6. **Max 3 drafts per lesson.** If the critic fails a lesson 3 times, the agent saves the best draft with a `needs_review: true` flag and moves on. No infinite loops.

---

## 1. Project Overview

A two-part system:

- **LangGraph Agent** (Python) — run locally with `langgraph dev`. Exposed as an HTTP/SSE server on `localhost:2024`. Orchestrates the full syllabus creation pipeline.
- **Next.js Frontend** — connects to the LangGraph dev server via the LangGraph SDK for live streaming updates. Connects to Supabase for realtime database changes to render completed lessons as they are written, without polling.

The user opens the Next.js app, submits their syllabus requirements, and watches the syllabus build itself in real time: search progress → chapter outline → lesson by lesson appearing in a BlockNote editor.

---

## 2. Architecture Diagram

```
User Browser (Next.js)
  │
  ├── LangGraph SDK ──► langgraph dev server (localhost:2024)
  │       SSE stream        │
  │   (node events,         │  Python graph runs here
  │    phase updates)       │  writes content to Supabase
  │                         ▼
  └── Supabase Realtime ◄── Supabase (PostgreSQL + Realtime)
        (lesson inserts,     Lessons, chapters, syllabuses
         chapter updates)    stored permanently here
```

The frontend receives two separate streams:
1. **LangGraph SSE** — tells it what the agent is *doing* (which node is active, search progress, critique text). Used for the live status panel.
2. **Supabase Realtime** — tells it when content is *done* (a lesson was accepted and saved). Used to render the actual syllabus content.

---

## 3. Tech Stack

```
Agent:
  - Python 3.11+
  - langgraph >= 0.2.50
  - langchain-anthropic (Claude claude-sonnet-4-20250514 as the LLM everywhere)
  - langchain-community (for web search tools)
  - supabase-py
  - pydantic v2
  - httpx (for scraping)
  - beautifulsoup4 (for HTML parsing)
  - python-dotenv

Frontend:
  - Next.js 14 (App Router)
  - @langchain/langgraph-sdk
  - @supabase/supabase-js
  - @blocknote/react @blocknote/core @blocknote/mantine
  - tailwindcss
  - zustand (state management)
  - typescript

External services:
  - Anthropic API (LLM)
  - Serper API (Google search — serper.dev)
  - Supabase project (free tier is fine)
```

---

## 4. Repository Structure

```
syllabus-agent/
├── agent/                          # LangGraph Python agent
│   ├── graph.py                    # Main graph definition and compilation
│   ├── state.py                    # State TypedDict and all Pydantic schemas
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── init_node.py            # Self-awareness / recovery entry point
│   │   ├── search_planner.py       # Structured output: SearchPlan
│   │   ├── web_search.py           # Pure logic: SERP + scrape
│   │   ├── findings_summarizer.py  # Summarize all search findings
│   │   ├── syllabus_outline.py     # Structured output: SyllabusOutline
│   │   ├── chapter_guard.py        # Self-awareness before each chapter
│   │   ├── lesson_writer.py        # Structured output: LessonContent
│   │   ├── critic.py               # Structured output: CritiqueResult
│   │   ├── accept_lesson.py        # Supabase upsert + state cleanup
│   │   └── reject_lesson.py        # Increment attempt counter, keep critique
│   ├── tools/
│   │   ├── serper.py               # Serper API wrapper
│   │   └── scraper.py              # httpx + BeautifulSoup scraper
│   ├── db/
│   │   └── supabase_client.py      # Supabase client singleton
│   ├── langgraph.json              # LangGraph dev server config
│   ├── requirements.txt
│   └── .env
│
└── frontend/                       # Next.js app
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                 # Landing: requirements form
    │   └── syllabus/
    │       └── [threadId]/
    │           └── page.tsx         # Main syllabus view
    ├── components/
    │   ├── RequirementsForm.tsx
    │   ├── AgentStatusPanel.tsx     # Live agent activity from LangGraph SSE
    │   ├── SyllabusRenderer.tsx     # Renders chapters + lessons from Supabase
    │   ├── LessonBlock.tsx          # BlockNote read-only viewer per lesson
    │   └── SearchProgressBar.tsx
    ├── lib/
    │   ├── langgraph.ts             # LangGraph SDK client + streaming hook
    │   ├── supabase.ts              # Supabase client + realtime hooks
    │   └── types.ts                 # Shared TypeScript types matching DB schema
    ├── store/
    │   └── syllabus.ts              # Zustand store
    ├── .env.local
    └── package.json
```

---

## 5. Supabase Schema

Run this SQL in the Supabase SQL editor exactly as written. The schema is designed for upserts and realtime.

```sql
-- Enable UUID generation
create extension if not exists "pgcrypto";

-- ─────────────────────────────────────────────
-- SYLLABUSES
-- One row per agent run / thread
-- ─────────────────────────────────────────────
create table syllabuses (
  id              uuid primary key default gen_random_uuid(),
  thread_id       text unique not null,         -- LangGraph thread_id
  title           text,
  user_requirements text not null,
  field           text,                         -- e.g. "English A1"
  status          text not null default 'init', -- init | searching | outlining | writing | done
  findings_summary text,
  total_chapters  int default 0,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index on syllabuses(thread_id);

-- ─────────────────────────────────────────────
-- SEARCH STEPS
-- One row per step in the search plan
-- ─────────────────────────────────────────────
create table search_steps (
  id              uuid primary key default gen_random_uuid(),
  syllabus_id     uuid references syllabuses(id) on delete cascade,
  step_index      int not null,
  topic           text not null,
  queries         jsonb not null,               -- array of {query, rationale}
  status          text not null default 'pending', -- pending | done
  findings        text,                         -- raw summarized findings for this step
  created_at      timestamptz default now(),
  unique(syllabus_id, step_index)
);

-- ─────────────────────────────────────────────
-- CHAPTERS
-- One row per chapter in the syllabus
-- ─────────────────────────────────────────────
create table chapters (
  id              uuid primary key default gen_random_uuid(),
  syllabus_id     uuid references syllabuses(id) on delete cascade,
  chapter_index   int not null,
  title           text not null,
  status          text not null default 'pending', -- pending | writing | done
  created_at      timestamptz default now(),
  updated_at      timestamptz default now(),
  unique(syllabus_id, chapter_index)
);

create index on chapters(syllabus_id);

-- ─────────────────────────────────────────────
-- SUBSTEPS
-- One row per lesson/substep within a chapter
-- ─────────────────────────────────────────────
create table substeps (
  id              uuid primary key default gen_random_uuid(),
  chapter_id      uuid references chapters(id) on delete cascade,
  syllabus_id     uuid references syllabuses(id) on delete cascade,
  position        int not null,                 -- order within chapter
  title           text not null,
  requirements    text not null,                -- what the writer must cover
  learning_objectives jsonb not null default '[]', -- string[]
  status          text not null default 'pending', -- pending | writing | done
  created_at      timestamptz default now(),
  unique(chapter_id, position)
);

create index on substeps(chapter_id);
create index on substeps(syllabus_id);

-- ─────────────────────────────────────────────
-- LESSONS
-- One row per completed (critic-approved) lesson
-- This is where the actual BlockNote content lives
-- ─────────────────────────────────────────────
create table lessons (
  id              uuid primary key default gen_random_uuid(),
  substep_id      uuid references substeps(id) on delete cascade unique,
  chapter_id      uuid references chapters(id) on delete cascade,
  syllabus_id     uuid references syllabuses(id) on delete cascade,
  title           text not null,
  content         jsonb not null,               -- BlockNote JSON block array
  summary         text,                         -- short summary for agent context
  draft_attempts  int not null default 1,
  needs_review    boolean not null default false, -- true if force-accepted after 3 fails
  created_at      timestamptz default now()
);

create index on lessons(chapter_id);
create index on lessons(syllabus_id);

-- ─────────────────────────────────────────────
-- REALTIME
-- Enable realtime on the tables the frontend subscribes to
-- ─────────────────────────────────────────────
alter publication supabase_realtime add table syllabuses;
alter publication supabase_realtime add table chapters;
alter publication supabase_realtime add table lessons;

-- ─────────────────────────────────────────────
-- UPDATED_AT TRIGGER
-- ─────────────────────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger syllabuses_updated_at before update on syllabuses
  for each row execute function update_updated_at();

create trigger chapters_updated_at before update on chapters
  for each row execute function update_updated_at();
```

---

## 6. Agent: State Definition (`agent/state.py`)

```python
from typing import TypedDict, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS (for .with_structured_output())
# ─────────────────────────────────────────────

class SearchQuery(BaseModel):
    query: str = Field(description="The exact search query string to use")
    rationale: str = Field(description="Why this query helps research the topic")

class SearchStep(BaseModel):
    step_index: int = Field(description="0-based index of this step")
    topic: str = Field(description="The topic or aspect being researched in this step")
    queries: list[SearchQuery] = Field(description="2-3 search queries for this topic", min_length=2, max_length=3)

class SearchPlan(BaseModel):
    steps: list[SearchStep] = Field(description="Ordered list of research steps", min_length=2, max_length=6)
    research_rationale: str = Field(description="Why these specific topics were chosen to research")

class SubstepSchema(BaseModel):
    position: int = Field(description="0-based position of this substep within the chapter")
    title: str = Field(description="Clear, specific title of this lesson")
    requirements: str = Field(description="Detailed description of what the writer must cover in this lesson. Be specific about depth, examples, and tone.")
    learning_objectives: list[str] = Field(description="2-4 concrete learning objectives the student achieves after this lesson", min_length=2, max_length=4)

class ChapterSchema(BaseModel):
    chapter_index: int = Field(description="0-based index of this chapter")
    title: str = Field(description="Chapter title")
    substeps: list[SubstepSchema] = Field(description="Ordered lessons within this chapter", min_length=1, max_length=8)

class SyllabusOutline(BaseModel):
    syllabus_title: str = Field(description="Full descriptive title of the syllabus")
    chapters: list[ChapterSchema] = Field(description="Ordered chapters of the syllabus", min_length=2, max_length=12)
    outline_rationale: str = Field(description="Brief explanation of the pedagogical structure chosen")

class LessonBlock(BaseModel):
    """A single BlockNote-compatible content block."""
    type: str = Field(description="BlockNote block type: 'paragraph', 'heading', 'bulletListItem', 'numberedListItem', 'codeBlock'")
    content: list[dict] = Field(description="Array of inline content objects: [{type: 'text', text: '...', styles: {}}]")
    props: dict = Field(default_factory=dict, description="Block props: for heading use {level: 1|2|3}")

class LessonContent(BaseModel):
    title: str = Field(description="The exact title of this lesson")
    blocks: list[LessonBlock] = Field(description="BlockNote-compatible content blocks forming the full lesson. Aim for 8-20 blocks.", min_length=5)
    summary: str = Field(description="1-2 sentence summary of what this lesson covers, for agent context reuse")

class CritiqueResult(BaseModel):
    critique: str = Field(description="Detailed critique of the lesson. If passing, briefly state why it meets requirements. If failing, be specific about what is missing or wrong.")
    improvement_points: list[str] = Field(description="Specific actionable improvements. Empty list if passing.", default_factory=list)
    pass_lesson: bool = Field(description="True if the lesson meets all requirements and learning objectives. False if it needs revision.")


# ─────────────────────────────────────────────
# ACTIVE SUBSTEP (held in state during write/critique loop)
# Cleared from state the moment the lesson is accepted
# ─────────────────────────────────────────────

class ActiveSubstep(TypedDict):
    substep_id: str           # Supabase substep row ID
    chapter_id: str           # Supabase chapter row ID
    position: int
    title: str
    requirements: str
    learning_objectives: list[str]
    current_draft: str        # BlockNote JSON string of current draft
    current_draft_blocks: list  # Raw blocks list
    critique: str             # Latest critic output (empty string if first attempt)
    improvement_points: list[str]
    draft_attempts: int


# ─────────────────────────────────────────────
# MAIN STATE
# Everything kept small. Content lives in Supabase.
# ─────────────────────────────────────────────

class SyllabusState(TypedDict):
    # Identity
    thread_id: str
    user_requirements: str

    # Self-awareness / recovery
    phase: Literal["init", "searching", "summarizing", "outlining", "writing", "done"]
    recovery_mode: bool          # True if resuming from a previous interrupted run
    syllabus_id: str             # Supabase syllabuses.id (set after first upsert)

    # Search phase
    search_plan: list[dict]      # Serialized SearchStep objects
    search_step_cursor: int      # Which step is next to execute
    findings_summary: str        # Final consolidated summary (set after summarizer node)

    # Outline phase
    syllabus_outline: list[dict] # Serialized ChapterSchema objects
    # chapters and substeps are written to Supabase immediately after outline generation
    # state only keeps the structure for cursor navigation

    # Writing phase
    chapter_cursor: int          # Which chapter is currently being written
    substep_cursor: int          # Which substep within that chapter
    active_substep: Optional[ActiveSubstep]  # Cleared on accept
    completed_lesson_ids: list[str]          # Supabase lesson IDs (for audit only)

    # Error tracking
    last_error: Optional[str]
```

---

## 7. Agent: Node Implementations

### 7.1 `agent/db/supabase_client.py`

```python
import os
from supabase import create_client, Client
from functools import lru_cache

@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # Use service role for agent writes
    return create_client(url, key)
```

### 7.2 `agent/nodes/init_node.py` — Self-Awareness Entry Point

This is the most important node. It runs first on every graph invocation and decides whether to start fresh or resume.

```python
from agent.state import SyllabusState
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig


async def init_node(state: SyllabusState, config: RunnableConfig) -> dict:
    """
    Self-awareness node. Always runs first.
    
    Checks Supabase for any existing syllabus linked to this thread_id.
    If found, reconstructs the correct cursor positions and returns the
    right phase so the graph resumes exactly where it left off.
    
    If not found, creates the syllabus row and starts fresh.
    """
    db = get_supabase()
    thread_id = config["configurable"]["thread_id"]
    user_requirements = state.get("user_requirements", "")

    # ── Check if syllabus already exists ──────────────────────────────────
    existing = (
        db.table("syllabuses")
        .select("*")
        .eq("thread_id", thread_id)
        .maybe_single()
        .execute()
    )

    if existing.data is None:
        # ── Fresh start: create syllabus row ──────────────────────────────
        created = (
            db.table("syllabuses")
            .insert({
                "thread_id": thread_id,
                "user_requirements": user_requirements,
                "status": "init",
            })
            .execute()
        )
        syllabus_id = created.data[0]["id"]
        return {
            "syllabus_id": syllabus_id,
            "phase": "searching",
            "recovery_mode": False,
            "search_step_cursor": 0,
            "chapter_cursor": 0,
            "substep_cursor": 0,
            "completed_lesson_ids": [],
            "search_plan": [],
            "syllabus_outline": [],
            "findings_summary": "",
            "active_substep": None,
        }

    # ── Existing syllabus: determine recovery point ────────────────────────
    syllabus = existing.data
    syllabus_id = syllabus["id"]
    status = syllabus["status"]

    if status == "done":
        # Nothing to do
        return {"syllabus_id": syllabus_id, "phase": "done", "recovery_mode": True}

    if status in ("init", "searching"):
        # Check how many search steps are already done
        done_steps = (
            db.table("search_steps")
            .select("step_index")
            .eq("syllabus_id", syllabus_id)
            .eq("status", "done")
            .execute()
        )
        done_indices = [s["step_index"] for s in (done_steps.data or [])]
        cursor = max(done_indices) + 1 if done_indices else 0

        # Recover search_plan from DB if it exists
        all_steps = (
            db.table("search_steps")
            .select("*")
            .eq("syllabus_id", syllabus_id)
            .order("step_index")
            .execute()
        )
        search_plan = [
            {"step_index": s["step_index"], "topic": s["topic"], "queries": s["queries"]}
            for s in (all_steps.data or [])
        ]

        return {
            "syllabus_id": syllabus_id,
            "phase": "searching" if search_plan else "searching",
            "recovery_mode": True,
            "search_step_cursor": cursor,
            "search_plan": search_plan,
            "findings_summary": syllabus.get("findings_summary") or "",
            "chapter_cursor": 0,
            "substep_cursor": 0,
            "completed_lesson_ids": [],
            "syllabus_outline": [],
            "active_substep": None,
        }

    if status == "outlining":
        # Search done. Need to run outline generator.
        return {
            "syllabus_id": syllabus_id,
            "phase": "outlining",
            "recovery_mode": True,
            "findings_summary": syllabus.get("findings_summary") or "",
            "search_step_cursor": 0,
            "chapter_cursor": 0,
            "substep_cursor": 0,
            "completed_lesson_ids": [],
            "search_plan": [],
            "syllabus_outline": [],
            "active_substep": None,
        }

    if status == "writing":
        # Reconstruct outline and find the next unwritten substep
        chapters_res = (
            db.table("chapters")
            .select("*, substeps(*, lessons(id))")
            .eq("syllabus_id", syllabus_id)
            .order("chapter_index")
            .execute()
        )
        chapters = chapters_res.data or []

        # Rebuild outline from DB
        syllabus_outline = []
        for ch in chapters:
            chapter_entry = {
                "chapter_index": ch["chapter_index"],
                "title": ch["title"],
                "substeps": [
                    {
                        "position": s["position"],
                        "title": s["title"],
                        "requirements": s["requirements"],
                        "learning_objectives": s["learning_objectives"],
                    }
                    for s in sorted(ch.get("substeps", []), key=lambda x: x["position"])
                ],
            }
            syllabus_outline.append(chapter_entry)

        # Find the first substep that has no lesson
        chapter_cursor = 0
        substep_cursor = 0
        completed_lesson_ids = []
        found = False

        for ch in chapters:
            substeps = sorted(ch.get("substeps", []), key=lambda x: x["position"])
            for ss in substeps:
                lessons = ss.get("lessons", [])
                if lessons:
                    completed_lesson_ids.append(lessons[0]["id"])
                else:
                    if not found:
                        chapter_cursor = ch["chapter_index"]
                        substep_cursor = ss["position"]
                        found = True

        return {
            "syllabus_id": syllabus_id,
            "phase": "writing",
            "recovery_mode": True,
            "syllabus_outline": syllabus_outline,
            "chapter_cursor": chapter_cursor,
            "substep_cursor": substep_cursor,
            "completed_lesson_ids": completed_lesson_ids,
            "findings_summary": syllabus.get("findings_summary") or "",
            "search_step_cursor": 0,
            "search_plan": [],
            "active_substep": None,
        }

    # Fallback
    return {"syllabus_id": syllabus_id, "phase": "searching", "recovery_mode": False}
```

### 7.3 `agent/nodes/search_planner.py`

```python
from langchain_anthropic import ChatAnthropic
from agent.state import SyllabusState, SearchPlan
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig

llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
planner_llm = llm.with_structured_output(SearchPlan)

SYSTEM = """You are a curriculum research planner. Given a syllabus topic and requirements,
you design a targeted research plan to gather international guidelines, best practices,
and curriculum standards for that syllabus.

Focus on:
- Official bodies and standards (CEFR, IB, Common Core, etc. depending on field)
- Academic best practices and pedagogical research
- Real curriculum examples from recognized institutions

Return a structured search plan with 3-6 steps, each with 2-3 specific search queries."""

async def search_planner_node(state: SyllabusState, config: RunnableConfig) -> dict:
    # Skip if we already have a plan (recovery mode with existing steps)
    if state.get("search_plan") and len(state["search_plan"]) > 0:
        return {}  # No state change, graph will route past this

    db = get_supabase()

    result: SearchPlan = await planner_llm.ainvoke([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Topic and requirements:\n{state['user_requirements']}"}
    ])

    # Persist each step to Supabase immediately
    for step in result.steps:
        db.table("search_steps").upsert({
            "syllabus_id": state["syllabus_id"],
            "step_index": step.step_index,
            "topic": step.topic,
            "queries": [q.model_dump() for q in step.queries],
            "status": "pending",
        }, on_conflict="syllabus_id,step_index").execute()

    # Update syllabus status
    db.table("syllabuses").update({"status": "searching"}).eq("id", state["syllabus_id"]).execute()

    return {
        "search_plan": [s.model_dump() for s in result.steps],
        "search_step_cursor": 0,
    }
```

### 7.4 `agent/nodes/web_search.py` — No LLM

```python
import httpx
import os
from bs4 import BeautifulSoup
from agent.state import SyllabusState
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig

SERPER_API_KEY = os.environ["SERPER_API_KEY"]
SERPER_URL = "https://google.serper.dev/search"

async def _serper_search(query: str) -> list[dict]:
    """Run a Serper search and return top 5 organic results."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            SERPER_URL,
            json={"q": query, "num": 5},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        )
        data = resp.json()
        return data.get("organic", [])

async def _scrape_url(url: str) -> str:
    """Fetch a URL and extract clean text. Returns empty string on failure."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # Limit to 3000 chars per page to avoid blowing up the summarizer
            return text[:3000]
    except Exception:
        return ""

async def web_search_node(state: SyllabusState, config: RunnableConfig) -> dict:
    """
    Executes the current search step.
    Pure logic — no LLM involved.
    
    For the current step_index:
    1. Run all queries through Serper
    2. Pick top 3 unique URLs across all queries
    3. Scrape each URL for content
    4. Concatenate findings and store in Supabase
    5. Advance the cursor
    """
    db = get_supabase()
    cursor = state["search_step_cursor"]
    search_plan = state["search_plan"]

    if cursor >= len(search_plan):
        # All steps done — this shouldn't be called, but guard anyway
        return {}

    current_step = search_plan[cursor]
    queries = current_step["queries"]  # list of {query, rationale}

    # ── Run all queries ───────────────────────────────────────────────────
    all_results = []
    seen_urls = set()
    for q in queries:
        results = await _serper_search(q["query"])
        for r in results:
            url = r.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    # Take top 4 unique results
    top_results = all_results[:4]

    # ── Scrape top results ────────────────────────────────────────────────
    scraped_parts = []
    for result in top_results:
        url = result.get("link", "")
        snippet = result.get("snippet", "")
        title = result.get("title", "")
        content = await _scrape_url(url)
        if content:
            scraped_parts.append(f"SOURCE: {title}\nURL: {url}\n\n{content}")
        elif snippet:
            scraped_parts.append(f"SOURCE: {title}\nSNIPPET: {snippet}")

    findings_text = "\n\n---\n\n".join(scraped_parts) if scraped_parts else "No substantial content found."

    # ── Persist to Supabase ───────────────────────────────────────────────
    db.table("search_steps").update({
        "status": "done",
        "findings": findings_text[:8000],  # cap stored per step
    }).eq("syllabus_id", state["syllabus_id"]).eq("step_index", cursor).execute()

    return {
        "search_step_cursor": cursor + 1,
    }
```

### 7.5 `agent/nodes/findings_summarizer.py`

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import SyllabusState
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig

llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)

SYSTEM = """You are a curriculum research analyst. You receive raw scraped content from 
multiple web sources about educational standards and curriculum design.

Your job is to produce a CONSOLIDATED RESEARCH SUMMARY (max 2000 words) that:
1. Identifies the key international standards and guidelines relevant to this syllabus
2. Lists the essential content areas and topics that should be covered
3. Notes recommended pedagogical approaches and sequencing
4. Highlights what distinguishes excellent syllabuses in this field

Write in clear, structured prose. This summary will be used to generate a syllabus outline."""

async def findings_summarizer_node(state: SyllabusState, config: RunnableConfig) -> dict:
    db = get_supabase()
    syllabus_id = state["syllabus_id"]

    # Load all step findings from Supabase
    steps_res = (
        db.table("search_steps")
        .select("step_index, topic, findings")
        .eq("syllabus_id", syllabus_id)
        .eq("status", "done")
        .order("step_index")
        .execute()
    )
    steps = steps_res.data or []

    # Build combined findings text
    combined = f"SYLLABUS REQUIREMENTS:\n{state['user_requirements']}\n\n"
    combined += "RESEARCH FINDINGS BY TOPIC:\n\n"
    for step in steps:
        combined += f"## Topic: {step['topic']}\n{step['findings'] or 'No findings.'}\n\n"

    # Summarize
    summary_response = await llm.ainvoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=combined)
    ])
    summary = summary_response.content

    # Persist summary to syllabus row
    db.table("syllabuses").update({
        "findings_summary": summary,
        "status": "outlining",
    }).eq("id", syllabus_id).execute()

    return {"findings_summary": summary, "phase": "outlining"}
```

### 7.6 `agent/nodes/syllabus_outline.py`

```python
from langchain_anthropic import ChatAnthropic
from agent.state import SyllabusState, SyllabusOutline
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig

llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.2)
outline_llm = llm.with_structured_output(SyllabusOutline)

SYSTEM = """You are a master curriculum designer. Based on research findings and user requirements,
you design a complete, structured syllabus outline.

Rules:
- Each chapter should have a clear, coherent theme
- Each substep (lesson) should be focused and completable in one session
- Requirements for each lesson must be specific enough that a writer can produce it without asking questions
- Learning objectives must be concrete and measurable (use Bloom's taxonomy verbs)
- The sequence must be pedagogically sound: foundational concepts before advanced ones
- Do not include a "review" or "assessment" chapter unless explicitly requested"""

async def syllabus_outline_node(state: SyllabusState, config: RunnableConfig) -> dict:
    # Skip if outline already exists (recovery)
    if state.get("syllabus_outline") and len(state["syllabus_outline"]) > 0:
        return {"phase": "writing"}

    db = get_supabase()

    prompt = f"""RESEARCH SUMMARY:
{state['findings_summary']}

USER REQUIREMENTS:
{state['user_requirements']}

Design a complete syllabus outline."""

    result: SyllabusOutline = await outline_llm.ainvoke([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt}
    ])

    # ── Persist chapters and substeps to Supabase (upsert) ────────────────
    syllabus_id = state["syllabus_id"]

    # Update syllabus title
    db.table("syllabuses").update({
        "title": result.syllabus_title,
        "total_chapters": len(result.chapters),
        "status": "writing",
    }).eq("id", syllabus_id).execute()

    for chapter in result.chapters:
        # Upsert chapter
        ch_res = db.table("chapters").upsert({
            "syllabus_id": syllabus_id,
            "chapter_index": chapter.chapter_index,
            "title": chapter.title,
            "status": "pending",
        }, on_conflict="syllabus_id,chapter_index").execute()

        chapter_id = ch_res.data[0]["id"]

        # Upsert substeps
        for substep in chapter.substeps:
            db.table("substeps").upsert({
                "chapter_id": chapter_id,
                "syllabus_id": syllabus_id,
                "position": substep.position,
                "title": substep.title,
                "requirements": substep.requirements,
                "learning_objectives": substep.learning_objectives,
                "status": "pending",
            }, on_conflict="chapter_id,position").execute()

    serialized_outline = [ch.model_dump() for ch in result.chapters]

    return {
        "syllabus_outline": serialized_outline,
        "chapter_cursor": 0,
        "substep_cursor": 0,
        "phase": "writing",
    }
```

### 7.7 `agent/nodes/chapter_guard.py` — Self-Awareness Before Writing

```python
from agent.state import SyllabusState, ActiveSubstep
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig


async def chapter_guard_node(state: SyllabusState, config: RunnableConfig) -> dict:
    """
    Self-awareness gate before the write/critique loop begins for each substep.
    
    Checks:
    1. Is this the end of all chapters? → signal done
    2. Has the current chapter advanced past all its substeps? → advance chapter cursor
    3. Does this substep already have a lesson in Supabase? → skip it
    4. Everything OK → load substep from Supabase and populate active_substep
    
    This is the node that makes the agent safe to restart at any point.
    """
    db = get_supabase()
    syllabus_id = state["syllabus_id"]
    outline = state["syllabus_outline"]
    chapter_cursor = state["chapter_cursor"]
    substep_cursor = state["substep_cursor"]

    # ── Check: all chapters done ──────────────────────────────────────────
    if chapter_cursor >= len(outline):
        return {"phase": "done"}

    current_chapter = outline[chapter_cursor]
    substeps = current_chapter["substeps"]

    # ── Check: all substeps in this chapter done ──────────────────────────
    if substep_cursor >= len(substeps):
        # Mark chapter as done in Supabase
        db.table("chapters").update({"status": "done"}).eq(
            "syllabus_id", syllabus_id
        ).eq("chapter_index", chapter_cursor).execute()

        return {
            "chapter_cursor": chapter_cursor + 1,
            "substep_cursor": 0,
            "active_substep": None,
        }

    current_substep_meta = substeps[substep_cursor]

    # ── Load the Supabase chapter and substep rows ─────────────────────────
    chapter_res = (
        db.table("chapters")
        .select("id")
        .eq("syllabus_id", syllabus_id)
        .eq("chapter_index", chapter_cursor)
        .single()
        .execute()
    )
    chapter_id = chapter_res.data["id"]

    substep_res = (
        db.table("substeps")
        .select("id, status")
        .eq("chapter_id", chapter_id)
        .eq("position", substep_cursor)
        .single()
        .execute()
    )
    substep_id = substep_res.data["id"]
    substep_status = substep_res.data["status"]

    # ── Check: lesson already exists for this substep (crash recovery) ────
    existing_lesson = (
        db.table("lessons")
        .select("id")
        .eq("substep_id", substep_id)
        .maybe_single()
        .execute()
    )

    if existing_lesson.data:
        # Lesson already written and accepted — skip to next
        completed_ids = state.get("completed_lesson_ids", [])
        completed_ids.append(existing_lesson.data["id"])
        return {
            "substep_cursor": substep_cursor + 1,
            "completed_lesson_ids": completed_ids,
            "active_substep": None,
        }

    # ── Mark substep as writing ───────────────────────────────────────────
    db.table("substeps").update({"status": "writing"}).eq("id", substep_id).execute()
    db.table("chapters").update({"status": "writing"}).eq("id", chapter_id).execute()

    # ── Populate active_substep ───────────────────────────────────────────
    active: ActiveSubstep = {
        "substep_id": substep_id,
        "chapter_id": chapter_id,
        "position": substep_cursor,
        "title": current_substep_meta["title"],
        "requirements": current_substep_meta["requirements"],
        "learning_objectives": current_substep_meta["learning_objectives"],
        "current_draft": "",
        "current_draft_blocks": [],
        "critique": "",
        "improvement_points": [],
        "draft_attempts": 0,
    }

    return {"active_substep": active}
```

### 7.8 `agent/nodes/lesson_writer.py`

```python
from langchain_anthropic import ChatAnthropic
from agent.state import SyllabusState, LessonContent
from langchain_core.runnables import RunnableConfig
import json

llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0.4)
writer_llm = llm.with_structured_output(LessonContent)

SYSTEM = """You are an expert educational content writer. You write clear, engaging, 
well-structured lessons for syllabuses.

Your output must be a complete lesson in BlockNote-compatible JSON format.

BlockNote block types you can use:
- paragraph: { type: "paragraph", content: [{type: "text", text: "...", styles: {}}], props: {} }
- heading: { type: "heading", content: [{type: "text", text: "...", styles: {}}], props: {level: 2} }
- bulletListItem: { type: "bulletListItem", content: [{type: "text", text: "...", styles: {}}], props: {} }
- numberedListItem: { type: "numberedListItem", content: [{type: "text", text: "...", styles: {}}], props: {} }
- codeBlock: { type: "codeBlock", content: [{type: "text", text: "...", styles: {}}], props: {language: "..."} }

For text styles object, valid keys are: bold, italic, underline, strikethrough, code (all boolean).

Writing rules:
- Start with a brief intro paragraph (no heading needed)
- Use headings to organize major sections
- Use bullet/numbered lists for steps, rules, examples
- Write at the appropriate level for the requirements
- Be thorough but focused — do not pad or digress
- Aim for 600-1200 words of actual content"""

async def lesson_writer_node(state: SyllabusState, config: RunnableConfig) -> dict:
    active = state["active_substep"]

    # Build the writer prompt
    # If this is a revision, include the critique
    revision_context = ""
    if active["draft_attempts"] > 0 and active["critique"]:
        revision_context = f"""

PREVIOUS CRITIQUE (attempt {active['draft_attempts']}):
{active['critique']}

SPECIFIC IMPROVEMENTS NEEDED:
{chr(10).join(f"- {p}" for p in active['improvement_points'])}

Rewrite the lesson addressing ALL of the above issues."""

    prompt = f"""LESSON TITLE: {active['title']}

REQUIREMENTS:
{active['requirements']}

LEARNING OBJECTIVES (all must be addressed):
{chr(10).join(f"- {obj}" for obj in active['learning_objectives'])}
{revision_context}

Write the complete lesson now."""

    result: LessonContent = await writer_llm.ainvoke([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt}
    ])

    # Serialize blocks to string for state (state must stay serializable)
    blocks_json = [block.model_dump() for block in result.blocks]

    updated_active = {
        **active,
        "current_draft": result.summary,  # summary for agent context (small)
        "current_draft_blocks": blocks_json,
        "draft_attempts": active["draft_attempts"] + 1,
    }

    return {"active_substep": updated_active}
```

### 7.9 `agent/nodes/critic.py`

```python
from langchain_anthropic import ChatAnthropic
from agent.state import SyllabusState, CritiqueResult
from langchain_core.runnables import RunnableConfig
import json

llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
critic_llm = llm.with_structured_output(CritiqueResult)

SYSTEM = """You are a strict curriculum quality reviewer. You evaluate lesson content 
against its requirements and learning objectives.

You pass a lesson ONLY if ALL of the following are true:
1. All learning objectives are addressed with sufficient depth
2. The lesson covers everything in the requirements — no major gaps
3. The content is accurate and appropriate for the target level
4. The lesson is well-structured and readable
5. The content is complete (not a stub or placeholder)

Be specific in your critique. If failing, list exactly what is missing or wrong.
If passing, confirm which requirements are met."""

async def critic_node(state: SyllabusState, config: RunnableConfig) -> dict:
    active = state["active_substep"]

    # Convert blocks back to readable text for the critic
    # (Critic doesn't need to understand JSON structure, just the content)
    def blocks_to_text(blocks: list) -> str:
        lines = []
        for block in blocks:
            content_parts = block.get("content", [])
            text = "".join(p.get("text", "") for p in content_parts)
            block_type = block.get("type", "paragraph")
            if block_type == "heading":
                level = block.get("props", {}).get("level", 2)
                lines.append(f"{'#' * level} {text}")
            elif block_type == "bulletListItem":
                lines.append(f"• {text}")
            elif block_type == "numberedListItem":
                lines.append(f"1. {text}")
            else:
                lines.append(text)
        return "\n".join(lines)

    lesson_text = blocks_to_text(active["current_draft_blocks"])

    prompt = f"""LESSON TITLE: {active['title']}

REQUIREMENTS:
{active['requirements']}

LEARNING OBJECTIVES:
{chr(10).join(f"- {obj}" for obj in active['learning_objectives'])}

LESSON CONTENT (attempt {active['draft_attempts']}):
{lesson_text}

Evaluate this lesson."""

    result: CritiqueResult = await critic_llm.ainvoke([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt}
    ])

    updated_active = {
        **active,
        "critique": result.critique,
        "improvement_points": result.improvement_points,
    }

    return {"active_substep": updated_active, "_critic_result": result.pass_lesson}
```

> **Note:** `_critic_result` is a temporary key used only for routing. The conditional edge reads it and it is not persisted across checkpoints (it is popped by the router).

### 7.10 `agent/nodes/accept_lesson.py`

```python
from agent.state import SyllabusState
from agent.db.supabase_client import get_supabase
from langchain_core.runnables import RunnableConfig


async def accept_lesson_node(state: SyllabusState, config: RunnableConfig) -> dict:
    """
    The critic approved this lesson (or max retries exceeded).
    
    1. Upsert lesson to Supabase (content lives here, not in state)
    2. Mark substep as done
    3. Clear active_substep from state
    4. Advance substep cursor
    """
    db = get_supabase()
    active = state["active_substep"]
    needs_review = active["draft_attempts"] >= 3 and not state.get("_critic_result", True)

    # Upsert lesson (substep_id is unique — safe to upsert on crash recovery)
    lesson_res = db.table("lessons").upsert({
        "substep_id": active["substep_id"],
        "chapter_id": active["chapter_id"],
        "syllabus_id": state["syllabus_id"],
        "title": active["title"],
        "content": active["current_draft_blocks"],  # BlockNote JSON goes HERE, not in state
        "summary": active["current_draft"],
        "draft_attempts": active["draft_attempts"],
        "needs_review": needs_review,
    }, on_conflict="substep_id").execute()

    lesson_id = lesson_res.data[0]["id"]

    # Mark substep done
    db.table("substeps").update({"status": "done"}).eq("id", active["substep_id"]).execute()

    completed_ids = state.get("completed_lesson_ids", []) + [lesson_id]

    return {
        "active_substep": None,                         # ← cleared from state
        "substep_cursor": state["substep_cursor"] + 1,
        "completed_lesson_ids": completed_ids,
    }
```

### 7.11 `agent/nodes/reject_lesson.py`

```python
from agent.state import SyllabusState
from langchain_core.runnables import RunnableConfig


async def reject_lesson_node(state: SyllabusState, config: RunnableConfig) -> dict:
    """
    Critic rejected the lesson. Just keep the critique in state and let
    the graph loop back to the writer. The writer will read the critique.
    No Supabase writes here — only the accepted version goes to DB.
    """
    # Nothing to write to DB. State already has the updated critique from critic_node.
    # The graph will route back to lesson_writer_node.
    return {}
```

---

## 8. Agent: Graph Definition (`agent/graph.py`)

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# OR for local dev without Postgres checkpointer:
from langgraph.checkpoint.memory import MemorySaver

from agent.state import SyllabusState
from agent.nodes.init_node import init_node
from agent.nodes.search_planner import search_planner_node
from agent.nodes.web_search import web_search_node
from agent.nodes.findings_summarizer import findings_summarizer_node
from agent.nodes.syllabus_outline import syllabus_outline_node
from agent.nodes.chapter_guard import chapter_guard_node
from agent.nodes.lesson_writer import lesson_writer_node
from agent.nodes.critic import critic_node
from agent.nodes.accept_lesson import accept_lesson_node
from agent.nodes.reject_lesson import reject_lesson_node


# ── Conditional edge functions ─────────────────────────────────────────────────

def route_after_init(state: SyllabusState) -> str:
    phase = state.get("phase", "searching")
    if phase == "done":
        return "done"
    if phase == "writing":
        return "chapter_guard"
    if phase == "outlining":
        return "syllabus_outline"
    if phase in ("searching", "summarizing"):
        if state.get("search_plan") and len(state["search_plan"]) > 0 and state.get("findings_summary"):
            return "syllabus_outline"
        if state.get("search_plan") and len(state["search_plan"]) > 0:
            return "search_router"
        return "search_planner"
    return "search_planner"

def route_search(state: SyllabusState) -> str:
    """After each search step or after search planner."""
    cursor = state.get("search_step_cursor", 0)
    plan = state.get("search_plan", [])
    if not plan:
        return "search_planner"
    if cursor < len(plan):
        return "web_search"
    return "findings_summarizer"

def route_after_chapter_guard(state: SyllabusState) -> str:
    phase = state.get("phase", "writing")
    if phase == "done":
        return "done_node"
    active = state.get("active_substep")
    if active is None:
        # Either advanced cursor (substep skipped or chapter done) → loop back to guard
        chapter_cursor = state.get("chapter_cursor", 0)
        outline = state.get("syllabus_outline", [])
        if chapter_cursor >= len(outline):
            return "done_node"
        return "chapter_guard"
    return "lesson_writer"

def route_after_critic(state: SyllabusState) -> str:
    active = state.get("active_substep", {})
    draft_attempts = active.get("draft_attempts", 0) if active else 0
    critic_passed = state.get("_critic_result", False)

    if critic_passed:
        return "accept_lesson"
    if draft_attempts >= 3:
        # Force-accept after 3 failed attempts
        return "accept_lesson"
    return "reject_lesson"


# ── Build graph ────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(SyllabusState)

    # Add nodes
    g.add_node("init", init_node)
    g.add_node("search_planner", search_planner_node)
    g.add_node("search_router", lambda state: {})  # passthrough routing node
    g.add_node("web_search", web_search_node)
    g.add_node("findings_summarizer", findings_summarizer_node)
    g.add_node("syllabus_outline", syllabus_outline_node)
    g.add_node("chapter_guard", chapter_guard_node)
    g.add_node("lesson_writer", lesson_writer_node)
    g.add_node("critic", critic_node)
    g.add_node("accept_lesson", accept_lesson_node)
    g.add_node("reject_lesson", reject_lesson_node)
    g.add_node("done_node", lambda state: {"phase": "done"})

    # Entry
    g.set_entry_point("init")

    # Edges from init
    g.add_conditional_edges("init", route_after_init, {
        "search_planner": "search_planner",
        "search_router": "search_router",
        "syllabus_outline": "syllabus_outline",
        "chapter_guard": "chapter_guard",
        "done": "done_node",
    })

    # Search planner → search router (to check if web search needed)
    g.add_edge("search_planner", "search_router")

    # Search router → web_search or summarizer
    g.add_conditional_edges("search_router", route_search, {
        "web_search": "web_search",
        "findings_summarizer": "findings_summarizer",
        "search_planner": "search_planner",
    })

    # After each web search step → back to search router (loop)
    g.add_edge("web_search", "search_router")

    # After summarizer → outline
    g.add_edge("findings_summarizer", "syllabus_outline")

    # After outline → chapter guard
    g.add_edge("syllabus_outline", "chapter_guard")

    # Chapter guard routing (self-aware: skip done, advance chapter, or write)
    g.add_conditional_edges("chapter_guard", route_after_chapter_guard, {
        "lesson_writer": "lesson_writer",
        "chapter_guard": "chapter_guard",  # loop when skipping substeps
        "done_node": "done_node",
    })

    # Write → Critic
    g.add_edge("lesson_writer", "critic")

    # Critic routing
    g.add_conditional_edges("critic", route_after_critic, {
        "accept_lesson": "accept_lesson",
        "reject_lesson": "reject_lesson",
    })

    # Accept → back to chapter guard (which will advance cursor and check next substep)
    g.add_edge("accept_lesson", "chapter_guard")

    # Reject → back to writer
    g.add_edge("reject_lesson", "lesson_writer")

    # Done
    g.add_edge("done_node", END)

    # Compile with memory checkpointer for local dev
    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


graph = build_graph()
```

---

## 9. LangGraph Configuration (`agent/langgraph.json`)

```json
{
  "dependencies": ["."],
  "graphs": {
    "syllabus_agent": "./graph.py:graph"
  },
  "env": ".env"
}
```

`agent/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
SERPER_API_KEY=...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

Run the dev server:
```bash
cd agent
pip install -r requirements.txt
langgraph dev
# Server running on http://localhost:2024
```

---

## 10. Frontend: Setup

### `frontend/.env.local`
```
NEXT_PUBLIC_LANGGRAPH_API_URL=http://localhost:2024
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

### `frontend/lib/types.ts`

```typescript
export interface Syllabus {
  id: string
  thread_id: string
  title: string | null
  user_requirements: string
  status: 'init' | 'searching' | 'outlining' | 'writing' | 'done'
  total_chapters: number
  created_at: string
}

export interface Chapter {
  id: string
  syllabus_id: string
  chapter_index: number
  title: string
  status: 'pending' | 'writing' | 'done'
}

export interface Substep {
  id: string
  chapter_id: string
  position: number
  title: string
  requirements: string
  learning_objectives: string[]
  status: 'pending' | 'writing' | 'done'
}

export interface Lesson {
  id: string
  substep_id: string
  chapter_id: string
  syllabus_id: string
  title: string
  content: BlockNoteBlock[]  // BlockNote JSON
  summary: string
  draft_attempts: number
  needs_review: boolean
  created_at: string
}

// Minimal BlockNote block type for rendering
export interface BlockNoteBlock {
  id?: string
  type: 'paragraph' | 'heading' | 'bulletListItem' | 'numberedListItem' | 'codeBlock'
  content: { type: 'text'; text: string; styles: Record<string, boolean> }[]
  props: Record<string, unknown>
  children?: BlockNoteBlock[]
}
```

### `frontend/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

// ── Realtime hook: subscribe to lessons for a syllabus ──────────────────────
import { useEffect, useState } from 'react'
import type { Lesson, Chapter } from './types'

export function useSyllabusRealtime(syllabusId: string | null) {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])

  // Initial load
  useEffect(() => {
    if (!syllabusId) return

    const loadInitial = async () => {
      const { data: ch } = await supabase
        .from('chapters')
        .select('*')
        .eq('syllabus_id', syllabusId)
        .order('chapter_index')

      const { data: ls } = await supabase
        .from('lessons')
        .select('*')
        .eq('syllabus_id', syllabusId)

      setChapters(ch || [])
      setLessons(ls || [])
    }

    loadInitial()
  }, [syllabusId])

  // Realtime subscriptions
  useEffect(() => {
    if (!syllabusId) return

    // Subscribe to new lessons (INSERT)
    const lessonsChannel = supabase
      .channel(`lessons:${syllabusId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'lessons',
          filter: `syllabus_id=eq.${syllabusId}`,
        },
        (payload) => {
          setLessons((prev) => [...prev, payload.new as Lesson])
        }
      )
      .subscribe()

    // Subscribe to chapter status updates (UPDATE)
    const chaptersChannel = supabase
      .channel(`chapters:${syllabusId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'chapters',
          filter: `syllabus_id=eq.${syllabusId}`,
        },
        (payload) => {
          if (payload.eventType === 'INSERT') {
            setChapters((prev) => [...prev, payload.new as Chapter].sort((a, b) => a.chapter_index - b.chapter_index))
          } else if (payload.eventType === 'UPDATE') {
            setChapters((prev) =>
              prev.map((ch) => (ch.id === payload.new.id ? (payload.new as Chapter) : ch))
            )
          }
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(lessonsChannel)
      supabase.removeChannel(chaptersChannel)
    }
  }, [syllabusId])

  return { chapters, lessons }
}
```

### `frontend/lib/langgraph.ts`

```typescript
import { Client } from '@langchain/langgraph-sdk'
import { useState, useCallback, useRef } from 'react'

const client = new Client({
  apiUrl: process.env.NEXT_PUBLIC_LANGGRAPH_API_URL!,
})

export { client }

export interface AgentEvent {
  node: string
  type: string
  data: unknown
}

export function useSyllabusAgent() {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [activeNode, setActiveNode] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const startAgent = useCallback(async (userRequirements: string) => {
    setIsRunning(true)
    setEvents([])

    // Create a new thread
    const thread = await client.threads.create()
    setThreadId(thread.thread_id)

    abortRef.current = new AbortController()

    try {
      // Stream the agent run
      const stream = client.runs.stream(
        thread.thread_id,
        'syllabus_agent',  // matches langgraph.json key
        {
          input: {
            user_requirements: userRequirements,
            thread_id: thread.thread_id,
            phase: 'init',
            recovery_mode: false,
            search_step_cursor: 0,
            chapter_cursor: 0,
            substep_cursor: 0,
            completed_lesson_ids: [],
            search_plan: [],
            syllabus_outline: [],
            findings_summary: '',
            active_substep: null,
          },
          streamMode: 'events',  // get node-level events
        }
      )

      for await (const event of stream) {
        if (abortRef.current?.signal.aborted) break

        if (event.event === 'on_chain_start') {
          setActiveNode(event.name)
        }

        if (event.event === 'on_chain_end' || event.event === 'on_chain_stream') {
          setEvents((prev) => [
            ...prev,
            { node: event.name, type: event.event, data: event.data },
          ])
        }
      }
    } finally {
      setIsRunning(false)
      setActiveNode(null)
    }

    return thread.thread_id
  }, [])

  const resumeAgent = useCallback(async (existingThreadId: string) => {
    setIsRunning(true)
    setThreadId(existingThreadId)
    abortRef.current = new AbortController()

    try {
      const stream = client.runs.stream(
        existingThreadId,
        'syllabus_agent',
        {
          input: null,  // LangGraph resumes from checkpoint automatically
          streamMode: 'events',
        }
      )

      for await (const event of stream) {
        if (abortRef.current?.signal.aborted) break
        if (event.event === 'on_chain_start') setActiveNode(event.name)
        if (event.event === 'on_chain_end') {
          setEvents((prev) => [...prev, { node: event.name, type: event.event, data: event.data }])
        }
      }
    } finally {
      setIsRunning(false)
      setActiveNode(null)
    }
  }, [])

  const stopAgent = useCallback(() => {
    abortRef.current?.abort()
    setIsRunning(false)
  }, [])

  return { startAgent, resumeAgent, stopAgent, events, activeNode, isRunning, threadId }
}
```

---

## 11. Frontend: Pages & Components

### `frontend/app/page.tsx` — Requirements Form

The landing page. Renders a form with:
- A large textarea for `user_requirements` (placeholder: "e.g. English A1 level for adult learners, CEFR aligned, 8 weeks, 2 hours/week")
- A submit button that calls `startAgent(userRequirements)` and then redirects to `/syllabus/[threadId]`
- No other UI on this page

```typescript
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSyllabusAgent } from '@/lib/langgraph'

export default function HomePage() {
  const [requirements, setRequirements] = useState('')
  const { startAgent, isRunning } = useSyllabusAgent()
  const router = useRouter()

  const handleSubmit = async () => {
    const threadId = await startAgent(requirements)
    router.push(`/syllabus/${threadId}`)
  }

  return (
    <main>
      <h1>Syllabus Generator</h1>
      <textarea
        value={requirements}
        onChange={(e) => setRequirements(e.target.value)}
        placeholder="Describe the syllabus you need..."
        rows={6}
      />
      <button onClick={handleSubmit} disabled={isRunning || !requirements.trim()}>
        {isRunning ? 'Starting...' : 'Generate Syllabus'}
      </button>
    </main>
  )
}
```

### `frontend/app/syllabus/[threadId]/page.tsx`

The main view. Orchestrates everything:

```typescript
'use client'
import { use, useEffect, useState } from 'react'
import { useSyllabusAgent } from '@/lib/langgraph'
import { useSyllabusRealtime } from '@/lib/supabase'
import { supabase } from '@/lib/supabase'
import AgentStatusPanel from '@/components/AgentStatusPanel'
import SyllabusRenderer from '@/components/SyllabusRenderer'
import type { Syllabus } from '@/lib/types'

export default function SyllabusPage({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = use(params)
  const [syllabus, setSyllabus] = useState<Syllabus | null>(null)
  const { resumeAgent, events, activeNode, isRunning } = useSyllabusAgent()
  const { chapters, lessons } = useSyllabusRealtime(syllabus?.id || null)

  useEffect(() => {
    // Load syllabus metadata
    const load = async () => {
      const { data } = await supabase
        .from('syllabuses')
        .select('*')
        .eq('thread_id', threadId)
        .maybeSingle()

      if (data) {
        setSyllabus(data)
        // If not done, resume the agent
        if (data.status !== 'done') {
          resumeAgent(threadId)
        }
      } else {
        // First visit — agent was started from the home page and is still initializing
        // Poll until the syllabus row appears (init_node creates it)
        const interval = setInterval(async () => {
          const { data: found } = await supabase
            .from('syllabuses')
            .select('*')
            .eq('thread_id', threadId)
            .maybeSingle()
          if (found) {
            setSyllabus(found)
            clearInterval(interval)
          }
        }, 1000)
        return () => clearInterval(interval)
      }
    }
    load()
  }, [threadId])

  // Subscribe to syllabus status changes
  useEffect(() => {
    if (!syllabus?.id) return
    const channel = supabase
      .channel(`syllabus-status:${syllabus.id}`)
      .on('postgres_changes', {
        event: 'UPDATE', schema: 'public', table: 'syllabuses',
        filter: `id=eq.${syllabus.id}`,
      }, (payload) => setSyllabus(payload.new as Syllabus))
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [syllabus?.id])

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', height: '100vh' }}>
      {/* Left panel: live agent status */}
      <AgentStatusPanel
        activeNode={activeNode}
        events={events}
        isRunning={isRunning}
        syllabusStatus={syllabus?.status || 'init'}
      />

      {/* Right panel: syllabus content as it appears */}
      <SyllabusRenderer
        syllabus={syllabus}
        chapters={chapters}
        lessons={lessons}
      />
    </div>
  )
}
```

### `frontend/components/AgentStatusPanel.tsx`

Shows what the agent is currently doing. Uses events from LangGraph SSE.

Implement as a scrollable left sidebar with:
- A top section: current phase badge (searching / outlining / writing) based on `syllabusStatus`
- An "Active Node" indicator: shows `activeNode` with a pulsing dot when `isRunning`
- A scrollable event log: shows the last 20 `events` entries, each showing `event.node` and a friendly label:
  - `search_planner` → "Planning research..."
  - `web_search` → "Searching web..."
  - `findings_summarizer` → "Summarizing findings..."
  - `syllabus_outline` → "Building outline..."
  - `chapter_guard` → "Checking chapter..."
  - `lesson_writer` → "Writing lesson..."
  - `critic` → "Reviewing lesson..."
  - `accept_lesson` → "✓ Lesson accepted"
  - `reject_lesson` → "↺ Revising lesson..."
  - `done_node` → "✓ Syllabus complete!"

### `frontend/components/SyllabusRenderer.tsx`

The main content area. Renders chapters and lessons as they arrive via Supabase Realtime.

```typescript
import type { Syllabus, Chapter, Lesson } from '@/lib/types'
import LessonBlock from './LessonBlock'

interface Props {
  syllabus: Syllabus | null
  chapters: Chapter[]
  lessons: Lesson[]
}

export default function SyllabusRenderer({ syllabus, chapters, lessons }: Props) {
  if (!syllabus) return <div>Loading...</div>

  return (
    <div style={{ overflowY: 'auto', padding: '2rem' }}>
      {syllabus.title && <h1>{syllabus.title}</h1>}
      <p style={{ color: 'gray' }}>{syllabus.user_requirements}</p>

      {chapters.map((chapter) => {
        const chapterLessons = lessons
          .filter((l) => l.chapter_id === chapter.id)
          .sort((a, b) => {
            // Sort by substep position — need substep data or sort by created_at
            return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          })

        return (
          <div key={chapter.id} style={{ marginBottom: '3rem' }}>
            <h2>
              Chapter {chapter.chapter_index + 1}: {chapter.title}
              {chapter.status === 'writing' && (
                <span style={{ marginLeft: 8, fontSize: 12, color: 'orange' }}>● Writing...</span>
              )}
            </h2>

            {chapterLessons.map((lesson) => (
              <LessonBlock key={lesson.id} lesson={lesson} />
            ))}

            {chapter.status === 'pending' && chapterLessons.length === 0 && (
              <div style={{ color: 'gray', fontStyle: 'italic' }}>Pending...</div>
            )}
          </div>
        )
      })}

      {syllabus.status === 'done' && (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'green' }}>
          ✓ Syllabus complete
        </div>
      )}
    </div>
  )
}
```

### `frontend/components/LessonBlock.tsx`

Renders a single lesson using BlockNote in read-only mode.

```typescript
'use client'
import { useEffect, useState } from 'react'
import type { Lesson } from '@/lib/types'

// BlockNote read-only rendering
// Install: @blocknote/react @blocknote/core @blocknote/mantine @mantine/core
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/mantine/style.css'

interface Props {
  lesson: Lesson
}

export default function LessonBlock({ lesson }: Props) {
  const editor = useCreateBlockNote({
    initialContent: lesson.content.length > 0 ? lesson.content : undefined,
  })

  // Update content if lesson content changes
  useEffect(() => {
    if (lesson.content && lesson.content.length > 0) {
      editor.replaceBlocks(editor.document, lesson.content as any)
    }
  }, [lesson.content])

  return (
    <div style={{ marginBottom: '2rem', border: '1px solid #eee', borderRadius: 8 }}>
      <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between' }}>
        <strong>{lesson.title}</strong>
        {lesson.needs_review && (
          <span style={{ color: 'orange', fontSize: 12 }}>⚠ Needs review</span>
        )}
      </div>
      <BlockNoteView editor={editor} editable={false} />
    </div>
  )
}
```

---

## 12. Implementation TODO (Ordered for the Coding Agent)

Execute these in order. Do not start a step until the previous one is tested.

### Phase A: Foundation

- [ ] **A1.** Create the repository structure as defined in Section 4
- [ ] **A2.** Set up the Supabase project. Run the full SQL from Section 5 in the Supabase SQL editor. Verify all tables exist and realtime is enabled.
- [ ] **A3.** Create `agent/requirements.txt` with all Python dependencies. Install them.
- [ ] **A4.** Create `agent/.env` with all environment variables.
- [ ] **A5.** Implement `agent/db/supabase_client.py`.
- [ ] **A6.** Implement `agent/state.py` with all Pydantic schemas and the `SyllabusState` TypedDict exactly as defined.
- [ ] **A7.** Create `agent/langgraph.json`.

### Phase B: Agent Nodes

- [ ] **B1.** Implement `agent/nodes/init_node.py`. Test it in isolation by calling it directly with a fresh state and verifying a syllabus row is created in Supabase.
- [ ] **B2.** Implement `agent/tools/serper.py` and `agent/tools/scraper.py`.
- [ ] **B3.** Implement `agent/nodes/search_planner.py`. Test with a sample requirement.
- [ ] **B4.** Implement `agent/nodes/web_search.py`. Test with a single step from a real plan.
- [ ] **B5.** Implement `agent/nodes/findings_summarizer.py`.
- [ ] **B6.** Implement `agent/nodes/syllabus_outline.py`. Verify it creates chapter and substep rows in Supabase on completion.
- [ ] **B7.** Implement `agent/nodes/chapter_guard.py`. This is the most critical node — test all paths: fresh substep, already-done substep (recovery), chapter complete, all chapters complete.
- [ ] **B8.** Implement `agent/nodes/lesson_writer.py`.
- [ ] **B9.** Implement `agent/nodes/critic.py`.
- [ ] **B10.** Implement `agent/nodes/accept_lesson.py`. Verify lesson is written to Supabase and active_substep is cleared.
- [ ] **B11.** Implement `agent/nodes/reject_lesson.py`.

### Phase C: Graph Assembly

- [ ] **C1.** Implement `agent/graph.py` with all nodes, edges, and conditional routing.
- [ ] **C2.** Run `langgraph dev` and verify the server starts without errors.
- [ ] **C3.** Run a full end-to-end test using the LangGraph Studio UI at `http://localhost:2024`. Input: "English A1 level for adult learners, CEFR aligned". Watch the full pipeline run. Verify: search steps appear in Supabase → chapters created → lessons inserted one by one.
- [ ] **C4.** Test recovery: interrupt the run mid-way (Ctrl+C). Restart `langgraph dev`. Resume the same thread. Verify the graph picks up exactly where it left off with no duplicate data.

### Phase D: Frontend

- [ ] **D1.** Create the Next.js project in `frontend/`. Install all dependencies.
- [ ] **D2.** Create `frontend/.env.local` with all environment variables.
- [ ] **D3.** Implement `frontend/lib/types.ts`.
- [ ] **D4.** Implement `frontend/lib/supabase.ts` including the `useSyllabusRealtime` hook.
- [ ] **D5.** Implement `frontend/lib/langgraph.ts` including the `useSyllabusAgent` hook.
- [ ] **D6.** Implement `frontend/app/page.tsx` (requirements form).
- [ ] **D7.** Implement `frontend/components/AgentStatusPanel.tsx`.
- [ ] **D8.** Implement `frontend/components/LessonBlock.tsx` with BlockNote read-only view.
- [ ] **D9.** Implement `frontend/components/SyllabusRenderer.tsx`.
- [ ] **D10.** Implement `frontend/app/syllabus/[threadId]/page.tsx`.
- [ ] **D11.** End-to-end test: open `localhost:3000`, submit requirements, watch status panel update via LangGraph SSE, watch lessons appear in the right panel via Supabase Realtime as the agent writes them.

---

## 13. Critical Edge Cases to Handle

Every one of these must be handled — do not skip them as "unlikely":

| Scenario | Where it's handled | What happens |
|---|---|---|
| Agent crashes mid-search step | `init_node` recovery | Reads `search_steps.status` from Supabase, sets cursor to first `pending` step |
| Agent crashes after outline but before any writing | `init_node` status=`outlining` | Sends to `syllabus_outline` which skips if state already has outline (reads from DB) |
| Agent crashes after chapter 2, lesson 3 | `init_node` + `chapter_guard` | Rebuilds cursors by scanning lessons table, skips all substeps that have lesson rows |
| Critic loops forever | `critic.py` + `route_after_critic` | After 3 failed attempts, `accept_lesson` runs with `needs_review=True` |
| Supabase upsert on duplicate lesson | `accept_lesson.py` | Uses `upsert` with `on_conflict="substep_id"` — safe to run twice |
| LangGraph SSE disconnects | `EventSource` / LangGraph SDK | SDK auto-retries; `resumeAgent` can be called manually from the UI |
| Syllabus outline node runs twice | `syllabus_outline_node` | Checks `state.syllabus_outline` — if non-empty, returns early. Upsert on DB. |
| Substep position collision | Supabase `unique(chapter_id, position)` | Upsert is safe, `chapter_id + position` is always unique |

---

## 14. BlockNote Content Format Reference

The agent's `LessonContent.blocks` must produce valid BlockNote JSON. Here is the exact format the writer must output for each block type:

```json
[
  {
    "type": "heading",
    "content": [{"type": "text", "text": "Introduction to Greetings", "styles": {}}],
    "props": {"level": 2}
  },
  {
    "type": "paragraph",
    "content": [{"type": "text", "text": "In this lesson we will learn...", "styles": {}}],
    "props": {}
  },
  {
    "type": "bulletListItem",
    "content": [{"type": "text", "text": "How to say hello formally", "styles": {}}],
    "props": {}
  },
  {
    "type": "bulletListItem",
    "content": [
      {"type": "text", "text": "The word ", "styles": {}},
      {"type": "text", "text": "bonjour", "styles": {"italic": true}},
      {"type": "text", "text": " means good morning", "styles": {}}
    ],
    "props": {}
  },
  {
    "type": "numberedListItem",
    "content": [{"type": "text", "text": "First, listen to the audio", "styles": {}}],
    "props": {}
  },
  {
    "type": "codeBlock",
    "content": [{"type": "text", "text": "print('Hello World')", "styles": {}}],
    "props": {"language": "python"}
  }
]
```

The `LessonContent` Pydantic schema and the writer system prompt must both enforce this format. The critic must also verify that the blocks are non-empty and that the content makes sense — not just that it's structured correctly.

---

## 15. What NOT to Do

- **Do not store lesson content in LangGraph state.** It belongs in Supabase only.
- **Do not use `getStateHistory` or loop over all past messages** to find chapter context. Use cursor integers and Supabase queries.
- **Do not give the writer the previous lessons** as context. The writer only receives the active substep's `title`, `requirements`, `learning_objectives`, and the latest `critique` (if any).
- **Do not run chapters in parallel.** Chapters may reference earlier content. Keep chapter writing sequential.
- **Do not run search steps in parallel** in the initial implementation. Get sequential working first, then optionally add `Send()` parallelism later.
- **Do not use the anon Supabase key in the agent.** Use `service_role` key server-side so row-level security doesn't block writes.
- **Do not let the critic see the full syllabus.** The critic only receives the single lesson, its requirements, and its learning objectives. Keeping context minimal keeps costs low and focus high.
