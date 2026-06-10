# Editor Quality Refactor + `haywire rename` CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the Haywire editor area (haybale libraries) — fix two latent bugs, close API gaps, de-duplicate code, replace a busy-wait, and shrink the 1739-line marketplace editor — while relocating library rename out of the editor into a new `haywire rename` CLI.

**Architecture:** A new studio CLI subcommand (`haywire rename`) owns the destructive library-rename operation (run with studio stopped, sidestepping the hot-reload corruption hazard). The marketplace editor then drops its in-app rename and points users at the CLI via a read-only field + info modal. The remaining six phases are independent, individually-shippable cleanups against the editor framework and its haybale implementations.

**Tech Stack:** Python 3.10+, NiceGUI/Quasar/Vue 3, `injector` DI, pytest, ruff, mypy, uv workspace. The `LibraryManager` service (marketplace), `EditorWrapper`/`Slot` (core UI), `HaystackState` (haystack), and the studio argparse CLI router (`app.py:272`).

---

## Source of truth & decisions

This plan implements the resolved decisions in `internals/handoff/handoff-editor-quality-refactor-20260610.md` (the `RESOLVED DECISIONS` blocks per phase). Two memories hold the deferred designs: `project_haywire_rename_cli` (the CLI, built here) and `project_per_library_storage_dir` (NOT in this plan).

**Two bugs fixed along the way (not pure refactors):**
1. **Dependency-matching key** (Phase 1): the marketplace gate matched declared deps against `distribution_name`+short-id instead of the canonical **`module_name`** (top-package-normalized). Fixed → fewer false "dependency missing" install blocks; folder-installs recognized.
2. **Cross-session rename staleness** (Phase 3): `HaystackState.rename_haystack` was the only mutator not broadcasting `GraphDataMutated`, so peer sessions never saw a rename. Fixed → broadcast folded into the state method.

**Quality gates (run after every multi-file change, per CLAUDE.md):**
```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```
Test-file gotcha (CLAUDE.md): in test files, `import haywire.core.graph.editor` before other haywire modules to avoid a circular import. Marketplace tests live in repo `tests/` (no barn-local test dir), imported as `from haybale_marketplace.library_manager import LibraryManager`.

---

## File Structure

**New files:**
- `packages/haywire-studio/src/haywire_studio/rename.py` — the `haywire rename` CLI logic: package rename (relocated from `LibraryManager.rename_project_library_streaming`) + JSON-aware graph-reference patch (dry-run by default).
- `tests/test_rename_cli.py` — unit tests for the CLI's graph-patch + rename orchestration.
- `tests/test_library_manager_dep_gating.py` — Phase 0/1 safety-net + red→green test for the module_name dependency-matching fix.
- `packages/haywire-core/src/haywire/core/workspace.py` — shared `default_save_dir()` helper (Phase 4).

**Modified (high-level):**
- `barn/haybale-marketplace/.../library_manager.py` — add `get_missing_dependencies_for_package`, rewrite `_lib_norm_aliases`→`_lib_module_norm`; **remove** `rename_project_library_streaming`.
- `barn/haybale-marketplace/.../editors/library_overview_editor.py` — dep-gating swap; remove rename path + graph-patch; add info-modal; collapse action-button + tab-panel repetition; move HTTP fetch out.
- `packages/haywire-core/src/haywire/ui/editor/wrapper.py` + `app/slot.py` — `set_dirty(refresh=...)` API.
- `barn/haybale-graph-editor/.../graph_editor.py`, `barn/haybale-studio/.../code_editor.py` — consume new `set_dirty` API; Save-As migration.
- `barn/haybale-haystack/.../state/haystack_state.py` + `editors/haystack_editor.py` — rename atomicity + broadcast; dirty accessor; Save-As dedup.
- `packages/haywire-studio/src/haywire_studio/app.py` — register `rename` subparser.
- `docs/reference/glossary.md` — already updated (module_name canonical key); no change needed here.

---

## PART A — `haywire rename` CLI (build first; Phase 6 depends on it)

### Task A1: Relocate the rename core into `rename.py` (pure move, behavior-preserving)

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/rename.py`
- Read for reference: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:484-710` (the current `rename_project_library_streaming` body)
- Test: `tests/test_rename_cli.py`

> **Why move, not copy:** `rename_project_library_streaming` has exactly one caller (the editor at `library_overview_editor.py:1308`), removed in Task B6. Relocating it (not duplicating) keeps one implementation.
>
> **REQUIRED, not optional:** Step 3 contains a `<PASTE ...>` marker for the ~210-line method body (library_manager.py:498-710). You MUST paste that body and apply the two transformations named below (registry→barn-scan for the dist-name; `on_output(...)`→`sink(...)`). Do not stub it — the CLI is non-functional without it. The body is not reproduced here only because it is long pre-existing code you are relocating verbatim.

- [ ] **Step 1: Write the failing test for the relocated validator**

