"""
E2B sandbox lifecycle helper.

Policy:
  1. Before creating anything, call `Sandbox.list()` and reuse any RUNNING
     sandbox whose template name is "desktop". The sandbox id is useless
     without E2B_API_KEY, so we happily commit it to the repo as a hint.
  2. If no running desktop sandbox exists, fall back to the id recorded in
     `.e2b_sandbox.json` and try to reconnect.
  3. Only if both fail do we create a new one.

File committed to repo: `.e2b_sandbox.json`
    { "sandbox_id": "...", "created_at": "2026-04-22T21:43:34Z",
      "template": "desktop" }

Usage:
    from scripts.e2b_sandbox import get_sandbox
    sbx = get_sandbox()          # reuse-first, create-last
    sbx.commands.run("pnpm test")

    python scripts/e2b_sandbox.py         # print active sandbox info
    python scripts/e2b_sandbox.py kill    # kill + clear state file
"""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from e2b import Sandbox
from e2b.exceptions import NotFoundException, SandboxException

TEMPLATE = "desktop"
STATE_FILE = Path(__file__).resolve().parent.parent / ".e2b_sandbox.json"
DEFAULT_TIMEOUT = 60 * 60  # 1 hour; bump per call if a job needs more


def _require_key() -> str:
    key = os.environ.get("E2B_API_KEY")
    if not key:
        raise RuntimeError("E2B_API_KEY not set")
    return key


def _load_state() -> dict | None:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _save_state(sandbox_id: str) -> None:
    STATE_FILE.write_text(json.dumps({
        "sandbox_id": sandbox_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "template": TEMPLATE,
    }, indent=2) + "\n")


def _find_running_desktop() -> str | None:
    """Ask the E2B API what is currently running under this account."""
    try:
        paginator = Sandbox.list()
        items = list(paginator.next_items())
        while getattr(paginator, "has_next", False):
            items.extend(paginator.next_items())
    except Exception:
        return None
    for info in items:
        if info.name == TEMPLATE and str(info.state).lower().endswith("running"):
            return info.sandbox_id
    return None


def get_sandbox(timeout: int = DEFAULT_TIMEOUT) -> Sandbox:
    _require_key()

    # 1. prefer anything already running on the account
    running_id = _find_running_desktop()
    if running_id:
        try:
            sbx = Sandbox.connect(running_id)
            sbx.set_timeout(timeout)
            _save_state(running_id)
            return sbx
        except (NotFoundException, SandboxException):
            pass

    # 2. try the id recorded in the repo
    state = _load_state()
    if state and state.get("sandbox_id"):
        try:
            sbx = Sandbox.connect(state["sandbox_id"])
            sbx.set_timeout(timeout)
            return sbx
        except (NotFoundException, SandboxException):
            pass

    # 3. cold start
    sbx = Sandbox.create(template=TEMPLATE, timeout=timeout)
    _save_state(sbx.sandbox_id)
    return sbx


def kill_persisted() -> None:
    state = _load_state()
    if state and state.get("sandbox_id"):
        try:
            Sandbox.connect(state["sandbox_id"]).kill()
        except Exception:
            pass
    STATE_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "kill":
        kill_persisted()
        print("killed + state cleared")
    else:
        sbx = get_sandbox()
        info = sbx.get_info()
        print(f"sandbox_id  = {sbx.sandbox_id}")
        print(f"template    = {info.name}")
        print(f"cpu / mem   = {info.cpu_count} / {info.memory_mb} MB")
        print(f"state       = {info.state}")
        print(f"started_at  = {info.started_at}")
        print(f"end_at      = {info.end_at}")
