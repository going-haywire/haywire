---
status: draft
doc_template: system-reference
scope: The studio as a product — AppShell, Workspace, Sessions, slots, editors, panels, context-driven rendering
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

The studio is the haywire UI as a product. It is modelled after the workspace paradigms of **Blender** and **VS Code**: a flexible, area-based layout where each region hosts a different *editor*, the layout can be saved as a named *workspace preset*, and every UI decision is driven by a shared `SessionContext` rather than hard-wired component-to-component communication.

Three design goals shape every decision in this layer:

- **Session isolation** — each browser tab is a fully independent session with its own selection state, interaction mode, and editor instances. Multiple users can connect to the same running haywire server simultaneously without interfering.
- **Context-driven rendering** — UI panels and editors do not talk to each other directly. They read from and write to a central `SessionContext` and broadcast structured events when that context changes. Producers and consumers are decoupled.
- **Open extensibility** — both editors and panels are registered via DI-managed registries (`EditorTypeRegistry`, `PanelRegistry`). A library can ship its own editors and panels that are auto-discovered and inserted into the UI, following the same two-stage decorator + registration pattern used by nodes, widgets, and themes.

The studio's machinery is split across four sub-stories:

- **[app-shell](app-shell/app-shell-arch.md)** — the `AppShell` that builds the page chrome (TopBar, ActivityBar, ContextBar, StatusBar) and hosts the four slots.
- **[workspace](workspace/workspace-arch.md)** — `WorkspaceState`, named presets, persistence; one `WorkspaceManager` per session.
- **[canvas](canvas/canvas-arch.md)** — the graph canvas Vue/NiceGUI hybrid component, minimap, zoom/pan.
- **[rendering](rendering/rendering-arch.md)** — NiceGUI integration, the `hui` module, slot stacks, the reactive rendering pipeline.

## 2. Components

### 2.1 The Layout Model — slots and bars

Every page is built by `AppShell`, which divides the browser window into a fixed set of **slots**. Every slot has a **bar** (the control strip — vertical icons for Left/Right, horizontal tabs for Main/Bottom) and an **area** (the content region where the active editor renders).

```text
┌──────────────────────────────────────────────────────────┐
│  TopBar  (workspace name, switcher, save)                │
├────┬──────────┬─────────────────────┬──────────────┬─────┤
│ A  │          │    Main Slot        │              │  C  │
│ c  │  Left    │  ┌────┬────┬─────┐  │              │  o  │
│ t  │  Slot    │  │Tab1│Tab2│+    │  │    Right     │  n  │
│ i  │          │  ├────┴────┴─────┤  │    Slot      │  t  │
│ v  │ (driven  │  │   Main        │  │              │  e  │
│ i  │  by      │  │   Editor      │  │  (context-   │  x  │
│ t  │  activ-  │  │   (Graph)     │  │   aware      │  t  │
│ y  │  ity     │  ├───────────────┤  │   editors)   │     │
│    │  bar)    │  │  Bottom       │  │              │  B  │
│ B  │          │  │  Slot         │  │  (driven by  │  a  │
│ a  │          │  │ (console,     │  │   context    │  r  │
│ r  │          │  │  terminal,    │  │   bar)       │     │
│    │          │  │  logs)        │  │              │     │
├────┴──────────┴─────────────────────┴──────────────┴─────┤
│                        StatusBar                         │
└──────────────────────────────────────────────────────────┘
```

| Slot / Bar | Purpose | Driven by |
|---|---|---|
| **TopBar** | Workspace name, preset switcher, save button | Fixed |
| **ActivityBar** | Left slot's bar — icons selecting which editor fills the left slot | Clicks update `WorkspaceState.left.active_tab_key` |
| **Left Slot** | Sidebar content (e.g. Library Browser) | `WorkspaceState.left.active_tab_key` |
| **Main Slot** | Primary tabbed workspace, hosts the active editor | `WorkspaceState.main` |
| **Bottom Slot** | Optional retractable tabbed slot below main | `WorkspaceState.bottom` |
| **Right Slot** | Context-sensitive sidebar (e.g. Properties) | `WorkspaceState.right.active_tab_key` |
| **ContextBar** | Right slot's bar — icons selecting which editor fills the right slot | Clicks update `WorkspaceState.right.active_tab_key` |
| **StatusBar** | Session diagnostics | Fixed |

