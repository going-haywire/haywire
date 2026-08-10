# Linked Libraries Detect-at-Edit-Time Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a library author detect `linked_libraries` drift (both missing and stale entries) directly in the Library Overview Editor's Edit dialog, without going through `haywire share`.

**Architecture:** Extend the existing `DepDrift`/`detect_share_drift()` machinery in `haywire-core` with a reverse-direction field (`decorator_unused`) and an injectable library source. Turn the Edit dialog's read-only `linked_libraries` label into an editable multi-select (mirroring the existing `os` field), and add a "Refresh" button that runs detection and merges only additions into the select's in-memory value — never writes to disk directly, never removes entries automatically. The existing Save Changes button, which already round-trips through `write_haybale_fields` (where `linked_libraries` is already an `EDITABLE_FIELD`), persists the result.

**Tech Stack:** Python, NiceGUI (`ui.select` via `haywire.ui.elements.select_field`), pytest.

## Global Constraints

- `linked_libraries` detection/merge is the ONLY thing this feature touches. It never reads or writes `[project] dependencies` in any `pyproject.toml`, and it does not replace or duplicate `haywire share`'s own Detect step — pip-dependency drift stays exclusively a Share-flow concern.
- Nothing is written to `haybale.toml` as a side effect of clicking Refresh. Only the dialog's existing Save Changes action writes.
- Refresh never removes an entry automatically. A currently-selected-but-no-longer-detected entry is surfaced as a warning; the user deletes the chip themselves if they agree.
- The Refresh button is disabled (with a tooltip) when the library has no discoverable module directory. Unresolved imports (`DetectedDeps.unresolved`) are not surfaced in this dialog.
- `detect_share_drift()` must remain backward compatible: existing callers (`haywire share`, `haywire deps check`, `results.py`, `pipeline.py`) call it with no `libraries` argument and must keep working unchanged.
- Every new/modified docstring or comment must say `haybale.toml`'s `linked_libraries`, never `@library(dependencies=[...])` — that decorator kwarg was removed and now raises `TypeError` (ADR-0025).

---

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/publishing/drift/model.py` | Add `decorator_unused` field + docstring to `DepDrift` (modify) |
| `packages/haywire-core/src/haywire/core/publishing/drift/detect.py` | Add injectable `libraries` param to `detect_share_drift()`; compute `decorator_unused` (modify) |
| `tests/test_share_drift.py` | Tests for `decorator_unused` and the injectable `libraries` param (modify) |
| `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py` | Replace read-only `linked_libraries` label with editable multi-select + Refresh button (modify) |
| `tests/marketplace/test_overview_edit_dialog_linked_libraries.py` | New tests for the multi-select + Refresh behavior (create) |
| `docs/haybale/marketplace/haybale-marketplace-arch.md` | Rewrite §6 to describe the new detect-at-edit-time flow, with an explicit non-goal line (modify) |
| `docs/reference/glossary.md` | Add/update entries for `decorator_unused` and the edit-dialog Refresh flow (modify) |

---

### Task 1: `DepDrift.decorator_unused` — the reverse-direction field

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/publishing/drift/model.py`
- Test: `tests/test_share_drift.py`

**Interfaces:**
- Consumes: nothing new — pure dataclass field addition.
- Produces: `DepDrift.decorator_unused: list[str]` — declared `linked_libraries` entries with no matching detected import. Consumed by Task 2 (`detect_share_drift`) and Task 4 (the editor).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_share_drift.py` (new section, keep existing tests untouched):

```python
@pytest.mark.unit
def test_depdrift_decorator_unused_defaults_empty() -> None:
    drift = DepDrift(lib_dir=Path("/fake"))
    assert drift.decorator_unused == []


