"""What an uninstall would affect: graph usage and pip reverse-dependencies.

Pure functions over the filesystem and the installed distribution metadata —
no registry, no DI, no UI. The uninstall flow calls these from a thread and
renders the result; nothing here mutates anything.

Both answer questions the old confirm modal only *asserted*. It warned that
"any graph nodes using this library will show as errors" without ever
checking, and said nothing at all about other pip packages that need the
distribution being removed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

#: Directories never worth walking for graphs. `.venv` in particular holds
#: every installed library's own example graphs, which are not the user's.
_SKIP_DIRS = frozenset({".venv", ".git", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"})

#: Graph documents. `.haywire` is the only graph extension (see
#: haybale_haystack.panels.file_browser.menu.file._GRAPH_EXTS).
_GRAPH_GLOB = "*.haywire"


@dataclass(frozen=True)
class GraphUsage:
    """One graph file that references the library under inspection."""

    path: Path
    references: int

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class UninstallImpact:
    """Everything the confirm step needs to show. Read-only by construction."""

    library_id: str
    dist_name: str = ""
    install_type: str = ""
    graphs: list[GraphUsage] = field(default_factory=list)
    pip_dependents: list[str] = field(default_factory=list)
    #: Set when the graph scan could not run (no workspace open).
    graphs_scanned: bool = True

    @property
    def total_references(self) -> int:
        return sum(g.references for g in self.graphs)

    @property
    def is_editable(self) -> bool:
        """EDITABLE installs keep their source on disk after the venv removal."""
        return self.install_type.upper() == "EDITABLE"


def _norm(name: str) -> str:
    """Normalize a distribution/module name for comparison.

    Same rule as LibraryManager._norm — pip treats ``-``, ``_`` and ``.`` as
    equivalent separators, so ``haybale-foo`` and ``haybale_foo`` are one name.
    """
    return re.sub(r"[-_.]+", "_", name).lower()


def find_graph_usage(root: Path, library_id: str) -> list[GraphUsage]:
    """Every ``*.haywire`` under *root* that references *library_id*.

    Components are serialized with a ``registry_key`` of
    ``"<library_id>:<kind>:<ClassName>"`` — so a plain-text search for
    ``"<library_id>:"`` finds nodes, types, adapters and widgets in one pass,
    which a nodes-only walk would miss.

    Deliberately a text search rather than a JSON parse: a graph that is
    malformed or from a future schema still reports honestly instead of
    vanishing from the impact list, and it stays fast enough to thread over a
    whole workspace.

    Results are sorted by descending reference count, then by path, so the
    most-affected graph leads.
    """
    needle = f"{library_id}:"
    found: list[GraphUsage] = []

    for path in _iter_graph_files(root):
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # An unreadable graph is worth neither a crash nor silence.
            logger.warning("Uninstall impact: cannot read %s: %s", path, exc)
            continue
        count = body.count(needle)
        if count:
            found.append(GraphUsage(path=path, references=count))

    found.sort(key=lambda g: (-g.references, str(g.path)))
    return found


def _iter_graph_files(root: Path):
    """Walk *root* for graph documents, skipping vendored/tooling directories."""
    if not root.is_dir():
        return
    for path in root.rglob(_GRAPH_GLOB):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def find_pip_dependents(dist_name: str) -> list[str]:
    """Installed distributions whose ``Requires-Dist`` names *dist_name*.

    ``uv uninstall`` removes a distribution without resolving what still needs
    it, so this is the only warning the user gets before a dependent package
    breaks on next import.

    Names only — the version specifier is deliberately dropped, since the
    question at hand is "what breaks", not "what range was asked for".
    """
    if not dist_name:
        return []

    import importlib.metadata as meta

    target = _norm(dist_name)
    dependents: set[str] = set()

    for dist in meta.distributions():
        try:
            own_name = dist.metadata["Name"]
        except (KeyError, TypeError):
            continue
        if not own_name or _norm(own_name) == target:
            continue
        for requirement in dist.requires or []:
            if _norm(_requirement_name(requirement)) == target:
                dependents.add(own_name)
                break

    return sorted(dependents)


def _requirement_name(requirement: str) -> str:
    """The bare distribution name from a ``Requires-Dist`` entry.

    Entries look like ``haywire-core>=0.0.31``, ``foo[extra]==1.0`` or
    ``bar; python_version < "3.12"`` — everything after the name is stripped.
    """
    head = requirement.split(";", 1)[0].strip()
    return re.split(r"[<>=!~\[\s(]", head, maxsplit=1)[0].strip()
