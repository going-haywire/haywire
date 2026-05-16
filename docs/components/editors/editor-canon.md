---
status: draft
doc_template: canonical-example
scope: Authoring editors — BaseEditor subclass, @editor decorator, draw lifecycle, @redraw_on/@react_on handler decorators, Signal vocabulary, Reveal/Close/BroadcastClose lifecycle commands, OpenBehavior tab modes
see-also:
  - ../panels/panel-canon.md
  - ../states/state-canon.md
  - ../../guides/signals.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Editor — Canonical Example

## 1. What it solves

An **editor** is a self-contained UI module that fills one slot of the studio's workspace layout. As an author, you write a class that inherits from `BaseEditor`, decorate it with `@editor(...)`, implement `draw(context, container)` to build its NiceGUI subtree into a provided container, and optionally decorate handler methods with `@redraw_on(...)` (framework redraws the editor after the handler returns) or `@react_on(...)` (pure side-effect, no auto-redraw) to react to signals on the session bus.

Editors are the primary extension point for adding workspace UI. Once your library's `register_components()` calls `add_folder_to_registry(..., EditorTypeRegistry)`, the editor is auto-discovered and available in any workspace where its `default_slot` is hostable. The studio binds editor instances to slots lazily, one per session.

The lifecycle is: instance is constructed when its wrapper first occupies a slot → the framework auto-subscribes the editor's decorated handler methods to the session's typed signal bus → the framework calls `draw(context, container)` to build the subtree → every published `Signal` whose type matches a decorated handler invokes that handler; for `@redraw_on` handlers the wrapper redraws once after the dispatch pass → `cleanup()` runs when the editor is permanently removed.