@pytest.mark.unit
def test_depdrift_decorator_unused_does_not_count_as_drift() -> None:
    drift = DepDrift(lib_dir=Path("/fake"), decorator_unused=["haybale_old"])
    assert drift.has_drift is False
    assert drift.has_findings is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_share_drift.py -k decorator_unused -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'decorator_unused'`

- [ ] **Step 3: Implement the field**

In `packages/haywire-core/src/haywire/core/publishing/drift/model.py`, replace the whole file:

```python
"""The `DepDrift` data model — no logic, just the shape of a drift result."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DepDrift:
    """What one library's declarations and its actual imports say about each other.

    All lists are sorted. Only ``pyproject_missing`` is drift: an import the
    published manifest does not declare, so a consumer installs the library and
    it fails on import. Everything else is a *fact about the library*, and each
    is handled differently:

    * ``decorator_missing`` — registered haywire libraries the source imports
      that ``haybale.toml``'s ``linked_libraries`` does not list. Applied
      AUTOMATICALLY, never offered as a choice, because there is nothing to
      decide: ``detect_deps`` only emits a name here when the source imports it
      AND it resolves to an installed, registered library, so the entry is
      provably true. It carries no version specifier, narrows nothing for
      consumers, and its only effects are hot-reload scope tracking and the
      marketplace's enable/disable gating. Reported rather than silent, though
      — it edits a hand-authored file (``haybale.toml``).
    * ``decorator_unused`` — declared ``linked_libraries`` entries with no
      matching detected import. The reverse of ``decorator_missing``. Never
      removed automatically, same reasoning as ``unused_declarations``: a
      dynamic import ``detect_deps`` cannot see looks exactly like an unused
      declaration, so acting on this without asking would break hot-reload
      scope tracking for a dependency that is genuinely still needed.
    * ``unused_declarations`` — declared but not imported. Inert for consumers;
      common for transitive deps and optional features. Removing is a decision,
      never automatic, because ``detect_deps`` cannot see dynamic imports.
    * ``pyproject_version_lag`` — ``(dist_name, declared_floor,
      installed_version)`` for declared floors below what is installed. NOT
      drift: the correct floor is the lowest version that still works, which
      requires resolving and testing candidates. Static scanning cannot reach
      it, so "installed is newer" is an observation that time passed, not
      evidence the declaration is wrong. Raising it on that basis would narrow
      consumer compatibility from the author's dev-machine state.
    * ``unresolved`` — imports that mapped to no distribution, usually dynamic.

    Consequently ``has_drift`` counts ``pyproject_missing`` only: you cannot
    refuse to publish over something the tool fixes unconditionally.
    """

    lib_dir: Path
    pyproject_missing: list[str] = field(default_factory=list)
    decorator_missing: list[str] = field(default_factory=list)
    decorator_unused: list[str] = field(default_factory=list)
    unused_declarations: list[str] = field(default_factory=list)
    pyproject_version_lag: list[tuple[str, str, str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True iff an imported distribution is undeclared — the breaking state.

        Excludes ``decorator_missing`` and ``decorator_unused``: both are
        facts about ``linked_libraries``, never states the author is required
        to resolve before publishing.
        """
        return bool(self.pyproject_missing)

    @property
    def has_findings(self) -> bool:
        """True iff the detect report has anything at all to show for this library."""
        return bool(
            self.pyproject_missing
            or self.decorator_missing
            or self.decorator_unused
            or self.unused_declarations
            or self.pyproject_version_lag
            or self.unresolved
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_share_drift.py -k decorator_unused -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full drift test file to check nothing broke**

Run: `uv run pytest tests/test_share_drift.py -v`
Expected: PASS (all — existing tests construct `DepDrift` with keyword args only, so the new field with a default is additive)

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/publishing/drift/model.py tests/test_share_drift.py
git commit -m "feat(drift): add DepDrift.decorator_unused — reverse linked_libraries drift"
```

---

### Task 2: Compute `decorator_unused` in `detect_share_drift()` + injectable library source

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/publishing/drift/detect.py`
- Test: `tests/test_share_drift.py`

**Interfaces:**
- Consumes: `DepDrift.decorator_unused` (Task 1), `DetectedDeps.library_decorator` (existing, from `haywire.core.library.dep_detect.detect_deps`), `HaywireLibrarySource` protocol (existing, from `haywire.core.library.dep_detect`).
- Produces: `detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift` — the new keyword-only `libraries` param, defaulting to `EntryPointLibrarySource()` when omitted. Consumed by Task 4 (the editor passes `manager.registry`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_share_drift.py`, after `test_drift_decorator_missing_registered_library`:

```python
@pytest.mark.unit
def test_drift_decorator_unused_when_declared_but_not_imported(tmp_path: Path, monkeypatch) -> None:
    """linked_libraries declares a library the source no longer imports —
    surfaced as decorator_unused, not auto-removed."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haywire-core~=0.0.1"],
        decorator_deps=["haybale_core"],  # declared...
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",  # ...but not imported
    )
    drift = detect_share_drift(lib)
    assert "haybale_core" in drift.decorator_unused
    assert drift.decorator_missing == []
    assert drift.has_drift is False
    assert drift.has_findings is True


@pytest.mark.unit
def test_drift_decorator_unused_empty_when_still_imported(tmp_path: Path, monkeypatch) -> None:
    """A declared linked_libraries entry that is still imported is not flagged."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haywire-core~=0.0.1", "haybale-core~=0.0.1"],
        decorator_deps=["haybale_core"],
        init_body_imports=(
            "from haywire.core.node.registry import NodeRegistry\nfrom haybale_core import types\n"
        ),
    )
    drift = detect_share_drift(lib)
    assert drift.decorator_unused == []


@pytest.mark.unit
def test_detect_share_drift_accepts_injected_library_source(tmp_path: Path, monkeypatch) -> None:
    """A caller with a live registry (e.g. the marketplace editor) can inject
    it instead of relying on EntryPointLibrarySource — same as detect_deps
    itself already allows via its `libraries` param."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haywire-core~=0.0.1"],
        decorator_deps=[],
        init_body_imports="from haybale_fake_dep import x\n",
    )
    fake_source = _FakeLibrarySource(["haybale-fake-dep"])
    # EntryPointLibrarySource would not know about haybale-fake-dep (it isn't
    # really installed), so decorator_missing would be empty by default —
    # injecting the fake source is what makes it appear, proving the param
    # is actually used rather than ignored.
    drift = detect_share_drift(lib, libraries=fake_source)
    assert "haybale_fake_dep" in drift.decorator_missing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_share_drift.py -k "decorator_unused or injected_library_source" -v`
Expected: FAIL — `decorator_unused` tests fail with `AssertionError` (field always empty, logic not implemented yet); `injected_library_source` test fails with `TypeError: detect_share_drift() got an unexpected keyword argument 'libraries'`

- [ ] **Step 3: Implement**

In `packages/haywire-core/src/haywire/core/publishing/drift/detect.py`, replace the whole file:

```python
"""Dependency-drift detection (Plan E follow-up, piece 3).

