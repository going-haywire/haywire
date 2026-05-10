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
- **Two-channel decoupling** — editors and panels do not talk to each other directly. Observations flow on the **signal channel** (`Session.signal(s: ContextSignal)`); imperative workspace mutations flow on the **lifecycle channel** (`Session.lifecycle(cmd: LifecycleCommand)`). Producers and consumers are decoupled; cross-session synchronisation is opt-in per signal class.
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

The `AppShell` (`packages/haywire-core/src/haywire/ui/app/shell.py`) is the layout container that hosts the four slots, builds the resizable dividers between areas, and owns the orchestration logic that routes signals and lifecycle commands across slots. `AppShell` is constructed once per browser session.

### 2.2 Workspaces

A **workspace snapshot** is a plain JSON dict — one key per slot name — persisted to `.haywire/workspace_state.json` per project. (Earlier versions also stored a `"haystack"` key naming the active haystack TOML; that responsibility moved to `HaystackSettings.last_haystack_name` in the haybale-haystack library.) The `WorkspaceManager` (`packages/haywire-core/src/haywire/ui/workspace/manager.py`) is intentionally dumb:

- `WorkspaceManager.snapshot: dict` — the raw dict loaded from disk, or `{}` if the file is missing or unparseable.
- `WorkspaceManager.save(snapshot)` — write the dict to disk and update `self.snapshot`.

The structure of each slot's sub-dict is defined and interpreted by the slot classes themselves. `WorkspaceManager` knows nothing about editors, `OpenBehavior`, or active tabs. Slots produce a snapshot when asked and consume one when restoring (`Slot.populate_from_snapshot`).

There is no named-preset system in the current implementation. The workspace state is a single snapshot per project; multi-preset support is future work.

### 2.3 Sessions

A `Session` (`packages/haywire-core/src/haywire/ui/session.py`) represents one connected browser tab. Each session owns:

- A `SessionContext` (per-session reactive state — see §2.4).
- A `WorkspaceManager` (the project's layout snapshot).
- Editor instances (cached per `EditorWrapper`; the slot owns the wrapper, the wrapper owns the instance).
- Two callback registrations into `AppShell`: a signal handler and a lifecycle handler.

Sessions are created and tracked by `SessionManager` (`packages/haywire-core/src/haywire/ui/session_manager.py`). When a browser connects, `SessionManager.create_session(...)` constructs the `Session`, attaches its `session_id` to the global `LibraryStateContainer` (which fan-instantiates every registered `SessionState` class for the new session), and returns it. `SessionManager.remove_session(session_id)` reverses the dance: `Session.cleanup()` first, then `LibraryStateContainer.detach_session(...)`. Cleanup-before-detach is deliberate so editors that read `ctx.data[X]` during their own cleanup still see live state.

```python
manager = SessionManager(container=app.library_state_container)
session = manager.create_session(project_state=app, workspace_manager=ws)
manager.broadcast_signal(some_signal, origin_session_id=session.session_id)
manager.remove_session(session.session_id)
```

### 2.4 SessionContext

`SessionContext` (`packages/haywire-core/src/haywire/ui/context.py`) is the small per-session reactive object visible to every editor and panel. Its surface is intentionally narrow:

| Attribute | Kind | Purpose |
|---|---|---|
| `session_id` | plain | UUID of this session |
| `app` | plain | The shared project state (graph data, settings, registries) |
| `session` | plain | Back-reference to the owning `Session` |
| `app_data` | plain | Typed proxy over the global `LibraryStateContainer` for `AppState` lookups (shared across all sessions) |
| `data` | plain | Typed proxy over the same container for `SessionState` lookups (scoped to *this* session) |
| `active_file` | reactive | The currently-active project file |
| `active_library` | reactive | The currently-selected library (in the Library Browser) |
| `active_component` | reactive | The currently-selected library component |
| `active_workbench_theme_key` | reactive | The active workbench theme |
| `active_node_theme_key` | reactive | The active node theme |

Editor-specific reactive state — selection, clipboard, the active graph — does **not** live on `SessionContext`. It lives on a library-owned `SessionState` class. For the graph canvas, that state is `EditState` (`barn/haybale-studio/haybale_studio/state/edit_state.py`), accessed via `ctx.data[EditState]`:

```python
edit = ctx.data[EditState]
node = edit.active_node.value          # NodeWrapper or None
selected = edit.selected_nodes.value   # set[str] of node IDs
edit.active_node.value = my_wrapper    # writes are reactive
```

This separation keeps the framework's `SessionContext` stable while each library owns the reactive surface its editors need. See [components/states](../../components/states/state-canon.md) for the full state model and [session-and-state](../session-and-state/session-and-state-arch.md) for the container's two-namespace asymmetry.

### 2.5 Two channels — signals and lifecycle commands

The studio has two complementary channels (`packages/haywire-core/src/haywire/core/session/signals_and_lifecycle.py`):

**Signal channel — observations.** `ContextSignal` subclasses describe a state move that already happened. Anyone may emit; the orchestrator fans out to every editor in the session via `Session.signal(s)`. Each slot calls `on_signal(...)` on **every** wrapper (the side-effect channel — fires regardless of which tab is active) and `redraw_on_signal(...) -> bool` on the **active** wrapper, redrawing if it returns `True`. Subscribers filter with plain `isinstance(signal, SignalType)`.

The base class is `ContextSignal`; concrete subclasses include:

- **Workbench / focus** — `ActiveFileMoved`, `ActiveLibraryMoved`, `ActiveComponentMoved`, `ActiveGraphMoved`.
- **Selection** — `SelectionMoved`.
- **Data + lifecycle** — `GraphDataMutated`, `LibraryCatalogChanged`.
- **Theme** — `ThemeMoved`.

Cross-session routing is a per-class property: set `cross_session: ClassVar[bool] = True` on a subclass and `Session.signal(...)` delegates to `SessionManager.broadcast_signal(...)` instead of dispatching locally. The transport stamps `subject = Subject.peer(origin_id)` on non-origin sessions so peer subscribers can distinguish "*this* session moved" from "*another* session moved." Among the built-ins, `GraphDataMutated` and `LibraryCatalogChanged` are cross-session; the rest are local-only.

Library authors who declare their own signal classes that other libraries subscribe to **must** list the signal-declaring library in their own `LibraryIdentity.dependencies`, so hot-reload reloads them as a pair. Without this, an `isinstance` check after a library reload can spuriously return `False` when the subscriber holds a stale class reference.

**Lifecycle channel — commands.** `LifecycleCommand` subclasses describe imperative mutations of the workspace tree. They are point-to-point or fan-out, not observations.

- `Reveal(editor=Cls, payload=..., label=...)` — bring an editor to the front. The orchestrator resolves `editor.class_identity.default_slot` and routes to that slot. If the slot is not hostable in the active workspace, the reveal is dropped with a warning. `payload` disambiguates multi-instance editors (`opens='on_payload'`); when supplied, the orchestrator switches to the specific `(editor_key, payload)` tab rather than the first matching binding.
- `Close(payload=...)` — close every tab bound to `payload` across all slots in the issuing session. Used for session-local close decisions.
- `BroadcastClose(payload=...)` — cross-session sibling of `Close`. Fans the close out to every session's AppShell so any matching tab disappears everywhere. Used when the underlying entity is gone for everyone (e.g. a graph entry was removed from the haystack, or the haystack itself was torn down by a library hot-reload).

Lifecycle commands are **local by default**. Session-scoped UI actions (e.g. `Reveal` a panel because the user clicked) belong to the issuing session — peer sessions own their own workspace state. Subclasses opt into cross-session fan-out by setting `cross_session: ClassVar[bool] = True` (mirroring `ContextSignal`); `Session.lifecycle()` checks the class flag and routes to `SessionManager.broadcast_lifecycle(...)` instead of dispatching locally. `BroadcastClose` is the only built-in that opts in. Use it for fact-driven imperatives where every session's tabs bound to a given payload must close; reserve `Close` for session-local actions.

### 2.6 Editors and panels

Editors fill slots; panels fill the inside of panel-aware editors. Both register via DI registries:

- `EditorTypeRegistry` — `BaseEditor` subclasses, decorated with `@editor(...)`. Registered by libraries via `add_folder_to_registry(folder_path=..., registry_cls=EditorTypeRegistry)` in `register_components()`. Built-in framework editors (currently none — all editors live in `haybale-studio` or other libraries) would bootstrap via `register_builtin_editors()`.
- `PanelRegistry` — `BasePanel` subclasses, decorated with `@panel(action=..., focus=...)`. Registered the same way. Panel-aware editors (e.g. `PropertiesEditor`) call `panel_registry.get_panels_for(actions_provider=self, focus=...)`, which filters panels by structural `isinstance(actions_provider, action)` and by `Focus.id` match.

For the editor authoring surface — `BaseEditor`, the `draw`/`on_signal`/`redraw_on_signal` lifecycle, `OpenBehavior` modes, slot constraints — see [components/editors](../../components/editors/editor-canon.md). For the panel surface — `@panel`, `Focus` classes, `PanelLayout` — see [components/panels](../../components/panels/panel-canon.md).

## 3. Data flow

### 3.1 Page render at session connect

```text
Browser opens NiceGUI page
  ├─ studio app.py page handler
  ├─ SessionManager.create_session(project_state=app, workspace_manager=ws)
  │   ├─ Session() — constructs SessionContext, registers session_id
  │   └─ container.attach_session(session_id) — fan-instantiates SessionStates
  ├─ AppShell(session, editor_registry)
  ├─ session.set_signal_orchestrator(shell._on_signal)
  ├─ session.set_lifecycle_orchestrator(shell._on_lifecycle)
  └─ shell.render()
      ├─ build TopBar / StatusBar
      ├─ instantiate four slots (left/right IconSlot, main/bottom TabSlot)
      ├─ each slot.populate_from_snapshot(workspace_manager.snapshot[slot_name])
      ├─ each slot.render(parent) — builds area container, calls draw() on active wrapper
      └─ install drag-resize handles between areas
```

### 3.2 User interaction → signal propagation

```text
User clicks a node in the graph canvas
  ├─ GraphEditor handler:  ctx.data[EditState].active_node.value = wrapper
  ├─ GraphEditor handler:  session.signal(SelectionMoved())
  └─ Session.signal — local-only path (cross_session=False):
      └─ AppShell._on_signal(signal)
          └─ for slot in (left, right, main, bottom):
              └─ slot.handle_signal(signal)
                  ├─ for wrapper in slot._bindings:
                  │     └─ wrapper.editor.on_signal(ctx, signal)   # side effects, all wrappers
                  └─ active_wrapper.editor.redraw_on_signal(ctx, signal)
                      ├─ True  → slot clears area, calls editor.draw(ctx, area)
                      └─ False → no-op
```

The `SelectionMoved` signal carries no payload (pointer-by-default rule, §6.3 of the design doc). Subscribers re-read `ctx.data[EditState]` to discover what the new selection is.

### 3.3 Cross-session broadcast (graph mutation)

```text
Session A: user edits a node's setting
  ├─ NodeWrapper.update_setting(...)
  ├─ session.signal(GraphDataMutated())
  └─ Session.signal — cross_session=True path:
      └─ session_manager.broadcast_signal(s, origin_session_id=A)
          ├─ For session A:    deliver as-is (subject=Subject.SELF)
          └─ For session B, C: deliver replace(s, subject=Subject.peer(A))
              └─ Each session's _dispatch_signal → AppShell._on_signal → slots
                  └─ Subscribers see signal.is_from_peer() == True
```

Cross-session signals never carry payload data either. Receivers re-read the relevant state from the shared project — for `GraphDataMutated` that's the entry in `ctx.app_data[HaystackState].get_by_id(<entry_id>)`. For `Subject.peer(...)` cases, peer state can be reached through `session_manager.get_session(peer_id).context`.

## 4. Performance, errors, and boundaries

### 4.1 Per-session memory

Each session holds editor instances, slots, a `WorkspaceManager`, and a `SessionContext` plus the per-session `SessionState` instances. For a typical workspace with four active editors, that's tens of KBs per session — comfortably scalable to dozens of concurrent connections on a single server.

### 4.2 Signal amplification

A single signal is delivered to **every wrapper** in every slot via `on_signal` (side-effect channel) and to the **active** wrapper in each slot via `redraw_on_signal` (redraw decision). Editors that use a tuple of relevant signal classes plus one `isinstance` check (the `_RELEVANT_SIGNALS` pattern, see editor-canon §3) keep this O(slots · wrappers) under a millisecond. Editors that do work in `on_signal`/`redraw_on_signal` themselves — I/O, AppState walks, expensive predicates — will dominate the dispatch path. The contract is: *both hooks are cheap; the heavy work goes in `draw()`, gated on `redraw_on_signal()` returning `True`.* Side effects in `on_signal` should also be cheap — typically issuing a few lifecycle commands, flipping a flag, or doing a single isinstance check.

### 4.3 Hot-reload

`EditorTypeRegistry` and `PanelRegistry` extend `BaseRegistry` and participate in the framework hot-reload loop. When an editor class is replaced, the orchestrator evicts cached wrappers, calls `cleanup()` on the old instance, and re-instantiates + `draw()` for any visible bindings. Slots subscribe to the registry's batch-event channel to learn when new `opens='required'` editors should auto-bind on next render.

The signal-class-reload caveat applies here too: subscribers that hold a reference to an old signal class object will see `isinstance()` return `False` after a reload of that class. Library authors who declare their own signal classes that other libraries subscribe to must list the signal-declaring library in their dependencies.

### 4.4 Boundary — what the studio is not

The studio layer does not own:

- **Graph data** — that lives in `HaystackState` (the multi-graph registry, accessed via `ctx.app_data[HaystackState]`) — an `AppState` defined by the haybale-haystack library, not the studio.
- **Library state** — that lives in `LibraryStateContainer`, accessed via `ctx.data[Cls]` / `ctx.app_data[Cls]`.
- **Settings resolution** — that's `SettingsRegistry` (see [architecture/settings](../settings/settings-arch.md)).
- **Execution** — interpreters and assembly run server-side, independent of UI presence.

The studio is a presentation and orchestration layer: it owns *which editor is in which slot, when does each get redrawn*. Everything else flows through the shared project state and the two channels.

## 5. Extensibility

A library extends the studio by adding any of:

- **Editors** — `@editor(...)` + `BaseEditor` subclass + `add_folder_to_registry(..., EditorTypeRegistry)` in `register_components()`.
- **Panels** — `@panel(editor=..., focus=...)` + `Panel` subclass + `add_folder_to_registry(..., PanelRegistry)`.
- **`Focus` classes** — `Focus` subclass + register via panel/focus discovery; `PropertiesEditor` picks them up automatically through `PanelRegistry.get_focuses_for(...)`.
- **Custom `ContextSignal` subclasses** — declare in the library, emit via `session.signal(...)`, list the declaring library in `LibraryIdentity.dependencies` of any library that subscribes.

The studio framework provides the slots, the signal/lifecycle channels, the editor and panel base classes, and `SessionContext`. Every concrete user-facing piece of the studio — graph editor, properties editor, library browser, file viewer, etc. — lives in `haybale-studio` or other libraries, registered through these extension points.
