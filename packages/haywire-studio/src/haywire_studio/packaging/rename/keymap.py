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

from pathlib import Path

from haywire.core.renames import parse_key_map

from .checks import check_clean_tree, check_write_access
from .graphs import apply_key_map_graphs, plan_key_map_graphs
from .model import Blocker, KeyMapPlan, KeyRename


def load_key_map(map_path: Path) -> tuple[list[KeyRename], list[Blocker]]:
    """Read and validate a key map file.

    Every problem is reported, not only the first: a missing or unreadable
    file, and each one :func:`haywire.core.renames.parse_key_map` finds.

    Returns ``(renames, blockers)``; *renames* is empty when there are blockers.
    """
    try:
        text = Path(map_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [], [Blocker(message=f"Cannot read key map {map_path}: {exc}")]
    renames, problems = parse_key_map(text, str(map_path))
    return renames, [Blocker(message=problem.message, remedy=problem.remedy) for problem in problems]


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
        return (
            False,
            f"Failed to patch graphs: {exc}\nRecover with:\n  git checkout -- . ':!.haywire/settings.json'",
        )
    return True, f"Rewrote {plan.total_changes} key(s) in {len(plan.graph_changes)} graph(s)."
