"""Static dependency detection for haybale libraries.

Walks a library's source tree, resolves every top-level imported module to
its providing distribution, and classifies the result into the two output
shapes downstream consumers need:

  - ``library_linked``: underscored module names for ``haybale.toml``'s
    ``linked_libraries``. Limited to *registered* haywire libraries;
    framework imports and third-party packages do not belong here.
  - ``pyproject``: distribution names with version specifiers, ready for
    ``[project] dependencies`` in the library's pyproject.toml. Includes
    framework, registered libraries, and third-party packages.

:func:`detect_deps` is pure (no writes) and reads installed-version metadata
from the running interpreter for the version floors. Dynamic imports
(``importlib.import_module(name)``) are not detected, so the output is a
suggestion to review rather than a complete answer.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import toml

from haywire.core.tomlio import edit_toml


# ──────────────────────────────────────────────────────────────────────────────
# Public types
# ──────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class HaywireLibrarySource(Protocol):
    """Minimal interface for an object that knows which dists are haywire libraries.

    Satisfied by the live ``LibraryRegistry``.
    """

    def list_names(self) -> list[str]:
        """Return the registry ids of all currently registered libraries."""
        ...

    def get_library_distribution_name(self, library_id: str) -> str | None:
        """Return the pip distribution name for a library id, or None."""
        ...


class EntryPointLibrarySource:
    """HaywireLibrarySource backed by ``importlib.metadata.entry_points()``.

    For callers that classify imports without a running haywire runtime or
    live registry. Treats any installed distribution declaring an entry point
    in the ``haywire.libraries`` group as a haywire library.

    The mapping is built lazily on first access and cached for the lifetime
    of the instance.
    """

    GROUP = "haywire.libraries"

    def __init__(self) -> None:
        self._cache: dict[str, str] | None = None  # entry-point name -> distribution name

    def _ensure_cache(self) -> dict[str, str]:
        if self._cache is None:
            cache: dict[str, str] = {}
            for ep in importlib.metadata.entry_points(group=self.GROUP):
                dist_name = ep.dist.name if ep.dist else None
                if dist_name:
                    cache[ep.name] = dist_name
            self._cache = cache
        return self._cache

    def list_names(self) -> list[str]:
        return list(self._ensure_cache().keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._ensure_cache().get(library_id)


@dataclass(frozen=True)
class DetectedDeps:
    """The classified result of scanning a library's imports.

    Both ``library_linked`` and ``pyproject`` are deterministically sorted.
    """

    library_linked: list[str] = field(default_factory=list)
    pyproject: list[str] = field(default_factory=list)
    resolved: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers (some shared with share.py)
# ──────────────────────────────────────────────────────────────────────────────


def find_module_dir(lib_dir: Path) -> Path | None:
    """Return the Python package directory inside a library directory.

    Checks the flat layout (``lib_dir/<module>/__init__.py``) and the src
    layout (``lib_dir/src/<module>/__init__.py``). Returns the first match,
    or None if no package directory is found. Skips dot-prefixed and
    underscore-prefixed entries.
    """
    for search_root in (lib_dir, lib_dir / "src"):
        if not search_root.is_dir():
            continue
        for child in sorted(search_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith((".", "_")):
                continue
            if (child / "__init__.py").exists():
                return child
    return None


def _read_self_module_name(lib_dir: Path) -> str | None:
    """Return the normalized module name of the library's own package, or None.

    Reads ``lib_dir/pyproject.toml`` ``[project] name`` and converts it to the
    underscored module form (``haybale-foo`` → ``haybale_foo``). ``None`` when
    the file is absent, unparseable, or declares no name.
    """
    pyproject = lib_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = toml.loads(pyproject.read_text())
    except toml.TomlDecodeError:
        return None
    name = data.get("project", {}).get("name")
    if not isinstance(name, str):
        return None
    return name.replace("-", "_").replace(".", "_")


def _read_pyproject_name(start: Path) -> str | None:
    """Walk up from *start* to the nearest pyproject.toml and return its project name."""
    for parent in start.parents:
        py = parent / "pyproject.toml"
        if py.is_file():
            try:
                data = toml.loads(py.read_text())
            except toml.TomlDecodeError:
                return None
            name = data.get("project", {}).get("name")
            if isinstance(name, str):
                return name
    return None


def _resolve_module_to_dist(module: str, mapping: Mapping[str, list[str]]) -> str | None:
    """Map a top-level module name to its installed distribution name.

    Falls back to locating the module on disk and walking up to its
    pyproject.toml, which covers editable installs in dev monorepos where the
    metadata mapping is sometimes incomplete. ``None`` when neither resolves.

    Args:
        mapping: ``importlib.metadata.packages_distributions()``. Passed in
            because building it scans every installed distribution (~1s in a
            large venv), so a run fetches it once, not once per module.
    """
    owners = mapping.get(module)
    if owners:
        return owners[0]
    # Fallback for editable installs.
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    return _read_pyproject_name(Path(spec.origin).resolve())


def _installed_version(dist: str) -> str | None:
    """Return the version of an installed distribution, or None."""
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Scanner
# ──────────────────────────────────────────────────────────────────────────────


def _collect_imports(module_dir: Path) -> tuple[set[str], set[str]]:
    """Walk every .py file in *module_dir* and collect imports.

    Returns ``(top_level_modules, haywire_subpaths)``:
      - top_level_modules: every distinct top-level module name imported
        (e.g. ``{"haywire", "haybale_core", "numpy"}``).
      - haywire_subpaths: full dotted paths for imports rooted at ``haywire``
        (e.g. ``{"haywire.core.node", "haywire.ui.elements"}``). Used to
        split ``.core.*`` from ``.ui.*``.

    Relative imports are skipped (they are intra-library).
    """
    top_level: set[str] = set()
    haywire_paths: set[str] = set()

    for py in module_dir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    full = alias.name
                    top_level.add(full.split(".")[0])
                    if full == "haywire" or full.startswith("haywire."):
                        haywire_paths.add(full)
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or node.module is None:
                    continue  # relative import — intra-library
                top_level.add(node.module.split(".")[0])
                if node.module == "haywire" or node.module.startswith("haywire."):
                    haywire_paths.add(node.module)

    return top_level, haywire_paths


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def detect_deps(lib_dir: Path, *, libraries: HaywireLibrarySource) -> DetectedDeps:
    """Statically infer a library's dependencies from its source imports.

    Args:
        lib_dir: The library's root directory (contains ``pyproject.toml``
            and the module package directory).
        libraries: Anything implementing :class:`HaywireLibrarySource` — the
            authoritative set of "things that are haywire libraries". In a
            running app this is the live ``LibraryRegistry``; tests pass a
            small fake.

    Returns:
        :class:`DetectedDeps` with the four classified outputs. Empty when
        the library has no module dir or no imports.
    """
    module_dir = find_module_dir(lib_dir)
    if module_dir is None:
        return DetectedDeps()

    self_module = _read_self_module_name(lib_dir)
    # The haywire.* submodule paths go unused: every haywire.* import maps to
    # haywire-core (see below).
    top_level, _haywire_paths = _collect_imports(module_dir)

    # Drop self and stdlib.
    stdlib: frozenset[str] = getattr(sys, "stdlib_module_names", frozenset())
    candidates = {m for m in top_level if m != self_module and m not in stdlib}

    # Build the set of registered haywire-library distribution names for fast lookup.
    registered_dists: set[str] = set()
    for lib_id in libraries.list_names():
        dist = libraries.get_library_distribution_name(lib_id)
        if dist:
            registered_dists.add(dist)

    linked: list[str] = []
    pyproject: list[str] = []
    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    # One venv-wide metadata scan for the whole run (it is ~1s in a large venv).
    dist_mapping = importlib.metadata.packages_distributions()

    for module in sorted(candidates):
        if module == "haywire":
            # The whole `haywire` top-level package ships in haywire-core,
            # including haywire.ui.

            pyproject.append(_format_specifier("haywire-core"))
            resolved["haywire"] = "haywire-core"
            continue

        dist = _resolve_module_to_dist(module, dist_mapping)
        if dist is None:
            unresolved.append(module)
            continue
        resolved[module] = dist

        if dist in registered_dists:
            # Registered haywire library — emit to both outputs.
            linked.append(module)
            pyproject.append(_format_specifier(dist))
        elif dist.startswith("haywire-"):
            # Framework dist reached via a top-level other than `haywire` (e.g.
            # `import haywire_studio`): pyproject only, not linked_libraries.
            pyproject.append(_format_specifier(dist))
        else:
            # Third-party.
            pyproject.append(_format_specifier(dist))

    linked.sort()
    pyproject.sort()
    unresolved.sort()
    return DetectedDeps(
        library_linked=linked,
        pyproject=pyproject,
        resolved=resolved,
        unresolved=unresolved,
    )


def set_pyproject_dependencies(lib_dir: Path, dependencies: list[str]) -> None:
    """Replace ``[project] dependencies`` in a library's pyproject.toml.

    The rest of the file, including its comments, is preserved.

    Raises:
        FileNotFoundError: the library has no pyproject.toml.
        toml.TomlDecodeError: the existing file is malformed. Nothing is
            written in that case.
    """
    pyproject = lib_dir / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"no pyproject.toml at {pyproject}")
    with edit_toml(pyproject) as data:
        project = data.setdefault("project", {})
        project["dependencies"] = list(dependencies)


def _format_specifier(dist: str) -> str:
    """Render a ``<dist>>=<version>`` requirement string.

    Always a floor and never a ceiling, for framework and third-party alike;
    an author who wants an upper bound writes it themselves.

    Falls back to bare ``<dist>`` if the installed version can't be read — a
    library that imports something declared but not installed in the running
    interpreter.
    """
    version = _installed_version(dist)
    if version is None:
        return dist
    return f"{dist}>={version}"
