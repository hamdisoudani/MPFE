"""
Single helper for E2B sandbox lifecycle.

Usage:
    from scripts.e2b_sandbox import get_sandbox
    sbx = get_sandbox()          # reconnects to persisted id, or creates one
    sbx.commands.run("pnpm test")

Persists the active sandbox id at .e2b_sandbox_id (gitignored) so repeat
runs reuse the same VM instead of cold-starting.

Template: "desktop" (8 CPU, 8 GB RAM).
"""
from __future__ import annotations
import os
from pathlib import Path
from e2b import Sandbox
from e2b.exceptions import NotFoundException, SandboxException

TEMPLATE = "desktop"
STATE_FILE = Path(__file__).resolve().parent.parent / ".e2b_sandbox_id"
DEFAULT_TIMEOUT = 60 * 60  # 1h


def _api_key() -> str:
    key = os.environ.get("E2B_API_KEY")
    if not key:
        raise RuntimeError("E2B_API_KEY not set in env")
    return key


def _load_id() -> str | None:
    if STATE_FILE.exists():
        sid = STATE_FILE.read_text().strip()
        return sid or None
    return None


def _save_id(sid: str) -> None:
    STATE_FILE.write_text(sid + "\n")


def get_sandbox(timeout: int = DEFAULT_TIMEOUT) -> Sandbox:
    _api_key()
    sid = _load_id()
    if sid:
        try:
            sbx = Sandbox.connect(sid)
            sbx.set_timeout(timeout)
            return sbx
        except (NotFoundException, SandboxException):
            pass  # stale id, fall through and create new
    sbx = Sandbox.create(template=TEMPLATE, timeout=timeout)
    _save_id(sbx.sandbox_id)
    return sbx


def kill_persisted() -> None:
    sid = _load_id()
    if not sid:
        return
    try:
        Sandbox.connect(sid).kill()
    except Exception:
        pass
    STATE_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "kill":
        kill_persisted()
        print("killed")
    else:
        sbx = get_sandbox()
        info = sbx.get_info()
        print(f"sandbox_id={sbx.sandbox_id} cpu={info.cpu_count} mem_mb={info.memory_mb} state={info.state}")
