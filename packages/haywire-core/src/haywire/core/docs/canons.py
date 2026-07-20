"""Runtime access to the component canons (docs/components/*/​*-canon.md).

In a built wheel the canons are force-included at haywire/docs/canons/
(see pyproject.toml). In a dev/editable checkout that directory does not
exist, so we fall back to the monorepo's docs/components/ found by walking
up from this file. Farmhand serves these as version-matched authoring
resources (farmhand://docs/canon/{area}).

Canon filenames are singular even though the area directory is plural
(nodes/node-canon.md), so we locate the file by glob, not by name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import haywire


def canons_dir() -> Path:
    packaged = Path(haywire.__file__).resolve().parent / "docs" / "canons"
    if packaged.is_dir():
        return packaged
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "components"
        if _canon_file(candidate, "nodes") is not None:
            return candidate
    raise FileNotFoundError(
        "Component canons not found: neither the packaged haywire/docs/canons "
        "nor a monorepo docs/components directory exists."
    )


def list_canon_areas() -> list[str]:
    root = canons_dir()
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and _canon_file(root, child.name) is not None
    )


def read_canon(area: str) -> str:
    path = _canon_file(canons_dir(), area)
    if path is None:
        raise FileNotFoundError(f"No canon for area '{area}'. Valid areas: {', '.join(list_canon_areas())}")
    return path.read_text(encoding="utf-8")


def _canon_file(root: Path, area: str) -> Optional[Path]:
    """Return the single ``*-canon.md`` inside ``root/area``, or None."""
    return next(iter(sorted((root / area).glob("*-canon.md"))), None)
