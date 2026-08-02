from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from haywire.core.di.config import create_library_system_service
from haywire.core.library.registry import LibraryRegistry
from haywire_studio.packaging.docs.extract import extract_library
from haywire_studio.packaging.docs.render import (
    coverage_report,
    doc_filename,
    render_component,
    render_overview,
    render_quickref,
    render_readme,
)


def _module_dir(library_path: Path) -> Path:
    """The package's importable module directory (contains __init__.py)."""
    if (library_path / "__init__.py").exists():
        return library_path
    for child in sorted(library_path.iterdir()):
        if child.is_dir() and (child / "__init__.py").exists():
            return child
    raise FileNotFoundError(f"No module directory under {library_path}")


def _library_id_for_path(service, library_path: Path) -> str:
    """Match the loaded library whose folder_path is under library_path.

    Collects ALL matching libraries rather than returning on the first hit:
    an exact match or "target is inside the library folder" is inherently
    unambiguous, but "library folder is inside target" (target is an
    ancestor directory, e.g. running against a repo root or a ``barn/``
    that holds several libraries) can match many libraries at once. Silently
    picking whichever one ``list_names()`` iterates to first would generate
    docs for the wrong library with no indication anything went wrong, so
    multiple matches raise instead.
    """
    registry = service.injector.get(LibraryRegistry)
    target = library_path.resolve()
    matches: list[str] = []
    for lib_id in registry.list_names():
        folder = Path(registry.get_library_identity(lib_id).folder_path).resolve()
        if folder == target or target in folder.parents or folder in target.parents:
            matches.append(lib_id)
    if not matches:
        raise ValueError(f"No loaded library found under {library_path}")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous library path {library_path}: matches {sorted(matches)}. Pass a more specific path."
        )
    return matches[0]


def _package_root(module_dir: Path) -> Path | None:
    """The library's package root (dir holding pyproject.toml + README), or None.

    Package layout: the parent of the module dir. Flat layout: the module dir
    itself. Framework-owned libraries baked inside another package (e.g.
    ``haywire.barn.builtin`` inside haywire-core) have no own package root and
    return None — they get in-wheel docs (OVERVIEW/QUICKREF/docs) but no README.
    """
    if (module_dir / "pyproject.toml").exists():
        return module_dir
    if (module_dir.parent / "pyproject.toml").exists():
        return module_dir.parent
    return None


def _pyproject_version(module_dir: Path) -> str | None:
    """``[project].version`` from the library's own pyproject.toml, or None.

    The version reaching the docs must come from SOURCE, not from the running
    interpreter. ``LibraryIdentity.version`` is whatever the ``@library``
    decorator evaluated at import time, and libraries commonly set it to
    ``importlib.metadata.version(...)`` — which reads the INSTALLED dist-info.
    An editable install snapshots that at install time, so right after a
    version bump the pyproject says X while the dist-info still says X-1, and
    the QUICKREF header ships contradicting the tag and install_spec it was
    published beside.

    Read with a regex rather than a toml parse: this is the same single
    ``version = "..."`` line that ``write_barn_versions`` rewrites, and
    matching how it is written keeps the two ends symmetrical without paying
    for a parse. Returns None when there is no package root or no version
    line, leaving the caller on its existing fallback.
    """
    package_root = _package_root(module_dir)
    if package_root is None:
        return None
    pyproject = package_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    match = re.search(r'^version\s*=\s*"([^"]*)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def _generate_one(
    service: Any,
    library_id: str,
    module_dir: Path,
    version: str | None = None,
) -> list[str]:
    """Extract + render + write every doc file for one library given a loaded
    service. Returns the coverage-report lines for that library.

    ``version`` overrides the version rendered into the docs. The share
    pipeline passes the version it just bumped to, so the docs, the tag, and
    the marketstall entry cannot disagree about which release they describe.
    With no override the library's own pyproject is the source of truth, and
    only when that is unavailable does the extracted ``LibraryIdentity``
    version stand — see :func:`_pyproject_version`.
    """
    doc = extract_library(service, library_id)

    resolved = version or _pyproject_version(module_dir)
    if resolved is not None and resolved != doc.version:
        doc = replace(doc, version=resolved)

    (module_dir / "OVERVIEW.md").write_text(render_overview(doc), encoding="utf-8")
    (module_dir / "QUICKREF.md").write_text(render_quickref(doc), encoding="utf-8")

    docs_dir = module_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    # Reconcile: the docs/ folder is 100% generator-owned, so prune any
    # per-component doc whose component no longer exists (renamed/deleted).
    # Without this, orphans accumulate and silently ship stale — and a CI
    # staleness gate (git diff --exit-code) never sees them.
    expected = {doc_filename(rec.registry_key) for rec in doc.components}
    for stale in docs_dir.glob("*.md"):
        if stale.name not in expected:
            stale.unlink()
    for rec in doc.components:
        (docs_dir / doc_filename(rec.registry_key)).write_text(render_component(rec), encoding="utf-8")

    # README lives at the package root and is skipped for libraries without one.
    package_root = _package_root(module_dir)
    if package_root is not None:
        notes_path = module_dir / "NOTES.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        readme_path = package_root / "README.md"
        existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else None
        readme_path.write_text(render_readme(doc, notes, existing), encoding="utf-8")

    return coverage_report(doc)


def generate_docs(library_path: str | None, version: str | None = None) -> list[str]:
    """Generate docs for a single library at ``library_path`` (default: cwd).

    ``version``, when given, is rendered into the docs instead of the
    library's own declared version — see :func:`_generate_one`.
    """
    lib_root = Path(library_path).resolve() if library_path else Path.cwd()
    module_dir = _module_dir(lib_root)

    service = create_library_system_service(
        workspace_root=str(lib_root),
        enable_file_watching=False,
        watch_settings=False,
    )
    library_id = _library_id_for_path(service, lib_root)
    return _generate_one(service, library_id, module_dir, version)


def generate_all_docs(repo_root: str | None, version: str | None = None) -> dict[str, list[str]]:
    """Generate docs for every in-repo library in ONE library-system load.

    Discovers libraries via the loaded registry and keeps those whose module
    dir resolves to a path under ``repo_root`` — that is exactly ``barn/*`` plus
    ``haywire.barn.builtin``, and excludes external site-packages installs.
    Returns {library_id: coverage_lines}, sorted by library id.

    ``version`` applies to EVERY library generated, which is correct precisely
    because the barn is versioned in lockstep (ADR 0023) — the share pipeline
    bumps all libraries to one version and passes that same value here.
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd()

    service = create_library_system_service(
        workspace_root=str(root),
        enable_file_watching=False,
        watch_settings=False,
    )
    registry = service.injector.get(LibraryRegistry)

    results: dict[str, list[str]] = {}
    for lib_id in sorted(registry.list_names()):
        module_dir = Path(registry.get_library_identity(lib_id).folder_path).resolve()
        if root == module_dir or root in module_dir.parents:
            results[lib_id] = _generate_one(service, lib_id, module_dir, version)
    return results
