# Editor Cleanup — High-Priority & Moderate Findings

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate five specific code-quality problems found in the haybale editor implementations: a banned `ui.card()` in a dialog, a duplicated save-as dialog helper, a duplicated registry-lookup helper, double-parsed marketplace.toml in `_render_list`, and a missing guard in `LibraryComponentEditor`.

**Architecture:** Four independent tasks, each scoped to one file or one pair of files. No shared infrastructure changes. No behaviour changes — every fix preserves existing functionality exactly. Tasks 1 and 4 are single-file fixes. Task 2 extracts a shared function into `haybale-graph-editor` (the common dependency). Task 3 extracts a shared helper into a new `_registry_utils.py` module inside `haybale-marketplace/editors/`. Task 5 is a single-method cleanup.

**Tech Stack:** Python 3.10+, NiceGUI, `haywire.ui.elements` (hui), `haywire.ui.modals`.

---

## File Map

| Task | File(s) touched | What changes |
|------|----------------|--------------|
| 1 | `barn/haybale-studio/haybale_studio/editors/code_editor.py` | `ui.card()` → `hui.dialog_card()` in `_build_save_as_dialog`; remove `_save_as_dialog`/`_save_as_input`/`_save_as_warning` instance fields; convert to inline dialog |
| 2 | `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_save_as.py` *(new)* | Extract shared `open_graph_save_as_dialog()` helper |
| 2 | `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` | Call shared helper; remove `_default_save_dir`, `_workspace_rel`, `_open_save_as_dialog` |
| 2 | `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` | Call shared helper; remove `_default_save_dir`, `_open_save_as_dialog` |
| 3 | `barn/haybale-marketplace/haybale_marketplace/editors/_registry_utils.py` *(new)* | `lookup_component_class(app, registry_key)` shared helper |
| 3 | `barn/haybale-marketplace/haybale_marketplace/editors/component_source_editor.py` | Remove `_REGISTRY_GETTER` dict + `_lookup_class`; use shared helper |
| 3 | `barn/haybale-marketplace/haybale_marketplace/editors/library_component_editor.py` | Remove `_lookup_class`; use shared helper; add `registry_key` guard |
| 4 | `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py` | Parse `marketplace.toml` once; extract `_lib_view()` normaliser |
| 5 | `barn/haybale-marketplace/haybale_marketplace/editors/library_component_editor.py` | Add `len(parts) != 3` guard on `registry_key.split` |

---

## Task 1: Fix `ui.card()` → `hui.dialog_card()` in `CodeEditor._build_save_as_dialog`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/code_editor.py:77-91` (fields), `296-314` (dialog builder), `286-294` (opener), `316-363` (save-as logic)

The current `_build_save_as_dialog` builds a persistent `ui.dialog` at `draw()` time and stores it as `self._save_as_dialog` / `self._save_as_input` / `self._save_as_warning`. The fix:

1. Drop the three stored-dialog instance fields.
2. Make `_open_save_as_dialog` build the dialog inline (opened immediately, discarded on close) using `hui.dialog_card()`.
3. Pass `context` directly to the inline builder instead of capturing at `draw()` time.

This keeps `_do_save_as`, `_show_save_as_warning`, `_clear_save_as_warning` exactly as they are — just wire them against a locally-built dialog.

- [ ] **Step 1: Establish a test baseline**

```sh
uv run pytest tests/ -k "code_editor" -v 2>&1 | tail -20
```

Expected: whatever currently passes — record it. If no tests exist, proceed.

- [ ] **Step 2: Remove the three stored-dialog fields from `__init__`**

In `code_editor.py`, delete lines 88–90:

```python
# DELETE these three lines from __init__:
        self._save_as_dialog: Optional[ui.dialog] = None
        self._save_as_input: Optional[ui.input] = None
        self._save_as_warning: Optional[ui.label] = None
```

Also remove the corresponding cleanup lines from `cleanup()` at the bottom of the file:

