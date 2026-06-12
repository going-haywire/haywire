# Handoff — LibraryOverviewEditor decompose + asyncio.ensure_future fix

**Date:** 2026-06-12
**Status:** open — two confirmed blockers from a thermo-nuclear code quality review of the editor architecture.
**Scope:** `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`

---

## One-paragraph context

`LibraryOverviewEditor` has grown to 1395 lines and owns four logically distinct
responsibilities: header/metadata rendering, enable/disable/uninstall actions,
a project-library edit dialog (with dependency detection), and the 3-step
install/update flow. A code-quality review flagged this as a structural blocker.
A second blocker in the same file is an `asyncio.ensure_future()` call that
violates the NiceGUI async rule in `.insights/feedback_nicegui_async.md` and
will break `ui.notify()` inside the coroutine under concurrent load.

---

## Blocker 1 — `asyncio.ensure_future` at line 610

### What it is

In `_render_center`, after building the marketplace-only scroll area, the
async overview fetch is scheduled like this:

```python
# library_overview_editor.py line 610
asyncio.ensure_future(
    self._load_marketplace_overview(marketplace_pkg, loading_row, content_area, context)
)
```

### Why it is wrong

`.insights/feedback_nicegui_async.md` documents that `asyncio.ensure_future()`
creates a task that runs outside the current NiceGUI slot stack context. Any
`ui.notify()` (or other NiceGUI UI call) inside `_load_marketplace_overview`
will crash with a "No context" error because the slot stack is per-asyncio-task.

### The fix

Replace with `background_tasks.create(...)`. The import is already present at
line 26:

```python
from nicegui import background_tasks
```

Change line 610 from:

```python
asyncio.ensure_future(
    self._load_marketplace_overview(marketplace_pkg, loading_row, content_area, context)
)
```

to:

```python
background_tasks.create(
    self._load_marketplace_overview(marketplace_pkg, loading_row, content_area, context),
    name=f"marketplace-overview-{marketplace_pkg.name}",
)
```

`_load_marketplace_overview` at line 1372 ends with UI mutations on
`loading_row` and `content_area` — verify those are wrapped in a `with client:`
guard or that they are still mounted when the task completes (the current code
does not guard them). If the editor is closed before the fetch completes the
elements will be gone. The safest fix is:

```python
async def _load_marketplace_overview(self, pkg, loading_row, content_area, context):
    from haybale_marketplace.state.marketplace_state import MarketplaceState
    marketplace_state = context.app_data.get(MarketplaceState) if context.app_data else None
    content = await marketplace_state.fetch_overview(pkg) if marketplace_state else None
    try:
        loading_row.set_visibility(False)
        with content_area:
            if content:
                ui.markdown(content).classes("w-full")
            else:
                ui.label("No overview available for this package.").classes("hw-text-muted text-sm italic")
                if pkg.source_url:
                    ui.link("View source repository →", pkg.source_url, new_tab=True).classes(
                        "text-xs hw-text-accent mt-1"
                    )
    except Exception:
        pass  # editor was closed before task completed — silently drop
```

This is a one-line change plus a safety guard. Do this first — it is the
smallest diff and fixes a real crash path.

---

## Blocker 2 — Decompose LibraryOverviewEditor (1395 → ~250 lines)

### Goal

The `LibraryOverviewEditor` class should own only its editor contract:
`draw()` → `_rebuild()` → delegate to helpers. The four responsibility
clusters should move to their own modules.

### Proposed file layout

```
barn/haybale-marketplace/haybale_marketplace/editors/
├── library_overview_editor.py          ← shrinks to ~250 lines (the editor class + _render_center shell)
├── _overview_actions.py                ← enable / disable / uninstall
├── _overview_edit_dialog.py            ← Edit dialog + detect-dependencies flow
└── _overview_install_flow.py           ← install-with-safety-check + 3-step install + version picker
```

The leading underscore signals these are internal to the editors package and
not part of the haybale-marketplace public API.

### What moves where

#### `_overview_actions.py`

Move these methods verbatim (they are pure service-call + notification, no
layout):

- `_enable_library(self, library_id, manager, context)`
- `_disable_library(self, library_id, manager, context)`
- `_reload_installed(library_id, manager)` (staticmethod)
- `_find_installed_by_dist_name(dist_name, manager)` (staticmethod)
- `_notify_library_changed(self, context)`
- `_confirm_uninstall(self, library_id, label, manager, context)`
- `_create_log_in_card(container, title)` (staticmethod)
- `_do_uninstall(self, library_id, label, manager, context)` (async)

