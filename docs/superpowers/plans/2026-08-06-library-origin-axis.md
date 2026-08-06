# Library Origin Axis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give installed libraries a second, orthogonal classification axis — `LibraryOrigin` (framework / project_local / pypi / git / unknown) — alongside the existing `InstallType` (mechanism), and centralize "is this library protected from Disable/Uninstall" into one predicate that replaces scattered per-call-site checks.

**Architecture:** New pure-function module `haybale_marketplace/library_origin.py` owns the `LibraryOrigin` enum and `compute_library_origin()`. `is_project_library()` moves there from `_overview_edit_dialog.py` (which imports it back for its own unrelated use). Three existing call sites (`is_required()`, the Uninstall-button gate, the Edit-vs-Uninstall split) switch to reading `origin.is_protected`. `LibraryRegistry.disable_library()` (core) gains a self-contained FOLDER-mechanism guard — the one piece of protection core can compute without workspace context. `project_local_libraries()` (Farmhand's write-gate) is renamed to `project_writable_libraries()` with no behavior change.

**Tech Stack:** Python 3.12, pytest, no new dependencies.

## Global Constraints

- **Purely additive w.r.t. current protected-library behavior.** The set of libraries protected from Disable/Uninstall (FOLDER + project-local + has-dependents) must be identical before and after every task. This is a centralization refactor, not a policy change.
- **`LibraryOrigin.UNKNOWN` is never protected.** No-catalog-entry libraries (bare `pip install -e` outside the marketplace flow) stay exactly as disable/uninstallable as today.
- **No install-metadata parsing** (`direct_url.json` / `importlib.metadata`). Origin for a library with no catalog `Haybale` row resolves to `UNKNOWN`, never guessed.
- **Core (`haywire-core`) does not gain workspace-root awareness.** `LibraryRegistry`/`LibraryDiscovery` stay exactly as workspace-agnostic as they are today. All origin computation lives in `haybale_marketplace`.
- **The registry-layer `disable_library()` guard is FOLDER-only.** `project_local` protection stays UI-layer-only — this is a documented, accepted asymmetry (see spec), not something any task should try to close further.
- **`is_editable()` (`install_type.py`) is untouched.** It answers a mechanism question, not a protection question.
- **`project_writable_libraries()` keeps its current broader behavior** (all EDITABLE installs) — only the name changes.
- Full spec: [internals/handoff/library-origin-and-required-classification.md](../../../internals/handoff/library-origin-and-required-classification.md).
- Full glossary entries already written: `docs/reference/glossary.md` (**InstallType**, **Library Origin**, `is_project_library()`, `project_writable_libraries()`, two flagged ambiguities). No glossary work in this plan — it's done.
- Lint/type baseline before touching each area: `uv run ruff check <path>` and `uv run mypy <path>` per CLAUDE.md's pre-edit baseline rule (these are multi-file, signature-changing edits).

---

## Correction to the spec found during planning

The spec's "Where things live" section says badges render in "Library Overview / Library Browser." That's imprecise — verified against the actual code:

- **Library Overview Editor** (`library_overview_editor.py:385-393`) renders per-row `hui.tag()` badges: an install-type tag (mechanism) and, when a marketplace catalog entry exists, a source tag (`marketplace_pkg.source`, "pypi" or other). This is the one place mechanism/origin badges actually render.
- **Library Browser** (`library_browser_editor.py`) has NO per-row badges in its compact list items (`_library_item`, line 625) — no mechanism or origin tag at all. It has a "Required" **filter toggle/section** (`_filter_required`, purple lock icon, groups libraries into a Required list section) — not a per-row badge.

Task 4 below implements the origin badge only in the Overview Editor, matching what actually exists. The Browser's Required section already gets its protection logic centralized in Task 3 — it needs no new badge, because it never had one.

## Fact found during planning: `Haybale.source` DOES take the literal value `"local"` today

`library_browser_editor.py:568-577` synthesizes ad-hoc `Haybale(..., source="local", ...)` objects for `[[heaps]]` entries not yet installed, to list them in the "Available" section. This is unrelated to origin computation: `compute_library_origin()` (Task 1) only ever reads `Haybale.source` for an **installed** library's matched catalog row (via distribution-name lookup), never for one of these synthetic heap-preview objects, which don't correspond to an installed `LibraryInfo` at all. No task needs to special-case this, but it's worth knowing so a reader doesn't think `"local"` never appears in the codebase — it does, just not on the path this plan touches.

---

### Task 1: `LibraryOrigin` enum + `compute_library_origin()` in a new module

**Files:**
- Create: `barn/haybale-marketplace/haybale_marketplace/library_origin.py`
- Create: `tests/marketplace/test_library_origin.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py:31-36` (remove `is_project_library`, import it back)
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:29` (import path)
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:66-69` (import path)

**Interfaces:**
- Produces:
  - `class LibraryOrigin(Enum)` with members `FRAMEWORK`, `PROJECT_LOCAL`, `PYPI`, `GIT`, `UNKNOWN`, and a property `is_protected -> bool` (`True` for `FRAMEWORK`/`PROJECT_LOCAL`, `False` otherwise).
  - `def is_project_library(lib: LibraryInfo, marketplace_path: str | None) -> bool` — moved verbatim from `_overview_edit_dialog.py`, same signature and behavior.
  - `def compute_library_origin(lib: LibraryInfo, marketplace_path: str | None, catalog_entry: "Haybale | None") -> LibraryOrigin` — the origin-detection function. `catalog_entry` is the caller-resolved `Haybale` row matching this library's `distribution_name` (or `None` if no catalog row exists) — callers already have this lookup (`_lookup_marketplace_pkg` in Overview; the Browser's `pm.caches` scan) so this module stays free of `SessionContext`/`MarketplaceState` coupling.