Slots can be **collapsed**: `SlotState.visible = False` hides the area; the adjacent bar expands to fill the space. Sizes (in pixels) are stored in `SlotState.size` and restored on next load. Detailed mechanics in [app-shell](app-shell/app-shell-arch.md).

### 2.2 Workspaces

A **workspace** is a named, serialisable snapshot of the entire layout: which editor lives in each slot, which tabs are open, which slots are visible, and what sizes they are. Represented by the `WorkspaceState` dataclass.

```text
WorkspaceState
  ├── name: str                    "Graph Editing"
  ├── left: SlotState              active_tab_key="library_browser", visible=True, size=250
  ├── main: MainSlotState
  │     ├── tabs: [TabState]       editor_key="graph_editor"
  │     └── active_tab_key: "graph_editor"
  ├── bottom: BottomSlotState
  │     ├── tabs: []               (re-derived from registry on load)
  │     ├── active_tab_key: "console"
  │     ├── visible: False
  │     └── size: 200
  └── right: SlotState             active_tab_key="properties", visible=True, size=350
```

Three presets ship with haywire:

| Preset | Left | Main | Bottom | Right |
|---|---|---|---|---|
| **Graph Editing** | Library Browser | Graph Editor | hidden | Properties |
| **Development** | Library Browser | Graph Editor | Console | Properties |
| **Debugging** | hidden | Graph Editor | Console (large) | Properties |

Each session has one `WorkspaceManager` that owns the set of presets. Switching is instant and non-destructive — each preset is a complete independent state. Presets persist to `.haywire/workspaces.json` and are reloaded on next startup. Detailed mechanics in [workspace](workspace/workspace-arch.md).

### 2.3 Sessions

Haywire is a multi-user server. Every browser tab that connects gets its own **`Session`** object, created when NiceGUI fires `app.on_connect` and destroyed when the tab disconnects.

A session holds:

| Attribute | Type | Purpose |
|---|---|---|
| `session_id` | `str` | UUID, unique per connection |
| `context` | `SessionContext` | Per-tab selection and mode state |
| `workspace_manager` | `WorkspaceManager` | Layout presets for this tab |
| `_editors` | `dict[str, BaseEditor]` | Live editor instances keyed by slot |
| `_context_subscribers` | `list[Callable]` | Registered change callbacks |

```text
Browser connects
  │
  ▼
SessionManager.create_session()
  │   creates Session, injects project state
  ▼
AppShell.render()
  │   reads WorkspaceState, builds NiceGUI layout
  │   instantiates editors → calls editor.render(container, context)
  │   subscribes editors to context changes
  ▼
User interacts
  │   editor mutates context, fires notify_context_changed(event)
  │   session.notify_context_changed() → calls all subscribers
  │   editors react via on_context_changed(event, context)
  ▼
Browser disconnects
  │
  ▼
SessionManager.remove_session() → session.cleanup() → editors garbage-collected
```

Shared (server-wide) vs per-session state:

| Shared | Per-session |
|---|---|
| `HaywireGraph` (data model) | `SessionContext` (selection, mode) |
| `NodeRegistry`, `LibraryManager` | `WorkspaceManager` (layout) |
| `SessionManager` | Editor instances |
| Graph mutations | `active_node`, `active_edge`, etc. |

Cross-session events: when a graph mutation happens (a node is added), producers call `session.notify_cross_session_context_change(event)`, which routes through `SessionManager.broadcast()` to fan a `DATA_MUTATED` event to *all* sessions so every connected tab refreshes.

