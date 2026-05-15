---
status: draft
doc_template: system-reference
scope: The studio as a product — AppShell, slots, sessions, signal/lifecycle channels, editor/panel hosting
see-also:
  - app-shell/app-shell-arch.md
  - workspace/workspace-arch.md
  - canvas/canvas-arch.md
  - rendering/rendering-arch.md
  - ../session-and-state/session-and-state-arch.md
  - ../../components/editors/editor-canon.md
  - ../../components/panels/panel-canon.md
  - ../../reference/glossary.md
---

# Studio — Architecture

## 1. Overview

The studio is the haywire UI as a product. It is modelled after the workspace paradigms of **Blender** and **VS Code**: a flexible, area-based layout where each region hosts a different *editor*, the layout is persisted per project as a JSON snapshot, and every UI decision is driven by a shared `SessionContext` plus library-owned `SessionState` rather than hard-wired component-to-component communication.

Three design goals shape every decision in this layer:

- **Session isolation** — each browser tab is a fully independent session with its own selection state, interaction mode, editor instances, and library-owned reactive state. Multiple users can connect to the same running haywire server simultaneously without interfering.
- **Pub/sub decoupling** — editors, panels, and the shell do not talk to each other directly. Every interaction flows as a `Signal` published on a per-session typed bus: observations (concrete `Signal` subclasses like `SelectionMoved`, `GraphDataMutated`) describe state moves; imperatives (`CommandSignal` subclasses like `Reveal`, `Close`) request workspace-tree mutations. Authors emit with `Session.publish(...)` and subscribe with `Session.subscribe(SignalType, handler)` (or via the `@redraw_on` / `@react_on` decorators on editor methods). Cross-session synchronisation is opt-in per signal class.
- **Open extensibility** — both editors and panels are registered via DI-managed registries (`EditorTypeRegistry`, `PanelRegistry`). A library can ship its own editors, panels, and `Focus` classes that are auto-discovered and inserted into the UI, following the same two-stage decorator + folder-scan pattern used by nodes, widgets, and themes.

## 2. Components

### 2.1 The layout model — slots and bars

A studio session is a single-page workspace with four named **slots** arranged around a fixed-chrome `TopBar` and `StatusBar`:

| Slot | Class | Layout | Hosts |
|---|---|---|---|
| **Left** | `IconSlot` | Vertical icon bar + content area (drag-resizable width) | One `opens='required'` editor visible at a time, switched by clicking icons |
| **Right** | `IconSlot` | Vertical icon bar + content area (drag-resizable width) | One `opens='required'` editor visible at a time, switched by clicking icons |
| **Main** | `TabSlot` | Horizontal tab bar + content area (fills remaining space) | Multiple tabbed editors, supports `required` / `on_context` / `on_payload` |
| **Bottom** | `TabSlot` | Horizontal tab bar + content area (drag-resizable height; foldable) | Multiple tabbed editors, supports all `OpenBehavior` modes |

Each slot is a concrete subclass of `Slot` (`packages/haywire-core/src/haywire/ui/app/slot.py`):
- `IconSlot` — uses an `IconSlotBar` with vertical icon buttons; only one binding is visible at a time and the bar acts as the selector. Only `opens='required'` editors are valid here (enforced by the `@editor` decorator at class-definition time).
- `TabSlot` — uses a `TabSlotBar` with horizontal tab headers; multiple bindings can coexist; the user picks which is in front.

Slots own:

- their list of `EditorWrapper` bindings (`self._bindings`),
- the currently active wrapper (`self._active`),
- the NiceGUI area container that hosts the active wrapper's UI subtree,
- visibility state and the divider that resizes them.

The `AppShell` (`packages/haywire-core/src/haywire/ui/app/shell.py`) is the layout container that hosts the four slots, builds the resizable dividers between areas, and subscribes to `Reveal` / `Close` / `BroadcastClose` lifecycle commands on the session signal bus — `Reveal` is dispatched point-to-point to the editor's `default_slot`; `Close` (and `BroadcastClose`) fan out across every slot. `AppShell` is constructed once per browser session.

### 2.2 Workspaces

A **workspace snapshot** is a plain JSON dict — one key per slot name — persisted to `.haywire/workspace_state.json` per project. (Earlier versions also stored a `"haystack"` key naming the active haystack TOML; that responsibility moved to `HaystackSettings.last_haystack_name` in the haybale-haystack library.) The `WorkspaceManager` (`packages/haywire-core/src/haywire/core/session/workspace/manager.py`) is intentionally dumb:

- `WorkspaceManager.snapshot: dict` — the raw dict loaded from disk, or `{}` if the file is missing or unparseable.
- `WorkspaceManager.save(snapshot)` — write the dict to disk and update `self.snapshot`.

