"""A project's heaps: the libraries on local disk the marketplace shows as ``local``.

Heaps are derived from the project's ``pyproject.toml`` on every read: each
``[tool.uv.workspace]`` member and each ``[tool.uv.sources]`` entry with a
``path`` that holds a library (a package with a ``haybale.toml``), plus the
libraries beside such a path source (the rest of a dev repo's ``barn/``). A
``[[heaps]]`` entry in ``.haywire/marketplace.toml`` is a hand-written
override: it adds a library found nowhere in ``pyproject.toml``, or replaces
the derived heap of the same name. See ADR 0096.
"""

from __future__ import annotations

import logging
from pathlib import Path

import toml

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.haybale_toml import HAYBALE_TOML, read_haybale_toml_lenient

logger = logging.getLogger(__name__)


def derive_heaps(project_root: Path) -> list[dict]:
    """Return a heap entry for each library ``pyproject.toml`` names by path.

    Each entry holds ``name`` (the distribution name), ``path`` (absolute, in
    this checkout), and, where the library's ``haybale.toml`` declares them,
    ``label``, ``description`` and ``linked_libraries`` (as distribution
    names). Workspace members come first, sorted, then path sources in file
    order, then the folders beside a path source that holds a library, sorted;
    a library named twice appears once.

    Returns an empty list when ``pyproject.toml`` is missing or unreadable.
    """
    try:
        pyproject = toml.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, toml.TomlDecodeError):
        return []
    uv = pyproject.get("tool", {}).get("uv", {})

    candidates: list[Path] = []
    workspace = uv.get("workspace", {})
    excluded = {p.resolve() for pattern in workspace.get("exclude", []) for p in project_root.glob(pattern)}
    for pattern in workspace.get("members", []):
        candidates += sorted(p for p in project_root.glob(pattern) if p.resolve() not in excluded)
    sources = [
        project_root / s["path"]
        for s in uv.get("sources", {}).values()
        if isinstance(s, dict) and isinstance(s.get("path"), str)
    ]
    candidates += sources
    for folder in dict.fromkeys(s.resolve().parent for s in sources if _heap_entry(s.resolve()) is not None):
        candidates += sorted(p for p in folder.iterdir() if p.is_dir())

    heaps: list[dict] = []
    seen: set[str] = set()
    for lib_dir in candidates:
        entry = _heap_entry(lib_dir.resolve())
        if entry is not None and entry["name"].lower() not in seen:
            seen.add(entry["name"].lower())
            heaps.append(entry)
    return heaps


def layer_heaps(derived: list[dict], written: list[dict]) -> list[dict]:
    """Return *derived* heaps with the hand-written *written* ones layered on top.

    A written entry replaces the derived heap of the same name, compared
    case-insensitively; the rest of *written* follows the derived heaps.
    """
    overrides = {str(h.get("name", "")).lower() for h in written}
    return [h for h in derived if str(h.get("name", "")).lower() not in overrides] + list(written)


def _heap_entry(lib_dir: Path) -> dict | None:
    """The heap entry for the library in *lib_dir*, or ``None`` when it holds no library."""
    module_dir = find_module_dir(lib_dir) if lib_dir.is_dir() else None
    if module_dir is None or not (module_dir / HAYBALE_TOML).is_file():
        return None
    try:
        project = toml.loads((lib_dir / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
    except (OSError, toml.TomlDecodeError) as exc:
        logger.warning(f"Skipping heap {lib_dir}: unreadable pyproject.toml ({exc})")
        return None
    name = project.get("name")
    if not isinstance(name, str) or not name:
        return None

    declared = read_haybale_toml_lenient(module_dir)
    entry: dict[str, object] = {"name": name, "path": str(lib_dir)}
    for key in ("label", "description"):
        if isinstance(declared.get(key), str) and declared[key]:
            entry[key] = declared[key]
    linked = declared.get("linked_libraries") or []
    if linked:
        # The install gate matches distribution names; haybale.toml declares module names.
        entry["linked_libraries"] = [str(m).replace("_", "-") for m in linked]
    return entry
