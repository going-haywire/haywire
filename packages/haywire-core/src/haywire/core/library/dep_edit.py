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

from pathlib import Path

import toml

from haywire.core.library.decorator_io import norm_dep
from haywire.core.marketstall.requirement import dependency_name
from haywire.core.tomlio import edit_toml


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
        deps = [str(item) for item in project.get("dependencies", []) or []]
        out: list[str] = []
        found = False
        for item in deps:
            if norm_dep(dependency_name(item)) == target:
                out.append(entry)
                found = True
            else:
                out.append(item)
        if not found:
            out.append(entry)
        project["dependencies"] = out


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
        deps = [str(item) for item in project.get("dependencies", []) or []]
        declared = {norm_dep(dependency_name(item)) for item in deps}
        for entry in entries:
            name = norm_dep(dependency_name(entry))
            if name in declared:
                continue
            deps.append(entry)
            declared.add(name)
        project["dependencies"] = deps


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
        deps = [str(item) for item in project.get("dependencies", []) or []]
        project["dependencies"] = [item for item in deps if norm_dep(dependency_name(item)) not in targets]