`haywire share` is the publish boundary: whatever the user emits here is what
downstream consumers will install. If the library's pyproject.toml or its
``haybale.toml`` ``linked_libraries`` are out of sync with the actual source
imports, the published library will fail to install or to enable for
consumers. The gate below detects that drift at share time so the user can fix
it before emitting. The Library Overview Editor's Edit dialog reuses the same
function for its Refresh button, scoped to `linked_libraries` only — see
:func:`detect_share_drift`'s ``libraries`` param.
"""

from pathlib import Path

from haywire.core.library.decorator_io import norm_dep
from haywire.core.library.dep_detect import (
    DetectedDeps,
    EntryPointLibrarySource,
    HaywireLibrarySource,
    detect_deps,
    find_module_dir,
)
from haywire.core.publishing.drift.model import DepDrift
from haywire.core.publishing.drift.versionspec import (
    _parse_floor_spec,
    _strip_specifier,
    version_lags,
)
from haywire.core.publishing.manifest.deps import _read_library_dependencies
from haywire.core.publishing.manifest.reader import read_manifest_lenient

_norm_dep = norm_dep


def detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift:
    """Compute the drift between detected and declared dependencies for one library.

    Drift surfaces only ``missing`` entries — items that detect_deps found in
    the source but are NOT declared in the library's pyproject.toml or
    ``haybale.toml``'s ``linked_libraries``. Extra declarations (declared but
    unused) are not flagged as drift: they are common (transitive deps,
    optional features) and false positives would block users unfairly.
    `share` is about correctness for consumers, which means "everything
    imported must be declared," not "everything declared must be imported."
    They are still reported, on ``unused_declarations`` and
    ``decorator_unused`` respectively, as facts the caller may act on.

    ``libraries`` is the :class:`HaywireLibrarySource` used to decide "is this
    distribution a registered haywire library" for the ``linked_libraries``
    side of the comparison. Defaults to :class:`EntryPointLibrarySource` so
    the gate works without a live haywire registry (`haywire share`,
    `haywire deps check`). A caller that already holds a live
    ``LibraryRegistry`` — the marketplace editor — should pass it here
    instead, since it reflects installed/enabled state more accurately than
    entry-point metadata.

    Returns an empty :class:`DepDrift` when no module dir is found (the
    library has no inspectable source). Callers should still treat that as
    "nothing to gate" rather than an error.

    Degrades to treating declarations as empty (surfacing everything as
    missing) not just on unparsable TOML but also on an invalid
    ``[tool.haywire].os`` declaration, since both go through
    :func:`read_manifest_lenient`.
    """
    if libraries is None:
        libraries = EntryPointLibrarySource()
    detected: DetectedDeps = detect_deps(lib_dir, libraries=libraries)

    # Read current declarations. Lenient: a malformed or unreadable manifest
    # treats declarations as empty so the drift report still surfaces what's
    # missing, rather than crashing a read-only report.
    pyproject_data = read_manifest_lenient(lib_dir)
    declared_pyproject: list[str] = list(pyproject_data.get("project", {}).get("dependencies", []))

    module_dir = find_module_dir(lib_dir)
    declared_decorator: list[str] = []
    if module_dir:
        declared_decorator = _read_library_dependencies(module_dir)

    # Convert declared_pyproject specs ("haywire-core~=0.0.1") to bare dist names
    # so we can compare against detected entries by name.
    decl_py_names = {_strip_specifier(s) for s in declared_pyproject}
    detected_py_names = {_strip_specifier(s) for s in detected.pyproject}
    pyproject_missing = sorted(detected_py_names - decl_py_names)

    # Declared but never imported. Reported, never removed automatically: a
    # dynamic import detect_deps cannot see looks exactly like an unused
    # declaration, so acting on this without asking would break the library.
    unused_declarations = sorted(decl_py_names - detected_py_names)

    # linked_libraries entries round-trip as bare module names in detect_deps
    # output; _read_library_dependencies already converts to pip-package form.
    # Re-normalize both sides so "haybale_core" and "haybale-core" compare
    # equal.
    decl_dec_norm = {_norm_dep(d) for d in declared_decorator}
    detected_dec_norm = {_norm_dep(d) for d in detected.library_decorator}
    decorator_missing = sorted(detected_dec_norm - decl_dec_norm)
    # The reverse: declared but no longer detected as imported. Reported only
    # — see DepDrift.decorator_unused for why this is never auto-removed.
    decorator_unused = sorted(decl_dec_norm - detected_dec_norm)

    pyproject_version_lag = _detect_pyproject_version_lag(declared_pyproject, libraries=libraries)

    return DepDrift(
        lib_dir=lib_dir,
        pyproject_missing=pyproject_missing,
        decorator_missing=decorator_missing,
        decorator_unused=decorator_unused,
        unused_declarations=unused_declarations,
        pyproject_version_lag=pyproject_version_lag,
        unresolved=list(detected.unresolved),
    )


def _detect_pyproject_version_lag(
    declared: list[str],
    *,
    libraries: HaywireLibrarySource,
) -> list[tuple[str, str, str]]:
    """Report declared haybale-* deps whose floor sits below the installed version.

    A fact, not a finding: see :class:`DepDrift`. Nothing here is ever raised
    automatically, and this does not count toward ``has_drift``.

    Scoped to registered haywire libraries and to the ``~=``/``>=``/``>``
    operators. ``==`` and ``<`` express deliberate intent that "lag" does not
    describe.
    """
    import importlib.metadata as _meta

    haybale_dists: set[str] = set()
    for lib_id in libraries.list_names():
        dist = libraries.get_library_distribution_name(lib_id)
        if dist:
            haybale_dists.add(dist)

    out: list[tuple[str, str, str]] = []
    for spec in declared:
        dist_name = _strip_specifier(spec)
        if dist_name not in haybale_dists:
            continue
        parsed = _parse_floor_spec(spec)
        if parsed is None:
            continue
        _op, declared_floor = parsed
        try:
            installed = _meta.version(dist_name)
        except _meta.PackageNotFoundError:
            continue
        if version_lags(declared_floor, installed):
            out.append((dist_name, declared_floor, installed))
    return sorted(out)
```

Note: `HaywireLibrarySource` must be importable from `haywire.core.library.dep_detect` — it already is (it's the `@runtime_checkable` `Protocol` defined at the top of that module, per the earlier `dep_detect.py` read). `_detect_pyproject_version_lag`'s type hint changes from `EntryPointLibrarySource` to `HaywireLibrarySource` since it now may receive either.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_share_drift.py -v`
Expected: PASS (all — including the 3 new tests and every pre-existing one, since `libraries=None` defaulting to `EntryPointLibrarySource()` preserves old behavior exactly)

- [ ] **Step 5: Run the dependent test files that call `detect_share_drift`**

Run: `uv run pytest tests/test_dep_detect.py -v`
Expected: PASS (unaffected — `detect_deps` itself is untouched)

Run: `uv run mypy packages/haywire-core/src/haywire/core/publishing/drift/`
Expected: no new errors

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/publishing/drift/detect.py tests/test_share_drift.py
git commit -m "feat(drift): injectable library source + decorator_unused in detect_share_drift"
```

---

### Task 3: Fix the stale docstring comment in `dep_detect.py`'s `DetectedDeps` (missed in the earlier cleanup pass)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/dep_detect.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new — pure documentation fix, no behavior change.

- [ ] **Step 1: Check the current line**

Run: `grep -n "library_decorator" packages/haywire-core/src/haywire/core/library/dep_detect.py`

Confirm line 107 still reads:
```python
    library_decorator: list[str] = field(default_factory=list)
```
with no trailing comment (the docstring above the class, lines 100-105, already documents it in class-level prose — this task only needs to check the class docstring itself references `linked_libraries` correctly).

- [ ] **Step 2: Read the class docstring**

Run: `sed -n '100,111p' packages/haywire-core/src/haywire/core/library/dep_detect.py`

If it already says `linked_libraries` (fixed in the earlier session), skip to Step 4. If it still says `@library(dependencies=[...])` decorator, proceed to Step 3.

- [ ] **Step 3: Fix if needed**

If stale, edit the docstring to read (matching the fix already applied to the module-level docstring in the same file):

```python
@dataclass(frozen=True)
class DetectedDeps:
    """The classified result of scanning a library's imports.

    Both ``library_decorator`` and ``pyproject`` are deterministically sorted.
    ``library_decorator`` entries are underscored module names destined for
    ``haybale.toml``'s ``linked_libraries``, despite the field's name (kept
    for backward compatibility with existing callers).
    """
```

- [ ] **Step 4: Verify no other stale references remain in this file**

Run: `grep -n "@library(dependencies" packages/haywire-core/src/haywire/core/library/dep_detect.py`
Expected: no output

- [ ] **Step 5: Commit (only if Step 3 made a change)**

```bash
git add packages/haywire-core/src/haywire/core/library/dep_detect.py
git commit -m "docs(dep_detect): clarify DetectedDeps.library_decorator targets linked_libraries"
```

If Step 2 found nothing stale, skip this task's commit entirely — note in the task tracker that Task 3 was a no-op verification.

---

### Task 4: Editable `linked_libraries` multi-select + Refresh button in the Edit dialog

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`
- Test: `tests/marketplace/test_overview_edit_dialog_linked_libraries.py` (create)

**Interfaces:**
- Consumes: `detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift` (Task 2), `DepDrift.decorator_missing` / `DepDrift.decorator_unused` (Task 1), `find_module_dir(lib_dir: Path) -> Path | None` (existing, `haywire.core.library.dep_detect`), `manager.registry: LibraryRegistry` (existing — satisfies `HaywireLibrarySource` structurally), `read_haybale_toml_lenient(package_dir: Path) -> dict` (existing).
- Produces: `build_edit_dialog(...)` unchanged signature; the identity dict passed to `on_save` now includes `"linked_libraries": list[str]`, consumed by the existing `manager.update_library_identity` → `write_haybale_fields` path (already accepts this key — no changes needed there).

- [ ] **Step 1: Write the failing tests**

Create `tests/marketplace/test_overview_edit_dialog_linked_libraries.py`:

```python
"""Tests for the linked_libraries multi-select and Refresh button in the
Library Overview Editor's Edit dialog.

