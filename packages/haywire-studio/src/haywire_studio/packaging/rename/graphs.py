"""Registry-key rewriting in the saved graph files of a workspace.

The rewrite of one graph dict lives in :mod:`haywire.core.renames.graph_keys`, which
graph pre-hydration shares; this module finds the graphs, plans, and writes them.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from haywire.core.renames.graph_keys import (
    KEY_FIELDS,
    LIST_KEY_FIELDS,
    KeyMapRewriter,
    is_registry_key,
    patch_graph_keys,
    patch_graph_tree,
)

from .discovery import find_graph_files
from .model import FileChange, KeyRename, Occurrence

__all__ = [
    "KEY_FIELDS",
    "LIST_KEY_FIELDS",
    "KeyMapRewriter",
    "apply_graphs",
    "apply_key_map_graphs",
    "is_registry_key",
    "patch_graph_keys",
    "patch_graph_tree",
    "plan_graphs",
    "plan_key_map_graphs",
]


def plan_graphs(
    root: Path,
    old: str,
    new: str,
    *,
    old_module: str | None = None,
    new_module: str | None = None,
) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute graph changes without writing anything."""
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        count, leftovers = patch_graph_tree(data, old, new, old_module=old_module, new_module=new_module)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift


def apply_graphs(
    changes: list[FileChange],
    old: str,
    new: str,
    *,
    old_module: str | None = None,
    new_module: str | None = None,
) -> None:
    """Rewrite each planned graph on disk. No backups — a clean tree is the
    precondition, so ``git checkout .`` is the rollback.
    """
    for change in changes:
        data = json.loads(change.path.read_text(encoding="utf-8"))
        patch_graph_tree(data, old, new, old_module=old_module, new_module=new_module)
        change.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def plan_key_map_graphs(
    root: Path, renames: list[KeyRename]
) -> tuple[list[FileChange], list[Occurrence], KeyMapRewriter]:
    """Compute the key map's graph changes under *root* without writing anything.

    Returns ``(changes, drift, rewriter)``; *rewriter* holds the tallies.
    """
    rewriter = KeyMapRewriter(renames)
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        before = Counter(rewriter.key_counts)
        count, leftovers = patch_graph_keys(data, rewriter)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        rewriter.key_graphs.update(set(rewriter.key_counts - before))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift, rewriter


def apply_key_map_graphs(changes: list[FileChange], renames: list[KeyRename]) -> None:
    """Rewrite each planned graph on disk by the key map."""
    rewriter = KeyMapRewriter(renames)
    for change in changes:
        text = change.path.read_text(encoding="utf-8")
        data = json.loads(text)
        patch_graph_keys(data, rewriter)
        # Keep the file's own escaping, so every value the map doesn't touch stays byte-identical.
        change.path.write_text(json.dumps(data, indent=2, ensure_ascii=text.isascii()), encoding="utf-8")
