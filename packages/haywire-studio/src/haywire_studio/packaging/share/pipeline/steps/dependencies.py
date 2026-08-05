"""Steps 2–5 — every write to a library's ``[project] dependencies``.

One module owns one file's mutations. That is the whole point: the framework
floor used to be written by one step and silently rewritten by another, because
both went through a whole-list overwrite. Here each apply names the entries it
touches (via ``haywire.core.library.dep_edit``) and cannot express "replace
everything", so the wrong write is not available to make.

The screens this module backs, in order:

  2. **Framework requirement** — the ``haywire-core`` floor. The one authored
     floor in the whole flow, and the only entry :func:`apply_framework` may
     touch.
  3. **Unused declarations** — remove declarations the source no longer
     imports. Destructive and optional; never automatic, because a dynamic
     import looks identical to an unused declaration.
  4. **Undeclared imports** — add what the source imports but does not declare.
     Per-item: no-pin, floor at installed, custom, or skip.
  5. **Version floors** — a declared floor sits below what is installed. Per
     item: keep (the default, and a no-op), sync, or custom. Never raised
     automatically — see :class:`DepDrift`.

Why the framework floor is authored while other floors are not: it is one
decision per publish rather than N, it is the axis authors actually reason
about, its recommended option is "keep what is declared" so the default narrows
nothing, and its consequence is stated in consumer terms. That is a floor set
by an informed human answering one question — not a tool inferring from
installed metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.decorator_io import merge_decorator_list_field
from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.dep_edit import add_dependencies, remove_dependencies, set_dependency
from haywire.core.marketstall.requirement import CORE

from haywire_studio.packaging.share.pipeline.errors import ManifestError
from haywire_studio.packaging.share.pipeline.fixes import _MANIFEST_FAILURE_TYPES
from haywire_studio.packaging.share.pipeline.steps.framework import parse_specifier

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


def apply_framework(pipeline: "SharePipeline", specifier: str) -> list[Path]:
    """Write *specifier* as the ``haywire-core`` floor in every barn library.

    Touches exactly one entry per file. The marketstall's ``require`` is
    derived from what this writes (see ``steps/commit.apply_marketstall``), so
    this is the single authoring point for the framework requirement — there is
    no second carrier to keep in sync.
    """
    text = str(parse_specifier(specifier))
    written: list[Path] = []
    for lib_dir in pipeline._barn_library_dirs():
        pyproject = lib_dir / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            set_dependency(lib_dir, f"{CORE}{text}")
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.append(pyproject)
    return pipeline.record(written)


def apply_removals(pipeline: "SharePipeline", removals: dict[Path, list[str]]) -> list[Path]:
    """Drop the named distributions from each library's pyproject.

    *removals* maps a barn library dir to the distribution names the author
    chose to remove. A library absent from the mapping, or mapped to an empty
    list, is left untouched — "keep them" is a valid answer and writes nothing.
    """
    written: list[Path] = []
    for lib_dir, dist_names in removals.items():
        if not dist_names:
            continue
        try:
            remove_dependencies(lib_dir, dist_names)
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.append(lib_dir / "pyproject.toml")
    return pipeline.record(written)


def apply_additions(
    pipeline: "SharePipeline",
    pyproject_entries: dict[Path, list[str]],
    decorator_entries: dict[Path, list[str]],
) -> list[Path]:
    """Declare what the source imports but the manifests omit.

    *pyproject_entries* maps a library dir to fully-formed PEP 508 entries —
    the author already chose each one's pin via the screen's per-item control,
    so this writes them verbatim rather than deciding specifiers itself.
    Distributions already declared are skipped by ``add_dependencies``: an
    addition never restates an existing floor.

    *decorator_entries* maps a library dir to package names for
    ``@library(dependencies=[...])``. Merged in union mode — the decorator
    lists which libraries must be enabled, and dropping one there breaks
    hot-reload scope tracking.
    """
    written: list[Path] = []
    for lib_dir, entries in pyproject_entries.items():
        if not entries:
            continue
        try:
            add_dependencies(lib_dir, entries)
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.append(lib_dir / "pyproject.toml")

    for lib_dir, names in decorator_entries.items():
        if not names:
            continue
        module_dir = find_module_dir(lib_dir)
        if module_dir is None:
            continue
        init_file = module_dir / "__init__.py"
        if not init_file.is_file():
            continue
        try:
            merge_decorator_list_field(init_file, "dependencies", names, mode="union")
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.append(init_file)

    return pipeline.record(written)


def apply_floors(pipeline: "SharePipeline", floors: dict[Path, list[str]]) -> list[Path]:
    """Rewrite the specifiers the author chose to change on the floors screen.

    *floors* maps a library dir to fully-formed entries replacing the declared
    ones. Only entries the author actively changed appear here: the screen
    defaults every control to the currently declared specifier, so the
    no-interaction outcome is provably no change and nothing narrows unless
    someone reached in.
    """
    written: list[Path] = []
    for lib_dir, entries in floors.items():
        if not entries:
            continue
        try:
            for entry in entries:
                set_dependency(lib_dir, entry)
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.append(lib_dir / "pyproject.toml")
    return pipeline.record(written)