### 2.4 SessionContext

`SessionContext` is the central state object for one browser session — the single source of truth that editors read and write. Think of it as Blender's `bContext`: a bag of pointers to whatever is currently active.

```python
@dataclass
class SessionContext:
    session_id: str

    # Graph state
    active_graph: Any | None          # currently viewed HaywireGraph
    active_node: Any | None           # selected NodeWrapper
    active_edge: Any | None           # selected edge
    selected_nodes: set[str]          # multi-selection (node IDs)
    selected_edges: set[str]          # multi-selection (edge IDs)

    # Interaction
    interaction_mode: InteractionMode # IDLE, EDITING, CONNECTING, …

    # Editor state
    active_editor: str | None         # focused editor registry key

    # Library state
    active_library: Any | None        # InstalledLibrary or MarketplaceEntry
    active_component: Any | None      # selected node/widget/renderer metadata

    # State namespaces (see architecture/session-and-state)
    app_data: AppDataNamespace        # AppState lookups
    data: SessionDataNamespace        # SessionState lookups (this session only)
```

Library-author state extension points (`AppState`, `SessionState`) live in [architecture/session-and-state](../session-and-state/session-and-state-arch.md). The state namespaces (`ctx.app_data`, `ctx.data`) are part of `SessionContext`'s contract.

### 2.5 Context Events

The studio's reactive layer. Every mutation to `SessionContext` is paired with a structured event broadcast via `session.notify_context_changed(event)`. Subscribers react in `on_context_changed(event, context)`.

Event flow:

```text
Editor / panel mutates context
  ↓
session.notify_context_changed(ContextChangedEvent(...))
  ↓
session._context_subscribers — every registered subscriber
  │   (each subscriber typically dispatches by event.kind)
  │
  ├─ Editor A.on_context_changed → re-renders if relevant
  ├─ Editor B.on_context_changed → updates its tab title
  └─ AppShell.on_context_changed → switches active slot if `reveal_editor` set
```

`reveal_editor` is an optional field on `ContextChangedEvent`. When set to an editor's registry key, the AppShell switches the hosting slot to that editor as part of the same event dispatch — replacing the older `metadata['main_tabs']` / `metadata['bottom_tabs']` shims.

### 2.6 Editors and Panels

**Editors** are full-slot UI components. One instance per slot per session. Discovered via `EditorTypeRegistry`; an editor declares its identity via `@editor(key=..., default_slot=...)` and is auto-registered when its module loads.

**Panels** are context-sensitive sub-sections rendered inside *panel-aware* editors (most commonly `PropertiesEditor`). Panels self-register via `@panel(focus=...)`, declare a `Focus` (the SessionContext slice they care about), and the host editor queries `PanelRegistry` at render time for matching panels.

Authoring surfaces:

- [components/editors](../../components/editors/editor-canon.md) — how to author an editor.
- [components/panels](../../components/panels/panel-canon.md) — how to author a panel.

The four built-in editor categories:

| Editor | Slot | Source |
|---|---|---|
| `LibraryBrowserEditor` | Left | `haywire-studio` |
| `GraphEditor` | Main | `haywire-core` |
| `PropertiesEditor` (panel-aware) | Right | `haywire-core` |
| `ConsoleEditor` | Bottom | `haywire-core` |

## 3. Data flow

### 3.1 Page render at session connect

```text
Session connects
  ↓
SessionManager.create_session()
  ├─ instantiate Session
  ├─ inject SessionContext, WorkspaceManager, app_data namespace
  └─ inject session_id into newly-instantiated SessionState classes
     (eager fanout; see architecture/session-and-state §3.2)
  ↓
AppShell.render(session)
  ├─ read WorkspaceState (from WorkspaceManager.active_preset)
  ├─ for each slot:
  │     EditorTypeRegistry.get(slot.active_tab_key) → editor_cls
  │     editor = editor_cls(session.context)
  │     editor.render(container, session.context)
  │     session._editors[slot] = editor
  │     subscribe editor.on_context_changed → session._context_subscribers
  └─ panels self-register via PanelRegistry — discovered at host editor's
     render time, not by AppShell
```

