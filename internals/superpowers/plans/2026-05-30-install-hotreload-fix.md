# Install Hot-Reload Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix marketplace library installation corrupting the running registry when pip upgrades collateral libraries, and redesign the install UX to a 3-step flow with an upgrade-impact confirmation and a streaming progress popup.

**Architecture:** Three layers of change — (1) `LibraryRegistry.remove_library()` gains `sys.modules` ejection so upgraded libraries are cleanly evicted before pip touches files; (2) `LibraryManager.install_streaming()` is split into `dry_run()` + `install()` so the UI can interpose a confirmation step; (3) `LibraryOverviewEditor._install_package()` is rewritten to drive the new 3-step flow using two new `haywire.ui.modals`.

**Tech Stack:** Python, NiceGUI, `uv pip` subprocess, `haywire.ui.components.popup.Popup`

---

## File Map

| File | Change |
|------|--------|
| `packages/haywire-core/src/haywire/core/library/registry.py` | `remove_library()` gains `sys.modules` ejection; new `find_library_by_distribution_name()` |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py` | Split `install_streaming()` into `dry_run()` + `install()`; add `_parse_dry_run_removals()`; delete manual `sys.modules` block in `update_library_identity` |
| `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py` | **Already created** — no changes needed |
| `packages/haywire-core/src/haywire/ui/modals/upgrade_impact_modal.py` | **New** — two-section confirmation popup |
| `packages/haywire-core/src/haywire/ui/modals/__init__.py` | Export `upgrade_impact_modal` |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | Rewrite `_install_package()` to use the new 3-step flow |
| `tests/core/test_libraries/test_registry_remove_library.py` | **New** — unit tests for `remove_library()` ejection and `find_library_by_distribution_name()` |
| `tests/test_library_manager_dry_run.py` | **New** — unit tests for `dry_run()` and `_parse_dry_run_removals()` |

---

## Task 1: `remove_library()` ejects `sys.modules` entries

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/registry.py:299-315`
- Create: `tests/core/test_libraries/test_registry_remove_library.py`

The ejection derives the top-level module name from the library's source path in `_library_sources`. For example, source path `.../site-packages/haybale_core` → top-level name `haybale_core`. All `sys.modules` keys equal to that name or starting with `haybale_core.` are deleted.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_libraries/test_registry_remove_library.py`:

