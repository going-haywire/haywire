---
status: draft
doc_template: canonical-example
scope: Authoring editors — BaseEditor subclass, @editor decorator, on_signal/redraw_on_signal/draw lifecycle, ContextSignal filtering, Reveal/Close/BroadcastClose lifecycle commands, OpenBehavior tab modes
see-also:
  - ../panels/panel-canon.md
  - ../states/state-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Editor — Canonical Example

## 1. What it solves

An **editor** is a self-contained UI module that fills one slot of the studio's workspace layout. As an author, you write a class that inherits from `BaseEditor`, decorate it with `@editor(...)`, implement `draw(context, container)` to build its NiceGUI subtree into a provided container, and optionally implement `redraw_on_signal(context, signal) -> bool` to request a redraw when relevant state moves and/or `on_signal(context, signal)` to run side effects regardless of whether this editor is the active tab.

Editors are the primary extension point for adding workspace UI. Once your library's `register_components()` calls `add_folder_to_registry(..., EditorTypeRegistry)`, the editor is auto-discovered and available in any workspace where its `default_slot` is hostable. The studio binds editor instances to slots lazily, one per session.

The lifecycle is: instance is constructed when its wrapper first occupies a slot → the orchestrator calls `draw(context, container)` to build the subtree → on every `ContextSignal` the orchestrator calls `on_signal(context, signal)` on **every** wrapper in the slot (active or not), then calls `redraw_on_signal(context, signal)` only on the **active** wrapper; if that returns `True`, the orchestrator clears the container and calls `draw()` again → `cleanup()` runs when the editor is permanently removed.

