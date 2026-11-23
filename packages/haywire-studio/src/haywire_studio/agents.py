"""The adapters a Haywire project commits, so every supported agent harness connects to it.

An adapter is a harness's own small config file that points it at the project's own Haywire:
the Farmhand bridge (``haywire farmhand bridge``), started from the project's environment.
Every supported harness gets its adapter, whoever created the project, so the project works
the same for everyone who opens it. :data:`HARNESSES` is the one list; supporting another
harness means adding its writer there.

Writers merge into files that already exist and keep everything else in them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

#: The command every adapter starts the bridge with, from the project's own environment.
BRIDGE_COMMAND = ["uv", "run", "--frozen", "--quiet", "haywire", "farmhand", "bridge"]
SERVER = "farmhand"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _claude(project: Path) -> list[Path]:
    """Claude Code: the bridge in ``.mcp.json``, allowed and switched on in ``.claude/settings.json``."""
    mcp = project / ".mcp.json"
    config = _read_json(mcp)
    command, *args = BRIDGE_COMMAND
    config.setdefault("mcpServers", {})[SERVER] = {"command": command, "args": args}
    _write_json(mcp, config)

    settings_path = project / ".claude" / "settings.json"
    settings = _read_json(settings_path)
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    if f"mcp__{SERVER}" not in allow:
        allow.append(f"mcp__{SERVER}")
    enabled = settings.setdefault("enabledMcpjsonServers", [])
    if SERVER not in enabled:
        enabled.append(SERVER)
    _write_json(settings_path, settings)
    return [mcp, settings_path]


#: Every supported harness and the writer of its adapter.
HARNESSES: dict[str, Callable[[Path], list[Path]]] = {"Claude Code": _claude}


def write_adapters(project: Path) -> list[Path]:
    """Write or refresh every supported harness's adapter in ``project``; return the files written."""
    written: list[Path] = []
    for writer in HARNESSES.values():
        written += writer(project)
    return written