```python
"""Tests for LibraryRegistry.remove_library() sys.modules ejection
and find_library_by_distribution_name()."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from haywire.core.library.registry import LibraryRegistry
from haywire.core.library.install_type import InstallType


def _make_lib_mock(library_id: str) -> MagicMock:
    lib = MagicMock()
    lib.identity.id = library_id
    lib.identity.label = library_id
    lib.enabled = True
    return lib


def _register_fake(reg: LibraryRegistry, library_id: str, source_path: str, dist_name: str) -> None:
    """Inject a fake library directly into registry internals."""
    lib = _make_lib_mock(library_id)
    reg._libraries[library_id] = lib
    reg._library_sources[library_id] = source_path
    reg._library_install_types[library_id] = InstallType.REGULAR
    reg._library_distribution_names[library_id] = dist_name


@pytest.mark.unit
def test_remove_library_ejects_top_level_module(tmp_path):
    """remove_library() must delete the top-level module from sys.modules."""
    reg = LibraryRegistry()
    source = str(tmp_path / "haybale_core")
    _register_fake(reg, "haybale_core", source, "haybale-core")

    # Plant a fake module in sys.modules
    fake_mod = types.ModuleType("haybale_core")
    sys.modules["haybale_core"] = fake_mod
    try:
        reg.remove_library("haybale_core")
        assert "haybale_core" not in sys.modules
    finally:
        sys.modules.pop("haybale_core", None)


@pytest.mark.unit
def test_remove_library_ejects_submodules(tmp_path):
    """remove_library() must also eject submodules (haybale_core.nodes.blur etc.)."""
    reg = LibraryRegistry()
    source = str(tmp_path / "haybale_core")
    _register_fake(reg, "haybale_core", source, "haybale-core")

    sys.modules["haybale_core"] = types.ModuleType("haybale_core")
    sys.modules["haybale_core.nodes"] = types.ModuleType("haybale_core.nodes")
    sys.modules["haybale_core.nodes.blur"] = types.ModuleType("haybale_core.nodes.blur")
    # A different package that shares a prefix — must NOT be ejected
    sys.modules["haybale_core_extra"] = types.ModuleType("haybale_core_extra")
    try:
        reg.remove_library("haybale_core")
        assert "haybale_core" not in sys.modules
        assert "haybale_core.nodes" not in sys.modules
        assert "haybale_core.nodes.blur" not in sys.modules
        assert "haybale_core_extra" in sys.modules  # unrelated — untouched
    finally:
        for k in ["haybale_core", "haybale_core.nodes", "haybale_core.nodes.blur", "haybale_core_extra"]:
            sys.modules.pop(k, None)


@pytest.mark.unit
def test_remove_library_no_source_path_skips_ejection(tmp_path):
    """remove_library() must not crash when the library has no recorded source path."""
    reg = LibraryRegistry()
    lib = _make_lib_mock("haybale_core")
    reg._libraries["haybale_core"] = lib
    # Intentionally no entry in _library_sources
    reg._library_distribution_names["haybale_core"] = "haybale-core"
    reg._library_install_types["haybale_core"] = InstallType.REGULAR

    sys.modules["haybale_core"] = types.ModuleType("haybale_core")
    try:
        result = reg.remove_library("haybale_core")
        assert result is True
        # Module may or may not be ejected — no crash is the requirement
    finally:
        sys.modules.pop("haybale_core", None)


@pytest.mark.unit
def test_find_library_by_distribution_name_returns_id(tmp_path):
    """find_library_by_distribution_name() must return the library_id for a known dist."""
    reg = LibraryRegistry()
    _register_fake(reg, "haybale_core", str(tmp_path), "haybale-core")
    assert reg.find_library_by_distribution_name("haybale-core") == "haybale_core"


@pytest.mark.unit
def test_find_library_by_distribution_name_unknown_returns_none():
    """find_library_by_distribution_name() must return None for unknown dist names."""
    reg = LibraryRegistry()
    assert reg.find_library_by_distribution_name("haybale-unknown") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/core/test_libraries/test_registry_remove_library.py -v
```

Expected: all 5 tests FAIL with `AttributeError: 'LibraryRegistry' object has no attribute 'find_library_by_distribution_name'` (or similar).

- [ ] **Step 3: Implement in `registry.py`**

In `remove_library()` (around line 299), add `sys.modules` ejection. Also add `find_library_by_distribution_name()` after `get_library_distribution_name()` at line 725.

Replace the existing `remove_library` method body:

```python
def remove_library(self, library_registry_id: str) -> bool:
    """Disable, unregister, and fully remove a library from all tracking dicts.

    After calling this, a subsequent scan_for_libraries() will rediscover
    and reimport the library from scratch, picking up any changes made to
    its source files (e.g. updated @library decorator values).
    """
    import sys
    library = self._libraries.get(library_registry_id)
    if not library:
        return False
    library.disable()
    self._unregister(library_registry_id)
    source_path = self._library_sources.pop(library_registry_id, None)
    self._library_install_types.pop(library_registry_id, None)
    self._library_distribution_names.pop(library_registry_id, None)

    # Eject stale module objects so scan_for_libraries() does a fresh import
    # rather than returning the cached pre-upgrade module from sys.modules.
    if source_path:
        module_name = os.path.basename(source_path.rstrip("/\\"))
        to_remove = [
            k for k in sys.modules
            if k == module_name or k.startswith(module_name + ".")
        ]
        for k in to_remove:
            del sys.modules[k]

    logger.info(f"Library '{library_registry_id}': Fully removed (ready for reload)")
    return True
```

Add at the bottom of the public API section (after `get_library_distribution_name`):

