"""Read and rewrite the decorator-authored half of a library's metadata.

Only fields the decorator owns are editable here. The PEP 621 half — version,
description, authors, keywords, urls — lives in ``pyproject.toml`` and reaches
the identity through the installed distribution, so writing a second copy would
be overwritten by the next ``uv sync``. That asymmetry is the point of ADR 0024,
not an omission.

Writes happen in the pipeline's ``publish`` step. The whole batch is validated
before any file is touched: a partially applied edit leaves two libraries
disagreeing about what was published, which is exactly the split this change
removes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.decorator_io import (
    _set_decorator_list_field,
    _set_decorator_str_field,
)
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.manifest.decorator_ast import read_decorator
from haywire.core.publishing.manifest.os_field import _DECLARABLE_OS_VALUES


@dataclass(frozen=True)
class LibraryEdit:
    """One library's editable metadata, as shown and as submitted."""

    lib_dir: Path
    name: str
    label: str
    on_reload: str
    os: list[str] = field(default_factory=list)
    examples_path: str = ""
    tests_path: str = ""


@dataclass(frozen=True)
class MetadataPlan:
    """Current values for every barn library, one entry each."""

    edits: list[LibraryEdit] = field(default_factory=list)


def _init_py(lib_dir: Path) -> Path | None:
    module_dir = find_module_dir(lib_dir)
    return (module_dir / "__init__.py") if module_dir else None


def plan_metadata(repo_root: Path) -> MetadataPlan:
    """Read each barn library's current editable metadata.

    A library whose module directory or ``__init__.py`` cannot be found is
    skipped rather than reported empty — an empty form would invite the user to
    "fix" it by overwriting a file the wizard never read.
    """
    edits: list[LibraryEdit] = []
    for lib_dir in barn_library_dirs(repo_root):
        init_py = _init_py(lib_dir)
        if init_py is None or not init_py.is_file():
            continue
        decorator = read_decorator(init_py)
        edits.append(
            LibraryEdit(
                lib_dir=lib_dir,
                name=lib_dir.name,
                label=decorator.label,
                on_reload=decorator.on_reload,
                os=list(decorator.os),
                examples_path=decorator.examples_path,
                tests_path=decorator.tests_path,
            )
        )
    return MetadataPlan(edits=edits)


def validate_edit(lib_dir: Path, edit: LibraryEdit) -> list[str]:
    """Everything wrong with *edit*, in human-readable form. Empty when clean.

    Declared paths are checked against the working tree: an empty path means
    "no examples", which needs no check, but a declared one asserts a file the
    publish would otherwise contradict. Rows are tag-pinned, so a wrong path is
    unfixable without cutting another release.
    """
    problems: list[str] = []

    if not edit.label.strip():
        problems.append(f"{edit.name}: label cannot be empty")

    try:
        LibraryReloadAction(edit.on_reload.strip().lower())
    except ValueError:
        problems.append(f"{edit.name}: on_reload must be none, refresh or restart — got {edit.on_reload!r}")

    for value in edit.os:
        if value not in _DECLARABLE_OS_VALUES:
            problems.append(f"{edit.name}: unknown platform {value!r}")

    for label, declared in (("examples_path", edit.examples_path), ("tests_path", edit.tests_path)):
        if declared and not (lib_dir / declared).exists():
            problems.append(f"{edit.name}: {label} {declared!r} does not exist")

    return problems


def apply_metadata(repo_root: Path, edits: list[LibraryEdit]) -> list[Path]:
    """Write every edit. Validates the whole batch first; returns files written.

    Raises :class:`ValueError` listing every problem when validation fails,
    before any file is touched.
    """
    problems: list[str] = []
    for edit in edits:
        problems.extend(validate_edit(edit.lib_dir, edit))
    if problems:
        raise ValueError("; ".join(problems))

    written: list[Path] = []
    for edit in edits:
        init_py = _init_py(edit.lib_dir)
        if init_py is None or not init_py.is_file():
            continue
        source = init_py.read_text()
        source = _set_decorator_str_field(source, "label", edit.label.strip())
        source = _set_decorator_str_field(source, "on_reload", edit.on_reload.strip().lower())
        source = _set_decorator_list_field(source, "os", list(edit.os))
        source = _set_decorator_str_field(source, "examples_path", edit.examples_path.strip())
        source = _set_decorator_str_field(source, "tests_path", edit.tests_path.strip())
        init_py.write_text(source)
        written.append(init_py)
    return written
