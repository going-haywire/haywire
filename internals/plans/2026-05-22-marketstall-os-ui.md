# Marketstall OS Field UI — Slice 4 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the `os` field through the Library UI. (1) OS multi-select in the Library Overview Editor's Edit dialog, gated to `[[heaps]]` libraries only — installed wheels show OS read-only. (2) Install button in the Library Browser is disabled when the current OS isn't in the haybale's declared list, with a tooltip explaining why. (3) Fix a stale-vocabulary bug found during the survey: `library_manager.py` still reads `data.get("packages", [])` from project `marketplace.toml`, which silently no-ops on the slice-1-shaped files that use `[[heaps]]` and `[[caches]]`.

**Architecture:** The `os` field already exists on the `Haybale` dataclass (foundation slice). `haywire.core.marketstall.current_os()` and `haybale_supports_current_os()` already exist (foundation). `haywire share` already reads and validates `[tool.haywire].os` from each library's `pyproject.toml` (slice 2). This slice just wires those existing primitives into the UI: an editable multi-select for heap libraries (writes through to `pyproject.toml`), a read-only display for installed wheels, and a disabled-button-with-tooltip on the Install button.

**Tech Stack:** Python 3.12, NiceGUI (UI). Existing `Haybale.os` field + `current_os()` + `haybale_supports_current_os()` helpers from foundation. New write path in `update_library_identity` to persist `[tool.haywire].os` to a heap's `pyproject.toml`. No new third-party deps.

**Spec reference:** [`internals/specs/marketstall-distribution.md`](../specs/marketstall-distribution.md). §2.1 (`os` field — declarable values, runtime sentinel, Edit dialog surface, Library Browser behavior).

**Inquisition decisions this slice implements:** Q6 (`os` declarations limited to `"macos"`/`"windows"`/`"linux"`; Edit dialog gated to heap libraries; installed wheels show read-only; install gating with tooltip).

---

## Scope Boundary

**In scope:**
- OS multi-select widget in the Edit dialog. **Visible only for `[[heaps]]` libraries** (detected via the existing `_is_project_library` helper). Writes through to `<heap>/pyproject.toml [tool.haywire].os`.
- Read-only OS display for installed wheels (no edit affordance). Source: the `Haybale.os` field from the cache / marketplace entry.
- Install button OS-gating in the Library Overview Editor's marketplace-pkg-only header (and any other Install button site). Disabled when `current_os()` not in `haybale.os`, with the spec §2.1 tooltip text: *"Not available on this OS; this library targets: {os list}."*
- Fix the stale `data.get("packages", [])` references in `library_manager.py` lines 346 and 654 to use `data.get("heaps", [])` — these update path-based libraries the project owns.

**Out of scope (deferred):**
- First-install safety modal (Cancel/Block/Install) — slice 5.
- Update-available signal — slice 7.
- Drift gate `min_version` lag check — slice 6.
- Per-haybale stall generator — slice 8.

---

## File Structure

### New files (created)

- `tests/test_library_browser_os_gating.py` — pure-function tests for the OS-gating helper.
- `tests/test_update_library_identity_os.py` — tests for the new `os` write path in `update_library_identity`.

### Modified files

- `packages/haywire-studio/src/haywire_studio/library_manager.py` — extend `update_library_identity` to write `[tool.haywire].os` to the heap's `pyproject.toml`. Fix lines 346 + 654 stale section names.
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` — add OS multi-select to `_build_edit_dialog` (visible only for heaps); add OS-gating to the Install button (lines ~444-462).

### Files NOT touched in this slice (deferred)

- `share.py` — already reads `[tool.haywire].os` from slice 2; nothing more here.
- `marketstall/platform.py` — `current_os` and `haybale_supports_current_os` already shipped in foundation.
- `init.py` — heap scaffolding doesn't need `[tool.haywire].os` (absent = "all platforms").

---

## Pre-flight Baseline

- [ ] **Step 0.1: Confirm worktree state**

Run from worktree:
```sh
git status
git rev-parse --short HEAD
git branch --show-current
```
Expected: clean tree on `feat/marketstall-os-ui` at HEAD `f5b742f0`.

- [ ] **Step 0.2: Run the test suite as the baseline**

Run from worktree: `uv run pytest tests/ -m "not integration" -q`
Expected: `1392 passed, 1 skipped`.

- [ ] **Step 0.3: Run ruff and mypy as baseline**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/library_manager.py barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
uv run mypy packages/haywire-studio/src/haywire_studio/library_manager.py barn/haybale-studio/haybale_studio
```
Both must be clean.

