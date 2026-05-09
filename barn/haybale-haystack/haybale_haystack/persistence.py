"""Persistence — free functions for per-haystack TOML I/O.

These functions move the file-I/O logic out of HaystackState (an AppState)
into pure helpers. HaystackState holds the in-memory registry; persistence.py
serializes/deserializes named haystacks to/from ``<workspace>/haystacks/*.toml``.

Each TOML file represents one named haystack — a list of per-graph entries the
user wants restored together, plus optional metadata for the active graph.

TOML schema (compatible with haywire-studio's legacy Haystack.save_haystack)
-----------------------------------------------------------------------------

    [haystack]
    name = "default"
    active_graph = "graphs/foo.haywire"   # optional; relative to workspace_root

    [[graphs]]
    path    = "graphs/foo.haywire"        # relative to workspace_root
    execute = false

Notes
-----
- ``active_path`` is stored relative to ``workspace_root``; on load it is
  reconstructed as an absolute ``Path`` and returned from ``load_haystack``.
- Paths are always stored as *relative* strings so haystacks are portable
  when the workspace is moved. If a path is outside workspace_root (edge case)
  the absolute form is stored as a fallback, matching legacy behaviour.
- The project uses the ``toml`` package (both reads and writes) — do NOT
  switch to ``tomli`` / ``tomli_w`` without updating all callers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import toml

if TYPE_CHECKING:
    pass  # HaystackState is not yet defined — avoid circular imports

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def haystack_dir(workspace_root: Path) -> Path:
    """Return the ``haystacks/`` directory inside *workspace_root*."""
    return workspace_root / "haystacks"


def haystack_path(workspace_root: Path, name: str) -> Path:
    """Return the absolute path for a named haystack TOML file."""
    return haystack_dir(workspace_root) / f"{name}.toml"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_haystacks(workspace_root: Path) -> list[str]:
    """Return a sorted list of haystack names available in *workspace_root*.

    Args:
        workspace_root: Root directory of the Haywire workspace.

    Returns:
        Sorted list of haystack name strings (stems of ``*.toml`` files in
        ``<workspace_root>/haystacks/``).
    """
    d = haystack_dir(workspace_root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.toml"))


def dump_haystack(
    state,
    workspace_root: Path,
    name: str,
    active_path: Optional[Path] = None,
) -> Path:
    """Serialize the current set of open graphs to a haystack TOML file.

    Only file-backed entries (``entry.path is not None``) are written.
    Entries without a path (untitled / never-saved) are silently skipped.

    The written format is backward-compatible with haywire-studio's legacy
    ``Haystack.save_haystack``: top-level ``[haystack]`` section with an
    optional ``active_graph`` key, and ``[[graphs]]`` array of tables.

    Args:
        state:          Object with an ``all_entries()`` method returning an
                        iterable of ``GraphEntry`` instances.
        workspace_root: Root directory used to compute relative paths.
        name:           Haystack name (also used as the TOML filename stem).
        active_path:    Absolute path of the currently active graph, or None.
                        Stored as a relative path inside the TOML so it can
                        be restored by ``load_haystack``.

    Returns:
        The ``Path`` to the written haystack file.
    """
    target = haystack_path(workspace_root, name)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Build the active_graph value as a relative (or absolute fallback) string
    active_rel: Optional[str] = None
    if active_path is not None:
        try:
            active_rel = str(active_path.relative_to(workspace_root))
        except ValueError:
            active_rel = str(active_path)

    # Build graph entries — only saved (file-backed) graphs
    graphs_list = []
    for entry in state.all_entries():
        if entry.path is None:
            continue
        try:
            rel = str(entry.path.relative_to(workspace_root))
        except ValueError:
            rel = str(entry.path)
        graphs_list.append(
            {
                "path": rel,
                "execute": entry.is_executing,
            }
        )

    haystack_meta: dict = {"name": name}
    if active_rel is not None:
        haystack_meta["active_graph"] = active_rel

    data: dict = {
        "haystack": haystack_meta,
        "graphs": graphs_list,
    }

    target.write_text(toml.dumps(data))
    logger.info(f"Haystack '{name}' saved to {target} ({len(graphs_list)} graphs)")
    return target


def load_haystack(
    state,
    workspace_root: Path,
    name: str,
) -> Optional[Path]:
    """Load a named haystack TOML file and open each listed graph.

    Graphs listed in the TOML that no longer exist on disk are skipped with a
    warning. Graphs marked ``execute = true`` have ``start_execution()`` called
    on their entry after opening.

    Unlike the legacy ``Haystack.load_haystack``, this function does **not**
    clear existing entries — that side effect belongs to the caller
    (``HaystackState``). This keeps persistence.py a pure I/O helper.

    Args:
        state:          Object with an ``open_graph(path: Path) -> GraphEntry``
                        method.
        workspace_root: Root directory used to resolve relative paths.
        name:           Haystack name (filename stem in ``haystacks/``).

    Returns:
        The absolute ``Path`` of the active graph if one was stored, otherwise
        ``None``.  Returns ``None`` (rather than raising) if the file is
        missing — the caller decides whether that is an error.
    """
    source = haystack_path(workspace_root, name)
    if not source.exists():
        logger.warning(f"Haystack '{name}' not found at {source}")
        return None

    data = toml.loads(source.read_text())
    haystack_meta = data.get("haystack", {})
    active_graph_rel: Optional[str] = haystack_meta.get("active_graph")
    graphs_data = data.get("graphs", [])

    for gd in graphs_data:
        rel_path = gd.get("path")
        if not rel_path:
            continue
        abs_path = workspace_root / rel_path
        if not abs_path.exists():
            logger.warning(f"Haystack '{name}': skipping missing graph: {abs_path}")
            continue
        try:
            entry = state.open_graph(abs_path)
            if gd.get("execute", False):
                entry.start_execution()
        except Exception as exc:
            logger.error(f"Haystack '{name}': error loading {abs_path}: {exc}")

    logger.info(f"Haystack '{name}' loaded from {source} ({len(graphs_data)} entries in file)")

    if active_graph_rel is None:
        return None
    return workspace_root / active_graph_rel


def delete_haystack(workspace_root: Path, name: str) -> bool:
    """Delete a named haystack TOML file.

    Args:
        workspace_root: Root directory of the Haywire workspace.
        name:           Haystack name (filename stem).

    Returns:
        ``True`` if the file existed and was removed, ``False`` otherwise.
    """
    target = haystack_path(workspace_root, name)
    if not target.exists():
        return False
    target.unlink()
    logger.info(f"Haystack '{name}' deleted")
    return True


def rename_haystack(workspace_root: Path, old_name: str, new_name: str) -> bool:
    """Rename a haystack file on disk, updating the ``name`` field inside.

    Refuses to overwrite an existing file with *new_name*.

    Args:
        workspace_root: Root directory of the Haywire workspace.
        old_name:       Current haystack name (filename stem).
        new_name:       Desired new name (filename stem).

    Returns:
        ``True`` if the rename succeeded, ``False`` otherwise.
    """
    src = haystack_path(workspace_root, old_name)
    dst = haystack_path(workspace_root, new_name)
    if not src.exists():
        return False
    if dst.exists():
        return False  # refuse to overwrite

    try:
        src.rename(dst)
    except OSError:
        return False

    # Update the stored name inside the TOML (best-effort)
    try:
        data = toml.loads(dst.read_text())
        if "haystack" in data:
            data["haystack"]["name"] = new_name
            dst.write_text(toml.dumps(data))
    except Exception:
        pass  # file rename succeeded even if TOML update fails

    logger.info(f"Haystack '{old_name}' renamed to '{new_name}'")
    return True