```python
# tests/test_rename_cli.py
"""Tests for the haywire rename CLI (haywire_studio.rename)."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_sanitize_name_rejects_path_separators():
    from haywire_studio.rename import sanitize_rename

    assert sanitize_rename("foo/bar") is None
    assert sanitize_rename("..") is None
    assert sanitize_rename("My Lib") == "my_lib"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_rename_cli.py::test_sanitize_name_rejects_path_separators -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.rename'`

- [ ] **Step 3: Create `rename.py` with the relocated logic**

Move the body of `LibraryManager.rename_project_library_streaming` (library_manager.py:484-710, including its private helpers `_sanitize_name`, file-rewrite, dir-rename, and `uv sync` invocation) into module-level functions in `rename.py`. Convert the streaming `on_output` callback into a plain `print`/logger sink (CLI context, no UI). Expose:

```python
# packages/haywire-studio/src/haywire_studio/rename.py
"""haywire rename CLI: rename a project library + patch graph references.

Runs OUT of process with studio stopped — it renames installed package dirs,
rewrites 4 manifest files, and runs `uv sync`, none of which is safe under a
live studio (hot-reload/sys.modules corruption). See project_haywire_rename_cli.
"""
from __future__ import annotations

import re
from pathlib import Path


def sanitize_rename(new_name: str) -> str | None:
    """Return a module-safe name, or None if invalid (empty / path separators)."""
    new_name = new_name.strip()
    if not new_name or "/" in new_name or "\\" in new_name or ".." in new_name:
        return None
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", new_name.lower()).strip("_")
    return sanitized or None


def rename_library(
    old_library: str,
    new_name: str,
    workspace_root: Path,
    *,
    sink=print,
) -> tuple[bool, str]:
    """Rename a project library end-to-end (dirs + 4 manifests + uv sync).

    Relocated verbatim from LibraryManager.rename_project_library_streaming;
    on_output streaming replaced with `sink`. See library_manager.py history.
    """
    # <PASTE the relocated body from library_manager.py:498-710 here,
    #  replacing `self.registry...` lookups with the dist-name resolved from
    #  the workspace barn/ scan, and `on_output(...)` calls with `sink(...)`.>
    raise NotImplementedError  # replaced by the pasted body
```

> **Implementer note:** the original method reads `self.registry.get_library_distribution_name(library_id)`. In the CLI there's no live registry — resolve the current dist-name by scanning `workspace_root / "barn"` for the directory matching `old_library` (it IS the `haybale-<name>` dir name). Keep all validation branches (empty name, path separators, already-installed, dir-exists) returning `(False, message)`.

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_rename_cli.py::test_sanitize_name_rejects_path_separators -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/rename.py tests/test_rename_cli.py
git commit -m "feat(rename-cli): relocate library-rename core into haywire_studio.rename

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A2: JSON-aware, key-scoped graph-reference patch (dry-run by default)

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/rename.py`
- Test: `tests/test_rename_cli.py`

> **Why this replaces the editor's blunt patch:** the old editor did `text.replace(old_id + ":", new_id + ":")` across all `graphs/**/*.json` — matching the substring anywhere, including user values. This version walks the parsed JSON and only rewrites registry-key fields.

- [ ] **Step 1: Write the failing test (false-match must NOT be patched)**

```python
@pytest.mark.unit
def test_patch_graphs_dry_run_only_touches_registry_keys(tmp_path):
    import json
    from haywire_studio.rename import patch_graph_references

    graphs = tmp_path / "graphs"
    graphs.mkdir()
    g = graphs / "g1.json"
    g.write_text(json.dumps({
        "nodes": [{"type": "foo:node:adder"}],         # registry key — SHOULD change
        "meta": {"note": "see foo:bar in docs"},        # user value — must NOT change
    }))

    changes = patch_graph_references(graphs, "foo", "bar", apply=False)

    # dry-run reports the one real key change, leaves the file untouched
    assert changes.files_changed == 1
    assert changes.replacements == 1
    on_disk = json.loads(g.read_text())
    assert on_disk["nodes"][0]["type"] == "foo:node:adder"   # unchanged (dry-run)
    assert on_disk["meta"]["note"] == "see foo:bar in docs"  # never a candidate
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_rename_cli.py::test_patch_graphs_dry_run_only_touches_registry_keys -v`
Expected: FAIL — `ImportError: cannot import name 'patch_graph_references'`

- [ ] **Step 3: Implement the key-scoped patch + dry-run + backup**

```python
# append to rename.py
import json
import shutil
from dataclasses import dataclass, field


@dataclass
class PatchResult:
    files_changed: int = 0
    replacements: int = 0
    changed_files: list[str] = field(default_factory=list)


# JSON fields whose VALUES are registry keys ("<lib>:<kind>:<name>").
# Update if the graph schema gains key-bearing fields.
_KEY_FIELDS = ("type",)


