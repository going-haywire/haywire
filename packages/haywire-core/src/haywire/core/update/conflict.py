"""Pre-write conflict check for a proposed framework pin.

Runs against the REAL workspace, never a temp-dir copy: a copy resolves
differently, because ``[tool.uv.sources]`` carries ``{workspace = true}`` and,
under ``--dev``, absolute dev-repo paths. So: write-resolve-restore — hold the
original text in memory, write the proposed pin, resolve, restore in a
``finally``.

What the check is worth: it reliably BLOCKS a bad pin — an unsatisfiable
resolution (a barn library whose floor excludes the new core) is deterministic
and knowable now. It does NOT bless a good one: resolution is not installation,
and the real sync happens later inside ``uv run`` (downloads, sdist builds, a
possibly-moved index). Hence "No conflicts found", never "your next launch will
succeed".
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from haywire.core.update.pin import rewrite_pins


@dataclass(frozen=True)
class ConflictResult:
    """Whether the proposed pin resolves, and what it would change.

    ``changes`` holds only the lines the pin ADDED relative to the baseline
    run — the raw output is noisy with pre-existing venv drift (a real run
    reported "Would uninstall 33 packages" that had nothing to do with the
    pin), and showing that unfiltered would alarm the user with removals we
    did not cause.
    """

    ok: bool
    message: str
    changes: list[str] = field(default_factory=list)


def _uv_sync_dry_run(cwd: Path) -> tuple[bool, str]:
    """``uv sync --dry-run`` in *cwd*. Returns (ok, merged output)."""
    proc = subprocess.run(
        ["uv", "sync", "--dry-run"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def diff_resolutions(baseline: str, proposed: str) -> list[str]:
    """Lines in *proposed* that the *baseline* run did not also produce."""
    seen = {line.strip() for line in baseline.splitlines() if line.strip()}
    out: list[str] = []
    for line in proposed.splitlines():
        stripped = line.strip()
        if stripped and stripped not in seen:
            out.append(stripped)
    return out


def check_pin_conflict(project_root: Path, version: str) -> ConflictResult:
    """Resolve the proposed pin against the real workspace, then restore it."""
    pyproject = project_root / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")

    _, baseline_output = _uv_sync_dry_run(project_root)

    try:
        pyproject.write_text(rewrite_pins(pyproject, version), encoding="utf-8")
        ok, proposed_output = _uv_sync_dry_run(project_root)
    finally:
        pyproject.write_text(original, encoding="utf-8")

    if not ok:
        return ConflictResult(ok=False, message=proposed_output.strip())
    return ConflictResult(
        ok=True,
        message="No conflicts found.",
        changes=diff_resolutions(baseline_output, proposed_output),
    )
