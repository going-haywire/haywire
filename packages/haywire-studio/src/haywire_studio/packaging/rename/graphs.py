"""Registry-key rewriting inside saved graphs.

Name-based and fully recursive. Measured across the repo's 8 graphs there are
13,242 ``registry_key`` + 2,893 ``widget_key`` + 8 ``chain_adapter_keys``
values, and they sit at many different depths — inside every port of every
node, not at a handful of fixed paths. Graph-groups will nest whole graphs
inside nodes, so depth is unbounded by design.

Matching by field name is safe *for these fields specifically* because the
key grammar is unambiguous: all 16,143 real values match
``<dist>:<kind>[:<sub>]:<Name>``. A value starting ``<old-dist>:`` in one of
these fields is certainly a registry key, never a coincidence. The same is
NOT true of a bare ``name`` field, which is why ``library.name`` keeps a
position-scoped rule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery import find_graph_files
from .model import FileChange, Occurrence

#: Fields whose value is a single registry key.
KEY_FIELDS = frozenset({"registry_key", "widget_key"})

#: Fields whose value is a list of registry keys.
LIST_KEY_FIELDS = frozenset({"chain_adapter_keys"})

#: ``<dist>:<kind>:<Name>`` with an optional extra kind segment (themes use
#: ``<dist>:theme:<type>:<Name>``). Verified against all 16,143 real values.
_KEY_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_]+){2,3}$")


def is_registry_key(value: str) -> bool:
    """True if *value* is shaped like a registry key."""
    return bool(_KEY_GRAMMAR.match(value))


def _rewrite(value: object, old: str, new: str) -> tuple[object, int]:
    """Rewrite one key value if it belongs to *old*. Colon-scoped, so
    ``haybale-foo`` never matches ``haybale-foobar``, and grammar-guarded, so
    prose parked in a key field is left alone."""
    if not isinstance(value, str):
        return value, 0
    if not value.startswith(old + ":") or not is_registry_key(value):
        return value, 0
    return new + value[len(old) :], 1


def _walk(node: object, old: str, new: str, in_library: bool = False) -> int:
    """Recurse the whole tree, rewriting key fields wherever they appear."""
    count = 0

    if isinstance(node, dict):
        for key, value in node.items():
            if key in KEY_FIELDS:
                node[key], hit = _rewrite(value, old, new)
                count += hit
            elif key in LIST_KEY_FIELDS and isinstance(value, list):
                for i, item in enumerate(value):
                    value[i], hit = _rewrite(item, old, new)
                    count += hit
            elif key == "name" and in_library and value == old:
                # Position-scoped: only the library block's own name. A bare
                # `name` anywhere else is a graph/port/user value.
                node[key] = new
                count += 1
            else:
                count += _walk(value, old, new, in_library=(key == "library"))

    elif isinstance(node, list):
        for item in node:
            count += _walk(item, old, new, in_library=in_library)

    return count


def _scan_leftovers(obj: object, old: str, trail: str = "") -> list[str]:
    """Every remaining string containing *old*, as dotted paths. Drift
    detector: a hit means a key-bearing field this module does not know."""
    found: list[str] = []
    if isinstance(obj, str):
        if old in obj:
            found.append(trail)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            found += _scan_leftovers(value, old, f"{trail}.{key}" if trail else str(key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found += _scan_leftovers(item, old, f"{trail}[{i}]")
    return found


def patch_graph_tree(data: dict, old: str, new: str) -> tuple[int, list[str]]:
    """Rewrite every registry key in *data* in place.

    Returns ``(replacements, leftover_paths)``.
    """
    count = _walk(data, old, new)
    return count, _scan_leftovers(data, old)


def plan_graphs(root: Path, old: str, new: str) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute graph changes without writing anything."""
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        count, leftovers = patch_graph_tree(data, old, new)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift


def apply_graphs(changes: list[FileChange], old: str, new: str) -> None:
    """Rewrite each planned graph on disk. No backups — a clean tree is the
    precondition, so ``git checkout .`` is the rollback."""
    for change in changes:
        data = json.loads(change.path.read_text(encoding="utf-8"))
        patch_graph_tree(data, old, new)
        change.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
