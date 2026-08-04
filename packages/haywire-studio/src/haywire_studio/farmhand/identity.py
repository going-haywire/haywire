"""Studio sidecar identity file: <workspace>/.haywire/studio.json.

Written when the studio mounts the Farmhand MCP endpoint so a later process
(the farmhand4claude plugin's startup script) can identify WHICH project owns
the studio on a given port — reuse it, ask the user, or clean up a stale one.

Sits beside farmhand_token (see auth.py) and follows the same .haywire/ +
.gitignore discipline. The recycled-pid guard is best-effort: os.kill(pid, 0)
proves liveness; a matching create_time (via psutil, when obtainable) proves
it is the same process, but its absence never blocks.
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

IDENTITY_FILENAME = "studio.json"


def _ensure_gitignored(haywire_dir: Path) -> None:
    gitignore = haywire_dir / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if IDENTITY_FILENAME not in existing:
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{IDENTITY_FILENAME}\n")


def write_identity(workspace_root: Path | str, port: int) -> dict:
    """Write the current process's studio identity to <workspace>/.haywire/studio.json.

    Returns the dict written. Ensures the sidecar is gitignored.
    """
    root = Path(workspace_root).resolve()
    haywire_dir = root / ".haywire"
    haywire_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignored(haywire_dir)

    ident = {
        "pid": os.getpid(),
        "port": port,
        "project": root.name,
        "project_path": str(root),
        "started_at": time.time(),
        "host": socket.gethostname(),
        "role": "haywire-studio",
        "url": f"http://127.0.0.1:{port}",
    }
    (haywire_dir / IDENTITY_FILENAME).write_text(json.dumps(ident, indent=2), encoding="utf-8")
    return ident


def read_identity(workspace_root: Path | str) -> dict | None:
    """Return the parsed sidecar, or None if absent or unparseable."""
    sidecar = Path(workspace_root) / ".haywire" / IDENTITY_FILENAME
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def identity_status(ident: dict) -> str:
    """Best-effort: 'dead' (pid gone), 'recycled' (pid alive but a provably
    different process), or 'alive' (pid live; same process or unverifiable)."""
    pid = ident.get("pid")
    if not isinstance(pid, int) or not _pid_alive(pid):
        return "dead"
    recorded = ident.get("started_at")
    try:
        import psutil

        actual = psutil.Process(pid).create_time()
        if isinstance(recorded, (int, float)) and abs(actual - recorded) > 2.0:
            return "recycled"
    except Exception:
        pass  # lookup failed — cannot disprove liveness
    return "alive"