The structure of each slot's sub-dict is defined and interpreted by the slot classes themselves. `WorkspaceManager` knows nothing about editors, `OpenBehavior`, or active tabs. Slots produce a snapshot when asked and consume one when restoring (`Slot.populate_from_snapshot`).

There is no named-preset system in the current implementation. The workspace state is a single snapshot per project; multi-preset support is future work.

### 2.3 Sessions

A `Session` (`packages/haywire-core/src/haywire/core/session/session.py`) represents one connected browser tab. Each session owns:

- A `SessionContext` (per-session reactive state — see §2.4).
- A `WorkspaceManager` (the project's layout snapshot).
- Editor instances (cached per `EditorWrapper`; the slot owns the wrapper, the wrapper owns the instance).
- A per-session `SignalBus` instance — the only intra-session dispatch channel. Editors auto-subscribe their `@redraw_on` / `@react_on` decorated methods at instantiation; the AppShell subscribes its workspace-mutation handlers directly.

Sessions are created and tracked by `SessionManager` (`packages/haywire-core/src/haywire/core/session/session_manager.py`). When a browser connects, `SessionManager.create_session(...)` constructs the `Session`, attaches its `session_id` to the global `LibraryStateContainer` (which fan-instantiates every registered `SessionState` class for the new session), and returns it. `SessionManager.remove_session(session_id)` reverses the dance: `Session.cleanup()` first, then `LibraryStateContainer.detach_session(...)`. Cleanup-before-detach is deliberate so editors that read `ctx.data[X]` during their own cleanup still see live state.

```python
manager = SessionManager(container=app.library_state_container)
session = manager.create_session(project_state=app, workspace_manager=ws)
manager.broadcast(some_signal)
manager.remove_session(session.session_id)
```

### 2.4 SessionContext

`SessionContext` (`packages/haywire-core/src/haywire/core/session/context.py`) is the small per-session reactive object visible to every editor and panel. Its surface is intentionally narrow:

| Attribute | Kind | Purpose |
|---|---|---|
| `session_id` | plain | UUID of this session |
| `app` | plain | The shared project state (graph data, settings, registries) |
| `session` | plain | Back-reference to the owning `Session` |
| `app_data` | plain | Typed proxy over the global `LibraryStateContainer` for `AppState` lookups (shared across all sessions) |
| `data` | plain | Typed proxy over the same container for `SessionState` lookups (scoped to *this* session) |
| `active_file` | signal field | The currently-active project file |
| `active_library` | signal field | The currently-selected library (in the Library Browser) |
| `active_component` | signal field | The currently-selected library component |
| `active_workbench_theme_key` | signal field | The active workbench theme |
| `active_node_theme_key` | signal field | The active node theme |

Editor-specific reactive state — selection, clipboard, the active graph — does **not** live on `SessionContext`. It lives on a library-owned `SessionState` class. For the graph canvas, that state is `EditState` (`barn/haybale-studio/haybale_studio/state/edit_state.py`), accessed via `ctx.data[EditState]`:

```python
edit = ctx.data[EditState]
node = edit.active_node          # NodeWrapper or None
selected = edit.selected_nodes   # set[str] of node IDs
edit.active_node = my_wrapper    # writes emit a signal
```

This separation keeps the framework's `SessionContext` stable while each library owns the reactive surface its editors need. See [components/states](../../components/states/state-canon.md) for the full state model and [session-and-state](../session-and-state/session-and-state-arch.md) for the container's two-namespace asymmetry.

### 2.5 The signal bus — observations and imperatives on one channel

The studio runs a single per-session typed pub/sub bus (`packages/haywire-core/src/haywire/core/session/signals/bus.py`). Every payload subclasses `Signal` from `packages/haywire-core/src/haywire/core/session/signals/`. Authors emit with `Session.publish(s)` and listen with `Session.subscribe(SignalType, handler)`. Subscribers match by exact type — subclasses do not inherit subscriptions.

Two payload flavours share the bus; the split is vocabulary, not transport:

**Observations (concrete `Signal` subclasses).** Describe a state move that already happened. Concrete subclasses include:

- **Workbench / focus** — synthetic signals on `SessionContext`: `SessionContext.active_file`, `SessionContext.active_library`, `SessionContext.active_component`. Each is the field reference itself, which subscribers use directly as a subscription key. Plus the hand-authored `ActiveGraphMoved` (per-graph change beyond the simple field-write semantics).
- **Selection** — `SelectionMoved`.
- **Data + lifecycle** — `GraphDataMutated`, `LibraryCatalogChanged`.
- **Theme** — synthetic signals `SessionContext.active_workbench_theme_key`, `SessionContext.active_node_theme_key`.

Editors and panels declare interest via `@redraw_on(...)` / `@react_on(...)` on decorated methods, or via the `redraw_on=` keyword on `@panel(...)`; the framework wires the corresponding bus subscriptions at editor instantiation.

**Imperatives (`CommandSignal`).** Describe workspace-tree mutations. By convention there's one subscriber per command type — the AppShell — but the bus does not enforce that.

- `Reveal(editor=Cls, binding_id=..., label=...)` — bring an editor to the front. The AppShell handler resolves `editor.class_identity.default_slot` and routes to that slot. If the slot is not hostable in the active workspace, the reveal is dropped with a warning. `binding_id` disambiguates multi-instance editors (`opens='on_payload'`).
- `Close(binding_id=...)` — close every tab bound to `binding_id` across all slots in the issuing session. Used for session-local close decisions.
- `BroadcastClose(binding_id=...)` — cross-session sibling of `Close`. Each receiving session's AppShell closes matching tabs. Used when the underlying entity is gone for everyone (e.g. a graph entry was removed from the haystack).

**Cross-session routing.** Independent of observation/imperative: set `cross_session: ClassVar[bool] = True` on any `Signal` subclass and `Session.publish(...)` delegates to `SessionManager.broadcast(...)`, which fans out to every session (including the origin). Among the built-ins, `GraphDataMutated`, `LibraryCatalogChanged`, and `BroadcastClose` are cross-session; everything else is local-only.

Library authors who declare their own `Signal` subclasses that other libraries subscribe to **must** list the declaring library in their own `LibraryIdentity.dependencies`, so hot-reload reloads them as a pair. Without this, an `isinstance` check after a library reload can spuriously return `False` when the subscriber holds a stale class reference.

### 2.6 Editors and panels

Editors fill slots; panels fill the inside of panel-aware editors. Both register via DI registries:

- `EditorTypeRegistry` — `BaseEditor` subclasses, decorated with `@editor(...)`. Registered by libraries via `add_folder_to_registry(folder_path=..., registry_cls=EditorTypeRegistry)` in `register_components()`. Built-in framework editors (currently none — all editors live in `haybale-studio` or other libraries) would bootstrap via `register_builtin_editors()`.
- `PanelRegistry` — `BasePanel` subclasses, decorated with `@panel(action=..., focus=...)`. Registered the same way. Panel-aware editors (e.g. `PropertiesEditor`) call `panel_registry.get_panels_for(actions_provider=self, focus=...)`, which filters panels by structural `isinstance(actions_provider, action)` and by `Focus.id` match.

For the editor authoring surface — `BaseEditor`, `draw`, the `@redraw_on` / `@react_on` handler decorators, `OpenBehavior` modes, slot constraints — see [components/editors](../../components/editors/editor-canon.md). For the panel surface — `@panel`, `Focus` classes, `PanelLayout` — see [components/panels](../../components/panels/panel-canon.md).

## 3. Data flow

### 3.1 Page render at session connect

```text
Browser opens NiceGUI page
  ├─ studio app.py page handler
  ├─ SessionManager.create_session(project_state=app, workspace_manager=ws)
  │   ├─ Session() — constructs SessionContext + per-session SignalBus, registers session_id
  │   └─ container.attach_session(session_id) — fan-instantiates SessionStates
  ├─ AppShell(session, editor_registry)
  └─ shell.render()
      ├─ subscribe Reveal / Close / BroadcastClose on session.subscribe(...)
      ├─ build TopBar / StatusBar
      ├─ instantiate four slots (left/right IconSlot, main/bottom TabSlot)
      ├─ each slot.populate_from_snapshot(workspace_manager.snapshot[slot_name])
      │   └─ each EditorWrapper wires its editor's @redraw_on / @react_on
      │      handlers as session.subscribe(...) closures
      ├─ each slot.render(parent) — builds area container, calls draw() on active wrapper
      └─ install drag-resize handles between areas
```

### 3.2 User interaction → signal propagation

```text
User clicks a node in the graph canvas
  ├─ GraphEditor handler:  ctx.data[EditState].active_node = wrapper
  ├─ GraphEditor handler:  session.publish(SelectionMoved())
  └─ Session.publish — local-only path (cross_session=False):
      └─ SignalBus.publish(signal)
          └─ for handler in subscribers of type(signal), in registration order:
              ├─ wrapper closures wired from @redraw_on / @react_on
              │     • @redraw_on:  handler(ctx, signal) → flag wrapper for redraw
              │     • @react_on:   handler(ctx, signal) → side effect only
              └─ after dispatch: each flagged wrapper calls wrapper.redraw()
                 exactly once (slot clears area, calls editor.draw(ctx, area))
```

The `SelectionMoved` signal carries no payload (pointer-by-default rule, §6.3 of the design doc). Subscribers re-read `ctx.data[EditState]` to discover what the new selection is. Both `@redraw_on` and `@react_on` handlers fire regardless of whether their editor's wrapper is the active tab — backgrounded editors stay current (kept alive by Quasar `ui.tab_panels` keep-alive); on focus they're already drawn correctly.

### 3.3 Cross-session broadcast (graph mutation)

```text
Session A: user edits a node's setting
  ├─ NodeWrapper.update_setting(...)
  ├─ session.publish(GraphDataMutated())
  └─ Session.publish — cross_session=True path:
      └─ session_manager.broadcast(signal)
          └─ For every session (A, B, C):
              └─ session._dispatch(signal) → SignalBus.publish → subscribers
```

Cross-session signals never carry payload data either. Receivers re-read the relevant state from the shared project — for `GraphDataMutated` that's the entry in `ctx.app_data[HaystackState].get_by_id(<entry_id>)`. Peer-session state, if needed, can be reached through `session_manager.get_session(peer_id).context`.

## 4. Performance, errors, and boundaries

### 4.1 Per-session memory

Each session holds editor instances, slots, a `WorkspaceManager`, and a `SessionContext` plus the per-session `SessionState` instances. For a typical workspace with four active editors, that's tens of KBs per session — comfortably scalable to dozens of concurrent connections on a single server.

### 4.2 Dispatch cost

The typed bus dispatches by exact signal class: a publish of `SelectionMoved` only runs the handlers explicitly subscribed to `SelectionMoved`. Cost is `O(subscribers for type(signal))` plus the cost of each handler body. Editors that decorate their methods with `@redraw_on` / `@react_on` declare interest at the class level, so the framework auto-subscribes exactly once per editor instance — no broadcast-and-filter fan-out, no per-wrapper `isinstance` chain.

The contract is: *handlers are cheap; the heavy work goes in `draw()`, gated by `@redraw_on` (framework redraws once per dispatch pass) or by an explicit `wrapper.redraw()` inside a `@react_on` handler*. Multiple `@redraw_on` handlers on the same editor matching the same signal still trigger exactly one redraw — the framework collects flags during dispatch and calls `wrapper.redraw()` at the end of the pass. Side effects belong in `@react_on` handlers; typical work is issuing a lifecycle command (`session.publish(Close(...))`), flipping a flag, or persisting state.

### 4.3 Hot-reload

`EditorTypeRegistry` and `PanelRegistry` extend `BaseRegistry` and participate in the framework hot-reload loop. When an editor class is replaced, the framework drops its bus subscriptions, evicts cached wrappers, calls `cleanup()` on the old instance, and re-instantiates + `draw()` (which re-wires fresh subscriptions for the new class's decorated handlers) for any visible bindings. Slots subscribe to the registry's batch-event channel to learn when new `opens='required'` editors should auto-bind on next render.

The signal-class-reload caveat applies here too: handlers that hold a reference to an old `Signal` class object will see `isinstance()` / type lookup miss after a reload of that class. Library authors who declare their own `Signal` subclasses that other libraries subscribe to must list the declaring library in their dependencies.

### 4.4 Boundary — what the studio is not

The studio layer does not own:

- **Graph data** — that lives in `HaystackState` (the multi-graph registry, accessed via `ctx.app_data[HaystackState]`) — an `AppState` defined by the haybale-haystack library, not the studio.
- **Library state** — that lives in `LibraryStateContainer`, accessed via `ctx.data[Cls]` / `ctx.app_data[Cls]`.
- **Settings resolution** — that's `SettingsRegistry` (see [architecture/settings](../settings/settings-arch.md)).
- **Execution** — interpreters and assembly run server-side, independent of UI presence.

The studio is a presentation and orchestration layer: it owns *which editor is in which slot, when does each get redrawn*. Everything else flows through the shared project state and the per-session signal bus.

## 5. Extensibility

A library extends the studio by adding any of:

- **Editors** — `@editor(...)` + `BaseEditor` subclass + `add_folder_to_registry(..., EditorTypeRegistry)` in `register_components()`. Decorate handler methods with `@redraw_on(...)` / `@react_on(...)` to subscribe to signals.
- **Panels** — `@panel(action=..., focus=..., redraw_on=(...,))` + `BasePanel` subclass + `add_folder_to_registry(..., PanelRegistry)`. The host editor unions its registered panels' `redraw_on=` and subscribes the wrapper to the effective set.
- **`Focus` classes** — `Focus` subclass + register via panel/focus discovery; `PropertiesEditor` picks them up automatically through `PanelRegistry.get_focuses_for(...)`.
- **Custom `Signal` subclasses** — declare in the library (concrete `Signal` for observations, `CommandSignal` for imperatives), emit via `session.publish(...)`, list the declaring library in `LibraryIdentity.dependencies` of any library that subscribes.

The studio framework provides the slots, the signal/lifecycle channels, the editor and panel base classes, and `SessionContext`. Every concrete user-facing piece of the studio — graph editor, properties editor, library browser, file viewer, etc. — lives in `haybale-studio` or other libraries, registered through these extension points.