The redraw model is *clear-and-redraw*, not incremental. The orchestrator clears the NiceGUI element subtree before each `draw()` call. Editors that need cheaper redraws should keep the panel-mounting work behind a local cache and rebuild only the parts that actually changed; the heavy lifting belongs in panels (which have their own `poll`/`draw` cycle within an editor's container).

## 2. How it fits

```text
@editor(label=..., default_slot=...)    EditorTypeRegistry             AppShell + slot
class MyEditor(BaseEditor):              registers class                instantiates per slot;
    def draw(self, context,              on register_components()       calls draw() once,
             container): ...                                             then on_signal() on
    def on_signal(self, context,                                         every wrapper +
                  signal): ...                                           redraw_on_signal()
    def redraw_on_signal(self, context,                                  on the active one,
                         signal) -> bool: ...                            redrawing if True.
```

Editors *host* panels (in panel-aware editors like `PropertiesEditor`) but they don't own panel content — that's [components/panels](../panels/panel-canon.md). Editors don't render themselves into the canvas — that's the studio's job. They render into the NiceGUI `Element` that AppShell hands to `draw()`.

**Boundaries.** What slots are, how the AppShell works, the workspace snapshot system — see [architecture/studio](../../architecture/studio/studio-arch.md). Panels — see [components/panels](../panels/panel-canon.md). Library/session state accessed inside editors (e.g. `EditState` for selection) — see [components/states](../states/state-canon.md). Signal classes and lifecycle commands — see `haywire/ui/context_signals.py`.

## 3. Important concepts

**The `@editor` decorator.** Required on every editor class. Sets `class_identity` (an `EditorIdentity` dataclass) and `class_library` (derived from the module). Computes `registry_key` as `<library_id>:editor:<registry_id>`.

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `label` | no | class name | Display name in tabs and tooltips |
| `default_slot` | no | `'main'` | `'left'` / `'right'` / `'main'` / `'bottom'` |
| `icon` | no | `'extension'` | Material Design icon name |
| `opens` | no | `'required'` | `'required'` / `'on_context'` / `'on_payload'` — see below |
| `description` | no | `''` | Tooltip / accessibility text |
| `registry_id` | no | class name | Unique short ID within the library |

`@editor()` must be invoked with parentheses; the bare `@editor` form raises at class-definition time.

**`OpenBehavior` — how tabs come into being.** Three values:

- **`required`** — the shell guarantees exactly one auto-populated tab at startup. Uncloseable. Use for persistent panels: side editors, the main graph editor.
- **`on_context`** — singleton tab, on-demand. Content mirrors a slice of session context (e.g. `active_library`); a `Reveal` lifecycle command opens it. Closeable.
- **`on_payload`** — per-payload tab, on-demand. The payload is both the tab's identity and its content source; N distinct payloads → N distinct tabs. Closeable.

**Slot constraints.** `default_slot='left'` and `'right'` only support `opens='required'`. Bars don't have a tab structure to host on-demand or multi-instance editors. The decorator raises `ValueError` at class-definition time if you try.

**`draw(self, context, container)`** is the only abstract method. The orchestrator calls it on first slot assignment and again whenever `redraw_on_signal()` returns `True`. Before each call the orchestrator **clears** `container` — your code starts inside an empty NiceGUI element. Use `with container:` (or store children of one of `container`'s descendants) to build into it.

```python
def draw(self, context: SessionContext, container: Element) -> None:
    with container:
        ui.label('My Editor').classes('text-lg p-4')
        self._content = ui.column().classes('gap-2 p-4')
```

Store references to UI elements you'll later mutate as instance attributes — but remember they live only until the next `draw()` call, since the container is cleared between draws.

**`redraw_on_signal(self, context, signal) -> bool`** decides whether the editor needs a full redraw. Default returns `False` (never redraw). Fires only on the **active** wrapper in the slot — backgrounded wrappers can't be redrawn into a hidden panel meaningfully, so they catch up on `on_focus`. Filter by signal class with plain `isinstance`:

```python
_RELEVANT_SIGNALS = (SelectionMoved, ActiveGraphMoved, GraphDataMutated)

def redraw_on_signal(self, context: SessionContext, signal: ContextSignal) -> bool:
    return isinstance(signal, self._RELEVANT_SIGNALS)
```

`redraw_on_signal()` runs synchronously on every signal delivered to the active wrapper. Keep it cheap — no I/O, no AppState walks, no expensive predicates. A typical implementation is a tuple of relevant signal types and a single `isinstance` check. **Do not run side effects here** — it's a pure decision function. Side effects belong in `on_signal`.

**`on_signal(self, context, signal) -> None`** is the side-effect channel. It fires on **every** wrapper in the slot regardless of active state — including backgrounded tabs. Default is a no-op. Use it when something must happen even while the editor isn't visible:

- closing tabs in response to an entity removal (e.g. a HaystackEditor responding to a teardown signal by issuing local `Close(payload=...)` lifecycle commands);
- marking the editor stale so the next `on_focus`/`draw` re-reads underlying state;
- clearing in-memory caches.

```python
def on_signal(self, context: SessionContext, signal: ContextSignal) -> None:
    if isinstance(signal, MyTeardownSignal):
        for eid in signal.entry_ids:
            context.session.lifecycle(Close(payload=eid))
```

`on_signal` runs for every signal on every wrapper, so it's on the hot path in the same way `redraw_on_signal` is — keep it cheap and side-effect-only. Don't trigger redraws from here; if a redraw is also warranted, return `True` from `redraw_on_signal` (which fires only on the active wrapper, where redraws are meaningful).

**`on_focus(self, context)`** is called when the editor's wrapper becomes the active tab in its slot — on initial render, on programmatic `Slot.switch_to`, on user tab-click, or via `Slot.add_binding(activate=True)`. **Not** called when the user re-clicks the already-active tab. Runs **before** `draw()` on the newly-activated wrapper, so any context mutations this hook performs are visible to that draw and to any signals the hook broadcasts. Default is a no-op. Editors that own a slice of session state (e.g. a graph editor that updates `active_graph` when its tab becomes active) override this. Read `self.wrapper.payload` to disambiguate this instance from siblings.

**`cleanup(self)`** runs when the editor is permanently removed (slot reassigned, hot-reload eviction). Release subscriptions, cancel timers, drop UI references. Default is a no-op.

**`get_tab_label(self, context) -> str`** lets a tabbed editor (`opens='on_payload'`) return a dynamic label per instance. Default returns `self.class_identity.label`. Multi-instance editors typically derive the label from `self.wrapper.payload`.

**`async handle_close_request(self) -> bool`** gates tab close. The slot awaits this when the user clicks the X. Return `True` to allow close, `False` to veto. Editors with unsaved state typically pop a save/discard/cancel dialog and `await` the user's choice. Default returns `True` (always allow). Read `self.wrapper.state.is_dirty` if your editor uses the framework's dirty-state tracking.

**Reading and writing context.** `SessionContext` carries a small set of reactive fields (`active_file`, `active_library`, `active_component`, theme keys) and two namespaces:

- `context.app_data[Cls]` — `AppState` lookups, shared across all sessions.
- `context.data[Cls]` — `SessionState` lookups, scoped to this session. Selection state lives here. For the graph canvas, that's `EditState` (in `haybale-studio`):

```python
from haybale_studio.state.edit_state import EditState

node = context.data[EditState].active_node.value     # NodeWrapper or None
```

See [components/states](../states/state-canon.md) for the full state model.

**Driving other slots — the lifecycle channel.** To open or focus a tab in another slot, send a `Reveal` lifecycle command on `context.session`:

```python
from haywire.ui.context_signals import Reveal

context.session.lifecycle(Reveal(
    editor=LibraryDetailEditor,
    payload=library_id,    # for opens='on_payload'
))
```

The orchestrator resolves `editor.class_identity.default_slot` and routes the command. Use `Close(payload=...)` to close every tab bound to a payload across all slots in the issuing session (e.g. a session-local "discard" action).

Lifecycle commands are **local by default** — session-scoped UI actions like `Reveal`-on-click belong to the issuing session. Subclasses can opt into cross-session fan-out by setting `cross_session: ClassVar[bool] = True` (mirroring `ContextSignal`); `Session.lifecycle()` checks the class flag and routes via `SessionManager.broadcast_lifecycle` so every session's AppShell receives the command. Use this for fact-driven imperatives where the underlying entity is gone for everyone — `BroadcastClose(payload=...)` is the built-in: close matching tabs in **every** session.

```python
from haywire.ui.context_signals import BroadcastClose

# Underlying entry removed everywhere — close any GraphEditor tab bound
# to it, in this session AND every peer session.
context.session.lifecycle(BroadcastClose(payload=entry_id))
```

`BroadcastClose` is a subclass of `Close`, so AppShell's `_close_payload` handles it identically — the only difference is dispatch scope. Prefer `Close` for session-local UI actions; reserve `BroadcastClose` for cases where the close decision follows from a global fact rather than a session-local interaction.

**Imports.**

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior   # for code that inspects the enum
from haywire.ui.context_signals import (
    ContextSignal,
    SelectionMoved, ActiveGraphMoved, GraphDataMutated,   # observations
    Reveal, Close, BroadcastClose,                        # lifecycle commands
)
```

`context_signals` is the unified module — earlier code referenced `context_events`; that name was retired.

**Hot-reload.** `EditorTypeRegistry` extends `BaseRegistry`. When an editor class is reloaded, the orchestrator evicts cached instances, calls `cleanup()`, and re-instantiates + `draw()` for any visible bindings. Subscribers that hold a reference to the old class object would see `isinstance()` checks fail spuriously after a reload — this is why library authors who declare their own signal classes that other libraries subscribe to must list the signal-declaring library in their own `LibraryIdentity.dependencies`.

## 4. One comprehensive example

The studio's `PropertiesEditor` ([barn/haybale-studio/haybale_studio/editors/properties_editor.py](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py)) exercises every authoring concept: `default_slot='right'` with implicit `opens='required'`, `isinstance`-based signal filtering, a two-column `draw()` layout, panel-hosting via `PanelRegistry.get_panels_for(actions_provider, focus)`, an action protocol that panels call back into (`clear_selection`), reading `EditState` from `context.data`, and per-instance state preserved across redraws.

The salient excerpts:

```python
# barn/haybale-studio/haybale_studio/editors/properties_editor.py

from nicegui import ui

from haybale_studio.state.edit_state import EditState
from haywire.ui import elements as hui
from haywire.ui.context_signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.focus import Focus, focus_by_id
from haywire.ui.panel.registry import PanelRegistry


@editor(
    label="Properties",
    icon=hui.icon.node_settings,
    default_slot="right",
    description="Context-sensitive property panels for the active selection.",
)
class PropertiesEditor(BaseEditor):
    """Focus-driven properties editor: focus toolbar + panel content."""

    # Tuple of signal types this editor reacts to. Anything else: redraw_on_signal() returns False.
    _RELEVANT_SIGNALS = (SelectionMoved, ActiveGraphMoved, GraphDataMutated)

    # Per-instance state — survives across redraws because the editor instance
    # is reused; the *container* is cleared by the orchestrator, the Python
    # object is not. Initialise in __init__, never in draw().
    def __init__(self, panel_registry: PanelRegistry | None = None) -> None:
        self._container: Element | None = None
        self._toolbar: Element | None = None
        self._content: Element | None = None
        self._panel_registry = panel_registry
        self._context: SessionContext | None = None
        self._active_focus_id: str | None = None
        self._expansion_state: dict[str, bool] = {}

    # --- BaseEditor lifecycle ---------------------------------------------

    def redraw_on_signal(self, context: SessionContext, signal: ContextSignal) -> bool:
        # Cheap predicate. Runs on every signal delivered to the active wrapper.
        return isinstance(signal, self._RELEVANT_SIGNALS)

    def draw(self, context: SessionContext, container: Element) -> None:
        # Container is empty when draw() starts — the orchestrator cleared it.
        self._container = container
        self._context = context
        if self._panel_registry is None:
            # Pull the registry from DI on first draw. Tests inject directly.
            self._panel_registry = context.app.library_service.get_panel_registry()
        self._build_layout(context)

    # --- Action protocol — called BACK INTO this editor by panels --------

    def clear_selection(self) -> None:
        """Implements PropertiesEditorActions; panels call self.actions.clear_selection()."""
        if self._context is None:
            return
        edit_state = self._context.data[EditState]
        edit_state.active_node.value = None
        edit_state.active_edge.value = None
        edit_state.active_port.value = None

    # --- Layout construction (called once per draw) ----------------------

    def _build_layout(self, context: SessionContext) -> None:
        with self._container:
            with ui.row().classes("w-full h-full gap-0"):
                self._toolbar = ui.column().classes("gap-0").style(
                    "width: 36px; min-width: 36px; overflow-y: auto;"
                )
                self._content = ui.column().classes("flex-1 gap-0")
        self._refresh(context)

    def _refresh(self, context: SessionContext) -> None:
        # Toolbar and content are rebuilt together — this is the editor's
        # internal "redraw" hook, called after structural changes (active
        # focus moved). Container-level redraw is the orchestrator's job.
        self._rebuild_toolbar(context)
        self._rebuild_content(context)

    # _rebuild_toolbar / _rebuild_content omitted for brevity — see source.
```

What this example exercises:

| Concept | Where |
|---|---|
| `@editor(label, icon, default_slot='right', description)` — implicit `opens='required'` | top of class |
| `class_identity` and `class_library` set automatically by the decorator | (set on the class object) |
| Per-instance state initialised in `__init__`, persisted across redraws | `_active_focus_id`, `_expansion_state` |
| Tuple of `ContextSignal` classes for cheap `isinstance` filtering | `_RELEVANT_SIGNALS` |
| `redraw_on_signal(context, signal) -> bool` returns `True` to request redraw (active wrapper only) | `redraw_on_signal` |
| `draw(context, container)` builds the subtree; container starts cleared | `draw` |
| Pulling DI dependencies from `context.app` on first draw | `context.app.library_service.get_panel_registry()` |
| Reading `SessionState` (selection lives on `EditState`, not `SessionContext`) | `clear_selection` |
| Editor-as-actions-provider: panels call back into the editor | `clear_selection` (Protocol implementation) |
| Hosting panels via `PanelRegistry.get_panels_for(actions_provider, focus)` | `_rebuild_content` (full source) |
| Per-instance UI references (`_toolbar`, `_content`) re-fetched on each `draw` | layout fields |

For the `Focus` and `Panel` extension points the editor hosts, see [components/panels](../panels/panel-canon.md). For the `EditState` reactive state model, see [components/states](../states/state-canon.md). For the orchestrator that owns slots and routes signals, see [architecture/studio](../../architecture/studio/studio-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] `@editor(label='...', default_slot='...')` — both have sensible defaults; set them deliberately
- [ ] Choose `opens='required'` / `'on_context'` / `'on_payload'`
- [ ] Inherit from `BaseEditor`; implement `draw(self, context, container)` — required
- [ ] Override `redraw_on_signal(self, context, signal) -> bool` — default `False`; return `True` for signals that warrant a redraw of the active wrapper
- [ ] Override `on_signal(self, context, signal) -> None` only when you need side effects that must run while the editor is backgrounded (e.g. closing tabs in response to a teardown signal)
- [ ] Initialise instance state in `__init__`; container/UI refs re-fetched in `draw()`
- [ ] Use a tuple of `ContextSignal` classes + one `isinstance` for cheap `redraw_on_signal()` filtering
- [ ] Optional: `on_focus(self, context)` — runs *before* `draw()` on the newly-activated wrapper
- [ ] Optional: `cleanup(self)` — release subscriptions / timers
- [ ] Optional: `get_tab_label(self, context)` — dynamic per-payload label
- [ ] Optional: `async handle_close_request(self)` — veto/save dialog before tab close
- [ ] Drive other slots with `context.session.lifecycle(Reveal(editor=..., payload=...))`
- [ ] Use `BroadcastClose(payload=...)` instead of `Close(payload=...)` when the underlying entity is gone for every session, not just yours

### Imports

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior
from haywire.ui.context_signals import (
    ContextSignal,
    SelectionMoved, ActiveGraphMoved, GraphDataMutated,
    Reveal, Close, BroadcastClose,
)
```

### Slot rules

| `default_slot` | Valid `opens` values |
|---|---|
| `'left'` | `'required'` only |
| `'right'` | `'required'` only |
| `'main'` | `'required'`, `'on_context'`, `'on_payload'` |
| `'bottom'` | `'required'`, `'on_context'`, `'on_payload'` |