```python
def find_library_by_distribution_name(self, dist_name: str) -> str | None:
    """Return the library_id for a given pip distribution name, or None."""
    return next(
        (lid for lid, d in self._library_distribution_names.items() if d == dist_name),
        None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/core/test_libraries/test_registry_remove_library.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run lint and type-check on changed file**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/library/registry.py
uv run mypy packages/haywire-core/src/haywire/core/library/registry.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/registry.py \
        tests/core/test_libraries/test_registry_remove_library.py
git commit -m "feat: remove_library() ejects sys.modules; add find_library_by_distribution_name()"
```

---

## Task 2: Drop the redundant `sys.modules` block from `update_library_identity`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:803-812`

`update_library_identity` calls `remove_library()` at line 806 and then manually ejects `sys.modules` at lines 808–812. Now that `remove_library()` does this itself, the manual block is dead code.

- [ ] **Step 1: Delete the manual ejection block**

In `library_manager.py`, find this block (around lines 803–812):

```python
        # Fully remove the library from the registry (disable + unregister + tracking
        # dicts cleared) so scan_for_libraries() won't skip the "already instantiated"
        # guard and will reimport it fresh.
        self.registry.remove_library(library_id)

        # Eject the module (and all submodules) from sys.modules so the fresh
        # import triggered by scan_for_libraries() reads the updated __init__.py.
        to_remove = [k for k in sys.modules if k == module_name or k.startswith(module_name + ".")]
        for k in to_remove:
            del sys.modules[k]

        return True, f"Updated identity for {dist_name}"
```

Replace with:

```python
        # Fully remove the library from the registry (disable + unregister + tracking
        # dicts cleared, sys.modules ejected) so scan_for_libraries() reimports fresh.
        self.registry.remove_library(library_id)

        return True, f"Updated identity for {dist_name}"
```

Also remove the `import sys` at the top of `update_library_identity` (line 736) if it is no longer used elsewhere in the method. Check first:

```bash
grep -n "^import sys\|[^_]sys\." barn/haybale-marketplace/haybale_marketplace/library_manager.py | head -10
```

The top-of-file `import sys` at line 14 covers the whole module — only remove the local `import sys` inside the method body (line 736).

- [ ] **Step 2: Run the full unit test suite to catch regressions**

```bash
uv run pytest -m unit -v
```

Expected: all unit tests PASS.

- [ ] **Step 3: Lint and type-check**

```bash
uv run ruff check barn/haybale-marketplace/haybale_marketplace/library_manager.py
uv run mypy barn/haybale-marketplace/haybale_marketplace/library_manager.py
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py
git commit -m "refactor: remove redundant sys.modules ejection from update_library_identity"
```

---

## Task 3: Split `install_streaming()` into `dry_run()` + `install()`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:242-275`
- Create: `tests/test_library_manager_dry_run.py`

`dry_run(spec)` runs `uv pip install --dry-run <spec>` and returns a list of pip distribution names that would be uninstalled (i.e. will be upgraded). `install(spec, on_output, source_pkg)` runs the pre-eviction + actual install + rescan.

The `install_streaming()` method is **renamed** to `install()`. `install_streaming` is kept as a deprecated alias pointing to `install` so any external callers are not silently broken.

- [ ] **Step 1: Write failing tests**

Create `tests/test_library_manager_dry_run.py`:

