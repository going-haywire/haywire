"""Runtime access to the component canons (docs/components/*/​*-canon.md).

Back-compat shim over the full-tree accessor in :mod:`.tree`. The canons are
just the ``components/<area>/<area>-canon.md`` files inside the baked docs tree
(packaged at ``haywire/docs/``, monorepo ``docs/`` fallback in a dev checkout).

Canon filenames are singular even though the area directory is plural
(nodes/node-canon.md), so we locate the file by glob, not by name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .tree import docs_root


def canons_dir() -> Path:
    """The ``components/`` directory holding the per-area canon files."""
    return docs_root() / "components"


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


# Component *kind* (the middle token of a registry key, e.g. ``node``) → the
# canon *area* directory under ``components/``. The two differ irregularly:
# ``type`` lives in ``datatypes/``, ``state`` in ``states/``.
_KIND_TO_AREA = {
    "node": "nodes",
    "type": "datatypes",
    "adapter": "adapters",
    "widget": "widgets",
    "skin": "skins",
    "setting": "settings",
    "theme": "themes",
    "panel": "panels",
    "editor": "editors",
    "state": "states",
}


def canon_uri(kind: str) -> str:
    """The ``farmhand://docs/...`` URI of the canon for a component *kind*.

    Falls back to a plausible ``components/{kind}s/{kind}-canon.md`` shape for
    kinds without an explicit mapping so scaffolded references are never blank.
    """
    area = _KIND_TO_AREA.get(kind)
    if area is not None:
        path = _canon_file(canons_dir(), area)
        if path is not None:
            return f"farmhand://docs/{path.relative_to(docs_root()).as_posix()}"
    return f"farmhand://docs/components/{kind}s/{kind}-canon.md"