- [ ] **Step 1: Write the failing tests**

```python
# tests/marketplace/test_library_origin.py
"""LibraryOrigin — the second, orthogonal ("where did this come from") axis
alongside InstallType ("how did this reach the environment"). See
internals/handoff/library-origin-and-required-classification.md.
"""

from haybale_marketplace.library_origin import (
    LibraryOrigin,
    compute_library_origin,
    is_project_library,
)
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.marketstall.types import Haybale


def _lib(install_type: InstallType, folder_path: str, distribution_name: str = "") -> LibraryInfo:
    identity = LibraryIdentity(id="testlib", label="Test Lib", folder_path=folder_path)
    return LibraryInfo(
        identity=identity,
        enabled=True,
        install_type=install_type,
        distribution_name=distribution_name,
    )


class TestIsProtected:
    def test_framework_is_protected(self):
        assert LibraryOrigin.FRAMEWORK.is_protected is True

    def test_project_local_is_protected(self):
        assert LibraryOrigin.PROJECT_LOCAL.is_protected is True

    def test_pypi_is_not_protected(self):
        assert LibraryOrigin.PYPI.is_protected is False

    def test_git_is_not_protected(self):
        assert LibraryOrigin.GIT.is_protected is False

    def test_unknown_is_not_protected(self):
        # Deliberate: we don't know how this library got here, so we don't
        # newly restrict a working disable/uninstall path over an absence
        # of information. See spec's non-goals.
        assert LibraryOrigin.UNKNOWN.is_protected is False

    def test_exactly_two_members_are_protected(self):
        # Guards against a new LibraryOrigin member silently defaulting to
        # protected (or not) without an explicit decision.
        protected = [o for o in LibraryOrigin if o.is_protected]
        assert set(protected) == {LibraryOrigin.FRAMEWORK, LibraryOrigin.PROJECT_LOCAL}


class TestIsProjectLibrary:
    def test_true_when_folder_path_under_workspace_barn(self, tmp_path):
        workspace = tmp_path / "myproject"
        (workspace / "barn" / "haybale-foo").mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"))
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is True

    def test_false_when_folder_path_outside_workspace_barn(self, tmp_path):
        workspace = tmp_path / "myproject"
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other))
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is False

    def test_false_when_marketplace_path_is_none(self):
        lib = _lib(InstallType.EDITABLE, "/anywhere/haybale-foo")
        assert is_project_library(lib, None) is False

    def test_false_when_folder_path_is_none(self, tmp_path):
        identity = LibraryIdentity(id="testlib", label="Test Lib", folder_path=None)
        lib = LibraryInfo(
            identity=identity, enabled=True, install_type=InstallType.EDITABLE, distribution_name=""
        )
        marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is False


class TestComputeLibraryOrigin:
    def test_folder_mechanism_is_framework_origin(self, tmp_path):
        # Rule 1: FOLDER implies FRAMEWORK directly, no path analysis.
        lib = _lib(InstallType.FOLDER, "/anywhere/builtin")
        marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
        assert compute_library_origin(lib, marketplace_path, catalog_entry=None) is LibraryOrigin.FRAMEWORK

    def test_path_under_barn_is_project_local(self, tmp_path):
        # Rule 2: takes priority over any catalog entry.
        workspace = tmp_path / "myproject"
        (workspace / "barn" / "haybale-foo").mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"), "haybale-foo")
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="pypi")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.PROJECT_LOCAL

    def test_catalog_entry_source_pypi(self, tmp_path):
        # Rule 3: outside barn, with a catalog row.
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other), "haybale-foo")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="pypi")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.PYPI

    def test_catalog_entry_source_git(self, tmp_path):
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.REGULAR, str(other), "haybale-foo")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="git")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.GIT

    def test_no_catalog_entry_is_unknown(self, tmp_path):
        # Rule 4: bare `pip install -e` outside the marketplace flow — no
        # catalog row. Honest unknown, never guessed from mechanism.
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other), "")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
        assert origin is LibraryOrigin.UNKNOWN

    def test_regular_no_catalog_entry_is_unknown(self, tmp_path):
        other = tmp_path / "site-packages" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.REGULAR, str(other), "")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
        assert origin is LibraryOrigin.UNKNOWN
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/marketplace/test_library_origin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haybale_marketplace.library_origin'`

- [ ] **Step 3: Create `library_origin.py`**