def _rewrite_keys(obj, old_prefix: str, new_prefix: str) -> int:
    """Recursively rewrite registry-key fields in-place. Returns replacement count."""
    n = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _KEY_FIELDS and isinstance(v, str) and v.startswith(old_prefix):
                obj[k] = new_prefix + v[len(old_prefix):]
                n += 1
            else:
                n += _rewrite_keys(v, old_prefix, new_prefix)
    elif isinstance(obj, list):
        for item in obj:
            n += _rewrite_keys(item, old_prefix, new_prefix)
    return n


def patch_graph_references(
    graphs_dir: Path, old_id: str, new_id: str, *, apply: bool
) -> PatchResult:
    """Rewrite `old_id:` registry-key prefixes to `new_id:` in graphs/**/*.json.

    JSON-aware: only fields in _KEY_FIELDS are candidates. Dry-run by default
    (apply=False reports without writing). On apply, backs up each changed
    file to `<name>.json.bak` before writing.
    """
    result = PatchResult()
    if not graphs_dir.is_dir():
        return result
    old_prefix, new_prefix = old_id + ":", new_id + ":"
    for f in sorted(graphs_dir.glob("**/*.json")):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        count = _rewrite_keys(data, old_prefix, new_prefix)
        if count:
            result.files_changed += 1
            result.replacements += count
            result.changed_files.append(f.name)
            if apply:
                shutil.copy2(f, f.with_suffix(".json.bak"))
                f.write_text(json.dumps(data, indent=2))
    return result
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_rename_cli.py::test_patch_graphs_dry_run_only_touches_registry_keys -v`
Expected: PASS

- [ ] **Step 5: Add the apply-path test, run, verify**

```python
@pytest.mark.unit
def test_patch_graphs_apply_writes_and_backs_up(tmp_path):
    import json
    from haywire_studio.rename import patch_graph_references

    graphs = tmp_path / "graphs"
    graphs.mkdir()
    g = graphs / "g1.json"
    g.write_text(json.dumps({"nodes": [{"type": "foo:node:adder"}]}))

    patch_graph_references(graphs, "foo", "bar", apply=True)

    assert json.loads(g.read_text())["nodes"][0]["type"] == "bar:node:adder"
    assert (graphs / "g1.json.bak").exists()  # backup written
```

Run: `uv run pytest tests/test_rename_cli.py::test_patch_graphs_apply_writes_and_backs_up -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/rename.py tests/test_rename_cli.py
git commit -m "feat(rename-cli): JSON-aware key-scoped graph patch, dry-run by default

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A3: Wire the `rename` subcommand into the CLI router

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:280-295` (after the `share` subparser block)
- Modify: `packages/haywire-studio/src/haywire_studio/rename.py` (add `run_rename_cli`)
- Test: `tests/test_rename_cli.py`

- [ ] **Step 1: Write the failing test for the command orchestration**

```python
@pytest.mark.unit
def test_run_rename_cli_dry_run_does_not_write(tmp_path, capsys):
    import json
    from haywire_studio.rename import run_rename_cli

    # minimal workspace: graphs/ with one referencing graph
    (tmp_path / "graphs").mkdir()
    g = tmp_path / "graphs" / "g.json"
    g.write_text(json.dumps({"nodes": [{"type": "foo:node:x"}]}))

    # bundle: rename + patch, but dry-run (apply=False) skips package rename + writes
    code = run_rename_cli(
        old_library="haybale-foo", new_name="bar",
        workspace_root=tmp_path, apply=False,
    )

    assert code == 0
    # dry-run printed the plan and left the graph untouched
    assert json.loads(g.read_text())["nodes"][0]["type"] == "foo:node:x"
    out = capsys.readouterr().out
    assert "1 file" in out  # reports the would-be change
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_rename_cli.py::test_run_rename_cli_dry_run_does_not_write -v`
Expected: FAIL — `ImportError: cannot import name 'run_rename_cli'`

- [ ] **Step 3: Implement `run_rename_cli` (bundles rename + patch atomically)**

```python
# append to rename.py
def run_rename_cli(
    *, old_library: str, new_name: str, workspace_root: Path, apply: bool
) -> int:
    """Atomic: package rename + graph-reference patch. Dry-run unless apply=True.

    Returns a process exit code (0 ok, non-zero on failure).
    """
    sanitized = sanitize_rename(new_name)
    if sanitized is None:
        print(f"error: '{new_name}' is not a valid library name")
        return 2

    graphs_dir = workspace_root / "graphs"
    plan = patch_graph_references(graphs_dir, old_library.removeprefix("haybale-"),
                                  sanitized, apply=False)
    print(f"Will rename {old_library} -> haybale-{sanitized}")
    print(f"Graph references: {plan.replacements} key(s) in {plan.files_changed} file(s)")
    for name in plan.changed_files:
        print(f"  - {name}")

    if not apply:
        print("\nDry run. Re-run with --apply to perform the rename.")
        return 0

    ok, msg = rename_library(old_library, sanitized, workspace_root, sink=print)
    if not ok:
        print(f"error: {msg}")
        return 1
    patch_graph_references(graphs_dir, old_library.removeprefix("haybale-"),
                           sanitized, apply=True)
    print(f"Renamed to haybale-{sanitized}. Restart studio to pick up the change.")
    return 0
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_rename_cli.py::test_run_rename_cli_dry_run_does_not_write -v`
Expected: PASS

- [ ] **Step 5: Register the subparser in `app.py`**

In `packages/haywire-studio/src/haywire_studio/app.py`, after the `share_parser` block (ends ~line 295) and before the args are parsed, add:

```python
    rename_parser = subparsers.add_parser(
        "rename", help="Rename a project library (run with studio stopped)"
    )
    rename_parser.add_argument("old_library", help="Current library dir, e.g. haybale-foo")
    rename_parser.add_argument("new_name", help="New name (without the haybale- prefix)")
    rename_parser.add_argument(
        "--apply", action="store_true",
        help="Perform the rename. Without this flag, only a dry-run preview is printed.",
    )