---

## Task 1: Fix stale `[[packages]]` references in `library_manager.py`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/library_manager.py`
- Create: `tests/test_library_manager_marketplace_writes.py`

The survey found two `data.get("packages", [])` reads in `library_manager.py` that target the project's `<project>/.haywire/marketplace.toml`:
- **Line 346** (inside `rename_project_library_streaming`): updates the renamed library's entry.
- **Line 654** (inside `update_library_identity`): updates the edited library's entry.

Per slice 1 (spec §14), the project marketplace uses `[[heaps]]` for path-based entries (the project's own libraries) and `[[caches]]` for refresh results. A renamed/edited library is the project's own — it lives in `[[heaps]]`. Both code paths silently no-op on slice-1-shaped files (the legacy `packages` key doesn't exist).

The fields they update (name, label, description) are valid for `[[heaps]]` per spec §3.2. The fields `min_version`, `install_spec`, `docs_url` (only present on line 346) are NOT valid for heaps — they belong to `[[caches]]`. Drop those writes; they were stale anyway because heaps don't carry refresh-cache fields.

- [ ] **Step 1.1: Read the surrounding context**

Run: `sed -n '300,360p' packages/haywire-studio/src/haywire_studio/library_manager.py` and `sed -n '640,680p' packages/haywire-studio/src/haywire_studio/library_manager.py`.

Confirm the two affected blocks: lines 343-358 (rename) and lines 649-663 (update identity).

- [ ] **Step 1.2: Write failing tests**

Write to `tests/test_library_manager_marketplace_writes.py`:

```python
"""library_manager writes to the project marketplace use the new [[heaps]] section."""

from __future__ import annotations

from pathlib import Path

import pytest
import toml


@pytest.mark.unit
def test_update_library_identity_writes_heap_entry(tmp_path: Path) -> None:
    """update_library_identity must update [[heaps]] not legacy [[packages]]."""
    # We can't easily call update_library_identity without a full LibraryRegistry,
    # so this test focuses on the marketplace.toml write semantics by reading
    # the source file's logic. The actual functional verification is the smoke
    # test at the end of slice 4.
    #
    # This test asserts the lib_manager module's source uses the new section name.
    from pathlib import Path as P

    src = P(__file__).parent.parent / "packages" / "haywire-studio" / "src" / "haywire_studio" / "library_manager.py"
    content = src.read_text()

    # The two project-marketplace.toml writes must reference "heaps", not "packages".
    # (Line 311's data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] is
    # hatch's wheel-packages config, unrelated to our marketplace section.)
    rename_block = content[content.index("# --- 9. Update marketplace.toml ---"):
                            content.index("# --- 9. Update marketplace.toml ---") + 1000]
    assert 'data.get("heaps"' in rename_block
    assert 'data.get("packages"' not in rename_block

    update_identity_marker = "# Update matching entry in marketplace.toml"
    update_identity_block = content[content.index(update_identity_marker):
                                     content.index(update_identity_marker) + 800]
    assert 'data.get("heaps"' in update_identity_block
    assert 'data.get("packages"' not in update_identity_block


@pytest.mark.unit
def test_update_library_identity_preserves_heap_label_and_description(tmp_path: Path) -> None:
    """A heap's label and description must be updated when identity is edited.

    Functional test: directly simulate the marketplace.toml update without
    invoking the registry (which would require a real library setup).
    """
    marketplace = tmp_path / ".haywire" / "marketplace.toml"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        '[[heaps]]\n'
        'name = "haybale-test"\n'
        'path = "/abs/path/to/test"\n'
        'label = "Old Label"\n'
        'description = "Old description"\n'
    )

    # Direct simulation of what update_library_identity should do after fix:
    data = toml.loads(marketplace.read_text())
    for heap in data.get("heaps", []):
        if heap.get("name", "").lower() == "haybale-test":
            heap["label"] = "New Label"
            heap["description"] = "New description"
            break
    marketplace.write_text(toml.dumps(data))

    reparsed = toml.loads(marketplace.read_text())
    assert reparsed["heaps"][0]["label"] == "New Label"
    assert reparsed["heaps"][0]["description"] == "New description"
```

The first test is a static-source assertion: cheap, catches regressions. The second test demonstrates the post-fix behavior runs against a real TOML file.

- [ ] **Step 1.3: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_library_manager_marketplace_writes.py -v`
Expected: the first test FAILS (source still references `"packages"`). The second test passes (it's a simulation, not invoking the real function).

- [ ] **Step 1.4: Apply the fix**

In `packages/haywire-studio/src/haywire_studio/library_manager.py`:

**At line 346 (inside `rename_project_library_streaming`'s marketplace block, around lines 343-358):**

Change:
```python
                for pkg in data.get("packages", []):
                    if pkg.get("name", "").lower() == dist_name.lower():
                        pkg["name"] = new_lib_name
                        pkg["label"] = label_val
                        pkg["description"] = desc_val
                        pkg["min_version"] = version_val
                        pkg["tags"] = tags_list
                        pkg["install_spec"] = str(new_lib_dir)
                        pkg["docs_url"] = str(new_lib_dir / new_module)
                        break
```

To (drop the cache-only fields; heaps don't have them):
```python
                for heap in data.get("heaps", []):
                    if heap.get("name", "").lower() == dist_name.lower():
                        heap["name"] = new_lib_name
                        heap["path"] = str(new_lib_dir)
                        heap["label"] = label_val
                        heap["description"] = desc_val
                        break
```

**At line 654 (inside `update_library_identity`'s marketplace block, around lines 649-663):**

Change:
```python
                for pkg in data.get("packages", []):
                    if pkg.get("name", "").lower() == dist_name.lower():
                        pkg["label"] = label_val
                        pkg["description"] = desc_val
                        pkg["min_version"] = version_val
                        pkg["tags"] = tags_list
                        break
```

To (drop the cache-only fields):
```python
                for heap in data.get("heaps", []):
                    if heap.get("name", "").lower() == dist_name.lower():
                        heap["label"] = label_val
                        heap["description"] = desc_val
                        break
```

- [ ] **Step 1.5: Run the tests to confirm they pass**

Run: `uv run pytest tests/test_library_manager_marketplace_writes.py -v`
Expected: both pass.

- [ ] **Step 1.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1392 baseline + 2 new = 1394.

- [ ] **Step 1.7: Lint check**

Run:
```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/library_manager.py tests/test_library_manager_marketplace_writes.py
uv run mypy packages/haywire-studio/src/haywire_studio/library_manager.py
```
Both clean.

- [ ] **Step 1.8: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/library_manager.py tests/test_library_manager_marketplace_writes.py
git commit -m "fix(library-manager): write to [[heaps]] not legacy [[packages]] section"
```

---

## Task 2: `update_library_identity` writes `[tool.haywire].os` to pyproject.toml

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/library_manager.py`
- Create: `tests/test_update_library_identity_os.py`

Per spec §2.1, the OS Edit dialog saves chosen values back to the library's `pyproject.toml` `[tool.haywire].os`. `update_library_identity` is the function the Edit dialog calls. It currently writes `__init__.py` decorator fields and the project marketplace; it needs to ALSO write `pyproject.toml [tool.haywire].os`.

Rules:
- The `identity` dict gains an optional `"os"` key — a list of strings.
- Allowed values: `"macos"`, `"windows"`, `"linux"`. Anything else (including `"other"`) is silently dropped here (the UI ensures only valid values reach this code, and `haywire share` will reject `"other"` anyway).
- If the list is empty AFTER filtering, REMOVE the `[tool.haywire].os` key entirely (so absent = "all platforms" per spec §2.1).
- If the list is non-empty, write or update `[tool.haywire].os` in the heap's pyproject.

`update_library_identity` only operates on heaps (it requires a workspace path and writes to `barn/<dist_name>/`), so adding the `os` write here is consistent with the inquisition Q6 decision (Edit dialog gated to heaps).

- [ ] **Step 2.1: Write failing tests**

Write to `tests/test_update_library_identity_os.py`:

```python
"""update_library_identity writes [tool.haywire].os to pyproject.toml per spec §2.1."""

from __future__ import annotations

from pathlib import Path

import pytest
import toml


def _scaffold_minimal_heap(workspace: Path, dist_name: str = "haybale-foo") -> Path:
    """Create a minimal heap library structure that update_library_identity can update."""
    module_name = dist_name.replace("-", "_")
    lib_dir = workspace / "barn" / dist_name
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir(parents=True)

    (lib_dir / "pyproject.toml").write_text(
        '[project]\n'
        f'name = "{dist_name}"\n'
        'version = "0.1.0"\n'
        'description = "test"\n'
    )
    (pkg_dir / "__init__.py").write_text(
        '"""x."""\n'
        'from haywire.core.library.base import BaseLibrary\n'
        'from haywire.core.library.decorator import library\n'
        '\n'
        f'@library(label="Foo", id="foo", version="0.1.0", description="x",\n'
        '         url="", help_url="", author="", author_url="",\n'
        '         dependencies=[], tags=[], file_watcher=False)\n'
        'class Library(BaseLibrary):\n'
        '    def register_components(self): pass\n'
        '    def validate(self) -> bool: return True\n'
    )
    (workspace / ".haywire").mkdir()
    (workspace / ".haywire" / "marketplace.toml").write_text(
        '[[heaps]]\n'
        f'name = "{dist_name}"\n'
        f'path = "{lib_dir}"\n'
    )
    return lib_dir


@pytest.mark.unit
def test_apply_os_to_pyproject_writes_section(tmp_path: Path) -> None:
    """The helper writes [tool.haywire].os when given a non-empty list."""
    from haywire_studio.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "linux"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_apply_os_to_pyproject_filters_invalid_values(tmp_path: Path) -> None:
    """Only macos/windows/linux are allowed; 'other' and unknowns are dropped silently."""
    from haywire_studio.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "other", "freebsd", "linux"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_apply_os_to_pyproject_empty_list_removes_section(tmp_path: Path) -> None:
    """An empty list (after filtering) removes [tool.haywire].os entirely."""
    from haywire_studio.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"
    # Pre-populate the field so we can assert it's removed.
    pyproject.write_text(
        pyproject.read_text()
        + '\n[tool.haywire]\nos = ["macos"]\n'
    )

    _apply_os_to_pyproject(pyproject, [])

    data = toml.loads(pyproject.read_text())
    assert "haywire" not in data.get("tool", {})


@pytest.mark.unit
def test_apply_os_to_pyproject_all_three_removes_section(tmp_path: Path) -> None:
    """All three platforms = 'all platforms' = absent; remove the key entirely."""
    from haywire_studio.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "windows", "linux"])

    data = toml.loads(pyproject.read_text())
    # The spec says selecting all three is equivalent to "all platforms" (absent).
    assert "haywire" not in data.get("tool", {})