```python
"""Tests for LibraryManager.dry_run() and _parse_dry_run_removals()."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_manager():
    from haybale_marketplace.library_manager import LibraryManager
    registry = MagicMock()
    registry._library_distribution_names = {}
    registry._library_install_types = {}
    registry._library_sources = {}
    return LibraryManager(registry=registry)


@pytest.mark.unit
def test_parse_dry_run_removals_extracts_minus_lines():
    """_parse_dry_run_removals must return normalised dist names from ' - name==ver' lines."""
    mgr = _make_manager()
    output = (
        "Resolved 68 packages in 912ms\n"
        "Would uninstall 2 packages\n"
        " - haybale-core==0.0.5\n"
        " + haybale-core==0.0.6\n"
        " - haybale-visiongraph==0.0.5\n"
        " + haybale-visiongraph==0.0.6\n"
    )
    result = mgr._parse_dry_run_removals(output)
    assert result == ["haybale-core", "haybale-visiongraph"]


@pytest.mark.unit
def test_parse_dry_run_removals_no_changes():
    """_parse_dry_run_removals must return empty list for 'Would make no changes'."""
    mgr = _make_manager()
    output = "Resolved 12 packages in 120ms\nWould make no changes\n"
    result = mgr._parse_dry_run_removals(output)
    assert result == []


@pytest.mark.unit
def test_parse_dry_run_removals_empty_output():
    """_parse_dry_run_removals must return empty list for empty output."""
    mgr = _make_manager()
    assert mgr._parse_dry_run_removals("") == []


@pytest.mark.unit
async def test_dry_run_returns_removals_list():
    """dry_run() must call uv with --dry-run and return parsed removal names."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        # Simulate uv output for a dry-run that would upgrade haybale-core
        on_output(" - haybale-core==0.0.5")
        on_output(" + haybale-core==0.0.6")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph")

    assert result == ["haybale-core"]


@pytest.mark.unit
async def test_dry_run_already_satisfied_returns_empty():
    """dry_run() must return [] when uv reports no changes needed."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        on_output("Would make no changes")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph==0.0.6")

    assert result == []


@pytest.mark.unit
async def test_dry_run_resolver_error_raises():
    """dry_run() must raise RuntimeError when uv exits non-zero."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "error: no solution found"

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="Dependency resolution failed"):
            await mgr.dry_run("haybale-bad-pkg")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_library_manager_dry_run.py -v
```

Expected: FAIL — `AttributeError: 'LibraryManager' object has no attribute 'dry_run'`

- [ ] **Step 3: Implement `_parse_dry_run_removals()`, `dry_run()`, and rename `install_streaming()` to `install()`**

In `library_manager.py`, replace the `install_streaming` method (lines 242–275) with the following three methods:

```python
def _parse_dry_run_removals(self, output: str) -> list[str]:
    """Parse `uv pip install --dry-run` stdout and return distribution names
    of packages that would be uninstalled (i.e. upgraded/replaced).

    Lines of interest look like: ' - haybale-core==0.0.5'
    """
    names = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            # ' - name==version' → 'name'
            pkg_spec = stripped[2:].strip()
            dist_name = pkg_spec.split("==")[0].split("[")[0].strip()
            if dist_name:
                names.append(dist_name)
    return names

async def dry_run(self, install_spec: str) -> list[str]:
    """Run `uv pip install --dry-run` and return distribution names of packages
    that would be removed (upgraded) by the install.

    Returns:
        List of pip distribution names that would be uninstalled.
        Empty list when the spec is already satisfied.

    Raises:
        RuntimeError: when uv's dependency resolver fails (non-zero exit).
    """
    if Path(install_spec).is_dir():
        args = ["install", "--dry-run", "-e", install_spec]
    else:
        args = ["install", "--dry-run", install_spec]

    collected: list[str] = []

    def _collect(line: str) -> None:
        collected.append(line)

    success, stderr = await self._run_uv_streaming(args, _collect)
    if not success:
        raise RuntimeError(f"Dependency resolution failed: {stderr}")

    full_output = "\n".join(collected)
    return self._parse_dry_run_removals(full_output)

async def install(
    self,
    install_spec: str,
    on_output: Callable[[str], None],
    source_pkg: "Haybale | None" = None,
) -> tuple[bool, str]:
    """Install a package with live output streaming.

    Before running pip, pre-evicts any already-loaded regular libraries that
    would be upgraded by this install (discovered via a prior dry_run() call
    stored in _pending_removals, or re-derived here if called directly).

    When ``source_pkg`` is supplied and ``self.project_dir`` is set, the
    project's pyproject.toml is updated after a successful install so the
    next ``uv sync`` reproduces the install (spec: library-manager-install-sync).
    """
    if Path(install_spec).is_dir():
        args = ["install", "-e", install_spec]
    else:
        args = ["install", install_spec]

    # Pre-evict libraries that pip is about to upgrade.
    # dry_run() is cheap (instant when nothing changes); running it here
    # ensures install() is always safe to call directly (e.g. from tests).
    try:
        to_remove = await self.dry_run(install_spec)
    except RuntimeError:
        # Resolver failure — the actual install will also fail and report it.
        to_remove = []

    evicted: list[str] = []
    for dist_name in to_remove:
        lib_id = self.registry.find_library_by_distribution_name(dist_name)
        if lib_id and self.registry.get_library_install_type(lib_id) == InstallType.REGULAR:
            self.registry.remove_library(lib_id)
            evicted.append(dist_name)

    if evicted:
        on_output(f"Preparing upgrade: removing {', '.join(evicted)} from registry…")

    success, stderr = await self._run_uv_streaming(args, on_output)
    if not success:
        return False, f"Install failed: {stderr}"

    on_output("Invalidating caches...")
    self._invalidate_caches()

    on_output("Scanning for libraries...")
    await asyncio.to_thread(self.registry.scan_for_libraries)

    on_output("Enabling libraries...")
    self.registry.enable_all_libraries()

    if source_pkg is not None:
        self._sync_install_to_pyproject(source_pkg, on_output)

    return True, f"Installed: {install_spec}"

async def install_streaming(
    self,
    install_spec: str,
    on_output: Callable[[str], None],
    source_pkg: "Haybale | None" = None,
) -> tuple[bool, str]:
    """Deprecated alias for install(). Use install() directly."""
    return await self.install(install_spec, on_output, source_pkg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_library_manager_dry_run.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run the full unit suite to check for regressions**

```bash
uv run pytest -m unit -v
```

Expected: all PASS.

- [ ] **Step 6: Lint and type-check**

```bash
uv run ruff check barn/haybale-marketplace/haybale_marketplace/library_manager.py
uv run mypy barn/haybale-marketplace/haybale_marketplace/library_manager.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py \
        tests/test_library_manager_dry_run.py