```

Then in the command dispatch (where `init`/`share` are routed after `args = parser.parse_args()`), add:

```python
    elif args.command == "rename":
        from pathlib import Path
        from haywire_studio.rename import run_rename_cli
        raise SystemExit(run_rename_cli(
            old_library=args.old_library, new_name=args.new_name,
            workspace_root=Path.cwd(), apply=args.apply,
        ))
```

- [ ] **Step 6: Verify the subcommand is reachable**

Run: `uv run haywire rename --help`
Expected: prints usage with `old_library`, `new_name`, `--apply`.

- [ ] **Step 7: Run full gates + commit**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest tests/test_rename_cli.py -v
git add packages/haywire-studio/src/haywire_studio/app.py packages/haywire-studio/src/haywire_studio/rename.py tests/test_rename_cli.py
git commit -m "feat(rename-cli): register 'haywire rename' subcommand

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## PART B — Editor refactor (Phases 0–6)

### Task B1 (Phase 0+1): module_name dependency-matching — red→green bug fix

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py:715-764` (`_lib_norm_aliases`, `get_missing_dependencies`)
- Test: `tests/test_library_manager_dep_gating.py`

> **The bug:** `_lib_norm_aliases` matches declared deps against `distribution_name`+short-id. The canonical key is `module_name` (top-package-normalized). Folder installs have empty `distribution_name`, so the id-fallback papered over the gap and leniently accepted malformed bare-id deps. See handoff Phase 1 RESOLVED DECISIONS.

- [ ] **Step 1: Write the red→green test (correct module_name expectation)**

```python
# tests/test_library_manager_dep_gating.py
"""module_name-canonical dependency matching (handoff Phase 1)."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest


def _make_manager_with_lib(*, lib_id, module_name, dist_name):
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry.list_names.return_value = [lib_id]
    registry.is_library_enabled.return_value = True
    registry.get_library_distribution_name.return_value = dist_name
    identity = MagicMock()
    identity.module_name = module_name
    registry.get_library_identity.return_value = identity
    return LibraryManager(library_registry=registry)


@pytest.mark.unit
def test_dep_satisfied_by_module_name_even_when_dist_name_empty():
    """A folder-installed lib (no dist name) still satisfies a package-name dep."""
    mgr = _make_manager_with_lib(
        lib_id="widgets", module_name="haybale_widgets", dist_name=""
    )
    pkg = MagicMock()
    pkg.dependencies = ["haybale_widgets"]  # canonical package-name form

    missing = mgr.get_missing_dependencies_for_package(pkg, require_enabled=False)

    assert missing == []  # recognized via module_name; NOT a false "missing"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_library_manager_dep_gating.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'get_missing_dependencies_for_package'`

- [ ] **Step 3: Rewrite the alias helper + add the new method**

In `library_manager.py`, replace `_lib_norm_aliases` (lines 715-726) with a module_name-based helper, and add `get_missing_dependencies_for_package`:

```python
    def _lib_module_norm(self, lib_id: str) -> str:
        """Normalized TOP-LEVEL module name — the canonical dependency key.

        @library(dependencies=[...]) entries are top-level package names equal
        to the dependency's module_name top package (glossary: Dependency
        manifests). NOT distribution_name (empty for folder installs) and NOT
        the short id (never appears in module paths).
        """
        identity = self.registry.get_library_identity(lib_id)
        top = (identity.module_name or lib_id).split(".")[0]
        return self._norm(top)

    def get_missing_dependencies_for_package(
        self, pkg, *, require_enabled: bool
    ) -> list[str]:
        """Unmet deps for a NOT-yet-installed marketplace package (install gating).

        Matches each declared dep (top-package-normalized) against installed
        libraries' module_name. require_enabled=False ⇒ installed-at-all counts.
        """
        installed: set[str] = set()
        enabled: set[str] = set()
        for lid in self.registry.list_names():
            norm = self._lib_module_norm(lid)
            installed.add(norm)
            if self.registry.is_library_enabled(lid):
                enabled.add(norm)
        check = enabled if require_enabled else installed
        norm_top = lambda d: self._norm(d.split(".")[0])  # noqa: E731
        return [d for d in (pkg.dependencies or []) if norm_top(d) not in check]
```