Refresh only ever ADDS chips (from DepDrift.decorator_missing) and WARNS
about stale ones (DepDrift.decorator_unused) — it never writes to disk and
never removes a chip automatically. Only the dialog's existing Save Changes
action persists anything, via the identity dict's "linked_libraries" key.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haybale_marketplace.editors._overview_edit_dialog import (
    _refresh_linked_libraries,
)


class _FakeRegistry:
    """Minimal HaywireLibrarySource stand-in for LibraryRegistry."""

    def __init__(self, dists: dict[str, str]) -> None:
        self._dists = dists  # lib_id -> dist name

    def list_names(self) -> list[str]:
        return list(self._dists.keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._dists.get(library_id)


def _make_library(
    tmp_path: Path,
    *,
    module_name: str = "haybale_fake",
    linked_libraries: list[str] | None = None,
    init_body_imports: str = "",
) -> Path:
    """Scaffold a fake library dir with a haybale.toml and one import-bearing module.

    Mirrors the fixture in tests/test_share_drift.py, adapted for the
    haybale.toml-only shape (no @library decorator needed for detect_deps,
    which scans imports, not the decorator call).
    """
    lib_dir = tmp_path / "haybale-fake"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-fake"\nversion = "0.0.1"\n')
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir()
    linked = linked_libraries or []
    linked_toml = "[" + ", ".join(f'"{n}"' for n in linked) + "]"
    (pkg_dir / "haybale.toml").write_text(
        'name = "haybale-fake"\nid = "fake"\nlabel = "Fake"\n'
        f"linked_libraries = {linked_toml}\n"
    )
    (pkg_dir / "__init__.py").write_text(f"{init_body_imports}\n")
    return lib_dir


@pytest.mark.unit
def test_refresh_adds_missing_linked_library(tmp_path: Path) -> None:
    lib_dir = _make_library(
        tmp_path,
        linked_libraries=[],
        init_body_imports="from haybale_dep import x\n",
    )
    registry = _FakeRegistry({"dep": "haybale-dep"})

    result = _refresh_linked_libraries(lib_dir, current=[], libraries=registry)

    assert result.added == ["haybale_dep"]
    assert result.stale == []


@pytest.mark.unit
def test_refresh_warns_on_stale_entry_without_removing(tmp_path: Path) -> None:
    lib_dir = _make_library(
        tmp_path,
        linked_libraries=["haybale_old"],
        init_body_imports="",  # no longer imported
    )
    registry = _FakeRegistry({"old": "haybale-old"})

    result = _refresh_linked_libraries(lib_dir, current=["haybale_old"], libraries=registry)

    assert result.added == []
    assert result.stale == ["haybale_old"]


@pytest.mark.unit
def test_refresh_merges_additions_into_current_without_duplicating(tmp_path: Path) -> None:
    lib_dir = _make_library(
        tmp_path,
        linked_libraries=["haybale_dep"],
        init_body_imports="from haybale_dep import x\nfrom haybale_new import y\n",
    )
    registry = _FakeRegistry({"dep": "haybale-dep", "new": "haybale-new"})

    result = _refresh_linked_libraries(lib_dir, current=["haybale_dep"], libraries=registry)

    assert result.added == ["haybale_new"]
    assert sorted(result.merged) == ["haybale_dep", "haybale_new"]


@pytest.mark.unit
def test_refresh_returns_no_module_dir_when_source_missing(tmp_path: Path) -> None:
    lib_dir = tmp_path / "haybale-empty"
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-empty"\nversion = "0.0.1"\n')
    registry = _FakeRegistry({})

    result = _refresh_linked_libraries(lib_dir, current=[], libraries=registry)

    assert result.no_module_dir is True
    assert result.added == []
    assert result.stale == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/marketplace/test_overview_edit_dialog_linked_libraries.py -v`
Expected: FAIL — `ImportError: cannot import name '_refresh_linked_libraries'`

- [ ] **Step 3: Implement `_refresh_linked_libraries` and wire the multi-select + button**

In `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`:

First, update the module docstring and imports. Replace:

```python
"""Edit-metadata dialog for LibraryOverviewEditor.

Writes ``haybale.toml`` and nothing else — no ``uv sync``, no module eviction,
no restart. The runtime reads that file at the point of use, so the next render
shows the change.

What this dialog deliberately cannot write, and why:

* ``name`` / ``id`` — immutable. They key every saved graph's node references
  and every consumer's ``install_spec``. Renaming runs from the CLI with studio
  stopped, because it rewrites installed packages and runs ``uv sync``.
* ``version`` / ``origin`` — the share wizard writes these from facts it
  observes (the lockstep bump, the git remote), and would overwrite anything
  typed here on the next publish.
* ``[deprecated]`` — retiring a library is rare and deliberate, so it is
  hand-edited in the file rather than given a control that invites a stray
  click.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from nicegui import ui

from haywire.core.library.haybale_toml import read_display, read_haybale_toml_lenient
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.modals import info_modal

from haybale_marketplace.library_origin import is_project_library

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)
```

with:

```python
"""Edit-metadata dialog for LibraryOverviewEditor.

Writes ``haybale.toml`` and nothing else — no ``uv sync``, no module eviction,
no restart. The runtime reads that file at the point of use, so the next render
shows the change.

What this dialog deliberately cannot write, and why:

* ``name`` / ``id`` — immutable. They key every saved graph's node references
  and every consumer's ``install_spec``. Renaming runs from the CLI with studio
  stopped, because it rewrites installed packages and runs ``uv sync``.
* ``version`` / ``origin`` — the share wizard writes these from facts it
  observes (the lockstep bump, the git remote), and would overwrite anything
  typed here on the next publish.
* ``[deprecated]`` — retiring a library is rare and deliberate, so it is
  hand-edited in the file rather than given a control that invites a stray
  click.

``linked_libraries`` is the one exception to "no detection here": it is a
provably-true fact (see ``DepDrift.decorator_missing``'s docstring), not an
authored decision like pip dependencies, so a Refresh button may detect and
propose it directly — see :func:`_refresh_linked_libraries`. This does NOT
extend to pip dependencies: ``[project] dependencies`` stays exclusively a
``haywire share`` concern (see marketplace-arch.md §6).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from nicegui import ui

from haywire.core.library.dep_detect import HaywireLibrarySource, find_module_dir
from haywire.core.library.haybale_toml import read_display, read_haybale_toml_lenient
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.core.publishing.drift.detect import detect_share_drift
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.modals import info_modal

from haybale_marketplace.library_origin import is_project_library

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RefreshResult:
    """Outcome of one Refresh click — never written to disk by this module."""

    added: list[str] = field(default_factory=list)
    """Newly detected linked_libraries entries, not yet in `current`."""
    stale: list[str] = field(default_factory=list)
    """Entries in `current` no longer detected as imported. Never auto-removed."""
    merged: list[str] = field(default_factory=list)
    """`current` + `added`, deduplicated and sorted — the value to put back
    into the multi-select. Equals `current` (unchanged) when `added` is empty."""
    no_module_dir: bool = False
    """True when the library has no inspectable source — Refresh has nothing to scan."""


def _refresh_linked_libraries(
    lib_dir: Path,
    *,
    current: list[str],
    libraries: HaywireLibrarySource,
) -> _RefreshResult:
    """Detect linked_libraries drift for one library, in both directions.

    Pure — no writes. `added` and `stale` are computed via
    :func:`detect_share_drift`, scoped to its `decorator_missing` /
    `decorator_unused` fields only; the pyproject-dependency fields on the
    returned `DepDrift` are deliberately ignored here, since pip-dependency
    authoring stays out of this dialog (see the module docstring).
    """
    if find_module_dir(lib_dir) is None:
        return _RefreshResult(no_module_dir=True)

    drift = detect_share_drift(lib_dir, libraries=libraries)
    current_set = set(current)
    added = sorted(n for n in drift.decorator_missing if n not in current_set)
    merged = sorted(current_set | set(added))
    return _RefreshResult(added=added, stale=list(drift.decorator_unused), merged=merged)
```

Next, replace the `linked_libraries` read-only display block. Find:

```python
        # linked_libraries is maintained by `haywire share`'s drift detector,
        # which can prove what a library actually imports.
        ui.label(
            f"Linked libraries: {', '.join(lib.identity.linked_libraries or []) or '(none)'}"
            " (maintained by Share)"
        ).classes("text-xs hw-text-dim")
```

Replace with:

```python
        # linked_libraries is editable here, unlike pip dependencies: it is a
        # provably-true fact about what the source imports (see the module
        # docstring), so Refresh may detect and propose additions directly.
        current_linked = list(
            read_haybale_toml_lenient(Path(lib.identity.folder_path)).get("linked_libraries") or []
        )
        linked_select = (
            hui.select_field(
                options={n: n for n in current_linked},
                value=current_linked,
                multiple=True,
                label="Linked libraries",
                in_popup=True,
            )
            .classes("w-full")
            .props("use-chips new-value-mode=add-unique")
        )

        _module_dir = find_module_dir(Path(lib.identity.folder_path))

        def _do_refresh(sel=linked_select, m=manager, lib_dir=Path(lib.identity.folder_path)):
            result = _refresh_linked_libraries(lib_dir, current=list(sel.value or []), libraries=m.registry)
            if result.no_module_dir:
                ui.notify("No inspectable source found — nothing to detect.", type="warning")
                return
            # Merge additions into the select's options AND value: ui.select
            # only shows chips for values present in `options`.
            merged_options = {n: n for n in result.merged}
            sel.set_options(merged_options, value=result.merged)
            if result.added:
                ui.notify(f"Added: {', '.join(result.added)}", type="positive")
            else:
                ui.notify("Nothing new detected.", type="info")
            if result.stale:
                ui.notify(
                    f"No longer detected as imported: {', '.join(result.stale)}. "
                    "Remove the chip yourself if this is correct.",
                    type="warning",
                )

        with ui.row().classes("items-center gap-2"):
            refresh_button = ui.button(
                "Refresh",
                icon="refresh",
                on_click=_do_refresh,
            ).props("size=sm flat")
            if _module_dir is None:
                refresh_button.disable()
                refresh_button.tooltip("No inspectable source found for this library.")
```

Finally, update `_save()` to include `linked_libraries` in the identity dict. Find:

```python
        async def _save():
            # Only the keys this dialog owns. write_haybale_fields edits in
            # place, so an omitted key is left alone rather than erased — which
            # is why linked_libraries and [deprecated] survive a save untouched.
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "homepage_url": url_input.value.strip(),
                "documentation_url": docs_url_input.value.strip(),
                "issues_url": issues_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
            }
```

Replace with:

```python
        async def _save():
            # Only the keys this dialog owns. write_haybale_fields edits in
            # place, so an omitted key is left alone rather than erased — which
            # is why [deprecated] survives a save untouched. linked_libraries
            # IS owned here now (unlike pip dependencies) — see module docstring.
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "homepage_url": url_input.value.strip(),
                "documentation_url": docs_url_input.value.strip(),
                "issues_url": issues_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
                "linked_libraries": list(linked_select.value or []),
            }
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/marketplace/test_overview_edit_dialog_linked_libraries.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full marketplace test suite to check for regressions**

