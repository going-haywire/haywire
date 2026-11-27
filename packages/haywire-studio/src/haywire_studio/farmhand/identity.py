"""Studio sidecar identity file: <workspace>/.haywire/studio.json.

Written when the studio mounts the Farmhand MCP endpoint so a later process
(the Farmhand bridge, ``haywire_studio.farmhand.bridge``) can identify WHICH project owns
the studio on a given port — reuse it, ask the user, or clean up a stale one.

Like everything in a project's .haywire/, it is local and never committed
(ADR 0096). The recycled-pid guard is best-effort:
os.kill(pid, 0) proves liveness; a matching create_time (via psutil, when
obtainable) proves it is the same process, but its absence never blocks.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path

import psutil

from haywire.core.storage import HAYWIRE_DIR, ensure_haywire_dir

logger = logging.getLogger(__name__)


IDENTITY_FILENAME = "studio.json"


def write_identity(workspace_root: Path | str, port: int, *, auth_required: bool = False) -> dict:
    """Write the current process's studio identity to <workspace>/.haywire/studio.json.

    ``auth_required`` mirrors the security document's ``auth.enabled`` at the
    moment the studio mounted Farmhand, so a later process (the
    Farmhand bridge) can tell whether this studio
    expects a credential without opening a connection first.

    Returns the dict written.
    """
    root = Path(workspace_root).resolve()
    haywire_dir = ensure_haywire_dir(root / HAYWIRE_DIR)

    ident = {
        "pid": os.getpid(),
        "port": port,
        "project": root.name,
        "project_path": str(root),
        # The process's own start, which identity_status compares: the studio mounts Farmhand seconds later.
        "started_at": psutil.Process(os.getpid()).create_time(),
        "host": socket.gethostname(),
        "role": "haywire-studio",
        "url": f"http://127.0.0.1:{port}",
        "auth_required": auth_required,
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
    different process), or 'alive' (pid live; same process or unverifiable).
    """
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
        # Lookup failed: it cannot disprove liveness.
        logger.debug("psutil lookup of pid %s failed", pid, exc_info=True)
    return "alive"