```python
# DELETE from cleanup():
        self._save_as_dialog = None
        self._save_as_input = None
        self._save_as_warning = None
```

- [ ] **Step 3: Replace `_build_save_as_dialog` and `_open_save_as_dialog` with a single inline-dialog method**

Delete the existing `_build_save_as_dialog` method (lines 296–314) and replace `_open_save_as_dialog` (lines 286–294) with:

```python
    def _open_save_as_dialog(self, context: "SessionContext") -> None:
        path = self._resolve_path()
        default = path.name if path is not None else "untitled.txt"

        with ui.dialog() as dialog, hui.dialog_card("w-[420px]"):
            with ui.column().classes("w-full gap-2"):
                ui.label("Save As").classes("text-base font-semibold")
                path_input = (
                    hui.input_field(label="File path", value=default, autofocus=True)
                )
                warning_label = ui.label("").classes("text-xs hw-text-danger -mt-1")
                warning_label.set_visibility(False)

                def _clear_warning(_=None) -> None:
                    warning_label.set_visibility(False)

                path_input.on("update:model-value", _clear_warning)

                with ui.row().classes("w-full justify-end gap-2 mt-1"):
                    ui.button("Cancel", on_click=dialog.close).props("flat dense")
                    ui.button(
                        "Save",
                        on_click=lambda: self._do_save_as(context, dialog, path_input, warning_label),
                    ).props("color=positive dense")

        dialog.open()
```

- [ ] **Step 4: Update `_do_save_as` signature to accept the local widgets**

Replace the existing `_do_save_as` signature (line 320) and its first three lines:

```python
    def _do_save_as(
        self,
        context: "SessionContext",
        dialog: "ui.dialog",
        path_input: "ui.element",
        warning_label: "ui.label",
    ) -> None:
        path_str = (path_input.value or "").strip()
        if not path_str:
            warning_label.text = "Please enter a file path."
            warning_label.set_visibility(True)
            return
```

Replace the body's remaining references to `self._save_as_input`, `self._show_save_as_warning`, and `self._clear_save_as_warning`:

- Every `self._show_save_as_warning(msg)` → `warning_label.text = msg; warning_label.set_visibility(True)`
- `path_str = (self._save_as_input.value or "").strip()` → already handled in new signature above

Delete `_show_save_as_warning` and `_clear_save_as_warning` methods entirely (they are now inlined).

- [ ] **Step 5: Update the two call sites of `_open_save_as_dialog`**

There are two callers — both already pass no arguments in the current code and need `context` threaded through:

In `_save` (line 275):
```python
            self._open_save_as_dialog(context)
```

In `handle_close_request` (line 407):
```python
                self._open_save_as_dialog(context)
```

Both callers already have `context` in scope. No signature change needed for those methods.

Also update the toolbar "Save As" button in `draw()` (line 178) which currently uses `on_click=self._open_save_as_dialog` with no args — change to a lambda:

```python
                    ui.button(
                        "Save As",
                        icon="save_as",
                        on_click=lambda ctx=context: self._open_save_as_dialog(ctx),
                    ).props("flat dense size=sm").tooltip("Save under a different name")
```

- [ ] **Step 6: Verify no `self._save_as_dialog`, `self._save_as_input`, `self._save_as_warning` remain**

```sh
grep -n "_save_as_dialog\|_save_as_input\|_save_as_warning\|_show_save_as_warning\|_clear_save_as_warning\|ui\.card()" barn/haybale-studio/haybale_studio/editors/code_editor.py
```

Expected: no output.

- [ ] **Step 7: Run lint and tests**

```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/code_editor.py
uv run pytest tests/ -k "code_editor" -v 2>&1 | tail -20
```

Expected: ruff clean, tests same as baseline.