git commit -m "feat: split install_streaming into dry_run() + install() with pre-eviction"
```

---

## Task 4: New `upgrade_impact_modal`

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/modals/upgrade_impact_modal.py`
- Modify: `packages/haywire-core/src/haywire/ui/modals/__init__.py`

This modal shows two sections — "Installing" (the requested package) and "Also upgrading" (collateral side-effects) — with Cancel and Continue buttons. It follows the exact same `Popup`-based pattern as `confirm_modal` and `install_safety_modal`.

The modal is only shown when there are collateral upgrades. When the dry-run result is empty, the UI skips it entirely.

- [ ] **Step 1: Create `upgrade_impact_modal.py`**

```python
"""Upgrade impact modal — confirms collateral library upgrades before install.

Shown when `dry_run()` discovers that installing a requested library will
also upgrade other already-loaded libraries. Two sections:
  - "Installing": the package the user asked for
  - "Also upgrading": libraries that will be upgraded as side-effects

Two buttons: Cancel (abort) and Continue (proceed).
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.popup import Popup


def upgrade_impact_modal(
    *,
    installing: str,
    also_upgrading: list[str],
    on_continue: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
) -> Popup:
    """Open the upgrade impact confirmation modal and return the opened Popup.

    Args:
        installing: Display name of the package the user requested
            (e.g. "haybale-visiongraph").
        also_upgrading: List of pip distribution names that will be upgraded
            as collateral side-effects (e.g. ["haybale-core"]).
        on_continue: Called when the user clicks Continue. Popup closes after.
        on_cancel: Called when the user cancels. Optional.

    Returns:
        The opened Popup.
    """
    popup = Popup(
        title="Confirm install",
        width="400px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    confirmed = {"value": False}

    if on_cancel is not None:
        def _maybe_cancel() -> None:
            if not confirmed["value"]:
                on_cancel()
        popup.on_close(_maybe_cancel)

    with popup:
        with ui.column().classes("w-full gap-3 p-1"):
            with ui.column().classes("gap-1"):
                ui.label("Installing").classes("text-xs font-semibold hw-text-dim uppercase tracking-wide")
                ui.label(installing).classes("text-sm")

            ui.separator()

            with ui.column().classes("gap-1"):
                ui.label("Also upgrading").classes(
                    "text-xs font-semibold hw-text-dim uppercase tracking-wide"
                )
                ui.label(
                    "Installing this library requires upgrading the following already-loaded libraries."
                ).classes("text-xs hw-text-dim")
                for name in also_upgrading:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("upgrade", size="14px").classes("hw-text-accent")
                        ui.label(name).classes("text-sm font-mono")

            def _do_continue() -> None:
                confirmed["value"] = True
                on_continue()
                popup.close()

            with ui.row().classes("w-full justify-end gap-2 mt-1"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button("Continue", on_click=_do_continue).props("flat dense").style(
                    "color: var(--hw-positive);"
                )

    popup.open()
    return popup
```