Update `get_installed_dependents` (728-742) and `get_missing_dependencies` (744-764) to call `_lib_module_norm` in place of the removed `_lib_norm_aliases`. Fix the misleading "distribution name" wording in the `get_missing_dependencies` / nearby docstrings to say "module name (top package)".

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_library_manager_dep_gating.py -v`
Expected: PASS

- [ ] **Step 5: Swap the editor's hand-rolled gating onto the new method**

In `library_overview_editor.py`, replace lines 477-485 (the `_installed_ids = {...}` set + `_missing_deps` comprehension) with:

```python
                            _missing_deps = manager.get_missing_dependencies_for_package(
                                marketplace_pkg, require_enabled=False
                            )
```

- [ ] **Step 6: Run gates + commit**

```bash
uv run mypy barn/haybale-marketplace/haybale_marketplace/library_manager.py
uv run pytest tests/test_library_manager_dep_gating.py tests/test_library_manager_dry_run.py -v
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py tests/test_library_manager_dep_gating.py
git commit -m "fix(marketplace): match deps by module_name, not dist-name/id

Fixes false 'dependency missing' install blocks and folder-install misses.
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B2 (Phase 2): `set_dirty(refresh=...)` API + swallow-with-log

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py:227-235`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:330-339`
- Modify: `barn/haybale-studio/haybale_studio/editors/code_editor.py:264-272`
- Test: `tests/ui/test_editor_wrapper_set_dirty.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_editor_wrapper_set_dirty.py
import haywire.core.graph.editor  # noqa: F401  (circular-import guard, CLAUDE.md)

from unittest.mock import MagicMock
import pytest


@pytest.mark.unit
def test_set_dirty_refresh_true_calls_slot_refresh_bar():
    from haywire.ui.editor.wrapper import EditorWrapper

    slot = MagicMock()
    w = EditorWrapper.__new__(EditorWrapper)  # avoid full ctor
    from haywire.ui.editor.wrapper import EditorWrapperState
    w._state = EditorWrapperState()
    w._slot = slot

    w.set_dirty(True, refresh=True)

    assert w._state.is_dirty is True
    slot._refresh_bar.assert_called_once()


@pytest.mark.unit
def test_set_dirty_default_is_lazy():
    from haywire.ui.editor.wrapper import EditorWrapper, EditorWrapperState

    slot = MagicMock()
    w = EditorWrapper.__new__(EditorWrapper)
    w._state = EditorWrapperState()
    w._slot = slot

    w.set_dirty(True)  # no refresh kwarg

    slot._refresh_bar.assert_not_called()  # lazy default preserved
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/ui/test_editor_wrapper_set_dirty.py -v`
Expected: FAIL — `TypeError: set_dirty() got an unexpected keyword argument 'refresh'`

- [ ] **Step 3: Add the opt-in refresh to `set_dirty`**

In `wrapper.py`, replace `set_dirty` (227-235):

```python
    def set_dirty(self, value: bool, *, refresh: bool = False) -> None:
        """Mark the wrapped editor's content as dirty (or not).

        Lazy by default — the tab bar reads ``state.is_dirty`` on its next
        render. Pass ``refresh=True`` to eagerly repaint the bar now (used by
        editors that change dirtiness outside a normal redraw cycle).
        """
        self._state.is_dirty = bool(value)
        if refresh and self._slot is not None:
            try:
                self._slot._refresh_bar()
            except Exception:
                logger.warning(
                    "set_dirty(refresh=True): tab-bar refresh failed", exc_info=True
                )
```

Confirm `logger` is imported in `wrapper.py` (it is — used at line 254). If not, add `logger = logging.getLogger(__name__)`.

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/ui/test_editor_wrapper_set_dirty.py -v`
Expected: PASS (both)

- [ ] **Step 5: Collapse the duplicated reach in both consumers**

In `graph_editor.py`, replace `_sync_tab_dirty` body (330-339):

```python
    def _sync_tab_dirty(self, entry) -> None:
        """Mirror the entry's unsaved state to the tab bar via wrapper.set_dirty."""
        is_dirty = entry is not None and (entry.unsaved or entry.path is None)
        self.wrapper.set_dirty(is_dirty, refresh=True)
```

In `code_editor.py`, replace `_update_save_state` body (264-272):

```python
    def _update_save_state(self) -> None:
        is_dirty = self._content != self._original
        self.wrapper.set_dirty(is_dirty, refresh=True)