```python
# barn/haybale-marketplace/haybale_marketplace/library_origin.py
"""LibraryOrigin — the second, orthogonal axis alongside InstallType.

InstallType (haywire.core.library.install_type) answers "how did this
library reach the Python environment" (REGULAR / EDITABLE / FOLDER) — a
pure filesystem fact, workspace-agnostic, computed in haywire-core.

LibraryOrigin answers "where did the code come from / who owns it"
(FRAMEWORK / PROJECT_LOCAL / PYPI / GIT / UNKNOWN) — this requires
workspace context (the project's barn/ root), which haywire-core
deliberately does not have. Origin computation therefore lives here, at
the marketplace layer, not in core.

``LibraryOrigin.is_protected`` is the single predicate every "can this be
disabled/uninstalled" check should read, replacing the OR-of-scattered-
checks pattern the original narrow is_required() fix used but didn't
generalize. See internals/handoff/library-origin-and-required-classification.md.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType

if TYPE_CHECKING:
    from haywire.core.marketstall.types import Haybale


class LibraryOrigin(enum.Enum):
    """Where a library's code came from / who owns it."""

    FRAMEWORK = "framework"  # This library IS the framework (e.g. builtin).
    PROJECT_LOCAL = "project_local"  # Lives under this workspace's own barn/.
    PYPI = "pypi"  # Came from a marketplace install, catalog source=pypi.
    GIT = "git"  # Came from a marketplace install, catalog source=git.
    UNKNOWN = "unknown"  # No catalog entry — origin honestly unresolvable.

    @property
    def is_protected(self) -> bool:
        """True when Disable/Uninstall should never be offered for this origin.

        FRAMEWORK and PROJECT_LOCAL only. UNKNOWN is deliberately NOT
        protected — an editable install with no catalog entry (e.g. a bare
        ``pip install -e ../some-other-repo`` outside the marketplace flow)
        stays exactly as disable/uninstallable as it always was; origin's
        job is to correctly protect the two cases it CAN prove, not to
        become a general trust gate for everything it can't classify.
        """
        return self in (LibraryOrigin.FRAMEWORK, LibraryOrigin.PROJECT_LOCAL)


def is_project_library(lib: LibraryInfo, marketplace_path: str | None) -> bool:
    """Return True if lib is the local project library (lives under workspace/barn/).

    Low-level path-check primitive — one input to compute_library_origin(),
    but also used independently by callers that only need this narrower
    question (e.g. the Edit dialog's heap-vs-installed-wheel branching).
    """
    if not marketplace_path or not lib.identity.folder_path:
        return False
    workspace_root = Path(marketplace_path).parent.parent
    return Path(lib.identity.folder_path).is_relative_to(workspace_root / "barn")


def compute_library_origin(
    lib: LibraryInfo,
    marketplace_path: str | None,
    catalog_entry: "Haybale | None",
) -> LibraryOrigin:
    """Compute lib's LibraryOrigin.

    Rules, in order:
      1. FOLDER mechanism implies FRAMEWORK directly — no path analysis.
         There is exactly one FOLDER-mechanism library today (builtin),
         discovered through its own dedicated folder-scan path, structurally
         distinct from the pip entry-point path. Revisit only if a second
         FOLDER-mechanism library ever ships.
      2. Path under this workspace's barn/ (is_project_library) -> PROJECT_LOCAL.
         Takes priority over any catalog entry — a project's own barn/
         library that also happens to have a stale catalog row is still
         project-local first.
      3. A matching catalog Haybale row exists -> its source field
         ("pypi" / "git") maps directly.
      4. No catalog row -> UNKNOWN. Never guessed from mechanism — a wrong
         guess is worse than an honest unknown for a safety classification.

    ``catalog_entry`` is the caller-resolved Haybale row matching lib's
    distribution_name (or None). Callers already have this lookup
    (LibraryOverviewEditor._lookup_marketplace_pkg, or a scan over
    MarketplaceState.get_project_haybales() / parse_project_marketplace(...).caches)
    — resolving it here would couple this module to SessionContext/
    MarketplaceState, which it deliberately stays free of.
    """
    if lib.install_type is InstallType.FOLDER:
        return LibraryOrigin.FRAMEWORK
    if is_project_library(lib, marketplace_path):
        return LibraryOrigin.PROJECT_LOCAL
    if catalog_entry is not None:
        if catalog_entry.source == "pypi":
            return LibraryOrigin.PYPI
        if catalog_entry.source == "git":
            return LibraryOrigin.GIT
    return LibraryOrigin.UNKNOWN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/marketplace/test_library_origin.py -v`
Expected: PASS (all tests in `TestIsProtected`, `TestIsProjectLibrary`, `TestComputeLibraryOrigin`)

- [ ] **Step 5: Remove `is_project_library` from `_overview_edit_dialog.py`, import it back**

In `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`, delete the function definition (lines 31-36) and add the import:

```python
# Remove this function definition (lines 31-36):
# def is_project_library(lib: LibraryInfo, marketplace_path: str | None) -> bool:
#     """Return True if lib is the local project library (lives under workspace/barn/)."""
#     if not marketplace_path or not lib.identity.folder_path:
#         return False
#     workspace_root = Path(marketplace_path).parent.parent
#     return Path(lib.identity.folder_path).is_relative_to(workspace_root / "barn")

# Add near the top, alongside the other imports:
from haybale_marketplace.library_origin import is_project_library
```

The rest of the file (`read_os_from_pyproject`, `build_edit_dialog`) is unchanged — both already call `is_project_library(...)` by name, and the import makes that name resolve to the moved function.

- [ ] **Step 6: Update the two other importers**

In `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:29`:

```python
# Before:
from haybale_marketplace.editors._overview_edit_dialog import is_project_library
# After:
from haybale_marketplace.library_origin import is_project_library
```

In `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:66-69`:

```python
# Before:
from haybale_marketplace.editors._overview_edit_dialog import (
    build_edit_dialog,
    is_project_library,
)
# After:
from haybale_marketplace.editors._overview_edit_dialog import build_edit_dialog
from haybale_marketplace.library_origin import is_project_library
```

- [ ] **Step 7: Run the full marketplace test suite**

