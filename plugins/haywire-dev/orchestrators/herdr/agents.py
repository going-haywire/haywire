#!/usr/bin/env python3
"""herdr's slot for the task view (ADR 0090): print herdr's live agent sessions as JSON.

Prints ``{"agents": [{"cwd": ..., "address": ..., "status": ...}]}`` from ``hc ls --json``:
the live terminals that run an agent, not a plain shell. ``tasks.py`` runs it with the
Python that runs ``tasks.py``. Without ``hc``, or when ``hc`` fails, prints nothing and
exits 1. Standard library only.
"""

from __future__ import annotations

import json
import subprocess
import sys

SHELLS = frozenset({"zsh", "bash", "fish", "sh"})


def main() -> int:
    try:
        proc = subprocess.run(["hc", "ls", "--json"], capture_output=True, text=True, check=True, timeout=30)
        terminals = json.loads(proc.stdout).get("terminals", [])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, AttributeError):
        return 1
    found = [
        {"cwd": t["cwd"], "address": t.get("address", ""), "status": t.get("status", "")}
        for t in terminals
        if t.get("state") == "live" and t.get("agent") not in SHELLS and t.get("cwd")
    ]
    print(json.dumps({"agents": found}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