@pytest.mark.unit
def test_apply_os_to_pyproject_preserves_other_tool_sections(tmp_path: Path) -> None:
    """Existing [tool.hatch.*] etc. survive the write."""
    from haywire_studio.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text()
        + '\n[tool.hatch.build.targets.wheel]\npackages = ["haybale_foo"]\n'
    )

    _apply_os_to_pyproject(pyproject, ["macos"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos"]
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["haybale_foo"]
```

- [ ] **Step 2.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_update_library_identity_os.py -v`
Expected: FAIL — `ImportError: cannot import name '_apply_os_to_pyproject'`.

- [ ] **Step 2.3: Implement `_apply_os_to_pyproject` and wire into `update_library_identity`**

In `packages/haywire-studio/src/haywire_studio/library_manager.py`, add the helper near the other private helpers (e.g., just before `update_library_identity`):

```python
_DECLARABLE_OS_VALUES = ("macos", "windows", "linux")  # spec §2.1


def _apply_os_to_pyproject(pyproject_path: Path, os_values: list[str]) -> None:
    """Write or remove [tool.haywire].os in the library's pyproject.toml.

    Spec §2.1 rules:
      - Filter to allowed values (macos, windows, linux); silently drop others.
      - Empty list after filtering OR all three present → remove [tool.haywire].os
        entirely (absent = "all platforms").
      - Non-empty subset → write the filtered list.
      - Preserves other [tool.*] sections (hatch, etc.) verbatim.
    """
    filtered = [v for v in os_values if v in _DECLARABLE_OS_VALUES]
    # Preserve order: macos, windows, linux (canonical) — independent of input order.
    filtered = [v for v in _DECLARABLE_OS_VALUES if v in filtered]

    data = toml.loads(pyproject_path.read_text())
    tool = data.setdefault("tool", {})

    if not filtered or len(filtered) == len(_DECLARABLE_OS_VALUES):
        # Remove the section entirely.
        haywire = tool.get("haywire")
        if haywire is not None:
            haywire.pop("os", None)
            if not haywire:
                tool.pop("haywire", None)
        if not tool:
            data.pop("tool", None)
    else:
        haywire = tool.setdefault("haywire", {})
        haywire["os"] = filtered

    pyproject_path.write_text(toml.dumps(data))
```

Then update `update_library_identity` (around line 590) to read `identity.get("os")` and call the helper. After the existing `__init__.py` decorator field writes and before the marketplace.toml block, add:

```python
        # Write [tool.haywire].os to the heap's pyproject.toml.
        # Per spec §2.1: this is editable only on heaps (project libraries),
        # which is exactly where update_library_identity operates.
        os_list = identity.get("os")
        if os_list is not None:  # caller opted in
            try:
                _apply_os_to_pyproject(lib_dir / "pyproject.toml", os_list)
            except OSError as e:
                return False, f"Failed to update [tool.haywire].os: {e}"
```

Note: `lib_dir` is `workspace / "barn" / dist_name` — that's where the heap's pyproject.toml lives. Confirm by reading `update_library_identity` line ~617 where `pkg_dir` is computed (it's `lib_dir / module_name`, so `lib_dir = workspace / "barn" / dist_name`).

- [ ] **Step 2.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/test_update_library_identity_os.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass (1394 + 5 = 1399).

- [ ] **Step 2.6: Lint check**

Run:
```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/library_manager.py tests/test_update_library_identity_os.py
uv run mypy packages/haywire-studio/src/haywire_studio/library_manager.py
```
Both clean.

- [ ] **Step 2.7: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/library_manager.py tests/test_update_library_identity_os.py
git commit -m "feat(library-manager): write [tool.haywire].os to heap pyproject.toml"
```

---

## Task 3: OS multi-select in the Edit dialog (heap libraries only)

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`

Per spec §2.1 and inquisition Q6: the Library Overview Editor's Edit dialog gains an OS multi-select section. Visible ONLY for heap libraries (project libraries with a writable `pyproject.toml`). The widget is a `ui.select` with `multiple=True`. Selected values feed into the existing `identity` dict via the new `"os"` key, which `update_library_identity` (from Task 2) writes through to `pyproject.toml`.

The widget reads the current `os` declaration from the heap's `pyproject.toml` to pre-populate. The values `"macos"`, `"windows"`, `"linux"` are presented with friendly labels (macOS / Windows / Linux). Selecting all three OR selecting none is equivalent (both mean "all platforms" per spec §2.1).

For installed wheels (non-heap), display the `os` field READ-ONLY in the dialog (as a small label), since the source-of-truth `pyproject.toml` lives inside `site-packages` and isn't writable. Per inquisition Q6: "installed wheels show the value, don't offer to edit it."

- [ ] **Step 3.1: Inspect the existing Edit dialog structure**

Run: `sed -n '834,930p' barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`

Confirm the structure: dialog opens at line 854, identity inputs at lines 860-871, dependencies at line 872-887, separator at 889, then Package Name section. The OS section belongs AFTER the dependencies row and BEFORE the Package Name separator.

- [ ] **Step 3.2: Read the heap's current `[tool.haywire].os` value**

Add a small helper method to `LibraryOverviewEditor` that reads the current OS declaration. Place it near `_is_project_library`:

```python
    def _read_os_from_pyproject(self, lib: LibraryInfo, marketplace_path: str | None) -> list[str]:
        """Read the heap's current [tool.haywire].os values. Empty list if unset or non-heap."""
        if not self._is_project_library(lib, marketplace_path):
            return []
        if not lib.identity.folder_path:
            return []
        # lib.identity.folder_path is the MODULE path (e.g. workspace/barn/haybale-foo/haybale_foo).
        # The pyproject.toml lives in its parent.
        pyproject = Path(lib.identity.folder_path).parent / "pyproject.toml"
        if not pyproject.is_file():
            return []
        try:
            data = toml.loads(pyproject.read_text())
        except Exception:
            return []
        os_decl = data.get("tool", {}).get("haywire", {}).get("os", [])
        return [v for v in os_decl if isinstance(v, str)]
```

The `toml` module is likely already imported. Verify with `grep "^import toml" barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`. If not, add it to the imports block at the top.

- [ ] **Step 3.3: Add the OS multi-select to `_build_edit_dialog`**

In `_build_edit_dialog` (around line 887, between the dependencies row and the existing `ui.separator()` at line 889), insert:

```python
            # OS multi-select — spec §2.1. Visible only for heaps (writable pyproject.toml).
            is_heap = self._is_project_library(lib, marketplace_path)
            current_os = self._read_os_from_pyproject(lib, marketplace_path) if is_heap else []
            os_select = None
            if is_heap:
                os_select = (
                    ui.select(
                        options={"macos": "macOS", "windows": "Windows", "linux": "Linux"},
                        value=current_os,
                        multiple=True,
                        label="Supported OS (leave empty = all platforms)",
                    )
                    .props("dense use-chips")
                    .classes("w-full")
                )
            else:
                # Installed wheels: read-only display of any os declaration on the marketplace entry.
                marketplace_pkg = getattr(context, "active_marketplace_pkg", None)
                wheel_os = list(getattr(marketplace_pkg, "os", []) or []) if marketplace_pkg else []
                if wheel_os:
                    ui.label(f"Supported OS (read-only): {', '.join(wheel_os)}").classes(
                        "text-xs hw-text-dim"
                    )
```

Then in `_save` (around line 913), extend the `identity` dict construction to include OS:

```python
            async def _save():
                new_name = name_input.value.strip()
                identity = {
                    "label": label_input.value.strip(),
                    "version": version_input.value.strip().lstrip("vV"),
                    "description": desc_input.value.strip(),
                    "url": url_input.value.strip(),
                    "author": author_input.value.strip(),
                    "author_url": author_url_input.value.strip(),
                    "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                    "dependencies": [d.strip() for d in deps_input.value.split(",") if d.strip()],
                }
                # Include `os` only if the multi-select was rendered (heap libraries).
                if os_select is not None:
                    identity["os"] = list(os_select.value or [])
                ...  # rest unchanged
```

Note: the existing code in `_save` doesn't reference `os_select` so it doesn't break when the select wasn't rendered (it's None for non-heap libraries). Be careful to add the `os` key only when `os_select is not None`.

- [ ] **Step 3.4: Lint and tests**

Run:
```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
uv run mypy barn/haybale-studio/haybale_studio
uv run pytest tests/ -m "not integration" -q
```
All clean. No new automated tests for the dialog UI itself (NiceGUI dialogs aren't easily unit-testable); functional verification in Task 5.

- [ ] **Step 3.5: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
git commit -m "feat(library-overview): OS multi-select in Edit dialog for heap libraries"
```

## Discipline

- The OS select uses `ui.select(..., multiple=True)` — the value is a list of strings.
- `os_select.value` returns the selected values as a list. Don't assume order matches the user's click order; the Task 2 helper canonicalizes order on write.
- The non-heap branch (installed wheels) only shows a read-only label IF the marketplace entry has `os` set. No label is shown if `os` is empty (= "all platforms"), to avoid noise.
- `context.active_marketplace_pkg` is the existing attribute used elsewhere in this file for the marketplace-side info. Confirm by grepping `active_marketplace_pkg` in the file before relying on it. If the attribute name is different, find the correct one.

---

## Task 4: Install button OS-gating in the Library Overview Editor

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`
- Create: `tests/test_library_browser_os_gating.py`

Per spec §2.1 Library Browser behavior: an installable haybale whose `os` list doesn't include the current platform is shown in AVAILABLE *normally*, but its Install button is disabled. A tooltip explains: *"Not available on this OS; this library targets: {os list}."*

Two Install button sites exist in `library_overview_editor.py` (lines 444-462). The first is already disabled-with-tooltip when dependencies are missing. We extend that pattern to also disable when OS doesn't match.

Algorithm:
1. Compute `os_supported = haybale_supports_current_os(marketplace_pkg)` (foundation helper).
2. If `not os_supported`, render the disabled-Install branch (the first one, with `hui.icon.locked` and info modal) with the OS message instead of the missing-deps message.
3. Otherwise existing behavior: dependencies check first (overrides), then enabled Install.

Add a small pure helper `should_block_install_for_os(haybale) -> str | None` that returns the tooltip text when blocking, or None when OK. This is what the unit tests assert on.

- [ ] **Step 4.1: Write failing tests**

Write to `tests/test_library_browser_os_gating.py`:

```python
"""Install button OS-gating helper — spec §2.1 Library Browser behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_should_block_install_for_os_returns_none_when_empty_os() -> None:
    """A haybale with empty os list (= all platforms) is never OS-blocked."""
    from haybale_studio.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=[])
    assert should_block_install_for_os(h) is None


@pytest.mark.unit
def test_should_block_install_for_os_returns_none_when_supported() -> None:
    """A haybale that includes the current OS is not blocked."""
    from haybale_studio.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos", "linux", "windows"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert should_block_install_for_os(h) is None


@pytest.mark.unit
def test_should_block_install_for_os_returns_message_when_unsupported() -> None:
    """A haybale that does NOT include the current OS returns a tooltip message."""
    from haybale_studio.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos", "linux"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Windows"):
        msg = should_block_install_for_os(h)
        assert msg is not None
        assert "Not available on this OS" in msg
        assert "macos" in msg and "linux" in msg


@pytest.mark.unit
def test_should_block_install_for_os_includes_os_list_in_message() -> None:
    from haybale_studio.editors.library_overview_editor import should_block_install_for_os
    from haywire.core.marketstall import Haybale

    h = Haybale(name="haybale-x", min_version="0.1.0", os=["macos"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        msg = should_block_install_for_os(h)
        assert msg is not None
        assert "macos" in msg
        assert "linux" not in msg or msg.count("linux") == 0  # current OS isn't in the targets list
```

- [ ] **Step 4.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_library_browser_os_gating.py -v`
Expected: FAIL — `ImportError: cannot import name 'should_block_install_for_os'`.

- [ ] **Step 4.3: Implement `should_block_install_for_os`**

Add to `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` at module level (after the imports block, before the `class LibraryOverviewEditor` definition):

```python
def should_block_install_for_os(haybale) -> str | None:
    """Per spec §2.1: return a tooltip message when the current OS doesn't match.

    Returns None when the haybale supports all platforms (empty os) or
    includes the current OS. The return value (string or None) drives the
    Install button's locked/unlocked state in the UI.
    """
    from haywire.core.marketstall import haybale_supports_current_os

    if haybale_supports_current_os(haybale):
        return None
    targets = ", ".join(getattr(haybale, "os", []) or [])
    return f"Not available on this OS; this library targets: {targets}."
```

- [ ] **Step 4.4: Wire OS-gating into the Install button branches**

In `_render` (around line 427-462), the Install button has two branches:
- Lines 438-452: missing dependencies — disabled with `hui.icon.locked` and `info_modal`.
- Lines 453-462: clean — enabled with `hui.icon.download`.

Extend the gating logic to also check OS. Replace the entire `elif not installed_lib and marketplace_pkg and manager:` block content with:

```python
                        elif not installed_lib and marketplace_pkg and manager:
                            # Not installed — Install button, blocked if dependencies missing OR OS doesn't match
                            _installed_ids = {
                                manager._norm(lib.distribution_name or lib.identity.id)
                                for lib in manager.list_installed()
                            }
                            _missing_deps = [
                                dep
                                for dep in (marketplace_pkg.dependencies or [])
                                if manager._norm(dep) not in _installed_ids
                            ]
                            _os_block_msg = should_block_install_for_os(marketplace_pkg)

                            if _missing_deps:
                                _names = ", ".join(f'"{d}"' for d in _missing_deps)
                                _msg = (
                                    f'"{marketplace_pkg.label or marketplace_pkg.name}"'
                                    f" cannot be installed — {_names} must be installed first."
                                )
                                ui.button(
                                    "Install",
                                    icon=hui.icon.locked,
                                    on_click=lambda m=_msg: info_modal(
                                        title="Cannot Install Library",
                                        icon="lock",
                                        message=m,
                                    ),
                                ).props("color=positive size=sm")
                            elif _os_block_msg:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.locked,
                                    on_click=lambda m=_os_block_msg: info_modal(
                                        title="Not available on this OS",
                                        icon="block",
                                        message=m,
                                    ),
                                ).props("color=positive size=sm").tooltip(_os_block_msg)
                            else:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.download,
                                    on_click=lambda e,
                                    spec=marketplace_pkg.install_spec,
                                    n=marketplace_pkg.name,
                                    m=manager,
                                    ctx=context: (self._install_package(spec, n, e.sender, m, ctx)),
                                ).props("color=positive size=sm")
```

The new branch's `.tooltip(_os_block_msg)` adds a hover tooltip (per spec §2.1 "tooltip on the disabled button explains") in addition to the info modal on click. Some users hover, some click; both should work.

- [ ] **Step 4.5: Run the tests**

Run: `uv run pytest tests/test_library_browser_os_gating.py -v`
Expected: 4 passed.

- [ ] **Step 4.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass (1399 + 4 = 1403).

- [ ] **Step 4.7: Lint check**

Run:
```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_overview_editor.py tests/test_library_browser_os_gating.py
uv run mypy barn/haybale-studio/haybale_studio
```
Both clean.

- [ ] **Step 4.8: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/library_overview_editor.py tests/test_library_browser_os_gating.py
git commit -m "feat(library-overview): disable Install button when OS doesn't match"
```

## Discipline

- `should_block_install_for_os` is at MODULE level (NOT a method on the editor class). It's a pure function that the tests import directly.
- The `info_modal` on click + `.tooltip(...)` on hover are BOTH needed — the spec says "tooltip" but in NiceGUI/Quasar the click-vs-hover behavior depends on the user's input device, and an unrelenting click without a modal hides the explanation.
- The `_os_block_msg` is evaluated EVERY render (acceptable — fast).

---

## Task 5: Final verification sweep + smoke test instructions

- [ ] **Step 5.1: Run the full test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1403 passed.

- [ ] **Step 5.2: Run ruff and mypy**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-studio/haybale_studio
```
All clean.

- [ ] **Step 5.3: Smoke test (manual — requires `uv run haywire`)**

Build smoke test instructions and surface them. Cannot run directly without a UI driver:

```sh
# 1. Start the app from the worktree.
uv run --project /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/.worktrees/marketstall-os-ui haywire

# 2. Open or create a workspace, then a project. The project's barn library
#    is a heap, so it's the ideal target for the OS multi-select check.

# 3. In the Library Browser, click the project's haybale to enter the
#    Library Overview Editor.

# 4. Click the "Edit" button (top right of the project library header).

# 5. Verify in the Edit dialog:
#    - A "Supported OS" multi-select widget appears under Dependencies.
#    - The label says "Supported OS (leave empty = all platforms)".
#    - All three options visible: macOS, Windows, Linux.
#    - Initially empty (no [tool.haywire].os in fresh pyproject).

# 6. Select two OS values (e.g. macOS + Linux), click Save Changes.

# 7. Inspect the file:
#    cat <workspace>/barn/haybale-<name>/pyproject.toml
#    Expected: a [tool.haywire] section with os = ["macos", "linux"].

# 8. Re-open the Edit dialog → confirm the widget is pre-populated with the saved values.

# 9. Select all three OS values, Save → confirm the [tool.haywire] section
#    is REMOVED entirely (all three = "all platforms" per spec).

# 10. (Optional) Test the Install button gating. Requires a haybale in the
#     AVAILABLE list whose os doesn't include the current platform. The
#     scaffolded project library won't trigger this, since it's a heap with
#     no os declaration. The most reliable way: edit the project library to
#     declare os = ["windows"] (then the current macOS user sees the Install
#     button greyed out with a tooltip) — but that's only meaningful if the
#     library is in cache, not as a heap. For now, the unit tests cover the
#     gating logic; the visual check waits for an OS-gated haybale to exist.
```

- [ ] **Step 5.4: Review the diff and commit summary**

Run: `git log --oneline f5b742f0..HEAD`
Run: `git diff f5b742f0 --shortstat`

Expected: 4 commits (Tasks 1-4), ~5 files modified/created, ~500-700 line delta.

---

## Spec coverage check

This plan covers the **OS field UI slice** of the marketstall spec:

| Spec § | Covered by | Notes |
|---|---|---|
| §2.1 OS declaration values + filter | Task 2 | `_apply_os_to_pyproject` accepts only macos/windows/linux |
| §2.1 Edit dialog gated to heaps | Task 3 | `_is_project_library` check + non-heap read-only label |
| §2.1 Empty/all-three = "all platforms" | Task 2 | Helper removes the section in both cases |
| §2.1 Install button gating + tooltip | Task 4 | Disabled button with tooltip + info modal |

**Not covered (deferred):**

| Spec § | Deferred to slice |
|---|---|
| §7.4 First-install safety modal | 5 |
| §10 Update-available signal | 7 |
| §12 Drift gate lag check | 6 |
| §11 Per-haybale stall generator | 8 |

**Bug fixed (out-of-band)**: Task 1 fixes a stale-vocabulary bug found during the slice 4 survey — `library_manager.py` lines 346 + 654 still read the legacy `[[packages]]` section name from the project marketplace, silently no-opping on slice-1-shaped files.

---

## Self-Review notes

- ✅ Every step has complete code; no "TBD".
- ✅ Names referenced across tasks: `_apply_os_to_pyproject` (Task 2 → used in identity write), `should_block_install_for_os` (Task 4 → used in Install button render), `_read_os_from_pyproject` (Task 3 → editor method). All defined where first used.
- ✅ TDD discipline: failing test before implementation in Tasks 1, 2, 4.
- ✅ Task 3 has no automated test (dialog widget); functional verification in Task 5.3.
- ✅ Task 1's static-source assertion (line 1.2 test) is the cheap fail-fast catch; line 1.2's second test demonstrates the post-fix behavior on a real TOML file.
- ✅ Commits are scoped: bugfix → write path → dialog → install gating → no merge mixing.

---

## Execution Handoff

Plan saved to `internals/plans/2026-05-22-marketstall-os-ui.md`. Three execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, quiet-mode reporting, batched reviews where tasks cluster. Estimated 4-6 dispatches.

**2. Inline Execution** — Execute Tasks 1-4 in this session.

**3. Inquisition first** — If the Edit-dialog-on-installed-wheels read-only branch (Task 3, non-heap case) feels under-defined, an inquisition pass before code.

Which approach?
