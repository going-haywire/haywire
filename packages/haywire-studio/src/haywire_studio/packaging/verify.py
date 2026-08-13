"""``haywire verify`` — prove every graph's registry keys still resolve.

Runs as a SEPARATE PROCESS after a rename, never in-process from the studio:
per .insights/project_docs_gen_reentrancy.md, building a second library
system repoints the global injector and settings registry.

Resolution is class-level only — ``registry.has(key)``. Nodes are never
instantiated: construction grabs hardware (the OAK-D and webcam graphs would
open cameras) and runs author code for no benefit, since a dangling
registry key is visible without building anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .rename.discovery import find_graph_files
from .rename.graphs import KEY_FIELDS, LIST_KEY_FIELDS, is_registry_key

#: Answers "is this registry key known to the loaded libraries?"
Resolver = Callable[[str], bool]


@dataclass
class GraphReport:
    """One graph's resolution result."""

    path: Path
    keys_checked: int = 0
    unresolved: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.unresolved


@dataclass
class VerifyReport:
    """The whole workspace's resolution result."""

    graphs: list[GraphReport] = field(default_factory=list)

    @property
    def graphs_checked(self) -> int:
        return len(self.graphs)

    @property
    def unresolved_total(self) -> int:
        return sum(sum(g.unresolved.values()) for g in self.graphs)

    @property
    def ok(self) -> bool:
        return all(g.ok for g in self.graphs)


def collect_keys(data: object) -> dict[str, int]:
    """Every registry key in *data*, with occurrence counts.

    Mirrors the rename walker: same fields, same unbounded recursion, so a
    key the rename would rewrite is a key verify checks.
    """
    counts: Counter[str] = Counter()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in KEY_FIELDS and isinstance(value, str) and is_registry_key(value):
                    counts[value] += 1
                elif key in LIST_KEY_FIELDS and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and is_registry_key(item):
                            counts[item] += 1
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return dict(counts)


def verify_graphs(workspace_root: Path, resolver: Resolver) -> VerifyReport:
    """Check every discoverable graph's keys against *resolver*."""
    import json

    report = VerifyReport()
    for path in find_graph_files(workspace_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        keys = collect_keys(data)
        graph_report = GraphReport(path=path, keys_checked=sum(keys.values()))
        for key, count in keys.items():
            if not resolver(key):
                graph_report.unresolved[key] = count
        report.graphs.append(graph_report)

    return report


def _live_resolver(workspace_root: Path) -> Resolver:
    """Resolve against the libraries installed in THIS interpreter.

    Boots a full library system (per .insights/project_docs_gen_reentrancy.md,
    this is expensive and mutates global DI state — verify always runs as a
    separate process, never in-process from the studio). Imported lazily so
    the pure functions above stay unit-testable without booting anything.
    """
    from typing import Any

    from haywire.core.adapter.registry import AdapterRegistry
    from haywire.core.di.config import create_library_system_service
    from haywire.core.node.registry import NodeRegistry
    from haywire.core.registry.base import BaseRegistry
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.state.registry import LibraryStateRegistry
    from haywire.core.types.registry import TypeRegistry
    from haywire.ui.skin.registry import SkinRegistry
    from haywire.ui.themes.registry import ThemeRegistry
    from haywire.ui.widget.registry import WidgetRegistry

    registry_classes: tuple[type[BaseRegistry[Any]], ...] = (
        NodeRegistry,
        TypeRegistry,
        WidgetRegistry,
        AdapterRegistry,
        SkinRegistry,
        ThemeRegistry,
        SettingsRegistry,
        LibraryStateRegistry,
    )

    service = create_library_system_service(
        workspace_root=str(workspace_root),
        enable_file_watching=False,
        watch_settings=False,
    )
    known: set[str] = set()
    for registry_cls in registry_classes:
        known.update(service.injector.get(registry_cls).list_names())
    return lambda key: key in known


def run_verify_cli(*, workspace_root: Path, verbose: bool = False, resolver: Resolver | None = None) -> int:
    """Print a resolution report. Returns 0 when everything resolves."""
    resolve = resolver or _live_resolver(Path(workspace_root))
    report = verify_graphs(Path(workspace_root), resolve)

    if report.graphs_checked == 0:
        print("No graphs found.")
        return 0

    for graph in report.graphs:
        if graph.ok:
            if verbose:
                print(f"  ✓ {graph.path}  ({graph.keys_checked} keys)")
        else:
            print(f"  ✗ {graph.path}")
            for key, count in sorted(graph.unresolved.items()):
                print(f"      {key}  ×{count}")

    print()
    if report.ok:
        print(f"All {report.graphs_checked} graph(s) resolve.")
        return 0

    broken = sum(1 for g in report.graphs if not g.ok)
    print(
        f"{report.unresolved_total} unresolved key(s) across {broken} of {report.graphs_checked} graph(s)."
    )
    return 1