- [ ] **Step 8: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/code_editor.py
git commit -m "fix(code-editor): use hui.dialog_card in save-as dialog, drop stored dialog fields"
```

---

## Task 2: Extract shared `open_graph_save_as_dialog()` from GraphEditor and HaystackEditor

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_save_as.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py:360-467`
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:486-573`

The two `_open_save_as_dialog` implementations share identical structure: path default-computation, `save_as_modal` invocation, overwrite-confirm stacking. They differ only in how they call save (`entry.save(save_as=...)` vs `hs.save_graph(entry, save_as=...)`). The shared helper accepts a `save_fn` callback that abstracts this difference.

- [ ] **Step 1: Establish test baseline**

```sh
uv run pytest tests/ -k "haystack or graph_editor" -v 2>&1 | tail -20
```

Record passing count.

- [ ] **Step 2: Create `graph_save_as.py` with the shared helper**

Create `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_save_as.py`:

```python
"""Shared Save-As dialog for graph containers.

Both GraphEditor and HaystackEditor open the same save-as flow; they
differ only in the save callback. This module owns the common logic:
default-path computation, save_as_modal invocation, and the stacked
overwrite-confirm flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from nicegui import ui

from haywire.core.workspace import default_save_dir
from haywire.ui.modals import confirm_modal, save_as_modal

if TYPE_CHECKING:
    from haybale_graph_editor.protocols import GraphContainer


def _compute_initial_path(
    entry: "GraphContainer",
    workspace_root: Path,
) -> str:
    """Return a relative-to-workspace initial path string for the save-as modal."""
    if entry.path is not None:
        try:
            return str(entry.path.relative_to(workspace_root))
        except ValueError:
            return entry.path.name
    save_dir = default_save_dir(workspace_root)
    graph_name = getattr(entry.editor.graph, "name", None) or "untitled"
    safe_name = graph_name.lower().replace(" ", "_")
    try:
        rel_dir = save_dir.relative_to(workspace_root)
        return str(rel_dir / f"{safe_name}.haywire")
    except ValueError:
        return f"{safe_name}.haywire"


def open_graph_save_as_dialog(
    *,
    app,
    entry: "GraphContainer",
    save_fn: Callable[[Path], bool],
    on_success: Optional[Callable[[Path], None]] = None,
    initial_path: Optional[str] = None,
) -> None:
    """Open the Save-As modal for a graph entry.

    Args:
        app: The project app state (provides workspace_root).
        entry: The graph container to save.
        save_fn: Called with the chosen absolute path. Returns True on success.
            The caller is responsible for the actual save — this function only
            handles the dialog flow and the overwrite-confirm stacking.
        on_success: Optional callback fired with the resolved path after a
            successful save. Use this to update session state, emit signals, etc.
        initial_path: Pre-fill override (relative to workspace_root). When None
            the value is derived from entry.path or a sensible default for
            unnamed entries.
    """
    workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))
    if initial_path is None:
        initial_path = _compute_initial_path(entry, workspace_root)

    def _do_save(save_path: Path) -> None:
        success = save_fn(save_path)
        if not success:
            ui.notify("Save failed — check the path and try again", type="negative")
            return
        ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
        if on_success is not None:
            on_success(save_path)

    def _on_confirm(save_path: Path, raw_input: str) -> None:
        if save_path == entry.path:
            _do_save(save_path)
            return
        if save_path.exists():
            confirm_modal(
                title="Overwrite file?",
                message=f'"{save_path.name}" already exists. Overwrite it?',
                confirm_label="Overwrite",
                danger=True,
                on_confirm=lambda: _do_save(save_path),
                on_cancel=lambda: open_graph_save_as_dialog(
                    app=app,
                    entry=entry,
                    save_fn=save_fn,
                    on_success=on_success,
                    initial_path=raw_input,
                ),
            )
            return
        _do_save(save_path)

    save_as_modal(
        title="Save Graph As",
        workspace_root=workspace_root,
        initial_path=initial_path,
        suffixes=(".haywire",),
        on_confirm=_on_confirm,
    )
```

- [ ] **Step 3: Run ruff on the new file**

```sh
uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/editors/graph_save_as.py
```

Expected: clean.

- [ ] **Step 4: Replace `GraphEditor._open_save_as_dialog` and its helpers**

In `graph_editor.py`:

1. Add import at the top of the file (with the other local imports):
```python
from .graph_save_as import open_graph_save_as_dialog
```

2. Delete the three methods `_default_save_dir` (lines 360–364), `_workspace_rel` (lines 366–377), and `_open_save_as_dialog` (lines 408–467) entirely.

3. Replace the call site in `_save_graph` (currently lines 404–406):
```python
        # No path yet — open the Save-As dialog
        app = context.app
        self._open_save_as_dialog(app, entry, context)
```
with:
```python
        # No path yet — open the Save-As dialog
        app = context.app

        def _save_fn(save_path: Path) -> bool:
            old_binding_id = self.wrapper._binding_id
            new_binding_id = entry.save(save_as=save_path)
            if new_binding_id is not None or not entry.unsaved:
                context.data[EditState].active_graph_path = save_path
                if new_binding_id is not None and old_binding_id != new_binding_id:
                    self.wrapper.repayload(new_binding_id, new_label=entry.display_name)
                session = context.session
                if session:
                    session.publish(ActiveGraphMoved())
                    session.publish(GraphDataMutated())
                return True
            return False

        open_graph_save_as_dialog(app=app, entry=entry, save_fn=_save_fn)
```

Also replace the `_workspace_rel` usage in `_update_header` (line 313):
```python
            self._graph_name_label.text = ("● " if entry.unsaved else "") + self._workspace_rel(entry.path)
```
with an inline computation (since `_workspace_rel` is deleted):
```python
            app = self._project_state
            root = Path(getattr(app, "workspace_root", str(Path.home()))) if app else Path.home()
            try:
                rel = str(entry.path.relative_to(root))
            except ValueError:
                rel = str(entry.path)
            self._graph_name_label.text = ("● " if entry.unsaved else "") + rel
```

- [ ] **Step 5: Verify `_default_save_dir`, `_workspace_rel`, `_open_save_as_dialog` are gone from graph_editor.py**

```sh
grep -n "_default_save_dir\|_workspace_rel\|_open_save_as_dialog" barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py
```

Expected: no output.

- [ ] **Step 6: Replace `HaystackEditor._open_save_as_dialog` and `_default_save_dir`**

In `haystack_editor.py`:

1. Add import alongside existing graph-editor imports:
```python
from haybale_graph_editor.editors.graph_save_as import open_graph_save_as_dialog
```

2. Delete `_default_save_dir` (lines 486–490) and `_open_save_as_dialog` (lines 492–573) entirely.

3. Replace every call site of `self._open_save_as_dialog(app, entry, context)`:

In `_on_entry_save` (line 337):
```python
        self._open_save_as_dialog(app, entry, context)
```
→
```python
        def _save_fn(save_path: Path) -> bool:
            return hs.save_graph(entry, save_as=save_path)

        def _on_success(save_path: Path) -> None:
            if entry.graph is context.data[EditState].active_graph:
                context.data[EditState].active_graph_path = save_path
                session = context.session
                if session:
                    session.publish(ActiveGraphMoved())

        open_graph_save_as_dialog(app=app, entry=entry, save_fn=_save_fn, on_success=_on_success)
```

In `_on_entry_save_as` (line 348):
```python
        self._open_save_as_dialog(app, entry, context)
```
→
```python
        def _save_fn(save_path: Path) -> bool:
            return hs.save_graph(entry, save_as=save_path)

        def _on_success(save_path: Path) -> None:
            if entry.graph is context.data[EditState].active_graph:
                context.data[EditState].active_graph_path = save_path
                session = context.session
                if session:
                    session.publish(ActiveGraphMoved())

        open_graph_save_as_dialog(app=app, entry=entry, save_fn=_save_fn, on_success=_on_success)
```

Note: both call sites need `hs = context.app_data[HaystackState]` to be in scope before the lambda — it is already present in `_on_entry_save`; add it to `_on_entry_save_as`:
```python
        hs = context.app_data[HaystackState]
```

- [ ] **Step 7: Verify no `_default_save_dir` or `_open_save_as_dialog` remain in haystack_editor.py**

```sh
grep -n "_default_save_dir\|_open_save_as_dialog" barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
```

Expected: no output.

- [ ] **Step 8: Run lint and tests**

```sh
uv run ruff check barn/haybale-graph-editor/ barn/haybale-haystack/
uv run pytest tests/ -k "haystack or graph_editor" -v 2>&1 | tail -20
```

Expected: ruff clean, test count same as baseline.

- [ ] **Step 9: Commit**

```sh
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_save_as.py \
        barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py \
        barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
git commit -m "refactor: extract open_graph_save_as_dialog, remove duplicated save-as logic in GraphEditor and HaystackEditor"
```

---

## Task 3: Extract shared registry-lookup helper in haybale-marketplace editors

**Files:**
- Create: `barn/haybale-marketplace/haybale_marketplace/editors/_registry_utils.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/component_source_editor.py:59-70, 172-191, 409-427`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_component_editor.py:94-95, 249-269`

`ComponentSourceEditor` has a module-level `_REGISTRY_GETTER` dict (singular keys like `"node"`) and two methods that use it. `LibraryComponentEditor` has an inline dict (plural keys like `"nodes"`) inside `_lookup_class`. Both boil down to: given a registry_key, find the right registry and call `.get(registry_key)`. A single `lookup_component_class(app, registry_key)` function covers both.

The key shape difference: `ComponentSourceEditor` splits `"lib:node:Foo"` → singular segment `"node"`, while `LibraryComponentEditor` derives plural `"nodes"` from `"node" + "s"`. The shared helper should accept the registry_key directly and split it internally (same split the callers already do), using singular keys (matching `haywire.core.library.utils` constants).

- [ ] **Step 1: Create `_registry_utils.py`**

Create `barn/haybale-marketplace/haybale_marketplace/editors/_registry_utils.py`:

```python
"""Shared registry-lookup utilities for marketplace editors.