Pattern: make these module-level functions that take the same arguments they
currently receive as `self.*` calls. Example:

```python
# _overview_actions.py
def enable_library(library_id: str, manager, context: SessionContext) -> None:
    manager.registry.enable_library(library_id)
    ui.notify(f"Enabled: {library_id}", type="positive")
    context.active_library = reload_installed(library_id, manager)
    notify_library_changed(context)
```

The editor class calls `enable_library(...)` instead of `self._enable_library(...)`.

#### `_overview_edit_dialog.py`

Move these methods:

- `_is_project_library(lib, marketplace_path)` (staticmethod)
- `_read_os_from_pyproject(lib, marketplace_path)` (currently instance method, can be static)
- `_build_edit_dialog(self, lib, marketplace_path, manager, context)`
- `_detect_dependencies(self, deps_input, manager, lib, marketplace_path)`
- `_write_pyproject_deps(lib_dir, deps, setter)` (staticmethod)
- `_do_update_identity(self, lib, identity, marketplace_path, manager, context)` (async)

The `_build_edit_dialog` method returns a `ui.dialog` — it doesn't need
`self` for anything beyond the method calls it closes over. Convert to a
module-level function:

```python
# _overview_edit_dialog.py
def build_edit_dialog(lib, marketplace_path, manager, context) -> ui.dialog:
    ...
```

The editor calls:
```python
on_click=lambda ilib=installed_lib, mp=marketplace_path, m=manager, ctx=context: (
    build_edit_dialog(ilib, mp, m, ctx).open()
),
```

#### `_overview_install_flow.py`

Move these methods:

- `_install_with_safety_check(self, pkg, button, manager, context)`
- `_install_package(self, install_spec, name, button, manager, context, source_pkg)` (async)
- `_open_version_picker(self, pkg, manager, context)`

Same pattern — convert to module-level functions. The install flow has no
instance state; it reads `context` and calls `manager`. Only
`_find_installed_by_dist_name` and `_notify_library_changed` are called from
inside; import them from `_overview_actions`.

```python
# _overview_install_flow.py
async def install_package(install_spec, name, button, manager, context, source_pkg=None):
    ...
```

#### What stays in `library_overview_editor.py`

- `TabConfig` dataclass + `_CFG_*` constants
- `should_block_install_for_os()` helper
- `LibraryOverviewEditor` class:
  - `__init__`, `_refresh_on_library_change`, `draw`, `_rebuild`
  - `_lookup_marketplace_pkg`
  - `_render_placeholder`
  - `_action_button` (small enough)
  - `_render_center` (the layout skeleton — now just wires tabs and delegates)
  - `_make_tab_panel`, `_registry_items`, `_component_row`
  - `_render_overview`, `_render_component_tab`
  - `_select_component`
  - `_load_marketplace_overview` (async, 15 lines after fix)

After extraction `_render_center` should shrink from ~370 lines to ~150 lines
because the action-button wiring delegates to `_overview_actions` functions
and the install/edit callbacks delegate to `_overview_install_flow` /
`_overview_edit_dialog` functions.

### Execution order

1. Fix `asyncio.ensure_future` → `background_tasks.create` first (one-liner,
   no structural risk, fixes the crash path).
2. Extract `_overview_actions.py` — pure functions, no UI layout, lowest
   risk of breakage.
3. Extract `_overview_install_flow.py` — self-contained async flow.
4. Extract `_overview_edit_dialog.py` — the edit dialog is the most complex
   extracted piece (it closes over `edit_dialog` in nested async `_save`);
   do this last.
5. Run `uv run pytest` and `uv run ruff check .` after each extraction step.

### What NOT to do

- Do not change the public editor interface (`draw`, `_rebuild`, signal
  subscriptions). The decompose is purely internal — no observable behavior
  change, no API surface change.
- Do not rename `LibraryOverviewEditor` or its registry key — those are
  stable identifiers referenced in workspace state JSON.
- Do not inline the extracted helpers back into `_render_center` during the
  refactor. The point is the class gets smaller, not that the helpers disappear.

---

## How to verify

```sh
uv run pytest -m "not integration"          # fast pass after each step
uv run pytest                               # full pass at the end
uv run ruff check barn/haybale-marketplace/
uv run ruff format --check barn/haybale-marketplace/
uv run mypy barn/haybale-marketplace/haybale_marketplace/
```

Manual smoke test: open the Marketplace editor in studio, select an installed
library, select a marketplace-only library (triggers the async overview fetch),
click Install on an uninstalled package, use the Edit dialog on a project
library. All paths must work without `ui.notify` errors or blank panels.