Run: `uv run pytest tests/marketplace/ -v`
Expected: PASS, no import errors from the two editors touched in Step 6.

- [ ] **Step 8: Lint and type-check**

Run: `uv run ruff check barn/haybale-marketplace/haybale_marketplace/library_origin.py barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Run: `uv run mypy barn/haybale-core/haybale_core/ tests/` (per CLAUDE.md's documented mypy target set — `haybale-marketplace` isn't in that list; run `uv run ruff check` as the binding gate here and confirm no new mypy errors show up in the full `uv run mypy` invocation from CLAUDE.md's Commands section if you run it)
Expected: no new errors.

- [ ] **Step 9: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/library_origin.py \
        barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py \
        barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py \
        barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py \
        tests/marketplace/test_library_origin.py
git commit -m "feat(marketplace): add LibraryOrigin axis, move is_project_library

New haybale_marketplace/library_origin.py owns the second, orthogonal
classification axis (framework/project_local/pypi/git/unknown) alongside
InstallType's mechanism axis, plus the centralized is_protected predicate.
is_project_library moves here from _overview_edit_dialog.py — it's a
building block of origin computation now, not a dialog-specific helper."
```

---

### Task 2: FOLDER-only guard on `LibraryRegistry.disable_library()`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/registry.py:251-261`
- Test: `tests/core/test_libraries/test_disable_library_folder_guard.py`