Both ComponentSourceEditor and LibraryComponentEditor need to resolve a
component class from a registry_key string. This module owns that lookup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from haywire.core.library.utils import (
    ADAPTER,
    EDITOR,
    NODE,
    PANEL,
    SETTING,
    SKIN,
    STATE,
    THEME,
    TYPE,
    WIDGET,
)

if TYPE_CHECKING:
    pass

# Maps the singular comp_type segment of a registry_key to the
# library_service getter method name.
_REGISTRY_GETTER: dict[str, str] = {
    NODE: "get_node_registry",
    WIDGET: "get_widget_registry",
    TYPE: "get_type_registry",
    ADAPTER: "get_adapter_registry",
    SKIN: "get_skin_registry",
    THEME: "get_theme_registry",
    SETTING: "get_settings_registry",
    STATE: "get_state_registry",
    PANEL: "get_panel_registry",
    EDITOR: "get_editor_registry",
}


def lookup_component_class(app, registry_key: str) -> Optional[type]:
    """Return the component class registered under registry_key, or None.

    Resolves the appropriate registry from app.library_service based on
    the singular comp_type segment of the key (e.g. 'node' in
    'mylib:node:MyNode').

    Args:
        app: The project app state (provides library_service).
        registry_key: Three-part key ``lib_id:comp_type:class_name``.

    Returns:
        The registered class, or None when the key is malformed, the
        registry is unavailable, or the class is not found.
    """
    if not app or not registry_key:
        return None
    parts = registry_key.split(":", 2)
    if len(parts) != 3:
        return None
    _lib_id, comp_singular, _class_name = parts
    getter_name = _REGISTRY_GETTER.get(comp_singular)
    if getter_name is None:
        return None
    try:
        svc = app.library_service
        registry = getattr(svc, getter_name, lambda: None)()
        if registry is None:
            return None
        return registry.get(registry_key)
    except Exception:
        return None