```

- [ ] **Step 6: Run full gates + commit**

> **Heads-up (handoff):** the warning log may surface a pre-existing silent `render_tab_into` failure. If a test/app now logs a warning here, that's a real bug to file — not a regression from this task.

```bash
uv run mypy packages/haywire-core/src/ && uv run pytest -m "not integration"
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py barn/haybale-studio/haybale_studio/editors/code_editor.py tests/ui/test_editor_wrapper_set_dirty.py
git commit -m "feat(editor): set_dirty(refresh=) opt-in bar refresh; drop private _slot reach

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B3 (Phase 3): Haystack rename atomicity + cross-session broadcast — bug fix

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py:468-495`
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:126,832-848`
- Test: `tests/test_haystack_state_rename.py`

- [ ] **Step 1: Write the failing test (rename updates pointer + broadcasts)**

```python
# tests/test_haystack_state_rename.py
import haywire.core.graph.editor  # noqa: F401

from unittest.mock import MagicMock, patch
import pytest


@pytest.mark.unit
def test_rename_updates_last_name_and_broadcasts(tmp_path):
    from haybale_haystack.state.haystack_state import HaystackState

    hs = HaystackState.__new__(HaystackState)
    hs._workspace_root = tmp_path
    settings = MagicMock()
    settings.last_haystack_name = "old"
    hs._haystack_settings = settings

    with patch("haybale_haystack.persistence.rename_haystack", return_value=True), \
         patch.object(hs, "_broadcast_data_mutated") as bcast:
        ok = hs.rename_haystack("old", "new")

    assert ok is True
    assert settings.last_haystack_name == "new"   # pointer kept in lockstep
    bcast.assert_called_once()                     # peer sessions notified
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_haystack_state_rename.py -v`
Expected: FAIL — `last_haystack_name` stays `"old"` / `_broadcast_data_mutated` not called.

- [ ] **Step 3: Fold the lockstep + broadcast into `rename_haystack`**

In `haystack_state.py`, replace `rename_haystack` (468-473):

```python
    def rename_haystack(self, old_name: str, new_name: str) -> bool:
        from haybale_haystack.persistence import rename_haystack as _rename

        if self._workspace_root is None:
            return False
        if not _rename(self._workspace_root, old_name, new_name):
            return False
        # Keep the in-memory pointer in lockstep (shared single state — fixes
        # ALL sessions) and broadcast like every other mutator does, so peer
        # sessions' headers update. rename was the lone mutator missing this.
        if self._haystack_settings.last_haystack_name == old_name:
            self._haystack_settings.last_haystack_name = new_name
        self._broadcast_data_mutated()
        return True
```

Add a public dirty accessor near `_mark_haystack_dirty` (after line 495):

```python
    @property
    def is_haystack_dirty(self) -> bool:
        """Whether the haystack-set diverges from its saved TOML."""
        return self._haystack_dirty
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_haystack_state_rename.py -v`
Expected: PASS

- [ ] **Step 5: Simplify the editor (drop private reaches)**

In `haystack_editor.py`, replace the `_do_rename` inner block (832-848) so it no longer touches `_haystack_settings` or calls the local notify — `rename_haystack` now owns both:

```python
        def _do_rename(new_name: str) -> None:
            if new_name == old_name:
                return
            if not hs.rename_haystack(old_name, new_name):
                ui.notify("Rename failed", type="negative", position="top-right")
                return
            ui.notify(f"Haystack renamed to '{new_name}'", type="positive")
```

At line 126, replace `is_dirty = hs._haystack_dirty` with:

```python
        is_dirty = hs.is_haystack_dirty
```

- [ ] **Step 6: Run gates + commit**

```bash
uv run mypy barn/haybale-studio/haybale_studio/ && uv run pytest tests/test_haystack_state_rename.py -v
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py tests/test_haystack_state_rename.py
git commit -m "fix(haystack): rename broadcasts cross-session; atomic last-name lockstep

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B4 (Phase 4): shared `default_save_dir` + GraphEditor Save-As migration

**Files:**
- Create: `packages/haywire-core/src/haywire/core/workspace.py`
- Modify: `barn/haybale-graph-editor/.../graph_editor.py:374-378,422-546`
- Modify: `barn/haybale-haystack/.../editors/haystack_editor.py:486-490`
- Modify: `barn/haybale-haystack/.../state/haystack_state.py:463-466`
- Test: `tests/test_workspace_save_dir.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_save_dir.py
import pytest


@pytest.mark.unit
def test_default_save_dir_prefers_graphs_subdir(tmp_path):
    from haywire.core.workspace import default_save_dir

    (tmp_path / "graphs").mkdir()
    assert default_save_dir(tmp_path) == tmp_path / "graphs"


@pytest.mark.unit
def test_default_save_dir_falls_back_to_root(tmp_path):
    from haywire.core.workspace import default_save_dir

    assert default_save_dir(tmp_path) == tmp_path  # no graphs/ subdir
```

- [ ] **Step 2: Run it, verify it fails**

Run: `uv run pytest tests/test_workspace_save_dir.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.workspace'`

- [ ] **Step 3: Create the shared helper**

