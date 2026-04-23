# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Build-time args (Railway injects these as --build-arg from service vars) ----
# LLM endpoints (three OpenAI-compatible providers)
ARG LLM_SMALL_BASE_URL
ARG LLM_SMALL_API_KEY
ARG LLM_SMALL_MODEL
ARG LLM_WRITER_BASE_URL
ARG LLM_WRITER_API_KEY
ARG LLM_WRITER_MODEL
ARG LLM_CRITIC_BASE_URL
ARG LLM_CRITIC_API_KEY
ARG LLM_CRITIC_MODEL

# Web search
ARG SERPER_API_KEY

# Supabase / Postgres (LangGraph checkpointer)
ARG SUPABASE_URL
ARG SUPABASE_SERVICE_ROLE_KEY
ARG SUPABASE_DB_URL

# Tracing (optional)
ARG AGENT_TRACE
ARG AGENT_TRACE_FILE
ARG AGENT_TRACE_STDOUT

# LangSmith (optional)
ARG LANGSMITH_API_KEY
ARG LANGSMITH_PROJECT
ARG LANGSMITH_TRACING

# ---- Promote build args to runtime ENV so the app sees them at both build & run ----
ENV LLM_SMALL_BASE_URL=${LLM_SMALL_BASE_URL} \
    LLM_SMALL_API_KEY=${LLM_SMALL_API_KEY} \
    LLM_SMALL_MODEL=${LLM_SMALL_MODEL} \
    LLM_WRITER_BASE_URL=${LLM_WRITER_BASE_URL} \
    LLM_WRITER_API_KEY=${LLM_WRITER_API_KEY} \
    LLM_WRITER_MODEL=${LLM_WRITER_MODEL} \
    LLM_CRITIC_BASE_URL=${LLM_CRITIC_BASE_URL} \
    LLM_CRITIC_API_KEY=${LLM_CRITIC_API_KEY} \
    LLM_CRITIC_MODEL=${LLM_CRITIC_MODEL} \
    SERPER_API_KEY=${SERPER_API_KEY} \
    SUPABASE_URL=${SUPABASE_URL} \
    SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY} \
    SUPABASE_DB_URL=${SUPABASE_DB_URL} \
    AGENT_TRACE=${AGENT_TRACE} \
    AGENT_TRACE_FILE=${AGENT_TRACE_FILE} \
    AGENT_TRACE_STDOUT=${AGENT_TRACE_STDOUT} \
    LANGSMITH_API_KEY=${LANGSMITH_API_KEY} \
    LANGSMITH_PROJECT=${LANGSMITH_PROJECT} \
    LANGSMITH_TRACING=${LANGSMITH_TRACING}

# ---- Install dependencies (layer-cached) ----
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install "langgraph-cli[inmem]>=0.2.0" && \
    pip install \
        "langgraph>=0.6.0" \
        "langchain-core>=0.3.0" \
        "langchain-openai>=0.2.0" \
        "langgraph-checkpoint-postgres>=2.0.0" \
        "psycopg[binary,pool]>=3.2" \
        "supabase>=2.9.0" \
        "pydantic>=2.9" \
        "python-dotenv>=1.0.1" \
        "httpx>=0.27"

# ---- Copy source & install package ----
COPY . .
RUN pip install -e .

# Railway sets $PORT dynamically
ENV PORT=8000
EXPOSE 8000

# Launch LangGraph API server serving the `syllabus` graph from langgraph.json
CMD ["sh", "-c", "langgraph dev --host 0.0.0.0 --port ${PORT:-8000} --no-browser"]