- [ ] **Step 2: Register in `__init__.py`**

In `packages/haywire-core/src/haywire/ui/modals/__init__.py`, add the import and export:

```python
from .upgrade_impact_modal import upgrade_impact_modal
```

And add `"upgrade_impact_modal"` to `__all__`.

The full updated file should be:

```python
"""Reusable modal dialogs built on :class:`haywire.ui.components.popup.Popup`."""

from .confirm_modal import confirm_modal
from .diff_modal import DiffSection, diff_modal
from .info_modal import info_modal
from .install_progress_modal import InstallProgressModal, install_progress_modal
from .install_safety_modal import install_safety_modal
from .pick_modal import pick_modal
from .rename_modal import rename_modal
from .save_as_modal import save_as_modal
from .upgrade_impact_modal import upgrade_impact_modal

__all__ = [
    "DiffSection",
    "InstallProgressModal",
    "confirm_modal",
    "diff_modal",
    "info_modal",
    "install_progress_modal",
    "install_safety_modal",
    "pick_modal",
    "rename_modal",
    "save_as_modal",
    "upgrade_impact_modal",
]
```

- [ ] **Step 3: Lint and type-check**

```bash
uv run ruff check packages/haywire-core/src/haywire/ui/modals/
uv run mypy packages/haywire-core/src/haywire/ui/modals/
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/modals/upgrade_impact_modal.py \
        packages/haywire-core/src/haywire/ui/modals/__init__.py
git commit -m "feat: add upgrade_impact_modal for pre-install collateral upgrade confirmation"
```

---

## Task 5: Rewrite `_install_package()` in `LibraryOverviewEditor`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:1453-1489`

Replaces the current single-step fire-and-forget with the 3-step flow:
1. (Already done upstream) `install_safety_modal` — unchanged
2. Run `dry_run()` — if collateral upgrades exist, open `upgrade_impact_modal` and wait for Continue
3. Open `install_progress_modal`, call `manager.install()`, call `modal.finish()`

The existing `_create_log_in_card` helper is no longer called from `_install_package` (it remains in the file for `_do_uninstall` and `_do_rename` which still use it).

- [ ] **Step 1: Rewrite `_install_package()`**

Find the method at line 1453 and replace it entirely:

```python
async def _install_package(
    self,
    install_spec: str,
    name: str,
    button,
    manager,
    context: "SessionContext",
    source_pkg: Haybale | None = None,
):
    """Install a package using the 3-step flow:
    dry-run → optional upgrade-impact confirmation → streaming progress popup.

    ``source_pkg`` enables write-back to the project's pyproject.toml so the
    install is reproducible via ``uv sync`` (spec: library-manager-install-sync).
    """
    from haywire.ui.modals import install_progress_modal, upgrade_impact_modal

    if button:
        try:
            button.disable()
            button.props("loading")
        except Exception:
            pass

    # Step 1: dry-run to discover collateral upgrades
    try:
        removals = await manager.dry_run(install_spec)
    except RuntimeError as exc:
        ui.notify(str(exc), type="negative")
        if button:
            try:
                button.enable()
                button.props(remove="loading")
            except Exception:
                pass
        return

    # Step 2: if collateral upgrades exist, confirm with the user
    if removals:
        confirmed = {"value": False}

        def _on_continue() -> None:
            confirmed["value"] = True

        upgrade_impact_modal(
            installing=name,
            also_upgrading=removals,
            on_continue=_on_continue,
        )

        # Wait for the user's decision (poll via asyncio.sleep — the modal
        # callbacks run on the NiceGUI event loop in the same task context).
        import asyncio as _asyncio
        for _ in range(600):  # 60 s timeout
            if confirmed["value"]:
                break
            await _asyncio.sleep(0.1)
        else:
            # Timed out or cancelled — abort silently
            if button:
                try:
                    button.enable()
                    button.props(remove="loading")
                except Exception:
                    pass
            return

        if not confirmed["value"]:
            if button:
                try:
                    button.enable()
                    button.props(remove="loading")
                except Exception:
                    pass
            return

    # Step 3: open progress popup and run the install
    progress = install_progress_modal(title=f"Installing {name}…")

    success, message = await manager.install(install_spec, progress.push, source_pkg)

    if success:
        progress.push(f"--- {name} installed successfully ---")
        progress.finish()
        ui.notify(f"Installed: {name}", type="positive")
        installed = self._find_installed_by_dist_name(name, manager)
        if installed:
            context.active_library = installed
        self._notify_library_changed(context)
    else:
        progress.push(f"--- ERROR: {message} ---")
        progress.finish(error=message)
        ui.notify(message, type="negative")
```