Run: `uv run pytest tests/marketplace/ tests/test_library_manager_marketplace_writes.py tests/marketplace/test_update_identity_quoting.py -v`
Expected: PASS — `test_update_library_identity_writes_haybale_toml` and its sibling in `test_update_identity_quoting.py` are unaffected since they call `manager.update_library_identity` directly with a hand-built dict (not through the dialog's `_save`), and `linked_libraries` was already an `EDITABLE_FIELD` before this change.

- [ ] **Step 6: Type-check**

Run: `uv run mypy barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`
Expected: no new errors

- [ ] **Step 7: Lint**

Run: `uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py tests/marketplace/test_overview_edit_dialog_linked_libraries.py`
Run: `uv run ruff format --check barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py tests/marketplace/test_overview_edit_dialog_linked_libraries.py`
Expected: both clean. If format check fails, run `uv run ruff format barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py tests/marketplace/test_overview_edit_dialog_linked_libraries.py` and re-check.

- [ ] **Step 8: Manual verification in the running studio**

Run: `uv run haywire` (in a project with at least one heap/project-local library under `barn/`)

1. Open the Library Overview Editor for a project-local library, click Edit.
2. Confirm "Linked libraries" now renders as a chip multi-select (not a read-only label), pre-populated with the current `linked_libraries`.
3. Add a genuine undeclared import to the library's source (e.g. `import haybale_core` somewhere it wasn't imported before), save the file, click Refresh in the dialog (may need to reopen the dialog first since the source edit happened outside it).
4. Confirm a new chip appears and a "Added: ..." notification shows.
5. Remove that import from source, click Refresh again.
6. Confirm the chip is NOT removed automatically, and a warning notification names it as no-longer-detected.
7. Manually delete the chip, click Save Changes, confirm `haybale.toml` on disk no longer lists it.
8. For a library with no module dir (or temporarily rename its package dir to break `find_module_dir`), confirm the Refresh button renders disabled with a tooltip.