The redraw model is *clear-and-redraw*, not incremental. The framework clears the NiceGUI element subtree before each `draw()` call. Editors that need cheaper redraws should keep the panel-mounting work behind a local cache and rebuild only the parts that actually changed; the heavy lifting belongs in panels (which have their own `poll`/`draw` cycle within an editor's container).

## 2. How it fits

```text
@editor(label=..., default_slot=...)    EditorTypeRegistry             AppShell + slot
class MyEditor(BaseEditor):              registers class                instantiates per slot;
    def draw(self, context,              on register_components()       wires bus subscriptions
             container): ...                                             for decorated handlers,
                                                                         calls draw() once,
    @redraw_on(SelectionMoved,                                           then redraws when a
               GraphDataMutated)                                         @redraw_on handler fires.
    def _refresh(self, ctx, signal): ...
```

Editors *host* panels (in panel-aware editors like `PropertiesEditor`) but they don't own panel content — that's [components/panels](../panels/panel-canon.md). Editors don't render themselves into the canvas — that's the studio's job. They render into the NiceGUI `Element` that AppShell hands to `draw()`.

**Boundaries.** What slots are, how the AppShell works, the workspace snapshot system — see [architecture/studio](../../architecture/studio/studio-arch.md). Panels — see [components/panels](../panels/panel-canon.md). Library/session state accessed inside editors (e.g. `EditState` for selection) — see [components/states](../states/state-canon.md). Signal classes (`Signal` base, `CommandSignal` for imperatives) — see `haywire/core/session/signals/`.

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
- **`on_payload`** — per-binding_id tab, on-demand. The binding_id is both the tab's identity and its content source; N distinct payloads → N distinct tabs. Closeable.

**Slot constraints.** `default_slot='left'` and `'right'` only support `opens='required'`. Bars don't have a tab structure to host on-demand or multi-instance editors. The decorator raises `ValueError` at class-definition time if you try.

**`draw(self, context, container)`** is the only abstract method. The framework calls it on first slot assignment and again whenever a `@redraw_on` handler fires. Before each call the framework **clears** `container` — your code starts inside an empty NiceGUI element. Use `with container:` (or store children of one of `container`'s descendants) to build into it.

```python
def draw(self, context: SessionContext, container: Element) -> None:
    with container:
        ui.label('My Editor').classes('text-lg p-4')
        self._content = ui.column().classes('gap-2 p-4')
```

Store references to UI elements you'll later mutate as instance attributes — but remember they live only until the next `draw()` call, since the container is cleared between draws.

**`@redraw_on(*signal_types)`** decorates a handler method. The framework subscribes the method to each listed `Signal` subclass on the per-session signal bus when the editor is instantiated. After every matching dispatch, the framework calls `wrapper.redraw()` for you — exactly once per dispatch pass even if several `@redraw_on` handlers on this editor match the same signal.

```python
@redraw_on(SelectionMoved, ActiveGraphMoved, GraphDataMutated)
def _refresh_on_state_move(self, ctx: SessionContext, signal: Signal) -> None:
    # Empty body is fine — the redraw is the point. Use the body when
    # there's preparatory state to update before draw() re-runs.
    ...
```

Method names are author-chosen; the decorator is the only marker. Multiple `@redraw_on` methods per class are allowed; each declares its own signal-type set. Both `@redraw_on` and `@react_on` fire regardless of whether the editor's wrapper is the active tab — backgrounded editors stay current (kept alive by Quasar `ui.tab_panels` keep-alive), so on focus they're already drawn correctly. `BaseEditor` has no abstract handler method to override; the decorator is the contract.

**`@react_on(*signal_types)`** is the pure side-effect variant. The framework dispatches the matching signal to the handler but does **not** auto-redraw afterwards. The author is responsible for any explicit `wrapper.redraw()`, `wrapper.force_close()`, or `session.publish(Reveal/Close/...)` calls inside the body.

```python
@react_on(HaystackTeardown)
def _close_stale_tabs(self, ctx: SessionContext, signal: HaystackTeardown) -> None:
    for eid in signal.entry_ids:
        ctx.session.publish(Close(binding_id=eid))
```

Use `@react_on` when something must happen on every signal reaching this editor (including from backgrounded tabs) but doesn't warrant a redraw of *this* editor — for example, issuing lifecycle commands, marking caches stale, or persisting state. If both side-effect and redraw are needed, prefer two methods: one `@redraw_on` (empty body, framework redraws) and one `@react_on` (the side effect). Don't trigger redraws from inside a `@react_on` handler unless you know the redraw shouldn't be amortised across the dispatch pass.

Handlers run synchronously on every matching publish; keep them cheap. The heavy lifting belongs in `draw()`, gated by the redraw decision.

**`on_focus(self, context)`** is called when the editor's wrapper becomes the active tab in its slot — on initial render, on programmatic `Slot.switch_to`, on user tab-click, or via `Slot.add_binding(activate=True)`. **Not** called when the user re-clicks the already-active tab. Runs **before** `draw()` on the newly-activated wrapper, so any context mutations this hook performs are visible to that draw and to any signals the hook broadcasts. Default is a no-op. Editors that own a slice of session state (e.g. a graph editor that updates `active_graph` when its tab becomes active) override this. Read `self.wrapper.binding_id` to disambiguate this instance from siblings.

*`GraphEditor` lives in `haybale-graph-editor` and reads its container from `app_data[GraphAppState]`. To host a graph in `GraphEditor`, your library must (a) implement the `GraphContainer` protocol (structurally — a duck-typed match is sufficient) and (b) register every open container into `GraphAppState`. `haybale-haystack`'s `GraphEntry` is the reference implementation.*

**`cleanup(self)`** runs when the editor is permanently removed (slot reassigned, hot-reload eviction). Release subscriptions, cancel timers, drop UI references. Default is a no-op.

**`get_tab_label(self, context) -> str`** lets a tabbed editor (`opens='on_payload'`) return a dynamic label per instance. Default returns `self.class_identity.label`. Multi-instance editors typically derive the label from `self.wrapper.binding_id`.

**`async handle_close_request(self) -> bool`** gates tab close. The slot awaits this when the user clicks the X. Return `True` to allow close, `False` to veto. Editors with unsaved state typically pop a save/discard/cancel dialog and `await` the user's choice. Default returns `True` (always allow). Read `self.wrapper.state.is_dirty` if your editor uses the framework's dirty-state tracking.

**Reading and writing context.** `SessionContext` carries a small set of signal fields (`active_file`, `active_library`, `active_component`, theme keys) and two namespaces:

- `context.app_data[Cls]` — `AppState` lookups, shared across all sessions.
- `context.data[Cls]` — `SessionState` lookups, scoped to this session. Selection state lives here. For the graph canvas, that's `EditState` (in `haybale-studio`):

```python
from haybale_studio.state.edit_state import EditState

node = context.data[EditState].active_node           # NodeWrapper or None
```

See [components/states](../states/state-canon.md) for the full state model.

**Driving other slots — lifecycle commands on the signal bus.** To open or focus a tab in another slot, publish a `Reveal` command on `context.session`:

```python
from haywire.core.session.signals import Reveal

context.session.publish(Reveal(
    editor=LibraryDetailEditor,
    binding_id=library_id,    # for opens='on_payload'
))
```

`Reveal`, `Close`, and `BroadcastClose` are `CommandSignal` payloads — the imperative half of the signal vocabulary. They travel on the same per-session typed bus as observation signals and are emitted with the same `session.publish(...)` call. The AppShell subscribes to each command type and routes it: `Reveal` resolves `editor.class_identity.default_slot` and dispatches to that slot; `Close(binding_id=...)` closes every tab bound to a `binding_id` across all slots in the issuing session.

Lifecycle commands are **local by default** — session-scoped UI actions like `Reveal`-on-click belong to the issuing session. Subclasses can opt into cross-session fan-out by setting `cross_session: ClassVar[bool] = True` (same class-level flag used by `Signal`); `Session.publish(...)` then delegates to `SessionManager.broadcast(...)` so every session's AppShell receives the command. Use this for fact-driven imperatives where the underlying entity is gone for everyone — `BroadcastClose(binding_id=...)` is the built-in: close matching tabs in **every** session.

```python
from haywire.core.session.signals import BroadcastClose

# Underlying entry removed everywhere — close any GraphEditor tab bound
# to it, in this session AND every peer session.
context.session.publish(BroadcastClose(binding_id=entry_id))
```

`BroadcastClose` is a subclass of `Close`. Because the bus matches subscribers by exact type, AppShell subscribes separately to `Close` and `BroadcastClose`, but the close handler is the same and reads the shared `binding_id` field. Prefer `Close` for session-local UI actions; reserve `BroadcastClose` for cases where the close decision follows from a global fact rather than a session-local interaction.

**Imports.**

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior   # for code that inspects the enum
from haywire.core.session.handlers import redraw_on, react_on
from haywire.core.session.signals import (
    Signal,
    SelectionMoved, ActiveGraphMoved, GraphDataMutated,   # observations
    Reveal, Close, BroadcastClose,                        # lifecycle commands
)
```

**Hot-reload.** `EditorTypeRegistry` extends `BaseRegistry`. When an editor class is reloaded, the framework evicts cached instances, calls `cleanup()`, drops the bus subscriptions wired for the decorated handlers, and re-instantiates + `draw()` for any visible bindings. Subscribers that hold a reference to the old class object would see `isinstance()` checks fail spuriously after a reload — this is why library authors who declare their own `Signal` subclasses that other libraries subscribe to must list the declaring library in their own `LibraryIdentity.dependencies`.

## 4. One comprehensive example

The studio's `PropertiesEditor` ([barn/haybale-studio/haybale_studio/editors/properties_editor.py](../../../barn/haybale-studio/haybale_studio/editors/properties_editor.py)) is the validation case for the panel-driven bus subscription model: it has **no** `@redraw_on` / `@react_on` decorators of its own. Instead, the framework unions the `redraw_on=` declarations from every panel registered against the editor's action contract and subscribes the editor's wrapper to that effective set. When any of those signals publishes, the wrapper redraws and the registered panels re-mount with fresh state. The editor *also* subscribes to the panel registry's batch lifecycle channel so it can reconcile its subscriptions when the catalog changes (library install / uninstall / panel hot-reload).

This pattern only applies to host editors with third-party panel content. Most editors decorate their own handler methods directly — see `HaystackEditor` (`@redraw_on(ActiveGraphMoved, GraphDataMutated, HaystackReloaded)` + `@react_on(HaystackTeardown)`) or `LibraryComponentEditor` (`@redraw_on(SessionContext.active_component, SelectionMoved, SessionContext.active_workbench_theme_key)`).

The salient excerpts:

```python
--8<-- "barn/haybale-studio/haybale_studio/editors/properties_editor.py:editor_example"
```

_rebuild_toolbar / _rebuild_content omitted for brevity — see source.

What this example exercises:

| Concept | Where |
|---|---|
| `@editor(label, icon, default_slot='right', description)` — implicit `opens='required'` | top of class |
| `class_identity` and `class_library` set automatically by the decorator | (set on the class object) |
| Per-instance state initialised in `__init__`, persisted across redraws | `_active_focus_id`, `_expansion_state` |
| `draw(context, container)` builds the subtree; container starts cleared | `draw` |
| Panel-driven bus subscriptions: editor unions registered panels' `redraw_on=` and subscribes the wrapper to the effective set | `_subscribe_panel_event_handlers` |
| Reconciling subscriptions on catalog mutation (library install / uninstall / hot-reload) | `_on_panel_registry_event` |
| Pulling DI dependencies from `context.app` on first draw | `context.app.library_service.get_panel_registry()` |
| Reading `SessionState` (selection lives on `EditState`, not `SessionContext`) | `clear_selection` |
| Editor-as-actions-provider: panels call back into the editor | `clear_selection` (Protocol implementation) |
| Hosting panels via `PanelRegistry.get_panels_for(actions_provider, focus)` | `_rebuild_content` (full source) |
| Per-instance UI references (`_toolbar`, `_content`) re-fetched on each `draw` | layout fields |

For the `Focus` and `Panel` extension points the editor hosts, see [components/panels](../panels/panel-canon.md). For the `EditState` reactive state model, see [components/states](../states/state-canon.md). For the bus and the AppShell that subscribes to lifecycle commands, see [architecture/studio](../../architecture/studio/studio-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] `@editor(label='...', default_slot='...')` — both have sensible defaults; set them deliberately
- [ ] Choose `opens='required'` / `'on_context'` / `'on_payload'`
- [ ] Inherit from `BaseEditor`; implement `draw(self, context, container)` — required
- [ ] Decorate handler methods with `@redraw_on(*SignalTypes)` for signals that warrant a full editor redraw — empty body is fine; the framework redraws once per dispatch pass
- [ ] Decorate handler methods with `@react_on(*SignalTypes)` for pure side effects — no auto-redraw; the body owns any explicit `wrapper.redraw()` / `session.publish(Reveal/Close/...)` calls
- [ ] Initialise instance state in `__init__`; container/UI refs re-fetched in `draw()`
- [ ] Optional: `on_focus(self, context)` — runs *before* `draw()` on the newly-activated wrapper
- [ ] Optional: `cleanup(self)` — release subscriptions / timers (the framework drops decorated-handler subscriptions automatically)
- [ ] Optional: `get_tab_label(self, context)` — dynamic per-binding_id label
- [ ] Optional: `async handle_close_request(self)` — veto/save dialog before tab close
- [ ] Drive other slots with `context.session.publish(Reveal(editor=..., binding_id=...))`
- [ ] Use `BroadcastClose(binding_id=...)` instead of `Close(binding_id=...)` when the underlying entity is gone for every session, not just yours

### Imports

```python
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import OpenBehavior
from haywire.core.session.handlers import redraw_on, react_on
from haywire.core.session.signals import (
    Signal,
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
