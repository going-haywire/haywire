# Building Editors

Editors are the primary extension point for adding new workspace panels to Haywire. Each editor occupies a named area (Left, Middle, Right, or Bottom), builds its own NiceGUI layout, and reacts to context changes via the event bus. This guide walks through everything you need to create, register, and integrate a custom editor.

For background on how editors fit into the larger UI architecture, see
[haywire_app.md](architecture/haywire_app.md).

## Table of Contents

1. [What Is an Editor?](#1-what-is-an-editor)
2. [Quick Start](#2-quick-start)
3. [The @editor Decorator](#3-the-editor-decorator)
4. [Implementing BaseEditor](#4-implementing-baseeditor)
5. [Registering an Editor](#5-registering-an-editor)
6. [Reacting to Context Changes](#6-reacting-to-context-changes)
7. [Reading and Writing Session Context](#7-reading-and-writing-session-context)
8. [Driving Other Areas](#8-driving-other-areas)
9. [NiceGUI Async Patterns](#9-nicegui-async-patterns)
10. [Best Practices](#10-best-practices)
11. [Full Example: A Custom Log Viewer Editor](#11-full-example-a-custom-log-viewer-editor)

---

## 1. What Is an Editor?

An editor is a class that:

- Is decorated with `@editor(...)`, which stamps it with an `EditorIdentity`
- Inherits from `BaseEditor`
- Implements `render()` to build its NiceGUI UI into a provided container
- Implements `on_context_changed()` to react when the session state changes

One instance of the editor class is created per area per session. The instance lives for as long as it occupies that area. When the user switches the area to a different editor the old instance is cleaned up and a new one is created.

---

## 2. Quick Start

Here is a minimal editor that displays a heading and a label that updates whenever the active node changes:

```python
from nicegui import ui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType

@editor(
    label='My Info',
    icon='info',
    default_slot='right',
)
class MyInfoEditor(BaseEditor):

    def __init__(self):
        self._status_label = None

    def render(self, container, context) -> None:
        with container:
            ui.label('My Info Panel').classes('text-lg font-bold p-4')
            self._status_label = ui.label('No node selected').classes('text-sm p-4')

    def on_context_changed(self, event, context) -> None:
        if event.change_type != ContextChangeType.SELECTION_CHANGED:
            return
        if self._status_label is None:
            return
        node = context.active_node
        if node:
            self._status_label.text = f'Active: {getattr(node, "name", str(node))}'
        else:
            self._status_label.text = 'No node selected'
```

After [registering it](#5-registering-an-editor) and adding its `registry_id` to a workspace preset, the editor appears in the configured area automatically.

---

## 3. The @editor Decorator

```python
@editor(
    label='Graph Editor',
    icon='account_tree',
    default_slot='main',            # 'left' | 'right' | 'main' | 'bottom'
    opens='on_payload',             # 'required' | 'on_context' | 'on_payload'
    context_field='active_graph_path',  # optional; field on SessionContext to mirror
    description='Visual node graph editor',
)
```

### Instance behavior: `opens`

The `opens` kwarg declares how an editor's tabs come into being and how
many can exist. Three values:

- **`required`** (default) — the shell guarantees one tab at startup.
  Uncloseable. Content typically reads from session context. Use for
  persistent panels (left/right side editors, bottom terminal, rarely
  main).

- **`on_context`** — singleton tab, on-demand. The tab's content mirrors
  a slice of session context (e.g. `active_library`). Opened when
  something fires `reveal_editor=...` with no payload; a second reveal
  with different context just redraws the same tab via `poll()`.
  Closeable. Not persisted across restart.

- **`on_payload`** — per-payload tab, on-demand. The tab's identity and
  content are determined by its `binding.payload`. Opened when the
  reveal fires `reveal_editor=... reveal_payload=<value>`; N distinct
  payloads means N distinct tabs. Closeable. Persisted across restart.

**Constraint:** `default_slot='left'` and `'right'` only support
`opens='required'`. Bars don't have a tab structure to host on-demand
or multi-instance editors — the decorator raises `ValueError` at
class-definition time if you try.

**`context_field`** (optional) names a `SessionContext` attribute that
the shell should mirror `binding.payload` into whenever this editor's
tab becomes active. Only meaningful for `on_payload` editors in the
main slot. Example: a FileViewer declares `context_field='active_file'`
so any peer editor reading `context.active_file` sees the currently-
focused file.

### What the decorator does

- Sets `MyEditor.class_identity` (an `EditorIdentity` dataclass) with all the metadata above
- Sets `MyEditor.class_library` (derived from the module's `__package__`)
- Computes the full `registry_key` as `{library_id}:editor:{registry_id}`
- Validates that the decorated class is a `BaseEditor` subclass

### What the decorator does NOT do

The decorator does **not** register the class. Registration is always explicit (see [Section 5](#5-registering-an-editor)). This means you can decorate a class, inspect or test it, and only register it in the specific applications that need it.

### registry_id vs. registry_key

`registry_id` is the short, human-readable identifier (`'my_info'`). The full `registry_key` includes the library prefix (`'my_library:editor:my_info'`). Workspace state files and `AppShell` use the short `registry_id` for slot configuration. The registry itself uses the full key internally.

---

## 4. Implementing BaseEditor

### `render(container, context)`

Called once when the editor is placed into a slot. Build your entire NiceGUI UI here. Always use `with container:` to ensure elements are created inside the correct slot:

```python
def render(self, container, context) -> None:
    with container:
        with ui.column().classes('w-full h-full p-4'):
            self._heading = ui.label('Hello').classes('text-lg')
            self._body    = ui.column().classes('w-full')
            self._populate(context)
```

Store references to elements you will update later. Do not rely on re-calling `render()` —
it is only called once per slot assignment.

### `on_context_changed(event, context)`

Called every time any editor in the session fires `notify_context_changed()`. Filter on
`event.change_type` to only react to relevant changes:

```python
def on_context_changed(self, event, context) -> None:
    if event.change_type in (
        ContextChangeType.SELECTION_CHANGED,
        ContextChangeType.DATA_MUTATED,
    ):
        self._body.clear()
        with self._body:
            self._populate(context)
```

For large updates, clear the container and rebuild. For small updates, modify element
attributes directly (see [Section 9](#9-nicegui-async-patterns) for async considerations).

### `cleanup()`

Optional. Called when the editor is removed from its area (either because the user switched to a different editor, or because the session disconnects). Use it to cancel timers, close file handles, or unsubscribe from external signals:

```python
def cleanup(self) -> None:
    if self._timer is not None:
        self._timer.cancel()
```

### `get_tab_label(context)`

Optional. Only relevant for editors placed in the Middle area's tab bar. Return a string to override the default label from `class_identity.label`:

```python
def get_tab_label(self, context) -> str:
    graph = context.active_graph
    return graph.name if graph else 'Graph'
```

---

## 5. Registering an Editor

Registration is separate from decoration by design. Choose the level that matches where your editor lives:

### Framework-level (ships with haywire-core)

Add the class to the `register_builtin_editors()` function:

```python
# packages/haywire-core/src/haywire/ui/editors/builtins.py
from haywire.ui.editors.my_info import MyInfoEditor

def register_builtin_editors(registry: EditorTypeRegistry) -> None:
    registry._register_class(MyInfoEditor)
```

### App-level (ships with haywire-app)

Call `_register_class()` during application startup, inside `setup_shared_services()`:

```python
# packages/haywire-app/src/haywire_app/app.py
from haywire_app.editors.my_info import MyInfoEditor

def setup_shared_services(self):
    ...
    self._editor_registry._register_class(MyInfoEditor)
```

### Library-level (ships inside a haybale library)

Scan a folder in `register_components()`. Any `@editor`-decorated class in the folder will be picked up:

```python
# my_library/library.py
from pathlib import Path
from haywire.ui.editor.registry import EditorTypeRegistry

class MyLibrary(BaseLibrary):
    def register_components(self):
        """Register nodes and custom types"""
        base_path = Path(__file__).parent
        ...

        # Register editors
        self.add_folder_to_registry(
            folder_path=str(base_path / 'editors'),
            registry_cls=EditorTypeRegistry
        )

```

---

## 6. Reacting to Context Changes

### Filtering by change type

Always filter on `event.change_type` before doing any work. Rebuilding UI unnecessarily on
every event type wastes CPU and causes visual flicker:

```python
def on_context_changed(self, event, context) -> None:
    if event.change_type not in (
        ContextChangeType.SELECTION_CHANGED,
        ContextChangeType.ACTIVE_LIBRARY_CHANGED,
    ):
        return
    self._rebuild(context)
```

### Full rebuild vs. incremental update

Use **full rebuild** (clear + re-render) when the structure of your UI changes significantly:

```python
def _rebuild(self, context) -> None:
    self._container.clear()
    with self._container:
        self._build_content(context)
```

Use **incremental update** (modify element attributes) when only values change:

```python
def on_context_changed(self, event, context) -> None:
    if event.change_type == ContextChangeType.DATA_MUTATED:
        node = context.active_node
        self._name_label.text = getattr(node, 'name', '—') if node else '—'
```

Incremental updates are always faster and do not cause layout shifts.

### Avoiding echo events

If your editor fires events, guard against processing your own events:

```python
def on_context_changed(self, event, context) -> None:
    if event.source_editor == 'my_info':
        return   # ignore events we originated
```

---

## 7. Reading and Writing Session Context

### Reading context

Access `SessionContext` attributes directly:

```python
node  = context.active_node     # NodeWrapper or None
graph = context.active_graph    # HaywireGraph or None
lib   = context.active_library  # InstalledLibrary, MarketplaceEntry, or None
mode  = context.interaction_mode
```

Access shared services through `context.metadata`:

```python
app     = context.metadata.get('project_state')   # HaywireApp
session = context.metadata.get('haywire_session')  # Session
panels  = context.metadata.get('panel_registry')   # PanelRegistry
```

### Writing context and firing events

Mutate the relevant context attribute, then call `notify_context_changed()`:

```python
def _on_library_selected(self, lib, context) -> None:
    context.active_library  = lib
    context.active_component = None

    session = context.metadata.get('haywire_session')
    if session:
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.ACTIVE_LIBRARY_CHANGED,
                source_editor='my_info',
            )
        )
```

Only write to context fields that are semantically appropriate for your editor. Do not
overwrite fields owned by another editor (e.g. don't reset `active_node` from a library
browser).

---

## 8. Driving Other Slots

### Revealing an editor when firing a context event

When an event should also surface a particular editor (e.g. selecting a
component should bring the component-detail editor to the front), attach the
target editor's `registry_key` to the `ContextChangedEvent` via the
`reveal_editor` field. The AppShell orchestrator resolves the target slot from
the editor's `class_identity.default_slot` and switches that slot before running
the normal poll/draw cycle, so the revealed editor receives the same event that
caused it to be revealed — a single render pass, no nested `WORKSPACE_CHANGED`.

```python
from haybale_studio.editors.library_component_editor import LibraryComponentEditor

context.session.notify_context_changed(
    ContextChangedEvent(
        change_type=ContextChangeType.ACTIVE_COMPONENT_CHANGED,
        source_editor='library_detail',
        reveal_editor=LibraryComponentEditor.class_identity.registry_key,
    )
)
```

If the revealed editor is not hostable in the active workspace (e.g. its
`default_slot` is not `left` or `right`, or the registry does not know the
key) the orchestrator logs a warning and the original event still propagates
to all currently-mounted editors.

### Switching tabs in main / bottom slots

`reveal_editor` works identically for all four slots (left, right, main,
bottom). Set it on the emitted `ContextChangedEvent` — the AppShell resolves
the hosting slot and switches as part of the same dispatch:

```python
session.notify_context_changed(
    ContextChangedEvent(
        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
        source_editor="file_browser",
        detail=entry,
        reveal_editor="studio:editor:graph_editor",
    )
)
```

If the target editor is not registered or its hosting slot is not active in
the current workspace, the orchestrator logs a warning and the event still
propagates.

When the target editor is `opens='on_payload'`, a reveal without a
`reveal_payload` is a no-op with a warning — payloads are mandatory for
per-payload editors. When the target is `opens='on_context'` and no
matching tab exists, the shell auto-creates a payload-less tab.

---

## 9. NiceGUI Async Patterns

NiceGUI's slot stack is stored **per asyncio task ID**. New tasks created with
`asyncio.ensure_future()` or `background_tasks.create()` start with an empty slot stack, which means `ui.notify()` and other context-discovering functions will crash inside them.

### Rule 1 — Async button handlers: return the coroutine

When a button's `on_click` handler needs to `await` something, return the coroutine from the lambda. NiceGUI detects the returned `Awaitable` and schedules it with the parent slot context preserved:

```python
# CORRECT — NiceGUI wraps the returned coroutine with the slot context
ui.button('Run', on_click=lambda e: self._run_async(context))

# WRONG — asyncio.ensure_future() creates a new task with an empty slot stack
ui.button('Run', on_click=lambda e: asyncio.ensure_future(self._run_async(context)))
```

This applies to any call to `ui.notify()`, `ui.dialog()`, or any NiceGUI function that
needs to discover the current client from the slot stack.

### Rule 2 — Creating UI in a background task: enter the container

If you genuinely need to create NiceGUI elements from a background task (e.g. after an async network fetch), enter the target container explicitly first:

```python
async def _load_and_render(self, container):
    data = await fetch_data()
    with container:                  # ← pushes container's slot onto THIS task's stack
        ui.label(data['name'])
        ui.label(data['value'])
```

### Rule 3 — Modifying existing elements: always safe

Setting attributes on existing elements (`.text`, `.value`, `.options`, `.props()`,
`.set_visibility()`) does not require the slot stack. It is safe to do from any background task:

```python
async def _poll_status(self):
    while True:
        status = await fetch_status()
        self._status_label.text = status   # safe — no slot context needed
        await asyncio.sleep(5)
```

---

## 10. Best Practices

**Keep `render()` fast.** Do the minimum structural work in `render()`. Defer heavy data
loading to an async background task that fills in a pre-created container.

**Store container references.** Save references to NiceGUI elements and containers you will update later. Element lookup by ID is slow and fragile.

```python
def render(self, container, context) -> None:
    with container:
        self._list = ui.column().classes('w-full')  # ← saved for later use
```

**Let context drive visibility, not internal flags.** Avoid maintaining separate `_is_node_selected` booleans. Read from `context.active_node` directly in `on_context_changed`.

**One rebuild strategy per editor.** Decide upfront whether your editor does full rebuilds or incremental updates. Mixed strategies are hard to maintain. For simple editors, full clear + rebuild is fine. For complex editors with expensive renders, invest in targeted updates.

**Guard against missing metadata.** Always use `.get()` on `context.metadata` — services may not be wired in all runtime environments (e.g. unit tests):

```python
app = context.metadata.get('project_state')
if app is None:
    return
```

**Use `compact-fields` for dense form areas.** If your editor renders Quasar input fields
(number, text, select, toggle) in a tight sidebar or inspector layout, add the
`compact-fields` CSS class to the wrapping container. This reduces vertical gaps, hides
validation space, and clamps field heights — all scoped to that container. The CSS is
injected globally by `AppShell`, so no `ui.add_css()` call is needed. See the
[Compact Field Styling](build_panels.md#10-compact-field-styling) section in the panel
guide for the full list of overrides and theme integration via CSS custom properties
(`--hw-compact-gap`, `--hw-compact-field-h`, `--hw-compact-row-min-h`).

**Implement `cleanup()`.** Even if you have nothing to clean up now, add a no-op and a
comment. Future modifications that add timers or subscriptions are easy to forget.

**`default_slot` is where the editor lives; `opens` is how its tabs
appear.** Set `default_slot` to place the editor in the right slot.
Set `opens` to say whether it auto-populates (`required`) or waits to
be triggered (`on_context` / `on_payload`). Workspace configs override
`default_slot` entirely; `opens` is a property of the editor class.

---

## 11. Full Example: A Custom Log Viewer Editor

This example implements a log-viewer editor that tails a log file from the project directory and displays new lines in real time. It demonstrates async background tasks, container management, and context reading.

```python
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent


@editor(
    label='Project Log',
    icon='subject',
    default_slot='bottom',
    description='Live tail of the project log file.',
)
class ProjectLogEditor(BaseEditor):

    def __init__(self):
        self._log_element = None
        self._log_path: Path | None = None
        self._tail_task: asyncio.Task | None = None

    def render(self, container, context: "SessionContext") -> None:
        app = context.metadata.get('project_state')
        if app and hasattr(app, 'workspace_root'):
            self._log_path = Path(app.workspace_root) / 'haywire.log'

        with container:
            with ui.column().classes('w-full h-full gap-0'):
                with ui.row().classes('w-full items-center px-2 py-1 border-b flex-shrink-0'):
                    ui.icon('subject').classes('text-gray-400')
                    ui.label('Project Log').classes('text-sm font-medium')
                    ui.space()
                    ui.button(
                        icon='delete_sweep',
                        on_click=lambda: self._log_element.clear()
                            if self._log_element else None,
                    ).props('flat round dense size=sm').tooltip('Clear')

                with ui.scroll_area().classes('flex-1 w-full'):
                    self._log_element = ui.log(max_lines=500).classes('w-full')

        # Start the background tail task
        # Rule 1: return coroutine so NiceGUI wraps it with slot context
        asyncio.ensure_future(self._tail_log())

    async def _tail_log(self) -> None:
        """Background task: append new lines to the log element."""
        if self._log_path is None or not self._log_path.exists():
            if self._log_element:
                self._log_element.push('Log file not found.')
            return

        # Rule 3: log.push() modifies an existing element — safe from background task
        offset = self._log_path.stat().st_size
        while True:
            try:
                current_size = self._log_path.stat().st_size
                if current_size > offset:
                    with self._log_path.open('r') as f:
                        f.seek(offset)
                        for line in f:
                            if self._log_element:
                                self._log_element.push(line.rstrip())
                    offset = current_size
            except OSError:
                pass
            await asyncio.sleep(1.0)

    def on_context_changed(self, event: 'ContextChangedEvent', context: "SessionContext") -> None:
        pass  # Log viewer is context-independent

    def cleanup(self) -> None:
        if self._tail_task and not self._tail_task.done():
            self._tail_task.cancel()
```

### Registering in a library

```python
# my_library/library.py
from pathlib import Path
from haywire.ui.editor.registry import EditorTypeRegistry

class MyLibrary(BaseLibrary):
    def register_components(self):
        """Register nodes and custom types"""
        base_path = Path(__file__).parent
        ...

        # Register editors
        self.add_folder_to_registry(
            folder_path=str(base_path / 'editors'),
            registry_cls=EditorTypeRegistry
        )
```

### Adding to a workspace preset

To make the editor appear by default, add its `registry_id` to a `WorkspaceState`:

```python
WorkspaceState(
    name='My Workspace',
    main=MainSlotState(
        tabs=[TabState(editor_key='graph_editor')],
        active_tab_key='graph_editor',
    ),
    bottom=BottomSlotState(
        visible=True,
        active_tab_key='project_log',   # ← our new editor
    ),
)
```