```

- [ ] **Step 2: Run ruff on new file**

```sh
uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/_registry_utils.py
```

Expected: clean.

- [ ] **Step 3: Update `ComponentSourceEditor` to use the shared helper**

In `component_source_editor.py`:

1. Add import (alongside existing imports):
```python
from ._registry_utils import lookup_component_class
```

2. Delete the `_REGISTRY_GETTER` dict (lines 59–70).

3. Replace `_lookup_class` (lines 172–191):
```python
    def _lookup_class(self, context: "SessionContext", registry_key: str) -> Optional[type]:
        return lookup_component_class(context.app, registry_key)
```

4. Replace `_resolve_registry` (lines 409–427) — this method uses `_REGISTRY_GETTER` directly to get the registry object (not the class). Extract just the registry-getter part:

```python
    def _resolve_registry(self, context: "SessionContext") -> Optional["BaseRegistry"]:
        """Return the BaseRegistry that owns self._registry_key, or None."""
        if not self._registry_key:
            return None
        app = context.app
        if app is None:
            return None
        parts = self._registry_key.split(":", 2)
        if len(parts) != 3:
            return None
        _lib_id, comp_singular, _class_name = parts
        from ._registry_utils import _REGISTRY_GETTER
        getter_name = _REGISTRY_GETTER.get(comp_singular)
        if getter_name is None:
            return None
        try:
            svc = app.library_service
            return getattr(svc, getter_name, lambda: None)()
        except Exception:
            return None