- [ ] **Step 9: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py tests/marketplace/test_overview_edit_dialog_linked_libraries.py
git commit -m "feat(marketplace): editable linked_libraries multi-select with Refresh detection"
```

---

### Task 5: Rewrite marketplace-arch.md §6 to describe the new flow

**Files:**
- Modify: `docs/haybale/marketplace/haybale-marketplace-arch.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Replace §6**

In `docs/haybale/marketplace/haybale-marketplace-arch.md`, replace the entire `## 6. Drift detection at edit time` section (currently lines 362–381, verify the exact range first with `grep -n "^## 6\.\|^## 7\." docs/haybale/marketplace/haybale-marketplace-arch.md` since earlier edits in this session may have shifted line numbers) with:

```markdown
## 6. Linked-libraries detection at edit time

The Library Overview Editor's Edit dialog can detect `linked_libraries`
drift directly, without going through `haywire share`. This is narrower than
it sounds: it touches exactly one field, in one direction that matters and
one that only warns.

**Why this field and not others.** `haybale.toml`'s `linked_libraries` is the
one dependency-shaped field the editor authors directly — every other
dependency concern (`[project] dependencies` in the library's pyproject)
stays exclusively a `haywire share` concern ([§5](#5-the-install--uninstall-pipeline)
does not touch it either). The distinction is decision vs. fact: a pip
dependency's version floor is an authored choice with real tradeoffs: Union
vs. Replace, which floor to pin, whether a lagging version matters. A missing
`linked_libraries` entry is provably true — `detect_deps` only reports one
when the source imports it *and* it resolves to an installed, registered
haywire library — so there is nothing to decide, only to confirm. Re-adding
detection for the fact-shaped field does not reopen the two-writer drift bug
that removed the old Union/Replace button (see [ADR reference below](#not-a-return-of-the-old-detect-dependencies-button)); adding it back for the
decision-shaped field would.

### How it works

1. The Edit dialog's "Linked libraries" field is a multi-select (chips), not
   a read-only label — the author can add or remove entries directly, same
   control shape as the `os` field.
2. A **Refresh** button runs `detect_share_drift(lib_dir, libraries=manager.registry)`
   — the same function `haywire share` uses, passed the studio's live
   `LibraryRegistry` instead of the CLI's entry-point-derived one, since the
   editor already has it.
3. Two outcomes, handled asymmetrically:

   | Finding | Field | Effect |
   | --- | --- | --- |
   | Detected import, not yet declared | `decorator_missing` | Added as a new chip immediately |
   | Declared, no longer detected as imported | `decorator_unused` | Warned about; never removed — the author deletes the chip themselves if they agree |

4. Nothing is written to disk by Refresh. The multi-select's value is staged
   in memory, same as every other field in this dialog; only clicking **Save
   Changes** writes `haybale.toml`, through the same `write_haybale_fields`
   path every other field uses.

The asymmetry in step 3 mirrors `unused_declarations` on the pyproject side
([§2.5](#25-conflict-resolution) is unrelated — see
[`DepDrift`](../../reference/glossary.md#library-pyproject) instead): a
missing entry is provably correct to add, but a no-longer-imported entry
looks exactly like a dynamic import the static scanner cannot see, so acting
on it without the author's confirmation could silently break hot-reload scope
tracking for a dependency that is still genuinely needed.

### Not a return of the old Detect Dependencies button

An earlier version of this dialog had a "Detect Dependencies" button that
scanned *both* `linked_libraries` and pip dependencies together, offering
Union/Replace across both. It was removed because the pip-dependency side
gave two uncoordinated writers to the same `[project] dependencies` list —
this button, and the Share wizard's own writer — which is what let the
framework floor get silently clobbered. That bug never existed on the
`linked_libraries` side: `decorator_missing` was already "applied
automatically, never a choice" even inside the Share flow, so a second
surface detecting the same provably-true fact does not recreate the
conflict. This feature is deliberately scoped to never grow pip-dependency
detection back into this dialog — that stays `haywire share`'s job, full
stop.
```