**Interfaces:**
- Consumes: `self._library_install_types: Dict[str, InstallType]` (already exists on `LibraryRegistry`, populated during scan — `registry.py:678`), `InstallType.FOLDER` (already imported in `registry.py:13`).
- Produces: `disable_library()` returns `False` (no exception) when the target's tracked install type is `InstallType.FOLDER`, in addition to its existing `False`-when-not-found behavior. No signature change, no new parameters.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_libraries/test_disable_library_folder_guard.py
"""LibraryRegistry.disable_library() refuses FOLDER-mechanism libraries.

The one guard core can compute without workspace context — see
internals/handoff/library-origin-and-required-classification.md,
"Known, accepted asymmetry" section. project_local protection stays
UI-layer-only; this guard covers FOLDER only (today: builtin).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from haywire.core.library.install_type import InstallType
from haywire.core.library.registry import LibraryRegistry


def make_library_mock(library_id: str = "builtin") -> MagicMock:
    lib = MagicMock()
    lib.identity.id = library_id
    lib.identity.label = library_id.capitalize()
    return lib


def register_with_install_type(reg: LibraryRegistry, library_id: str, install_type: InstallType) -> MagicMock:
    lib = make_library_mock(library_id)
    reg._libraries[library_id] = lib
    reg._library_install_types[library_id] = install_type
    return lib


class TestDisableLibraryFolderGuard:
    def test_folder_library_cannot_be_disabled(self):
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "builtin", InstallType.FOLDER)

        result = reg.disable_library("builtin")

        assert result is False
        lib.disable.assert_not_called()

    def test_editable_library_can_still_be_disabled(self):
        # The guard is FOLDER-only — must not regress EDITABLE/REGULAR.
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "haybale-foo", InstallType.EDITABLE)

        result = reg.disable_library("haybale-foo")

        assert result is True
        lib.disable.assert_called_once()

    def test_regular_library_can_still_be_disabled(self):
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "some-pkg", InstallType.REGULAR)

        result = reg.disable_library("some-pkg")

        assert result is True
        lib.disable.assert_called_once()

    def test_unknown_library_still_returns_false(self):
        # Pre-existing not-found behavior, unaffected by the new guard.
        reg = LibraryRegistry()
        assert reg.disable_library("does-not-exist") is False

    def test_folder_library_with_no_tracked_install_type_is_not_blocked(self):
        # A library present in _libraries but never scanned (no entry in
        # _library_install_types) must not be blocked by a guard it can't
        # evaluate — mirrors get_library_install_type()'s own None-safe read.
        reg = LibraryRegistry()
        lib = make_library_mock("untracked")
        reg._libraries["untracked"] = lib
        # Deliberately no reg._library_install_types["untracked"] = ...

        result = reg.disable_library("untracked")

        assert result is True
        lib.disable.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_libraries/test_disable_library_folder_guard.py -v`
Expected: FAIL — `test_folder_library_cannot_be_disabled` fails because `disable_library()` currently disables unconditionally (`result is True`, `lib.disable` was called).

- [ ] **Step 3: Add the guard**

In `packages/haywire-core/src/haywire/core/library/registry.py`, modify `disable_library`:

```python
    def disable_library(self, library_registry_id: str) -> bool:
        """Disable a specific library. Adds it to the persisted-disabled set.

        Refuses (returns False) for InstallType.FOLDER libraries — today
        this is only the framework-owned `builtin` library, for which
        disabling has no legitimate use. This is the one protection guard
        core can compute on its own (a pure filesystem-mechanism fact); it
        does NOT cover project-local libraries, which require workspace
        context core deliberately doesn't have — that protection remains
        enforced at the marketplace UI layer only. See
        internals/handoff/library-origin-and-required-classification.md.
        """
        library = self._libraries.get(library_registry_id)
        if not library:
            return False
        if self._library_install_types.get(library_registry_id) is InstallType.FOLDER:
            return False
        self._user_disabled.add(library_registry_id)
        self._persist_disabled_set()
        library.disable()
        logger.info(f"Library '{library.identity.label}': Disabled")
        self._fire_library_disabled(library)
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_libraries/test_disable_library_folder_guard.py -v`
Expected: PASS, all 5 tests.

- [ ] **Step 5: Run the existing disable/enable callback tests to confirm no regression**

Run: `uv run pytest tests/core/test_libraries/test_library_enabled_callbacks.py tests/core/test_libraries/test_registry_remove_library.py -v`
Expected: PASS — `TestDisableLibraryFiresCallback` in `test_library_enabled_callbacks.py` disables a library called `"midi"` with no `_library_install_types` entry set (untracked), which Step 3's `test_folder_library_with_no_tracked_install_type_is_not_blocked` case confirms is unaffected.

- [ ] **Step 6: Lint and type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/library/registry.py`
Run: `uv run mypy packages/haywire-core/src/haywire/`
Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/registry.py \
        tests/core/test_libraries/test_disable_library_folder_guard.py
git commit -m "fix(core): disable_library() refuses FOLDER-mechanism libraries

The registry layer was previously unprotected for ALL library kinds —
any caller could disable 'builtin' directly, bypassing the marketplace
UI's is_required() check entirely. This closes the FOLDER-mechanism case
at its source; project_local protection remains UI-layer-only (documented
asymmetry — core has no workspace-root awareness to compute it)."
```

---

### Task 3: Wire `origin.is_protected` into the three known call sites

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:494-512` (`is_required()`)
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:400,456,479` (Edit-vs-Uninstall split + Uninstall-button gate)
- Test: `tests/marketplace/test_required_badge_uses_origin.py`

**Interfaces:**
- Consumes: `LibraryOrigin`, `compute_library_origin` from `haybale_marketplace.library_origin` (Task 1).
- Produces: `is_required(lib)` in the Browser now reads `origin.is_protected OR has_dependents` instead of the inlined FOLDER/is_project_library checks. The Overview's `_is_project` boolean is replaced by `origin.is_protected`, and the Uninstall-button `elif` clause reads `not origin.is_protected` instead of the mechanism-name tuple check.

- [ ] **Step 1: Write the failing test (behavior-preservation, per the Global Constraint)**

```python
# tests/marketplace/test_required_badge_uses_origin.py
"""is_required() must produce the IDENTICAL protected set before and after
routing through LibraryOrigin.is_protected — this is a centralization
refactor, not a policy change. See Global Constraints in
docs/superpowers/plans/2026-08-06-library-origin-axis.md.
"""

from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType


def _lib(install_type: InstallType, folder_path: str, distribution_name: str = "") -> LibraryInfo:
    identity = LibraryIdentity(id="testlib", label="Test Lib", folder_path=folder_path)
    return LibraryInfo(
        identity=identity, enabled=True, install_type=install_type, distribution_name=distribution_name
    )


def test_folder_library_origin_is_protected(tmp_path):
    lib = _lib(InstallType.FOLDER, "/anywhere/builtin")
    marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is True


def test_project_local_library_origin_is_protected(tmp_path):
    workspace = tmp_path / "myproject"
    (workspace / "barn" / "haybale-foo").mkdir(parents=True)
    lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"))
    marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is True


def test_ordinary_editable_library_origin_is_not_protected(tmp_path):
    # An editable install of someone else's repo, outside barn/ — must NOT
    # be protected by origin alone (it may still be Required via
    # has_dependents, but that's a separate, orthogonal reason).
    other = tmp_path / "somewhere-else" / "haybale-foo"
    other.mkdir(parents=True)
    lib = _lib(InstallType.EDITABLE, str(other))
    marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is False
    assert origin is LibraryOrigin.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/marketplace/test_required_badge_uses_origin.py -v`
Expected: PASS already (this test only exercises Task 1's `compute_library_origin`, already implemented) — this step is a sanity check that Task 1 landed correctly, not a red step for Task 3's own code. Task 3's actual code change is a refactor of already-correct logic (per the Global Constraint, output must not change), so the meaningful verification is Step 6's full-suite run, not a new failing unit test for the call-site wiring itself.

- [ ] **Step 3: Rewire `is_required()` in `library_browser_editor.py`**

Replace lines 494-512:

```python
        def is_required(lib) -> bool:
            # Required if origin.is_protected (framework-owned or this
            # workspace's own project-local library) OR some other installed
            # library declares this one in its @library(dependencies=[...])
            # decorator. These are independent reasons for the same badge —
            # see LibraryOrigin.is_protected's docstring and the glossary
            # entry "required" vs "dependent".
            if not hasattr(lib, "identity"):
                return False
            origin = compute_library_origin(
                lib,
                str(marketplace_path) if marketplace_path else None,
                catalog_entry=_catalog_entry_for(lib),
            )
            if origin.is_protected:
                return True
            return bool(manager.get_installed_dependents(lib.identity.id))
```

Add the import at the top of the file (near the existing `from haybale_marketplace.library_origin import is_project_library` from Task 1's Step 6 — combine into one import line):

```python
from haybale_marketplace.library_origin import compute_library_origin, is_project_library
```

`is_required()` now needs a per-library catalog lookup. Add a small helper just above `_render_list` (or inline where `pm.caches` is already parsed at line ~545) that builds a `distribution_name -> Haybale` map once per render, reused by `is_required`:

```python
        # Built once per render, reused by is_required() below — matches the
        # Haybale rows already parsed for the Available/updates_available
        # block further down, just indexed by distribution_name for lookup.
        _catalog_by_dist_name: dict[str, "Haybale"] = {}
        if marketplace_path and marketplace_path.exists():
            try:
                from haywire.core.marketstall import parse_project_marketplace as _parse_pm

                for entry in _parse_pm(marketplace_path).caches:
                    if entry.name:
                        _catalog_by_dist_name[entry.name] = entry
            except Exception:
                pass

        def _catalog_entry_for(lib):
            dist_name = getattr(lib, "distribution_name", "") or ""
            return _catalog_by_dist_name.get(dist_name)
```

Place this block immediately before `def is_required(lib) -> bool:` (i.e., right after the existing `marketplace_path` computation at line ~476, before `is_required`'s definition) — `is_required` is defined and called before the later `pm = parse_project_marketplace(marketplace_path)` block at line ~545, so that later parse cannot be reused as-is; this adds one extra (cheap, cached-file) parse per render rather than restructuring the existing later block. Import `Haybale` for the type hint alongside the other imports at the top of the file:

```python
from haywire.core.marketstall import Haybale  # add to existing marketstall imports if not already present
```

- [ ] **Step 4: Rewire the Overview Editor's `_is_project` and Uninstall-button gate**

In `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`, replace line 400:

```python
                            # Before:
                            # _is_project = is_project_library(installed_lib, marketplace_path)
                            # After:
                            _origin = compute_library_origin(
                                installed_lib,
                                marketplace_path,
                                catalog_entry=marketplace_pkg,
                            )
```

`marketplace_pkg` is already computed earlier in this method (it's the parameter/local passed into `_render_center`, the same `Haybale | None` returned by `_lookup_marketplace_pkg` — confirm by reading the method signature above line 370 before editing; it is in scope at line 400 as the same value referenced at line 391 `if marketplace_pkg:`).

Replace every use of `_is_project` in the rest of the method (lines 456 and any other reference) with `_origin.is_protected`:

```python
                            # Line 456, before:
                            # if _is_project:
                            # After:
                            if _origin.is_protected:
```

Replace line 479's mechanism-name tuple check:

```python
                            # Before:
                            # elif installed_lib.install_type.name in ("REGULAR", "EDITABLE"):
                            # After:
                            elif not _origin.is_protected:
```

Add the import near the top of the file (combine with the existing `is_project_library` import updated in Task 1's Step 6):

```python
from haybale_marketplace.library_origin import compute_library_origin, is_project_library
```

(`is_project_library` itself may no longer be directly called in this file after this step — check with `grep -n is_project_library barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`; if the only remaining reference was line 400, now replaced, drop `is_project_library` from this file's import and keep only `compute_library_origin`.)

- [ ] **Step 5: Grep-verify no other call site was missed**

Run: `grep -rn "InstallType.FOLDER\|is_project_library\|install_type.name in\|install_type is InstallType" barn/ packages/ --include="*.py" | grep -v /tests/`

Expected output: only the definitions in `library_origin.py` (Task 1) and the FOLDER guard in `registry.py` (Task 2) — no remaining ad-hoc protection checks outside those two files. If any other hit appears (the spec names `library_manager.py:734`, `di/config.py:547`, and `registry.py:610,644` as pre-existing FOLDER *construction* sites, not protection checks — confirm each hit is construction/discovery, not a disable/uninstall gate, before leaving it alone).

- [ ] **Step 6: Run the full marketplace test suite**

Run: `uv run pytest tests/marketplace/ -v`
Expected: PASS. This is the real regression check for Task 3 (per Step 2's note) — confirms the Uninstall/Edit button rendering and `is_required()` filtering behave identically to before the rewire.

- [ ] **Step 7: Lint and type-check**

Run: `uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Run: `uv run mypy barn/haybale-studio/haybale_studio/`
Expected: no new errors.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py \
        barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py \
        tests/marketplace/test_required_badge_uses_origin.py
git commit -m "refactor(marketplace): route Required badge + Uninstall gate through origin.is_protected

is_required(), the Edit-vs-Uninstall split, and the Uninstall-button gate
each re-derived 'is this protected' independently (FOLDER check +
is_project_library, or a REGULAR/EDITABLE mechanism-name tuple). All three
now read the single LibraryOrigin.is_protected predicate. Behavior is
unchanged — verified by the full marketplace suite — this is a
centralization refactor, not a policy change."
```

---

### Task 4: Origin badge in the Library Overview Editor

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:384-393`
- Test: manual/visual (see Step 4 — no NiceGUI harness test exists for this render block today; follow the existing pattern of leaving badge rendering untested at the unit level, consistent with the surrounding code).

**Interfaces:**
- Consumes: `LibraryOrigin` from Task 1, `_origin` computed in Task 3's Step 4 (already in scope at this point in the method).

- [ ] **Step 1: Read the current badge-rendering block**

Confirm current state at `library_overview_editor.py:384-393`:

```python
                            if installed_lib:
                                inst_color = {
                                    "EDITABLE": "purple",
                                    "REGULAR": "blue",
                                    "FOLDER": "teal",
                                }.get(installed_lib.install_type.name, "grey")
                                hui.tag(installed_lib.install_type.name.lower(), color=inst_color)
                            if marketplace_pkg:
                                src_color = "blue" if marketplace_pkg.source == "pypi" else "purple"
                                hui.tag(marketplace_pkg.source, color=src_color)
```

Note: `_origin` (from Task 3 Step 4) is computed later in the method (inside the `if installed_lib and manager:` block, after this badge-rendering block, which runs unconditionally on `installed_lib` alone). Move the `_origin` computation earlier so it's available here — both blocks need `installed_lib` to be non-`None`; the badge block already guards on `if installed_lib:` separately from `if installed_lib and manager:`. Compute origin once, right after the existing `if installed_lib:` badge block starts, reusing it in both places.

- [ ] **Step 2: Replace the two `hui.tag()` calls with mechanism + origin badges, computing `_origin` once**

Final state of the block (this supersedes Task 3 Step 4's `_origin` computation — see the note below):

```python
                            if installed_lib:
                                inst_color = {
                                    "EDITABLE": "purple",
                                    "REGULAR": "blue",
                                    "FOLDER": "teal",
                                }.get(installed_lib.install_type.name, "grey")
                                hui.tag(installed_lib.install_type.name.lower(), color=inst_color)
                                # Origin badge — always shown, no suppression even for the
                                # single FOLDER+framework row (no special-casing anywhere,
                                # per the settled design). Computed once here; Task 3's
                                # protection checks further down this method reuse this
                                # same `_origin` value rather than recomputing it.
                                _origin = compute_library_origin(
                                    installed_lib, marketplace_path, catalog_entry=marketplace_pkg
                                )
                                origin_color = {
                                    LibraryOrigin.FRAMEWORK: "teal",
                                    LibraryOrigin.PROJECT_LOCAL: "purple",
                                    LibraryOrigin.PYPI: "blue",
                                    LibraryOrigin.GIT: "orange",
                                    LibraryOrigin.UNKNOWN: "grey",
                                }[_origin]
                                hui.tag(_origin.value, color=origin_color)
```

Remove the old `if marketplace_pkg: hui.tag(marketplace_pkg.source, ...)` block entirely — it's superseded by the origin badge, which already folds in the catalog `source` (via `compute_library_origin`'s rule 3) alongside the FOLDER/project-local cases it couldn't previously express.

Add the `LibraryOrigin` import (extends the import added in Task 3 Step 4):

```python
from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin, is_project_library
```

**Reconcile with Task 3 Step 4:** that step computed `_origin = compute_library_origin(installed_lib, marketplace_path, catalog_entry=marketplace_pkg)` at what was line 400, inside the `if installed_lib and manager:` block. This step computes the identically-named `_origin` earlier, inside the outer `if installed_lib:` badge block. Delete Task 3's copy — find the line `_origin = compute_library_origin(installed_lib, marketplace_path, catalog_entry=marketplace_pkg)` inside `if installed_lib and manager:` and remove it, since `_origin` computed by this step is already in scope there (same method, same `with` block, no intervening function boundary — confirm by reading the method body between the two points before deleting). Every other line in Task 3 Step 4 that reads `_origin.is_protected` (the `if _origin.is_protected:` at former line 456, and `elif not _origin.is_protected:` at former line 479) needs no further change — they now read the single value computed by this step.

- [ ] **Step 3: Run the full marketplace test suite**

Run: `uv run pytest tests/marketplace/ -v`
Expected: PASS.

- [ ] **Step 4: Manual verification**

Run: `uv run haywire` in a scratch project with at least one editable barn library and the `builtin` library present. Open the Library Manager, select `builtin` — confirm it shows `[folder]` and `[framework]` badges, both visible, no suppression. Select a project-local barn library — confirm `[editable]` and `[project_local]`. This is the one step in this plan without an automated assertion; note the result in the task's completion comment when checking this box off.

- [ ] **Step 5: Lint and type-check**

Run: `uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Run: `uv run mypy barn/haybale-studio/haybale_studio/`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
git commit -m "feat(marketplace): show LibraryOrigin badge in Library Overview

Replaces the marketplace_pkg.source-only badge (blank for FOLDER/
project-local libraries, which have no catalog row) with the full origin
badge — framework/project_local/pypi/git/unknown — computed the same way
for every library, no special-casing."
```

---

### Task 5: Rename `project_local_libraries()` → `project_writable_libraries()`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/farmhands/_helpers.py:37-54`
- Modify: `barn/haybale-studio/haybale_studio/farmhands/authoring.py:28,138`
- Modify: `tests/farmhand/test_baseline_tools.py:200,202`

**Interfaces:**
- Produces: `def project_writable_libraries(ctx: FarmhandContext) -> list[str]` — same signature, same behavior as the old `project_local_libraries`. `resolve_target_library` (in `_helpers.py`, calls the renamed function internally) keeps its own name and signature unchanged — only its internal call target changes.

- [ ] **Step 1: Update the failing reference first (rename the call site in the existing test)**

```python
# tests/farmhand/test_baseline_tools.py — around line 200
def test_editable_library_is_a_writable_target():
    """An editable (pip -e) barn library is authorable — that is the intent of -e.

    The barn/haybale-* libraries are editable installs, so the gate must accept
    them regardless of the workspace root.
    """
    from haybale_studio.farmhands._helpers import project_writable_libraries, resolve_target_library

    locals_ = project_writable_libraries(FarmhandContext())
    assert "testing" in locals_, f"editable library 'testing' should be writable, got {locals_}"
    # resolve_target_library returns it without raising the gate error.
    assert resolve_target_library(FarmhandContext(), "testing") == "testing"
```

Also update the comment above it (currently: `# The write gate is `project_local_libraries` / `resolve_target_library`.`) to name the new function:

```python
# The write gate is `project_writable_libraries` / `resolve_target_library`. Test the
# gate DECISION directly rather than driving the full write tool: a real write lands
# in the target library's actual on-disk folder (library_folder resolves to the real
# barn path — there is no test isolation for it), which would litter a shared barn
# library with artifacts. The gate function is the unit that actually changed.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/farmhand/test_baseline_tools.py::test_editable_library_is_a_writable_target -v`
Expected: FAIL — `ImportError: cannot import name 'project_writable_libraries'`

- [ ] **Step 3: Rename the function in `_helpers.py`**

```python
def project_writable_libraries(ctx: FarmhandContext) -> list[str]:
    """Libraries Farmhand may author into: the EDITABLE (pip ``-e``) installs.

    Uses ``InstallType.is_editable()`` — the SAME authority the source editor's
    read-only badge consults (ComponentSourceEditor._compute_is_editable) — so the
    UI "Edit" button and this write gate can never disagree. An editable install
    IS the developer's on-disk source (that is the point of ``-e``), and the
    framework hot-reloads it; Farmhand may write it regardless of whether its path
    sits under the current workspace root. REGULAR (site-packages, immutable) and
    FOLDER (framework-owned builtin) are excluded.

    Deliberately broader than LibraryOrigin.PROJECT_LOCAL (haybale_marketplace's
    "is this literally under this workspace's barn/" classification): any
    editable install anywhere satisfies Farmhand's actual need
    ("can I write this source"), including a symlinked-in editable install of
    someone else's library. Renamed from project_local_libraries, which implied
    the narrower origin-axis meaning it never actually had — see
    internals/handoff/library-origin-and-required-classification.md.
    """
    registry = ctx.registry(LibraryRegistry)
    result = []
    for lib_id in registry.list_names():
        install_type = registry.get_library_install_type(lib_id)
        if install_type is not None and install_type.is_editable():
            result.append(lib_id)
    return sorted(result)


def resolve_target_library(ctx: FarmhandContext, library: str | None) -> str:
    locals_ = project_writable_libraries(ctx)
    if library is not None:
        if library not in locals_:
            raise FarmhandError(
                "not_project_library",
                f"'{library}' is not a project-local library (project-local: {locals_ or 'none'}). "
                f"Farmhand writes source only into project-local libraries.",
                ids={"library": library},
            )
        return library
    if not locals_:
        raise FarmhandError(
            "no_project_library",
            "No project-local library exists in this workspace — create one with 'haywire init'.",
        )
    if len(locals_) > 1:
        raise FarmhandError(
            "ambiguous_project_library",
            f"Several project-local libraries exist; pass library= explicitly: {locals_}.",
        )
    return locals_[0]
```

(`resolve_target_library`'s error messages/`FarmhandError` codes — `not_project_library`, `no_project_library`, `ambiguous_project_library` — are left unchanged. They're agent-facing API surface consumed by name in `test_write_gate_rejects_unknown_library`'s `exc_info.value.code == "not_project_library"` assertion; renaming them is out of scope for this plan and not requested by the spec.)

- [ ] **Step 4: Update `authoring.py`'s import and call site**

```python
# authoring.py line 28, before:
#     project_local_libraries,
# After:
    project_writable_libraries,
```

```python
# authoring.py line 138, before:
#     if lib_id not in project_local_libraries(ctx):
# After:
    if lib_id not in project_writable_libraries(ctx):
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/farmhand/test_baseline_tools.py -v`
Expected: PASS, including `test_editable_library_is_a_writable_target` and `test_write_gate_rejects_unknown_library`.

- [ ] **Step 6: Grep-verify no stray references remain**

Run: `grep -rn "project_local_libraries" barn/ tests/ --include="*.py"`
Expected: no output (the old name is fully gone).

- [ ] **Step 7: Run the full Farmhand test suite**

Run: `uv run pytest tests/farmhand/ -v`
Expected: PASS.

- [ ] **Step 8: Lint and type-check**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/farmhands/_helpers.py barn/haybale-studio/haybale_studio/farmhands/authoring.py`
Run: `uv run mypy barn/haybale-studio/haybale_studio/`
Expected: no new errors.

- [ ] **Step 9: Commit**

```bash
git add barn/haybale-studio/haybale_studio/farmhands/_helpers.py \
        barn/haybale-studio/haybale_studio/farmhands/authoring.py \
        tests/farmhand/test_baseline_tools.py
git commit -m "refactor(farmhand): rename project_local_libraries -> project_writable_libraries

Same behavior (all EDITABLE installs) — only the name changes, to stop
implying equivalence with LibraryOrigin.PROJECT_LOCAL (haybale_marketplace's
narrower 'under this workspace's barn/' classification), which this
function was never scoped to and shouldn't be narrowed to match."
```

---

### Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the pre-commit gate**

Run: `uv run pytest -m "not browser and not perf" -q > /tmp/library_origin_full.log 2>&1; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 2: Check for failures explicitly**

Run: `grep -E "^FAILED|^ERROR" /tmp/library_origin_full.log`
Expected: no output.

- [ ] **Step 3: Full ruff + mypy per CLAUDE.md's Commands section**

Run: `uv run ruff check .`
Run: `uv run ruff format --check .`
Run: `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`
Expected: no errors from any of the three.

- [ ] **Step 4: Re-run the browser suite if UI changes warrant it**

Run: `uv run pytest -m browser -k "library" -v`
Expected: PASS (or "no tests ran" if no browser tests target the Library Manager UI specifically — confirm which before assuming either).

No commit for this task — it's verification of Tasks 1-5's cumulative state, not new code.