```

- [ ] **Step 4: Update `LibraryComponentEditor._lookup_class` and add the guard**

In `library_component_editor.py`:

1. Add import:
```python
from ._registry_utils import lookup_component_class
```

2. Replace `_lookup_class` (lines 249–269):
```python
    @staticmethod
    def _lookup_class(app, lib_id: str, comp_type: str, registry_key: str):
        """Look up the component class from the appropriate registry."""
        return lookup_component_class(app, registry_key)
```

3. Add the guard on the `registry_key.split` in `_rebuild` (line 94). Replace:
```python
            lib_id, comp_singular, class_name = registry_key.split(":", 2)
            comp_type = f"{comp_singular}s"
```
with:
```python
            parts = registry_key.split(":", 2)
            if len(parts) != 3:
                hui.empty_state(
                    f"Invalid component key: {registry_key}",
                    icon=hui.icon.warning,
                )
                return
            lib_id, comp_singular, class_name = parts
            comp_type = f"{comp_singular}s"
```

- [ ] **Step 5: Verify no stale `_REGISTRY_GETTER` or inline registry dicts remain**

```sh
grep -n "_REGISTRY_GETTER\|get_node_registry\|get_widget_registry" \
  barn/haybale-marketplace/haybale_marketplace/editors/component_source_editor.py \
  barn/haybale-marketplace/haybale_marketplace/editors/library_component_editor.py
```

Expected: only the import lines in `component_source_editor.py` (`from ._registry_utils import _REGISTRY_GETTER` in `_resolve_registry`). No inline dicts.

- [ ] **Step 6: Run lint and tests**

```sh
uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/
uv run pytest tests/ -k "marketplace or component or library" -v 2>&1 | tail -20
```

Expected: ruff clean, no new failures.

- [ ] **Step 7: Commit**

```sh
git add barn/haybale-marketplace/haybale_marketplace/editors/_registry_utils.py \
        barn/haybale-marketplace/haybale_marketplace/editors/component_source_editor.py \
        barn/haybale-marketplace/haybale_marketplace/editors/library_component_editor.py
git commit -m "refactor: extract lookup_component_class helper, add registry_key guard in LibraryComponentEditor"
```

---

## Task 4: Deduplicate marketplace.toml parsing and normalise lib duck-typing in `LibraryBrowserEditor._render_list`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:328-555`