### 3.2 User interaction → context propagation

```text
User clicks a node on the canvas
  ↓
GraphCanvas → emits "node selected" → SessionContext.active_node = wrapper
  ↓
session.notify_context_changed(
    ContextChangedEvent(kind='node_selected', node_id=..., reveal_editor='properties')
)
  ↓
AppShell sees reveal_editor='properties' → switches Right Slot to PropertiesEditor
  ↓
PropertiesEditor.on_context_changed → re-queries PanelRegistry for panels
                                       whose focus matches node_selected,
                                       re-renders panel list
  ↓
Each rendered panel calls Panel.draw(ctx, layout, actions)
  ↓
Panels read ctx.active_node and current state → render UI
```

### 3.3 Cross-session broadcast (graph mutation)

```text
Session A adds a node to the graph
  ↓
graph.mutate(...) → producer
  ↓
session_a.notify_cross_session_context_change(
    DataMutatedEvent(kind='node_added', node_id=...)
)
  ↓
SessionManager.broadcast(event)
  ↓
For each session in SessionManager._sessions:
    session.notify_context_changed(event)
      ↓
    All subscribers in that session react — graph re-renders, panels update
```

## 4. Performance, errors, and boundaries

### 4.1 Per-session memory

Each session holds editor instances, a `WorkspaceManager`, and the SessionContext + state-namespace pair. For typical workspaces with 4 active editors, that's tens of KBs per session — comfortably scalable to dozens of concurrent connections on a single server.

### 4.2 Context-event amplification

A single user action (selecting a node) produces one context event but multiple consumers react. Subscribers are called synchronously in registration order. Long-running work in `on_context_changed` blocks the dispatch chain — keep handlers fast; defer expensive work via `asyncio.create_task` or a panel-internal `reactive_field`.

### 4.3 Hot-reload

Editor and panel classes are tracked by `EditorTypeRegistry` and `PanelRegistry`, both `BaseRegistry` subclasses. When a library reloads, classes are re-registered and the next time AppShell renders (or the next time a panel-aware editor re-queries), the new class versions are picked up. *Existing instances* are not swapped mid-render — the framework waits for a natural boundary (slot switch, event dispatch). See [architecture/hot-reload](../hot-reload/hot-reload-arch.md).

### 4.4 Boundary — what the studio is not

- **Not a graph engine.** The studio renders graphs and orchestrates user input; it does not execute them. See [architecture/execution](../execution/execution-arch.md).
- **Not a state store.** Library state lives in `LibraryStateContainer` (see [architecture/session-and-state](../session-and-state/session-and-state-arch.md)).
- **Not a file system.** Project files (graphs, settings, workspaces) are read/written by `haywire-studio` services; the UI layer reads from `SessionContext` only.

## 5. Extensibility

A library plugin can extend the studio by shipping:

- **Editors** — `@editor(key='my_editor', default_slot='right')` classes registered via `register_components(..., EditorTypeRegistry)`.
- **Panels** — `@panel(focus=NodeFocus)` classes registered via `register_components(..., PanelRegistry)`.
- **State** — `AppState` / `SessionState` classes registered via `LibraryStateRegistry`.
- **Themes** — `WorkbenchTheme` / `NodeTheme` classes registered via `ThemeRegistry`.
- **Custom slots** — not currently extensible; the four-slot layout is fixed in `AppShell`.

Each follows the same two-stage decorator + folder-scan registration pattern. Hot-reload "just works" — the registries are `BaseRegistry` subclasses and the studio re-queries them at natural boundaries.