- [ ] **Step 2: Run the full unit suite**

```bash
uv run pytest -m unit -v
```

Expected: all PASS.

- [ ] **Step 3: Lint and type-check**

```bash
uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
uv run mypy barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
git commit -m "feat: rewrite _install_package() with dry-run, upgrade impact modal, progress popup"
```

---

## Task 6: End-to-end verification

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest
```

Expected: all tests PASS (922 unit tests + integration).

- [ ] **Step 2: Lint and type-check the entire touched surface**

```bash
uv run ruff check \
    packages/haywire-core/src/haywire/core/library/registry.py \
    packages/haywire-core/src/haywire/ui/modals/ \
    barn/haybale-marketplace/haybale_marketplace/library_manager.py \
    barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py

uv run mypy \
    packages/haywire-core/src/haywire/ \
    barn/haybale-marketplace/haybale_marketplace/
```

Expected: no errors.

- [ ] **Step 3: Manual smoke test**

```bash
uv run haywire
```

1. Open the marketplace in the Library panel.
2. Select an available library and click Install.
3. Verify: safety modal appears → click Install.
4. If the library has a collateral upgrade: verify the Upgrade Impact popup appears listing the collateral libraries → click Continue.
5. Verify: Install Progress popup opens with spinner and streaming log lines.
6. Verify: on completion, spinner disappears and "Done" button appears.
7. Verify: the graph editor remains functional (nodes not missing).

---

## Self-Review

### Spec coverage

| Requirement | Task |
|---|---|
| `remove_library()` ejects `sys.modules` | Task 1 |
| `find_library_by_distribution_name()` | Task 1 |
| Delete redundant ejection in `update_library_identity` | Task 2 |
| `_parse_dry_run_removals()` private method | Task 3 |
| `dry_run()` method | Task 3 |
| `install()` method with pre-eviction | Task 3 |
| `install_streaming()` deprecated alias | Task 3 |
| `upgrade_impact_modal` with two sections | Task 4 |
| `install_progress_modal` (already created) | Pre-existing |
| `popup.vue` width fix (already applied) | Pre-existing |
| 3-step install flow in `_install_package()` | Task 5 |

### Potential issues

**Polling loop in Task 5:** The `upgrade_impact_modal` confirmation uses an asyncio polling loop (`for _ in range(600): await sleep(0.1)`). This is the correct NiceGUI pattern for waiting on a user action inside an `async` handler without blocking the event loop. The 60-second timeout gracefully aborts if the user does nothing. If the user clicks Cancel on the `upgrade_impact_modal` (via backdrop or X), `confirmed["value"]` stays False and the loop expires → abort path taken. This is correct.

**`install()` runs dry-run a second time internally:** By design (Task 3 spec, Q2=B answer). The second dry-run is instant when nothing changes (uv resolves from lock). The pre-eviction inside `install()` is a safety net for callers that bypass `_install_package()` (e.g. tests, scripts). The UI's dry-run call and the internal one may differ by milliseconds — this is safe because we only act on the internal result.

**`_create_log_in_card` is kept:** `_do_uninstall` and `_do_rename` still use it. Do not remove it.