```python
# packages/haywire-core/src/haywire/core/workspace.py
"""Workspace path helpers shared across editor libraries."""
from __future__ import annotations

from pathlib import Path


def default_save_dir(workspace_root: Path) -> Path:
    """Return ``workspace_root/graphs`` if it exists, else ``workspace_root``."""
    graphs_dir = workspace_root / "graphs"
    return graphs_dir if graphs_dir.is_dir() else workspace_root
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `uv run pytest tests/test_workspace_save_dir.py -v`
Expected: PASS

- [ ] **Step 5: Replace the three duplicates with the helper**

In `graph_editor.py`, replace `_default_save_dir` (374-378):

```python
    def _default_save_dir(self, app) -> Path:
        from haywire.core.workspace import default_save_dir

        root = Path(getattr(app, "workspace_root", str(Path.home())))
        return default_save_dir(root)
```

Apply the identical replacement to `haystack_editor.py:486-490`. In `haystack_state.py:463`, change `graphs_dir = self._workspace_root / "graphs"` to use the helper for the base dir (keep the `rglob` scan).

- [ ] **Step 6: Migrate GraphEditor onto `save_as_modal`**

Delete the bespoke Save-As dialog from `graph_editor.py`: `_build_save_as_dialog` (457), `_do_save_as` (498), `_clear_exists_warning` (494), and the dialog half of `_open_save_as_dialog` (422-456) — and the 5 instance fields `_save_base_dir`, `_save_base_dir_label`, `_save_path_input`, `_save_exists_warning`, `_save_as_dialog`. Replace `_open_save_as_dialog` with a call to the canonical modal, mirroring `haystack_editor.py:567`'s `save_as_modal(...)` usage (same `save_as_modal` + `confirm_modal` overwrite flow). Read `haystack_editor.py:492-590` as the reference implementation before writing.

- [ ] **Step 7: Run full gates + commit**

```bash
uv run ruff check . && uv run mypy packages/haywire-core/src/ && uv run pytest -m "not integration"
git add packages/haywire-core/src/haywire/core/workspace.py barn/haybale-graph-editor/ barn/haybale-haystack/ tests/test_workspace_save_dir.py
git commit -m "refactor(editor): share default_save_dir; GraphEditor uses canonical save_as_modal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B5 (Phase 5): replace the busy-wait modal poll with an asyncio.Future

**Files:**
- Modify: `barn/haybale-marketplace/.../editors/library_overview_editor.py:1515-1560`
- Test: covered via existing marketplace flow tests; add a focused unit test for the decision bridge if practical.

> **Do NOT** "simplify" the await chain — it deliberately keeps `_install_package` on one task to drive the progress modal (handoff Phase 5 CONTEXT).

- [ ] **Step 1: Replace the poll loop**

In `_install_package`, replace the `confirmed = {"value": False}` block + the `for _ in range(600)` poll (1517-1560) with a Future bridge:

```python
        # Step 2: if collateral upgrades exist, confirm with the user
        if removals:
            loop = asyncio.get_event_loop()
            decision: asyncio.Future[bool] = loop.create_future()

            upgrade_impact_modal(
                installing=name,
                also_upgrading=removals,
                on_continue=lambda: decision.done() or decision.set_result(True),
                on_cancel=lambda: decision.done() or decision.set_result(False),
            )

            try:
                proceed = await decision
            finally:
                pass

            if not proceed:
                if button:
                    try:
                        button.enable()
                        button.props(remove="loading")
                    except Exception:
                        pass
                return
```

