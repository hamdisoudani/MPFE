"""Runtime tracer — logs every LLM call, Supabase query, and Serper request.
Opt-in via AGENT_TRACE=1. Writes JSONL to AGENT_TRACE_FILE (default agent_trace.jsonl)."""
from __future__ import annotations
import os, json, time, functools, threading
from typing import Any

_LOCK = threading.Lock()
_PATH = os.environ.get("AGENT_TRACE_FILE", "agent_trace.jsonl")
_T0 = time.time()
_SEQ = 0


def _emit(event: dict):
    global _SEQ
    with _LOCK:
        _SEQ += 1
        event = {"seq": _SEQ, "t": round(time.time() - _T0, 3), **event}
        with open(_PATH, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")
        if os.environ.get("AGENT_TRACE_STDOUT"):
            print(f"[trace #{_SEQ:03d} t={event['t']:6.2f}s] "
                  f"{event.get('kind'):12s} {event.get('summary','')}", flush=True)


def _summarize(obj: Any, limit: int = 180) -> str:
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        s = str(obj)
    return s if len(s) <= limit else s[:limit] + f"…(+{len(s)-limit}B)"


def install():
    if not os.environ.get("AGENT_TRACE"):
        return
    if os.path.exists(_PATH):
        try: os.remove(_PATH)
        except OSError: pass
    _wrap_llm()
    _wrap_supabase()
    _wrap_httpx()
    _emit({"kind": "tracer_on", "summary": f"file={_PATH}"})


def _wrap_llm():
    try:
        from langchain_openai import ChatOpenAI
    except Exception: return
    orig_inv = ChatOpenAI.invoke
    orig_ainv = ChatOpenAI.ainvoke

    def _prompt_text(prompt):
        if isinstance(prompt, str): return prompt
        try:
            return "\n".join(getattr(m, "content", "") or "" for m in prompt)
        except Exception: return str(prompt)

    @functools.wraps(orig_inv)
    def inv(self, prompt, *a, **kw):
        pt = _prompt_text(prompt); t0 = time.time()
        _emit({"kind": "llm_request", "model": self.model_name, "base_url": str(self.openai_api_base),
               "prompt_chars": len(pt), "prompt_head": pt[:400], "structured": bool(getattr(self, "_structured", False))})
        try:
            out = orig_inv(self, prompt, *a, **kw)
        except Exception as e:
            _emit({"kind": "llm_error", "model": self.model_name, "error": str(e)[:300]}); raise
        dt = round(time.time()-t0, 3)
        content = getattr(out, "content", None)
        out_chars = len(content) if isinstance(content, str) else len(json.dumps(out, default=str))
        _emit({"kind": "llm_response", "model": self.model_name, "elapsed_s": dt,
               "out_chars": out_chars, "out_head": _summarize(content if content else out, 300)})
        return out

    @functools.wraps(orig_ainv)
    async def ainv(self, prompt, *a, **kw):
        pt = _prompt_text(prompt); t0 = time.time()
        _emit({"kind": "llm_request", "model": self.model_name, "async": True,
               "prompt_chars": len(pt), "prompt_head": pt[:400]})
        try:
            out = await orig_ainv(self, prompt, *a, **kw)
        except Exception as e:
            _emit({"kind": "llm_error", "model": self.model_name, "error": str(e)[:300]}); raise
        dt = round(time.time()-t0, 3)
        content = getattr(out, "content", None)
        _emit({"kind": "llm_response", "model": self.model_name, "elapsed_s": dt, "async": True,
               "out_head": _summarize(content if content else out, 300)})
        return out

    ChatOpenAI.invoke = inv
    ChatOpenAI.ainvoke = ainv


def _wrap_supabase():
    try:
        from postgrest._sync.request_builder import SyncQueryRequestBuilder, SyncSingleRequestBuilder
    except Exception: return
    for klass in (SyncQueryRequestBuilder, SyncSingleRequestBuilder):
        orig = klass.execute
        @functools.wraps(orig)
        def ex(self, *a, _orig=orig, **kw):
            method = getattr(self, "http_method", "?")
            path = str(getattr(self, "path", "")) or str(getattr(self, "url", ""))
            t0 = time.time()
            try:
                out = _orig(self, *a, **kw)
            except Exception as e:
                _emit({"kind":"db_error", "method":method, "path":path, "error":str(e)[:200]}); raise
            dt = round(time.time()-t0, 3)
            data = getattr(out, "data", None)
            count = len(data) if isinstance(data, list) else (1 if data else 0)
            _emit({"kind":"db_call", "method":method, "path":path, "rows":count, "elapsed_s":dt,
                   "sample": _summarize(data if isinstance(data, dict) else (data[0] if data else None), 200)})
            return out
        klass.execute = ex


def _wrap_httpx():
    """Catch Serper (google.serper.dev) + any other HTTP from nodes."""
    try:
        import httpx
    except Exception: return
    orig_post = httpx.post
    orig_client_post = httpx.Client.post

    def _log(url, json_body, t0, resp, err=None):
        _emit({"kind":"http", "url": str(url), "elapsed_s": round(time.time()-t0,3),
               "status": getattr(resp, "status_code", None), "error": err,
               "req_body": _summarize(json_body, 200),
               "resp_head": _summarize(getattr(resp, "text", "")[:300] if resp else "", 300)})

    @functools.wraps(orig_post)
    def p(url, *a, **kw):
        t0 = time.time()
        try:
            r = orig_post(url, *a, **kw)
        except Exception as e:
            _log(url, kw.get("json"), t0, None, str(e)); raise
        _log(url, kw.get("json"), t0, r); return r
    httpx.post = p
