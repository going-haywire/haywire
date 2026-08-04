"""Framework-requirement step — one project-wide answer, two carriers.

A floor is a restriction on CONSUMERS, not a record of what the author
tested: raising it forces every consumer to upgrade their project before
they can install, and some cannot. So the recommended option is always the
lowest necessary one — keep what is already declared — and raising it is a
deliberate, consequence-annotated choice.

The single answer is written into two disjoint carriers:

  * the ``haywire-core`` floor in each library's ``pyproject.toml``, which is
    the ONLY guard on the bare ``uv add haybale-foo`` path (no UI to warn
    anyone), and
  * ``requires_haywire`` in the marketstall entry, which the marketplace reads
    in ``haywire.core.marketstall.framework_gate`` as a pre-emptive gate before
    the constraint file refuses the install. Advisory only: it is author-
    declared metadata and can be stale or absent, so a pass proves nothing and
    the resolver stays the real guard.

Never a ceiling by default: a ``<0.1.0`` stamped today becomes a lie the
moment 0.1.0 ships and nobody will remember to update it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import toml

from haywire.core.tomlio import edit_toml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from haywire_studio.packaging.share.pipeline.errors import InvalidSpecifierError
from haywire_studio.packaging.share.pipeline.results import FrameworkOption, FrameworkPlan

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

_CORE = "haywire-core"


def _installed_core_version() -> str:
    """The running ``haywire-core`` version. Patched wholesale in tests."""
    import importlib.metadata as _meta

    try:
        return _meta.version(_CORE)
    except _meta.PackageNotFoundError:
        return ""


def _dep_name(entry: str) -> str:
    """The bare package name from a PEP 508 dependency string."""
    head = entry.split(";", 1)[0].split(" @ ", 1)[0]
    return re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0].strip()


def haywire_core_floor(lib_dir: Path) -> str:
    """The ``haywire-core`` specifier this library declares, or "" if none."""
    pyproject = lib_dir / "pyproject.toml"
    if not pyproject.is_file():
        return ""
    data = toml.loads(pyproject.read_text())
    for entry in data.get("project", {}).get("dependencies", []) or []:
        if _dep_name(entry).lower() == _CORE:
            return entry[len(_dep_name(entry)) :].strip()
    return ""


def specifiers_equal(left: str, right: str) -> bool:
    """Compare two specifiers as parsed sets, never as raw strings.

    ``packaging`` reorders on ``str()`` — ``">=0.0.31,<1.0.0"`` round-trips as
    ``"<1.0.0,>=0.0.31"`` — so a string comparison yields false drift.
    """
    try:
        return SpecifierSet(left) == SpecifierSet(right)
    except InvalidSpecifier:
        return left.strip() == right.strip()


def parse_specifier(raw: str) -> SpecifierSet:
    """Validate an authored specifier. Raises InvalidSpecifierError."""
    text = (raw or "").strip()
    if not text:
        raise InvalidSpecifierError("A framework requirement cannot be empty.")
    try:
        return SpecifierSet(text)
    except InvalidSpecifier as exc:
        raise InvalidSpecifierError(
            f"{text!r} is not a valid PEP 440 specifier. Include the operator, "
            f"e.g. '>=0.0.31', '~=0.0.31', or '>=0.0.31,<1.0.0'."
        ) from exc


def _declared_floor(pipeline: "SharePipeline") -> str:
    """The specifier the barn libraries agree on, or the first one found.

    One project-wide answer: libraries built and tested against one installed
    framework have no honest basis for differing floors, so a disagreement is
    resolved by this step writing them all to the same value.
    """
    for lib_dir in pipeline._barn_library_dirs():
        floor = haywire_core_floor(lib_dir)
        if floor:
            return floor
    return ""


def _excluded_range(declared: str, installed: str) -> str:
    """Human phrasing for who a raise to *installed* would lock out."""
    try:
        low = SpecifierSet(declared)
        floors = [Version(spec.version) for spec in low if spec.operator in (">=", "~=", "==")]
    except (InvalidSpecifier, ValueError):
        floors = []
    if not floors:
        return f"Consumers below Haywire {installed} must update their project before installing."
    lowest = min(floors)
    target = Version(installed)
    if lowest >= target:
        return ""
    below = Version(f"{target.major}.{target.minor}.{max(target.micro - 1, 0)}")
    return f"Consumers on {lowest}–{below} must update their project before they can install this library."


def plan(pipeline: "SharePipeline") -> FrameworkPlan:
    """The framework requirement on offer, before the author picks."""
    installed = _installed_core_version()
    declared = _declared_floor(pipeline)

    options: list[FrameworkOption] = []
    if declared:
        options.append(
            FrameworkOption(
                specifier=declared,
                label="keep the current declaration",
                consequence=f"Usable by projects on Haywire {declared.lstrip('>=~^ ')} and newer. "
                f"No consumer has to upgrade.",
                recommended=True,
            )
        )
    if installed:
        raise_spec = f">={installed}"
        if not declared or not specifiers_equal(declared, raise_spec):
            options.append(
                FrameworkOption(
                    specifier=raise_spec,
                    label="require the version you built against",
                    consequence=_excluded_range(declared, installed),
                    recommended=not declared,
                )
            )
    if declared and declared.startswith(">="):
        compatible = f"~={declared.removeprefix('>=').strip()}"
        options.append(
            FrameworkOption(
                specifier=compatible,
                label="compatible release",
                consequence="Also excludes Haywire 0.1.0 and newer.",
            )
        )
    return FrameworkPlan(installed=installed, declared=declared, options=options)


def apply(pipeline: "SharePipeline", specifier: str) -> list[Path]:
    """Write *specifier* as the ``haywire-core`` floor in every barn library.

    Stores the answer on the pipeline so step 5's marketstall rebuild can emit
    the same value as ``requires_haywire`` — one authored answer, two carriers.
    """
    parsed = parse_specifier(specifier)
    text = str(parsed)

    written: list[Path] = []
    for lib_dir in pipeline._barn_library_dirs():
        pyproject = lib_dir / "pyproject.toml"
        if not pyproject.is_file():
            continue
        # edit_toml, not a toml.loads/dumps round trip: this is the library
        # author's own pyproject.toml, and rebuilding it from parsed dicts
        # deletes every comment they wrote.
        with edit_toml(pyproject) as data:
            project = data.setdefault("project", {})
            deps = project.setdefault("dependencies", [])
            new_deps: list[str] = []
            found = False
            for entry in deps:
                if _dep_name(str(entry)).lower() == _CORE:
                    new_deps.append(f"{_CORE}{text}")
                    found = True
                else:
                    new_deps.append(str(entry))
            if not found:
                new_deps.append(f"{_CORE}{text}")
            project["dependencies"] = new_deps
        written.append(pyproject)

    pipeline.requires_haywire = text
    pipeline.record(written)
    return written
