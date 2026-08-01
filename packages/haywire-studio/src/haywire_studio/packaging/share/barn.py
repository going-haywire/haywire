"""Repo-shape queries about ``barn/``.

The bottom layer of the share package: no imports from anywhere else in
``haywire_studio``, so every other share module can depend on it freely.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def current_ref(repo_root: Path) -> str | None:
    """The branch name HEAD points at, or ``None`` when HEAD is detached.

    Uses ``git symbolic-ref -q HEAD`` — not ``git rev-parse --abbrev-ref
    HEAD`` — as the detached-HEAD test. The latter prints the literal string
    ``"HEAD"`` in TWO situations that must not be conflated: genuine detached
    HEAD, and an unborn branch (a fresh repo before its first commit), where
    HEAD still symbolically points at a real branch name (e.g.
    ``refs/heads/main``) that simply has no commit yet. ``symbolic-ref``
    tells these apart: it fails only in the genuinely-detached case and
    succeeds (printing ``refs/heads/<name>``) for an unborn branch. This
    function never returns the literal string ``"HEAD"`` — not as a guess,
    not for either edge case.

    Returns ``None`` on any git failure (not a repo, git missing, timeout) as
    well as on genuine detachment — callers cannot tell those apart from the
    return value alone, matching this module's other "best-effort query"
    functions.
    """
    try:
        proc = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    ref = proc.stdout.strip()
    return ref.removeprefix("refs/heads/") if ref else None


def barn_library_dirs(repo_root: Path) -> list[Path]:
    """Every ``barn/*`` directory holding a ``pyproject.toml``, sorted by path.

    Symlinked entries are excluded. A symlink under ``barn/`` (e.g. a
    gitignored local-only dev library) is never committed`.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        return []
    return sorted(
        d for d in barn.iterdir() if d.is_dir() and not d.is_symlink() and (d / "pyproject.toml").is_file()
    )
