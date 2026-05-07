---
status: draft
doc_template: canonical-example
scope: Authoring editors — BaseEditor subclass, @editor decorator, render / on_context_changed lifecycle, OpenBehavior tab modes
see-also:
  - ../panels/panel-canon.md
  - ../states/state-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Editor — Canonical Example

## 1. What it solves

An **editor** is a full-slot UI component in the haywire studio. As an author, you write a class that inherits from `BaseEditor`, decorate it with `@editor(...)`, implement `render()` to build its NiceGUI UI into a provided container, and implement `on_context_changed()` to react when the session state changes. One instance per slot per session.

Editors are the primary extension point for adding workspace UI. Once registered (your library's `register_components()` picks it up automatically via `EditorTypeRegistry`), the editor can be assigned to a slot in any workspace preset and reacts to selection / interaction events through the shared `SessionContext`.

The lifecycle is: instance is created when the slot first renders → `render(container, context)` builds the NiceGUI subtree once → `on_context_changed(event, context)` runs every time the session state mutates → `cleanup()` runs when the slot switches to a different editor.

## 2. How it fits

```text
@editor(label=..., default_slot=...)    EditorTypeRegistry             AppShell
class MyEditor(BaseEditor):              registers class                instantiates per slot
    def render(self, container,          on register_components()       calls render(),
              context): ...                                              subscribes
    def on_context_changed(                                              on_context_changed
        self, event, context): ...                                       to session events
```

Editors *host* panels (in panel-aware editors like `PropertiesEditor`) but they don't own panel content — that's [components/panels](../panels/panel-canon.md). Editors don't render themselves into the canvas — that's the studio's job. They render into the *container* AppShell hands them.

**Boundaries.** What slots are, how the AppShell works, the workspace preset system — see [architecture/studio](../../architecture/studio/studio-arch.md). Panels — see [components/panels](../panels/panel-canon.md). Library/session state accessed inside editors — see [components/states](../states/state-canon.md).

## 3. Important concepts

**The `@editor` decorator.** Required on every editor class. Sets `class_identity` (an `EditorIdentity` dataclass), `class_library` (derived from the module), and computes the `registry_key` as `<library_id>:editor:<registry_id>`.

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `label` | yes | — | Display name in tabs and tooltips |
| `default_slot` | yes | — | `'left'` / `'right'` / `'main'` / `'bottom'` |
| `icon` | no | — | Material icon for the bar |
| `opens` | no | `'required'` | `'required'` / `'on_context'` / `'on_payload'` — see below |
| `description` | no | `''` | Tooltip / accessibility text |
| `registry_id` | no | class name | Unique short ID within the library |

**`OpenBehavior` — how tabs come into being.** Three values:

- **`required`** — the shell guarantees one tab at startup. Uncloseable. Use for persistent panels (left/right side editors, main graph editor).
- **`on_context`** — singleton tab, on-demand. Content mirrors a slice of session context (e.g. `active_library`); a `reveal_editor=...` event opens it. Closeable, not persisted across restart.
- **`on_payload`** — per-payload tab, on-demand. Tab identity comes from `binding.payload`; N distinct payloads → N distinct tabs. Closeable, persisted across restart.

**Slot constraints.** `default_slot='left'` and `'right'` only support `opens='required'`. Bars don't have a tab structure to host on-demand or multi-instance editors. The decorator raises `ValueError` at class-definition time if you try.

**`render(container, context)`.** Called once when the editor first occupies its slot. Build the NiceGUI subtree inside `container`. The base class handles `with container:` for you — your code starts inside the slot.

```python
def render(self, container, context):
    with container:
        ui.label('My Editor').classes('text-lg p-4')
        self._content = ui.column().classes('gap-2 p-4')
```

Store references to UI elements you'll later mutate as instance attributes (`self._content`, `self._status_label`).

**`on_context_changed(event, context)`.** Called whenever the session state mutates. The `event` is a `ContextChangedEvent` with a `change_type` field; the `context` is the live `SessionContext`. Filter by event kind:

```python
def on_context_changed(self, event, context):
    if event.change_type != ContextChangeType.SELECTION_CHANGED:
        return
    node = context.data[EditState].active_node.value
    self._status_label.text = f'Active: {node.name if node else "None"}'
```

The handler runs synchronously in the event-dispatch chain. Keep it fast. Long-running work goes in `asyncio.create_task` or a panel-internal `reactive_field`.

**`on_focus(self, slot, context)`.** Called by `Slot._activate` when the binding transitions from not-active to active. Override to mutate context and broadcast the corresponding event when this editor takes ownership of a slice of session state (e.g. `GraphEditor` setting `active_graph`). Not all editors need this.

**`cleanup(self)`.** Called when the slot switches to a different editor. Release subscriptions, stop background tasks, drop UI element references. The base class implementation is empty — override only if you have something to release.

**Reading and writing context.** `SessionContext` exposes:

- Direct fields: `context.active_node`, `context.active_edge`, `context.selected_nodes`, `context.interaction_mode`.
- Library state: `context.app_data[Cls]` (AppState) and `context.data[Cls]` (SessionState — see [components/states](../states/state-canon.md)).

Mutations broadcast automatically when you go through the session's `notify_context_changed` API.

**Driving other slots — `reveal_editor`.** A `ContextChangedEvent` can include `reveal_editor=<editor_key>`. The AppShell sees this and switches the hosting slot to that editor as part of the same dispatch. Use for "click a library entry → open its detail editor in the right slot" flows.

**Imports** (verified against codebase 2026-05):

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior   # for code that inspects the enum
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent
```

**Hot-reload.** `EditorTypeRegistry` extends `BaseRegistry`. New editor classes are picked up at the next render boundary; existing instances don't swap mid-render (NiceGUI element teardown is risky). Switch slots to force a fresh instance.

## 4. One comprehensive example

A worked example exercising every authoring concept: a `LogViewerEditor` for the bottom slot that shows a streaming log of context-change events, with filtering, an `on_focus` hook, and proper cleanup. Demonstrates `default_slot='bottom'`, `opens='on_context'`, panel-aware bottom-slot integration, NiceGUI async patterns, and reading both AppState and direct context.

```python
# my_lib/editors/log_viewer.py

from collections import deque
from typing import Any
from nicegui import ui

from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType

# Companion AppState that holds the log buffer. Lives across sessions
# so all tabs see the same log. See components/states/state-canon.md.
from ..state.log_buffer import LogBuffer

@editor(
    label='Log Viewer',
    icon='subject',
    default_slot='bottom',
    opens='on_context',           # Singleton tab; opens on-demand
    description='Streaming log of session events',
)
class LogViewerEditor(BaseEditor):
    """Bottom-slot editor showing a live log of context changes.
    Demonstrates lifecycle, async UI, and AppState consumption."""

    def __init__(self):
        # Local UI state — populated in render()
        self._table: ui.table | None = None
        self._filter_input: ui.input | None = None
        self._filter: str = ''

        # Local view buffer. Capped to avoid unbounded growth.
        self._rows: deque[dict[str, Any]] = deque(maxlen=200)

    # ── Lifecycle ─────────────────────────────────────────────────────

    def render(self, container, context) -> None:
        """Called once when the editor first occupies its slot.
        Build the entire UI subtree here."""
        with container:
            ui.label('Session Event Log').classes('text-md font-bold p-2')

            # Filter bar — typing updates self._filter immediately
            self._filter_input = ui.input(
                placeholder='Filter…',
                on_change=self._on_filter_change,
            ).classes('w-full px-2')

            # Table — rendered with current AppState contents
            self._table = ui.table(
                columns=[
                    {'name': 'time', 'label': 'Time', 'field': 'time'},
                    {'name': 'kind', 'label': 'Kind', 'field': 'kind'},
                    {'name': 'detail', 'label': 'Detail', 'field': 'detail'},
                ],
                rows=[],
                row_key='time',
            ).classes('w-full')

            ui.button('Clear', icon='clear', on_click=self._on_clear).classes('m-2')

        # Initial sync — pull existing entries from AppState
        self._refresh_from_buffer(context)

    def on_focus(self, slot, context) -> None:
        """Called when the bottom slot switches TO this editor.
        Refresh the view to catch up with anything that happened while
        we were inactive."""
        self._refresh_from_buffer(context)

    def on_context_changed(self, event, context) -> None:
        """Append a row for every context change."""
        # Filter by event kind — we only care about a few
        if event.change_type not in (
            ContextChangeType.SELECTION_CHANGED,
            ContextChangeType.GRAPH_LOADED,
            ContextChangeType.DATA_MUTATED,
        ):
            return

        # Append to local view + AppState (for cross-session visibility)
        row = {
            'time': self._now(),
            'kind': event.change_type.name,
            'detail': self._describe(event),
        }
        self._rows.append(row)

        # Push into AppState so other tabs see the same log
        buf = context.app_data[LogBuffer]
        buf.append(row)

        # Re-render if our table is mounted (and we're the active editor)
        if self._table is not None:
            self._sync_table()

    def cleanup(self) -> None:
        """Called when the slot switches to a different editor.
        Drop UI references; nothing async to release in this editor."""
        self._table = None
        self._filter_input = None
        self._rows.clear()

    # ── Local helpers — hb_* prefix would also be valid ────────────────

    def _on_filter_change(self, e):
        self._filter = (e.value or '').lower()
        self._sync_table()

    def _on_clear(self):
        self._rows.clear()
        self._sync_table()

    def _sync_table(self):
        """Apply the filter and update the table rows."""
        if self._table is None:
            return
        if self._filter:
            visible = [r for r in self._rows
                       if self._filter in r['kind'].lower()
                       or self._filter in r['detail'].lower()]
        else:
            visible = list(self._rows)
        self._table.rows = visible
        self._table.update()

    def _refresh_from_buffer(self, context):
        """Pull existing rows from AppState — runs in render() and
        on_focus() to catch up after slot switches."""
        buf = context.app_data[LogBuffer]
        self._rows.clear()
        for row in buf.recent(200):
            self._rows.append(row)
        self._sync_table()

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S.%f')[:-3]

    @staticmethod
    def _describe(event) -> str:
        bits = []
        if hasattr(event, 'node_id') and event.node_id:
            bits.append(f'node={event.node_id}')
        if hasattr(event, 'edge_id') and event.edge_id:
            bits.append(f'edge={event.edge_id}')
        return ' '.join(bits) or '—'
```

What this example exercises:

| Concept | Where |
|---|---|
| `@editor(label, icon, default_slot, opens, description)` decorator | top of class |
| `default_slot='bottom'` with `opens='on_context'` | decorator |
| `BaseEditor` lifecycle: `render`, `on_focus`, `on_context_changed`, `cleanup` | each method |
| Filtering events by `change_type` | `on_context_changed` |
| Reading AppState (`ctx.app_data[LogBuffer]`) | `on_context_changed`, `_refresh_from_buffer` |
| Storing UI element references on `self` for later mutation | `self._table`, `self._filter_input` |
| Local-state separation (`_filter`, `_rows`) from session context | every helper |
| Re-syncing on `on_focus` after slot switches | `on_focus` |
| Releasing references in `cleanup` | `cleanup` |
| `hb_*` / `_*` private helper convention | `_sync_table`, `_on_filter_change` |

For the panels that *might* be hosted inside a panel-aware editor variant of this, see [components/panels](../panels/panel-canon.md). For the AppState `LogBuffer` declaration, see [components/states](../states/state-canon.md).

---

## Quick reference

### Authoring checklist

- [ ] `@editor(label='...', default_slot='...')` — both required
- [ ] Choose `opens='required'` / `'on_context'` / `'on_payload'`
- [ ] Inherit from `BaseEditor`
- [ ] Implement `render(self, container, context)` — build the subtree
- [ ] Implement `on_context_changed(self, event, context)` — react
- [ ] Optional: `on_focus(self, slot, context)` for slot-activation behaviour
- [ ] Optional: `cleanup(self)` if you have async tasks or subscriptions to release
- [ ] Filter `on_context_changed` by `event.change_type` — keep handlers fast

### Imports

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent
```

### Slot rules

| `default_slot` | Valid `opens` values |
|---|---|
| `'left'` | `'required'` only |
| `'right'` | `'required'` only |
| `'main'` | `'required'`, `'on_context'`, `'on_payload'` |
| `'bottom'` | `'required'`, `'on_context'`, `'on_payload'` |
