"""``haywire rename --map``: rename components by their registry keys in every saved graph.

A key map is a TOML file of ``[[rename]]`` entries::

    [[rename]]
    old = "haybale-core:type:ArrayType"
    new = "haybale-core:type:ARRAY"
    old_module = "haybale_core.types.array_type"   # optional, with new_module
    new_module = "haybale_core.types.array"

Only saved graphs change. A parameterized type such as ``ArrayType[INT]`` or
``OPTIONAL[INT]`` saves its family's key with a nested ``element_type`` recipe,
so one entry per family covers every parameterization. Python sources, tests
and docs are left to the author.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from .checks import check_clean_tree, check_write_access
from .graphs import apply_key_map_graphs, is_registry_key, plan_key_map_graphs
from .model import Blocker, KeyMapPlan, KeyRename

_ENTRY_FIELDS = frozenset({"old", "new", "old_module", "new_module"})


def _kind(key: str) -> str:
    """The kind segments of *key*: ``node`` for ``lib:node:X``, ``theme:t`` for ``lib:theme:t:X``."""
    return ":".join(key.split(":")[1:-1])


def load_key_map(map_path: Path) -> tuple[list[KeyRename], list[Blocker]]:
    """Read and validate a key map file.

    Every problem is reported, not only the first: a missing or unreadable
    file, no ``[[rename]]`` entries, an unknown field, a value that isn't a
    registry key, an entry that changes nothing or changes the kind, only one
    of the two module fields, the same ``old`` twice, and a chain (an entry's
    ``new`` is another entry's ``old``, which one pass would not follow).

    Returns ``(renames, blockers)``; *renames* is empty when there are blockers.
    """
    try:
        document = tomllib.loads(Path(map_path).read_text(encoding="utf-8"))
    except OSError as exc:
        return [], [Blocker(message=f"Cannot read key map {map_path}: {exc}")]
    except tomllib.TOMLDecodeError as exc:
        return [], [Blocker(message=f"Key map {map_path} is not valid TOML: {exc}")]

    entries = document.get("rename")
    if not isinstance(entries, list) or not entries:
        return [], [
            Blocker(
                message=f"Key map {map_path} has no [[rename]] entries.",
                remedy='[[rename]]\nold = "<dist>:<kind>:<Name>"\nnew = "<dist>:<kind>:<Name>"',
            )
        ]

    blockers: list[Blocker] = []
    renames: list[KeyRename] = []
    for number, entry in enumerate(entries, start=1):
        where = f"[[rename]] #{number}"
        if not isinstance(entry, dict):
            blockers.append(Blocker(message=f"{where} is not a table."))
            continue
        unknown = sorted(set(entry) - _ENTRY_FIELDS)
        if unknown:
            blockers.append(
                Blocker(
                    message=f"{where} has unknown field(s): {', '.join(unknown)}.",
                    remedy="Allowed: old, new, old_module, new_module.",
                )
            )
            continue
        old, new = entry.get("old"), entry.get("new")
        bad = [
            f"{name} = {value!r}"
            for name, value in (("old", old), ("new", new))
            if not isinstance(value, str) or not is_registry_key(value)
        ]
        if bad:
            blockers.append(
                Blocker(
                    message=f"{where}: not a registry key: {'; '.join(bad)}.",
                    remedy='Write the whole key, e.g. "haybale-core:node:BeginPlayNode".',
                )
            )
            continue
        assert isinstance(old, str) and isinstance(new, str)
        if old == new:
            blockers.append(Blocker(message=f"{where}: old and new are both {old!r}."))
            continue
        if _kind(old) != _kind(new):
            blockers.append(Blocker(message=f"{where}: {old!r} → {new!r} changes the kind."))
            continue
        old_module, new_module = entry.get("old_module"), entry.get("new_module")
        if (old_module is None) != (new_module is None):
            blockers.append(Blocker(message=f"{where}: set both old_module and new_module, or neither."))
            continue
        if old_module is not None and not (isinstance(old_module, str) and isinstance(new_module, str)):
            blockers.append(Blocker(message=f"{where}: old_module and new_module must be strings."))
            continue
        renames.append(KeyRename(old=old, new=new, old_module=old_module, new_module=new_module))

    olds = [rename.old for rename in renames]
    for old in sorted({old for old in olds if olds.count(old) > 1}):
        blockers.append(Blocker(message=f"{old!r} is renamed more than once."))
    for rename in renames:
        if rename.new in olds:
            blockers.append(
                Blocker(
                    message=f"Chain: {rename.old!r} → {rename.new!r}, which is renamed again.",
                    remedy="Map each old key straight to its final key.",
                )
            )

    return ([] if blockers else renames), blockers


def plan_key_map(map_path: Path, workspace_root: Path) -> KeyMapPlan:
    """Load the key map and enumerate every graph change and blocker. Writes nothing."""
    workspace_root = Path(workspace_root)
    plan = KeyMapPlan(map_path=Path(map_path), workspace_root=workspace_root)

    plan.renames, plan.blockers = load_key_map(map_path)
    if plan.blockers:
        return plan

    plan.blockers += check_clean_tree(workspace_root)

    changes, drift, rewriter = plan_key_map_graphs(workspace_root, plan.renames)
    plan.graph_changes = changes
    plan.unrecognized = drift
    plan.key_counts = dict(rewriter.key_counts)
    plan.key_graphs = dict(rewriter.key_graphs)
    plan.copies = rewriter.copies

    plan.blockers += check_write_access([change.path for change in changes], [])
    return plan


def execute_key_map(plan: KeyMapPlan) -> tuple[bool, str]:
    """Apply *plan*'s graph changes. Returns ``(ok, message)``."""
    try:
        apply_key_map_graphs(plan.graph_changes, plan.renames)
    except (OSError, ValueError) as exc:
        return False, f"Failed to patch graphs: {exc}\nRecover with:\n  git checkout ."
    return True, f"Rewrote {plan.total_changes} key(s) in {len(plan.graph_changes)} graph(s)."