> Note `upgrade_impact_modal` already accepts `on_cancel` (`upgrade_impact_modal.py:25`) — the old code just never passed it, which is why cancel vs. timeout were indistinguishable. The 60s timeout is intentionally dropped (a user-decision modal shouldn't time out).

- [ ] **Step 2: Verify the button-state cleanup is single-sourced**

Confirm the remaining download-failure cleanup (the `try/finally` around the actual install in Steps after the modal) is the only other place toggling `button.enable()/props`. Wrap the post-decision install body in one `try/finally` if duplication remains.

- [ ] **Step 3: Run gates**

Run: `uv run mypy barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Run: `uv run pytest -k "install or marketplace" -m "not integration" -v`
Expected: PASS (no busy-wait; behavior preserved)

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
git commit -m "fix(marketplace): await upgrade-impact decision via Future, drop busy-wait poll

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B6 (Phase 6a): remove library rename from the editor; add the info modal

**Files:**
- Modify: `barn/haybale-marketplace/.../editors/library_overview_editor.py` (remove `_do_rename` 1290-1336, `_build_graph_patch_dialog` 1342-1392, `_patch_graph_files` 1394-1409; rework the edit-dialog name field 993-1034)
- Modify: `barn/haybale-marketplace/.../library_manager.py` (delete `rename_project_library_streaming` 484-710 — now in `rename.py`)

- [ ] **Step 1: Make the name field read-only + info button**

In `library_overview_editor.py`, in the Edit dialog (993-1013), remove the unlock/`lock_btn` machinery and the editable-name path. Replace with a read-only field + info button:

```python
            hui.section_label("Package Name")
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("haybale-").classes("text-sm font-mono hw-text-muted flex-shrink-0")
                ui.input(value=old_name_part).classes("flex-1").props("dense readonly")
                _cur = f"haybale-{old_name_part}"
                ui.button(icon="info", on_click=lambda c=_cur: info_modal(
                    title="Renaming a library",
                    icon="info",
                    message=(
                        "Renaming happens from the command line, with studio stopped:\n\n"
                        "  1. Quit studio\n"
                        f"  2. uv run haywire rename {c} <new-name>\n"
                        "  3. Restart studio\n\n"
                        "Why stopped: rename rewrites installed packages and runs "
                        "`uv sync`, which isn't safe while studio is running."
                    ),
                )).props("flat round dense size=sm").tooltip("How to rename")
```

- [ ] **Step 2: Simplify `_save` (identity-only path)**

In `_save` (1015-1034), drop the rename branch — only identity updates remain:

```python
                edit_dialog.close()
                await self._do_update_identity(lib, identity, marketplace_path, manager, context)
```

- [ ] **Step 3: Delete the dead rename + patch methods**

Remove `_do_rename` (1290-1336), `_build_graph_patch_dialog` (1342-1392), `_patch_graph_files` (1394-1409), and the now-unused warning dialog (1040-1064) if no longer referenced. In `library_manager.py`, delete `rename_project_library_streaming` (484-710).

- [ ] **Step 4: Find stale references (string-based, IDE-missed)**

Run: `grep -rn "rename_project_library_streaming\|_build_graph_patch_dialog\|_patch_graph_files\|_do_rename" packages/ barn/ tests/`
Expected: only the new `rename.py` / removed sites. Update any test that `patch(...)`-ed the removed symbols.

- [ ] **Step 5: Run full gates + commit**

```bash
uv run ruff check . && uv run mypy barn/haybale-marketplace/haybale_marketplace/ && uv run pytest -m "not integration"
git add barn/haybale-marketplace/
git commit -m "refactor(marketplace): remove in-app library rename; point to haywire rename CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B7 (Phase 6b): move HTTP fetch into MarketplaceState; collapse render repetition

**Files:**
- Modify: `barn/haybale-marketplace/.../state/marketplace_state.py` (add overview-fetch method)
- Modify: `barn/haybale-marketplace/.../editors/library_overview_editor.py` (call state; collapse action-buttons + tab-panels)

- [ ] **Step 1: Move the HTTP fetch to the state layer**

Move `_fetch_marketplace_overview` / `_github_raw_base` / `_load_marketplace_overview` (1620-1740) into `MarketplaceState` as e.g. `async def fetch_overview(self, pkg) -> str | None`. The editor calls `await context.app_data[MarketplaceState].fetch_overview(pkg)` and renders the result.

- [ ] **Step 2: Extract `_action_button` helper**

Replace the four near-identical blocked-button branches in `_render_center` (337-520) with one helper:

```python
    def _action_button(self, label, icon, *, block_reason, on_click, color):
        if block_reason:
            ui.button(label, icon=hui.icon.locked,
                      on_click=lambda m=block_reason: info_modal(
                          title="Action unavailable", icon="lock", message=m)
                      ).props(f"color={color} size=sm").tooltip(block_reason)
        else:
            ui.button(label, icon=icon, on_click=on_click).props(f"color={color} size=sm")
```

Rewrite the disable/enable/uninstall/install branches to call it.

- [ ] **Step 3: Loop the tab-panel construction**

Replace the 12 `_make_tab_panel(...)` calls (587-677) with a list of `TabConfig` + a loop (handoff Phase 6).

- [ ] **Step 4: Verify the editor is under 1000 lines**

Run: `wc -l barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Expected: < 1000.

- [ ] **Step 5: Run full gates + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy barn/haybale-marketplace/haybale_marketplace/ && uv run pytest
git add barn/haybale-marketplace/
git commit -m "refactor(marketplace): move overview fetch to state; collapse render repetition

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Full CI-parity gate (must be clean — baseline was zero errors):**

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

- [ ] **Manual smoke (run skill: `verify`):** launch the app, open the marketplace editor, confirm the Edit dialog shows a read-only name + working info modal; rename a haystack with two browser tabs open and confirm both headers update.

- [ ] **Run `uv run haywire rename haybale-<somelib> testname` (dry-run)** and confirm it prints a plan and writes nothing.

---

## Out of scope (separate sessions — see memories)

- **`project_per_library_storage_dir`** — per-library `~/.haywire/db/<lib>/` storage mechanism (undesigned).
- **Disentangle `haybale_graph_editor` from `haywire-studio`** — run `haywire-dep-check` to surface actual cross-package imports.
- **An ADR** for (a) the module_name dependency-key decision and (b) the rename-CLI relocation — offered but not yet written.
