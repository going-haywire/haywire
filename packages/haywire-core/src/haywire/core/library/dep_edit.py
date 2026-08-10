"""Entry-level edits to a library's ``[project] dependencies``.

Every operation here names the entries it touches and leaves the rest of the
array byte-identical. That is a correctness property, not a style preference,
and it replaces a whole-list overwrite that caused two distinct bugs:

  * **Clobbering.** Rebuilding the array from detected dependencies rewrote the
    ``haywire-core`` floor as a side effect of resolving unrelated drift. The
    framework requirement is authored by one step; nothing else may write it.
    With no operation that expresses "replace everything", the other steps
    *cannot* touch it.

  * **Lossy round-trips.** Entries can carry extras
    (``visiongraph[onnx,openvino,mediapipe]``), environment markers
    (``; sys_platform == "darwin"``), and direct references (``foo @ git+…``).
    Regenerating the array from detection reproduces none of those. Untouched
    entries are never read as data here, so there is nothing to lose.

Ordering: new entries append, existing entries never move. Hand-maintained
files keep their author's grouping, and a diff shows only what changed.

All writes go through ``edit_toml``, which preserves comments — these are the
library author's own files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import toml

from haywire.core.marketstall.requirement import dependency_name
from haywire.core.tomlio import edit_toml


def norm_dep(name: str) -> str:
    """Normalize a dep name to a comparable form (underscores, lowercase).

    Shared by ``haywire share``'s drift detection and the entry-level edits
    below, so both agree on when two spellings (``haybale-core`` vs.
    ``haybale_core``) name the same thing.
    """
    return re.sub(r"[-_.]+", "_", name).lower()


def read_dependencies(lib_dir: Path) -> list[str]:
    """The library's declared ``[project] dependencies``, verbatim.

    Raises ``FileNotFoundError`` when there is no pyproject.toml and
    ``toml.TomlDecodeError`` when it does not parse — callers rewriting the
    file must fail before they write, not silently overwrite.
    """
    pyproject = lib_dir / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"no pyproject.toml at {pyproject}")
    data = toml.loads(pyproject.read_text())
    deps = data.get("project", {}).get("dependencies", []) or []
    return [str(entry) for entry in deps]


def set_dependency(lib_dir: Path, entry: str) -> None:
    """Set the single dependency named by *entry*, appending if absent.

    ``set_dependency(d, "haywire-core>=0.0.38")`` replaces whatever entry
    currently names ``haywire-core`` and leaves every other entry alone. This
    is the only way the framework floor is ever written.
    """
    target = norm_dep(dependency_name(entry))
    with edit_toml(lib_dir / "pyproject.toml") as data:
        project = data.setdefault("project", {})
        deps = _dependencies_array(project)
        for index, item in enumerate(deps):
            if norm_dep(dependency_name(str(item))) == target:
                deps[index] = entry
                break
        else:
            deps.append(entry)


def add_dependencies(lib_dir: Path, entries: list[str]) -> None:
    """Append *entries* whose distributions are not already declared.

    An entry naming an already-declared distribution is skipped rather than
    overwritten: this operation adds what is missing, and changing an existing
    specifier is :func:`set_dependency`'s job. That split is what keeps an
    "add the imports you forgot" step from silently restating floors.
    """
    if not entries:
        return
    with edit_toml(lib_dir / "pyproject.toml") as data:
        project = data.setdefault("project", {})
        deps = _dependencies_array(project)
        declared = {norm_dep(dependency_name(str(item))) for item in deps}
        for entry in entries:
            name = norm_dep(dependency_name(entry))
            if name in declared:
                continue
            deps.append(entry)
            declared.add(name)


def remove_dependencies(lib_dir: Path, dist_names: list[str]) -> None:
    """Drop every entry naming one of *dist_names*.

    Takes bare distribution names, not full entries: the caller decided *which
    dependency* to remove, and should not have to reproduce the exact
    specifier text to make the removal match.
    """
    if not dist_names:
        return
    targets = {norm_dep(name) for name in dist_names}
    with edit_toml(lib_dir / "pyproject.toml") as data:
        project = data.setdefault("project", {})
        deps = _dependencies_array(project)
        # Back to front: deleting shifts every later index.
        for index in range(len(deps) - 1, -1, -1):
            if norm_dep(dependency_name(str(deps[index]))) in targets:
                del deps[index]


def _dependencies_array(project: Any) -> Any:
    """The live ``[project] dependencies`` array, created empty if absent.

    Returns the tomlkit array ITSELF, never a copy. Mutating it in place is
    what preserves the author's formatting: tomlkit keeps an array's existing
    layout — multi-line with one entry per line, trailing comma, indentation,
    and any per-entry comments — across `append`, `__setitem__` and `del`, but
    assigning a fresh Python list replaces the array wholesale and renders it
    inline, silently discarding both the layout and the comments.

    Style is preserved, not imposed: an array the author wrote inline stays
    inline. This is their file.
    """
    deps = project.get("dependencies")
    if deps is None:
        project["dependencies"] = []
        deps = project["dependencies"]
    return deps