Two problems in `_render_list`:

1. `marketplace.toml` is parsed **twice** — once for available packages (lines 447–480) and again for update detection (lines 488–512). They can share one parse.
2. The `hasattr(lib, "identity")` duck-typing dispatch (`_label`, `_enabled`, `matches`) repeats four times. Extract a small `_LibView` named-tuple normaliser so the filter logic reads cleanly.

- [ ] **Step 1: Add `_LibView` named-tuple above `_render_list`**

Add just before the `_render_list` method definition (around line 328), a small dataclass-like structure. Because this is internal to the method the cleanest form is a module-level `NamedTuple`. Add it at the top of the class body (after `__init__`, before `_refresh_on_library_change`) or at module level after the imports:

```python
from typing import NamedTuple

class _LibView(NamedTuple):
    """Normalised view of a LibraryInfo or Haybale for filter/display logic."""
    raw: object          # the original object for click handlers
    label: str
    version: str
    description: str
    tags: list
    enabled: bool
    dist_name: str | None
    is_installed: bool   # True for LibraryInfo, False for Haybale


def _lib_view(lib) -> "_LibView":
    """Normalise a LibraryInfo or Haybale into a _LibView."""
    if hasattr(lib, "identity"):
        return _LibView(
            raw=lib,
            label=lib.identity.label or "",
            version=lib.identity.version or "",
            description=lib.identity.description or "",
            tags=lib.identity.tags or [],
            enabled=lib.enabled,
            dist_name=lib.distribution_name,
            is_installed=True,
        )
    return _LibView(
        raw=lib,
        label=getattr(lib, "label", "") or getattr(lib, "name", ""),
        version=getattr(lib, "version", "") or "",
        description=getattr(lib, "description", "") or "",
        tags=getattr(lib, "tags", []) or [],
        enabled=getattr(lib, "enabled", True),
        dist_name=getattr(lib, "name", None),
        is_installed=False,
    )
```

Place `_LibView` and `_lib_view` at module level (after the imports section, before the `@editor` decorator for `LibraryBrowserEditor`).

- [ ] **Step 2: Parse `marketplace.toml` once and compute both `available` and `updates_available` together**

In `_render_list`, replace the two separate parse blocks (lines 447–512) with a single combined block. Insert this after the `disabled.sort(key=_label)` line and before the section-rendering `with self._list_container:`:

```python
        # Parse the project marketplace once for both "available" packages and
        # "updates available" indicators — avoids reading the file twice.
        available: list = []
        updates_available: set[str] = set()
        workspace_root = getattr(context.app, "workspace_root", None)
        marketplace_path = (
            Path(workspace_root) / ".haywire" / "marketplace.toml" if workspace_root else None
        )
        if marketplace_path and marketplace_path.exists():
            try:
                from packaging.version import Version
                from haywire.core.marketstall import Haybale, parse_project_marketplace

                pm = parse_project_marketplace(marketplace_path)

                # Updates available — compare caches vs installed versions
                for entry in pm.caches:
                    if not entry.min_version or not entry.name:
                        continue
                    lib = next(
                        (x for x in libraries if x.distribution_name == entry.name), None
                    )
                    if lib and lib.identity.version:
                        try:
                            if Version(entry.min_version) > Version(lib.identity.version):
                                updates_available.add(entry.name)
                        except Exception:
                            pass

                # Available (not yet installed) — caches + heaps
                if self._filter_available:
                    candidates: list = list(pm.caches)
                    for raw in pm.heaps:
                        name = raw.get("name")
                        if not isinstance(name, str):
                            continue
                        candidates.append(
                            Haybale(
                                name=name,
                                min_version="",
                                label=raw.get("label", ""),
                                description=raw.get("description", ""),
                                source="local",
                                install_spec=str(raw.get("path", "")),
                                dependencies=list(raw.get("dependencies", [])),
                            )
                        )
                    available = [
                        e for e in candidates if e.name not in installed_names and matches(e)
                    ]
                    available.sort(key=lambda x: x.label or x.name)
            except Exception as e:
                logger.warning(f"LibraryBrowser: failed to load marketplace: {e}")
```

