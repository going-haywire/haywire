"""Entry-level edits to a library's ``[project] dependencies``.

Every operation here names the entries it touches and leaves the rest of the
array byte-identical. There is no "replace everything" operation, so an entry
carrying extras (``visiongraph[onnx,openvino,mediapipe]``), an environment
marker (``; sys_platform == "darwin"``) or a direct reference
(``foo @ git+…``) survives an edit that does not name it.

Ordering: new entries append, existing entries never move.

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

    Two spellings of one distribution (``haybale-core`` and ``haybale_core``)
    normalize to the same string.
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
    currently names ``haywire-core`` and leaves every other entry alone.
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

    An entry naming an already-declared distribution is skipped, not
    overwritten; changing an existing specifier is :func:`set_dependency`'s job.
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

    Takes bare distribution names, not full entries, so the removal matches
    whatever specifier text the entry carries.
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

    Returns the tomlkit array itself, not a copy: mutate it in place. tomlkit
    keeps the array's layout and per-entry comments across `append`,
    `__setitem__` and `del`, but assigning a fresh Python list replaces the
    array wholesale and renders it inline, discarding both.
    """
    deps = project.get("dependencies")
    if deps is None:
        project["dependencies"] = []
        deps = project["dependencies"]
    return deps