- [ ] **Step 2: Update the doc's `see-also` frontmatter if needed**

Run: `grep -n "^see-also:" -A 10 docs/haybale/marketplace/haybale-marketplace-arch.md`

If `../../reference/glossary.md` is not already listed, add it. (It already is, per the file read earlier in this session — verify, don't blindly add a duplicate.)

- [ ] **Step 3: Preview the doc renders cleanly**

Run: `uv run mkdocs build --strict 2>&1 | grep -i "haybale-marketplace-arch\|warning" | head -30`
Expected: no new warnings referencing this file (broken anchor links, etc.)

- [ ] **Step 4: Commit**

```bash
git add docs/haybale/marketplace/haybale-marketplace-arch.md
git commit -m "docs(marketplace-arch): rewrite §6 for linked_libraries detect-at-edit-time"
```

---

### Task 6: Glossary updates

**Files:**
- Modify: `docs/reference/glossary.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Add a `decorator_unused` glossary entry**

Find the `DepDrift` row (search `grep -n "\*\*DepDrift\*\*" docs/reference/glossary.md`) and update its field list to mention `decorator_unused`. Also add a new row directly after the existing **Unused declaration** row:

```markdown
| **Decorator-unused** | A `linked_libraries` entry (`decorator_unused` on `DepDrift`) with no matching detected import — the reverse of **Decorator registration**. Reported, never auto-removed: a dynamic import `detect_deps` cannot see looks identical to a genuinely stale entry, so removing it without the author's confirmation risks silently breaking hot-reload scope tracking for a dependency still in use. Surfaced by the Edit dialog's Refresh button as a warning next to the multi-select chip. | unused decorator dep, stale linked library |
```

Update the `**DepDrift**` row's field list to read: `Fields: \`lib_dir\`, \`pyproject_missing\`, \`decorator_missing\`, \`decorator_unused\`, \`unused_declarations\`, \`pyproject_version_lag\`, \`unresolved\`.`

- [ ] **Step 2: Update the "one authoring path" line to name the exception explicitly**

Find (added in an earlier session on this same feature):

```
- A library's published manifest survives `haywire share` only if the **Three manifest layers** agree. The **Detect step** reports divergence; the Share flow's Review screen reconciles it. The Library Overview Editor is read-only for dependencies — one authoring path, not two.
```

Replace with:

```
- A library's published manifest survives `haywire share` only if the **Three manifest layers** agree. The **Detect step** reports divergence; the Share flow's Review screen reconciles it. The Library Overview Editor is read-only for **library pyproject** dependencies — one authoring path, not two. `linked_libraries` is the exception: the Edit dialog's Refresh button may detect and stage additions directly (never removals), because **Decorator registration** carries no author decision to protect against a second writer.
```

- [ ] **Step 3: Verify no stale `@library(dependencies` phrasing was reintroduced**

Run: `grep -n "@library(dependencies" docs/reference/glossary.md`
Expected: only the two existing "aliases to avoid" mentions (in the `linked_libraries` and `Decorator registration` rows), documenting the retired name — not new prose using it as current fact.

- [ ] **Step 4: Commit**

```bash
git add docs/reference/glossary.md
git commit -m "docs(glossary): add decorator_unused, note linked_libraries as the one editor-authored dependency field"
```

---

## Self-Review Notes

**Spec coverage against the 7 inquisition decisions:**

1. ✅ Q0 (decorator_missing/linked_libraries doesn't reopen "one authoring path") — encoded in Task 5's §6 rewrite and Task 6's glossary line.
2. ✅ Q1 (button next to the field, on-demand) — Task 4, Refresh button beside the multi-select.
3. ✅ Q2 (populate into pending state, Save Changes persists) — Task 4, `_do_refresh` only calls `sel.set_options(...)`, never `write_haybale_fields` directly; `_save()` reads `linked_select.value`.
4. ✅ Q3 (full multi-select, both directions, never auto-remove) — Task 1/2 (`decorator_unused`), Task 4 (`_refresh_linked_libraries`, warning notification, no auto-delete).
5. ✅ Q4 (reverse detection lives in `haywire-core`'s `DepDrift`, not forked into the marketplace plugin) — Task 1/2.
6. ✅ Q5 (live registry via `manager.registry`, injectable `libraries` param) — Task 2 (`libraries: HaywireLibrarySource | None = None`), Task 4 (`m.registry` passed in).
7. ✅ Q6 (no module dir → disabled button + tooltip; unresolved imports not surfaced) — Task 4, `_module_dir is None` branch; `_refresh_linked_libraries` never reads `drift.unresolved`.
8. ✅ Q7 (explicit non-goal in code + doc) — Task 4's module docstring addition, Task 5's "Not a return of the old Detect Dependencies button" subsection.

**Placeholder scan:** none found — every step has literal code, exact file paths, and runnable commands.

**Type consistency check:**
- `_refresh_linked_libraries(lib_dir: Path, *, current: list[str], libraries: HaywireLibrarySource) -> _RefreshResult` — used identically in Task 4's tests and implementation.
- `detect_share_drift(lib_dir: Path, *, libraries: HaywireLibrarySource | None = None) -> DepDrift` — Task 2 defines it, Task 4 calls it with the same keyword.
- `DepDrift.decorator_unused: list[str]` — Task 1 defines it, Task 2 populates it, Task 4/6 consume it. Consistent throughout.
- `_RefreshResult` fields (`added`, `stale`, `merged`, `no_module_dir`) — used consistently between Task 4's Step 1 tests and Step 3 implementation.

**Verified against the installed environment:** `nicegui.elements.select.Select.set_options` has signature `(self, options: list | dict, *, value: Any = Ellipsis) -> Self` in this venv, confirming Task 4 Step 3's `sel.set_options(merged_options, value=result.merged)` call is correct as written — no follow-up needed.