Delete the original two separate parse blocks (lines 447–512 in the original file).

- [ ] **Step 3: Replace the four `hasattr(lib, "identity")` blocks with `_lib_view` calls**

The three inner functions `_label`, `_enabled`, and `matches` inside `_render_list` all branch on `hasattr(lib, "identity")`. Replace them with calls to `_lib_view`:

```python
        def matches(lib) -> bool:
            if not q:
                return True
            v = _lib_view(lib)
            return (
                q in v.label.lower()
                or bool(v.description and q in v.description.lower())
                or any(q in t.lower() for t in v.tags)
            )

        def is_required(lib) -> bool:
            if not hasattr(lib, "identity"):
                return False
            return bool(manager.get_installed_dependents(lib.identity.id))
```

Replace `_enabled(lib)` references (used in list comprehensions) with:
```python
        def _enabled(lib) -> bool:
            return _lib_view(lib).enabled
```

Also replace `_label(lib)` references (used in sort keys):
```python
        def _label(lib) -> str:
            return _lib_view(lib).label
```

Note: `_lib_view` is called multiple times per library during filter/sort. This is fine — each call is O(1) attribute access. Do not cache `_lib_view` results unless profiling shows a problem.

- [ ] **Step 4: Verify no duplicate `parse_project_marketplace` calls remain**

```sh
grep -n "parse_project_marketplace" barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py
```

Expected: exactly one occurrence.

- [ ] **Step 5: Run lint and tests**

```sh
uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py
uv run pytest tests/ -k "library_browser or marketplace" -v 2>&1 | tail -20
```

Expected: ruff clean, no new failures.

- [ ] **Step 6: Commit**

```sh
git add barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py
git commit -m "refactor(library-browser): parse marketplace.toml once, extract _lib_view normaliser"
```

---

## Final verification

- [ ] **Run full test suite**

```sh
uv run pytest
```

Expected: all previously-passing tests still pass.

- [ ] **Run full lint + format check**

```sh
uv run ruff check .
uv run ruff format --check .
```

Expected: clean.

- [ ] **Run mypy on touched packages**

```sh
uv run mypy \
  barn/haybale-studio/haybale_studio/ \
  barn/haybale-graph-editor/haybale_graph_editor/ \
  barn/haybale-haystack/haybale_haystack/ \
  barn/haybale-marketplace/haybale_marketplace/
```

Expected: no new errors.

---

## Self-Review

**Spec coverage:**
- Task 1 ✓ — `ui.card()` → `hui.dialog_card()` in `CodeEditor._build_save_as_dialog`
- Task 2 ✓ — duplicate `_open_save_as_dialog` extracted to shared `open_graph_save_as_dialog()`
- Task 3 ✓ — duplicate `_REGISTRY_GETTER`/`_lookup_class` extracted to `_registry_utils.py`; `LibraryComponentEditor` guard added
- Task 4 ✓ — double `parse_project_marketplace` call collapsed; `_lib_view` normaliser replaces `hasattr` dispatch chains

**Skipped intentionally:**
- `HaystackEditor._render_entry` row-renderer extraction (moderate finding) — judged too close to the HaystackEditor decompose in the blockers handoff; doing it here would create conflict. Keep as a follow-up once the blockers handoff is merged.

**Placeholder scan:** No TBDs, no "similar to Task N" references, all code blocks are complete.

**Type consistency:** `open_graph_save_as_dialog` accepts `save_fn: Callable[[Path], bool]` — used consistently in both Task 2 call sites. `lookup_component_class` returns `Optional[type]` — matches both callers' `Optional[type]` return annotations. `_LibView` fields match all three usage sites in `_render_list`.
