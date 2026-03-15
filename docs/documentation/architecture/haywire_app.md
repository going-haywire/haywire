# Haywire UI Architecture

## Table of Contents

1. [Introduction & Philosophy](#1-introduction--philosophy)
2. [The Layout Model](#2-the-layout-model)
3. [Workspaces](#3-workspaces)
4. [Sessions](#4-sessions)
5. [Session Context](#5-session-context)
6. [Context Events](#6-context-events)
7. [Editors](#7-editors)
8. [Panels](#8-panels)
9. [Putting It All Together: A Typical Interaction](#9-putting-it-all-together-a-typical-interaction)
10. [Extensibility](#10-extensibility)

---

## 1. Introduction & Philosophy

Haywire's UI is modelled after the workspace paradigms of **Blender** and **VS Code**: a
flexible, area-based layout where each region can host a different *editor*, the overall
configuration can be saved as a named *workspace preset*, and every UI decision is driven by a shared *context* object rather than hard-wired component-to-component communication.

Three design goals shape every decision in the UI layer:

- **Session isolation** — each browser tab is a fully independent session with its own
  selection state, interaction mode, and editor instances. Multiple people can connect to the same running Haywire server simultaneously without interfering with each other.

- **Context-driven rendering** — UI panels and editors do not talk to each other directly. Instead, they read from and write to a central `SessionContext` object and broadcast structured events when that context changes. This decouples producers from consumers and makes the system trivially extensible.

- **Open extensibility** — both editors and panels are registered via a DI-managed registry. A node library can ship its own editors and panels that are discovered and inserted into the UI automatically, following the same two-stage decorator + registration pattern used by nodes, widgets, and renderers.

---

## 2. The Layout Model

Every page rendered by Haywire is built by the `AppShell`, which divides the browser window into a fixed set of **named areas**:

```
┌──────────────────────────────────────────────────────────┐
│  TopBar  (workspace name, switcher, save)                │
├────┬──────────┬─────────────────────┬──────────────┬─────┤
│    │          │    Middle Area      │              │     │
│    │          │  ┌────┬────┬─────┐  │              │     │
│    │          │  │Tab1│Tab2│+    │  │              │     │
│    │          │  ├────┴────┴─────┤  │              │     │
│ A  │  Left    │  │               │  │    Right     │  C  │
│ c  │  Area    │  │   Main        │  │    Area      │  o  │
│ t  │          │  │  Editor       │  │              │  n  │
│ i  │ (driven  │  │  (Graph)      │  │  (context-   │  t  │
│ v  │  by      │  │               │  │   aware      │  e  │
│ i  │  activ-  │  ├───────────────┤  │   editors)   │  x  │
│ t  │  ity     │  │  Bottom       │  │              │  t  │
│ y  │  bar)    │  │  Area         │  │  (driven by  │     │
│    │          │  │ (console,     │  │   context    │  B  │
│ B  │          │  │  terminal,    │  │   bar)       │  a  │
│ a  │          │  │  logs)        │  │              │  r  │
│ r  │          │  └───────────────┘  │              │     │
├────┴──────────┴─────────────────────┴──────────────┴─────┤
│                        StatusBar                         │
└──────────────────────────────────────────────────────────┘
```

| Area            | Description                                                     | Driven by                                       |
| --------------- | --------------------------------------------------------------- | ----------------------------------------------- |
| **TopBar**      | Workspace name, preset switcher, save button                    | Fixed                                           |
| **ActivityBar** | Left icon strip — selects which editor lives in the Left Area   | Clicks update `WorkspaceState.left_bar_active`  |
| **Left Area**   | Sidebar content (e.g. Library Browser)                          | `WorkspaceState.left.editor_key`                |
| **Middle Area** | Primary workspace — tabbed, with optional bottom split          | `WorkspaceState.middle`                         |
| **Right Area**  | Context-sensitive sidebar (e.g. Properties)                     | `WorkspaceState.right.editor_key`               |
| **ContextBar**  | Right icon strip — selects which editor lives in the Right Area | Clicks update `WorkspaceState.right_bar_active` |
| **StatusBar**   | Session diagnostics                                             | Fixed                                           |

### The Middle Area

The middle area is special: it hosts one or more **tabs**, each containing an independent
editor. An optional **bottom split** can be revealed to host a second editor below the tabs (typically the Console).

Areas can be **collapsed**: `AreaState.visible = False` hides the area and its icon strip
expands to fill the space. Sizes are stored in pixels in `AreaState.size` and restored on
next load.

---

## 3. Workspaces

A **workspace** is a named, serialisable snapshot of the entire layout: which editor lives in each area, which tabs are open, which areas are visible, and what sizes they are. It is
represented by the `WorkspaceState` dataclass.

```
WorkspaceState
  ├── name: str                  "Graph Editing"
  ├── left_bar_active: str       "library_browser"
  ├── left: AreaState            editor_key="library_browser", visible=True, size=250
  ├── middle: MiddleAreaState
  │     ├── tabs: [TabState]     editor_key="graph_editor"
  │     ├── active_tab_index: 0
  │     ├── bottom_visible: False
  │     └── bottom_editor_key: "console"
  ├── right_bar_active: str      "properties"
  └── right: AreaState           editor_key="properties", visible=True, size=350
```

### Built-in Presets

Three presets ship with Haywire:

| Preset            | Left            | Middle       | Bottom          | Right      |
| ----------------- | --------------- | ------------ | --------------- | ---------- |
| **Graph Editing** | Library Browser | Graph Editor | hidden          | Properties |
| **Development**   | Library Browser | Graph Editor | Console         | Properties |
| **Debugging**     | hidden          | Graph Editor | Console (large) | Properties |

### Switching and Persistence

The `WorkspaceManager` (one per session) manages the set of presets. Switching is instant and non-destructive — each preset is a complete independent state. The user can save a modified layout under a new name or overwrite an existing one. Presets are persisted to `.haywire/workspaces.json` inside the project folder and reloaded on the next startup.

---

## 4. Sessions

Haywire is a multi-user server. Every browser tab that connects gets its own **`Session`**
object, created when NiceGUI fires `app.on_connect` and destroyed when the tab disconnects.

A session holds:

| Attribute              | Type                    | Purpose                                  |
| ---------------------- | ----------------------- | ---------------------------------------- |
| `session_id`           | `str`                   | UUID, unique per connection              |
| `context`              | `SessionContext`        | Per-tab selection and mode state         |
| `workspace_manager`    | `WorkspaceManager`      | Layout presets for this tab              |
| `_editors`             | `Dict[str, BaseEditor]` | Live editor instances keyed by area slot |
| `_context_subscribers` | `List[Callable]`        | Registered change callbacks              |

### Session Lifecycle

```
Browser connects
    │
    ▼
SessionManager.create_session()
    │   creates Session, injects project_state
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
SessionManager.remove_session()
    │   calls session.cleanup()
    │   all editor instances garbage-collected
```

### Shared vs. Per-Session State

| Shared (server-wide)             | Per-session                        |
| -------------------------------- | ---------------------------------- |
| `HaywireGraph` (data model)      | `SessionContext` (selection, mode) |
| `NodeRegistry`, `LibraryManager` | `WorkspaceManager` (layout)        |
| `SessionManager`                 | Editor instances                   |
| Graph mutations                  | `active_node`, `active_edge`, etc. |

When a graph mutation happens (e.g. a node is added), `SessionManager.broadcast_data_mutation()` fires a `DATA_MUTATED` event to *all* sessions so every connected tab refreshes.

---

## 5. Session Context

`SessionContext` is the central state object for one browser session. It is the single source of truth that editors read and write. Think of it as Blender's `bContext` — a bag of pointers to whatever is currently active.

```python
@dataclass
class SessionContext:
    session_id: str

    # Graph state
    active_graph: Optional[Any]         # currently viewed HaywireGraph
    active_node: Optional[Any]          # selected NodeWrapper
    active_edge: Optional[Any]          # selected edge
    selected_nodes: Set[str]            # multi-selection (node IDs)
    selected_edges: Set[str]            # multi-selection (edge IDs)

    # Interaction
    interaction_mode: InteractionMode   # IDLE, EDITING, CONNECTING …

    # Editor state
    active_editor: Optional[str]        # focused editor registry key

    # Library state
    active_library: Optional[Any]       # InstalledLibrary or MarketplaceEntry
    active_component: Optional[Any]     # selected node/widget/renderer metadata

    # Workspace
    workspace_name: str                 # active preset name

    # Extensibility
    metadata: Dict[str, Any]           # shared services + editor-specific state
```

### The Metadata Dictionary

`context.metadata` is an open extensibility point. The application wires standard services into it at startup so that any editor or panel can access them without direct DI coupling:

| Key                   | Type            | Contents                                                   |
| --------------------- | --------------- | ---------------------------------------------------------- |
| `'project_state'`     | `HaywireApp`    | The main app object (node_registry, library_manager, etc.) |
| `'panel_registry'`    | `PanelRegistry` | The DI-managed panel registry                              |
| `'haywire_session'`   | `Session`       | The current session (for firing events)                    |
| `'middle_tabs'`       | `ui.tabs`       | NiceGUI tabs element (for programmatic tab switching)      |
| `'switch_right_area'` | `Callable`      | Callback to swap the right-area editor                     |

Editors and panels should always access services via `context.metadata` rather than storing their own references, since this keeps them session-safe.

### InteractionMode

`InteractionMode` is an enum that describes what the user is currently doing in the graph canvas:

| Value        | Meaning                            |
| ------------ | ---------------------------------- |
| `IDLE`       | Default state                      |
| `EDITING`    | Editing a node value or name       |
| `CONNECTING` | Drawing a connection between ports |
| `SELECTING`  | Rectangle-selecting nodes          |
| `PANNING`    | Panning the canvas                 |

---

## 6. Context Events

Editors and panels communicate exclusively through the event bus provided by `Session`. When an editor mutates `SessionContext`, it broadcasts a `ContextChangedEvent` to signal what changed. All subscribed editors receive the event and decide whether to react.

### Event Structure

```python
@dataclass
class ContextChangedEvent:
    change_type: ContextChangeType     # what kind of change happened
    source_editor: Optional[str]       # registry_id of the originating editor
    detail: Optional[Any]              # optional extra data
```

### Change Types

| `ContextChangeType`        | Triggered when                                       |
| -------------------------- | ---------------------------------------------------- |
| `SELECTION_CHANGED`        | Node or edge selection changes in the graph          |
| `ACTIVE_GRAPH_CHANGED`     | User switches to a different graph                   |
| `MODE_CHANGED`             | Interaction mode changes (e.g. starts connecting)    |
| `EDITOR_FOCUSED`           | A different editor gains focus                       |
| `WORKSPACE_CHANGED`        | The workspace preset is switched                     |
| `DATA_MUTATED`             | Graph structure changes (add/remove node or edge)    |
| `ACTIVE_LIBRARY_CHANGED`   | User selects a library in the LibraryBrowser         |
| `ACTIVE_COMPONENT_CHANGED` | User selects a component (node class, widget, etc.)  |
| `CUSTOM`                   | Reserved for application- or library-specific events |

### The Event Flow

```
1. User clicks a node in the graph canvas
        │
        ▼
2. GraphEditor updates context:
       context.active_node = node_wrapper
       context.selected_nodes = {node_id}
        │
        ▼
3. GraphEditor fires:
       session.notify_context_changed(
           ContextChangedEvent(
               change_type=ContextChangeType.SELECTION_CHANGED,
               source_editor='graph_editor',
           )
       )
        │
        ▼
4. Session iterates all subscribers (editor.on_context_changed callbacks)
        │
        ├── PropertiesEditor receives event
        │     → resolves context = ['node']
        │     → queries PanelRegistry for panels with editor='properties', context='node'
        │     → calls poll(context) on each → renders those returning True
        │
        └── Other editors receive event and filter by change_type
```

### Avoiding Echo Events

Editors can check `event.source_editor` to avoid re-processing their own changes:

```python
def on_context_changed(self, event, context):
    if event.source_editor == 'my_editor':
        return   # we fired this ourselves, ignore
    if event.change_type == ContextChangeType.SELECTION_CHANGED:
        self._rebuild(context)
```

---

## 7. Editors

An **editor** is a self-contained UI component that occupies one area of the workspace. Each editor knows how to build its own NiceGUI layout and how to react when the session context changes.

### Built-in Editors

from haywire.ui.workspace.workspace_state import _K_...

| constants = Registry Key        | Area   | Purpose                                          |
| ------------------ | ------ | ------------------------------------------------ |
| _K_GRAPH_EDITOR    = '__system__:editor:graph_editor'     | Middle | Visual node graph canvas                         |
| _K_PROPERTIES      = '__system__:editor:properties'       | Right  | Context-sensitive property panels                |
| _K_CONSOLE         = '__system__:editor:console'          | Bottom | Execution log stream                             |
| _K_LIBRARY_BROWSER = '__system__:editor:library_browser'  | Left   | Searchable installed/marketplace library list    |
| _K_LIBRARY_DETAIL  = '__system__:editor:library_detail'   | Middle | Full detail view for the selected library        |
| _K_COMPONENT_DETAIL = '__system__:editor:component_detail' | Right  | Documentation for the selected node/widget class |
| _K_FILE_BROWSER    = '__system__:editor:file_browser'     | Left   | Searchable installed/marketplace file list       |
| _K_FILE_VIEWER     = '__system__:editor:file_viewer'      | Middle | File content viewer                              |

### Editor Lifecycle

```
AppShell reads WorkspaceState.left.editor_key = "library_browser"
    │
    ▼
EditorTypeRegistry.get_by_id("library_browser")  →  LibraryBrowser class
    │
    ▼
instance = LibraryBrowser()
instance.render(container_element, session.context)
    │
    ▼
session.subscribe_context_changes(instance.on_context_changed)
    │
    ▼
[user interacts; on_context_changed fires as needed]
    │
    ▼
[area swap or disconnect]
session.unsubscribe_context_changes(instance.on_context_changed)
instance.cleanup()
```

### Area Placement Rules

- **Left** and **Right** areas hold a single editor at a time. Swapping replaces the
  existing editor (clearing the container and re-rendering a new instance).
- **Middle** area hosts one editor per tab. Tabs can be added/closed at runtime.
- **Bottom** split holds a single editor, toggled by the workspace state.
- `default_area` in the `@editor` decorator is a suggestion, not a constraint — editors can be placed in any area by the workspace configuration.

---

## 8. Panels

A **panel** is a smaller, context-sensitive sub-section that lives inside a panel-aware editor
(most commonly the `PropertiesEditor`). Unlike editors, panels are not directly wired to areas — they are discovered at runtime through the `PanelRegistry`.

### The Poll–Draw Lifecycle

Every time the context changes, a panel-aware editor:

1. **Resolves** the active context strings from `SessionContext`
   (e.g. `active_node` is set → context `'node'`).
2. **Queries** the `PanelRegistry` for panels registered to its `editor_key` and each
   context string, sorted by `order`.
3. **Polls** each panel: `PanelClass.poll(context) → bool`. Panels that return `False` are hidden; panels returning `True` are drawn.
4. **Draws** each visible panel inside a collapsible `ui.expansion` element via
   `panel.draw(context, layout)`.

```
PanelRegistry.get_panels(editor_key='properties', context='node')
    →  [NodePropertiesPanel, NodePortsPanel, NodeSettingsPanel]
                │                   │                │
           poll() = True       poll() = True    poll() = False (no config ports)
                │                   │
          draw(ctx, layout)   draw(ctx, layout)
```

### Built-in Panels

| Panel                 | Editor       | Context | Purpose                          |
| --------------------- | ------------ | ------- | -------------------------------- |
| `NodePropertiesPanel` | `properties` | `node`  | Name, class, registry ID         |
| `NodePortsPanel`      | `properties` | `node`  | Inlet/outlet/config port listing |
| `NodeSettingsPanel`   | `properties` | `node`  | Node-specific settings           |
| `GraphInfoPanel`      | `properties` | `graph` | Node/edge counts                 |
| `EdgeInfoPanel`       | `properties` | `edge`  | Source/target node info          |

### PanelLayout

Panels receive a `PanelLayout` helper rather than a raw NiceGUI container. This provides a stable, styled API (`label`, `row`, `column`, `separator`, `button`, `expansion`, `widget`) that insulates panels from direct NiceGUI dependency and ensures consistent styling across all panels.

---

## 9. Putting It All Together: A Typical Interaction

Here is a full end-to-end trace of what happens when a user clicks a node and the Properties sidebar updates to show that node's ports.

```
① User clicks a node in the Graph Editor canvas
        │
        ▼
② GraphCanvasManager fires selection callback
        │  GraphEditor updates SessionContext:
        │      context.active_node = <NodeWrapper>
        │      context.selected_nodes = {'node-42'}
        │
        ▼
③ GraphEditor calls:
        session.notify_context_changed(
            ContextChangedEvent(SELECTION_CHANGED, source_editor='graph_editor')
        )
        │
        ▼
④ Session.notify_context_changed() iterates subscribers:
        → GraphEditor.on_context_changed  (ignores own event)
        → PropertiesEditor.on_context_changed
        → LibraryBrowser.on_context_changed  (no-op)
        │
        ▼
⑤ PropertiesEditor._rebuild_panels(context):
        resolved contexts = ['node']   (because active_node is set)
        panels = PanelRegistry.get_panels('properties', 'node')
              = [NodePropertiesPanel, NodePortsPanel, NodeSettingsPanel]
        │
        ├── NodePropertiesPanel.poll(context) → True
        │       → draw(context, layout)  → name, class, ID rendered
        │
        ├── NodePortsPanel.poll(context) → True
        │       → draw(context, layout)  → port list rendered
        │
        └── NodeSettingsPanel.poll(context) → False (node has no config ports)
                → hidden
        │
        ▼
⑥ Right Area displays Properties panel with node info
```

---

## 10. Extensibility

### How Libraries Contribute Editors and Panels

Node libraries (haybale packages) can ship their own editors and panels using exactly the same two-stage pattern as nodes and renderers:

**Stage 1 — Decoration:** Apply `@editor(...)` or `@panel(...)` to a class. This sets
`class_identity` on the class but does NOT register it anywhere.

**Stage 2 — Registration:** In the library's `register_components()` method, call
`self.add_folder_to_registry(...)` or `self.add_folder_to_registry(...)` to scan and register the decorated classes.

```python
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry

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

        # Register panels
        self.add_folder_to_registry(
            folder_path=str(base_path / 'panels'),
            registry_cls=PanelRegistry
        )
```

### App-Level vs. Framework-Level vs. Library-Level

| Level         | When to use                                                     | Registration call                                                 |
| ------------- | --------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Framework** | Editors/panels that ship with `haywire-core` itself        | `register_builtin_editors(registry)`                              |
| **App**       | Editors tightly coupled to `haywire-app` (LibraryBrowser, etc.) | `registry._register_class(MyEditor)` in `setup_shared_services()` |
| **Library**   | Editors/panels shipped inside a haybale library package         | `registry.add_folder(...)` in `register_components()`             |

### Hot-Reload

Because `EditorTypeRegistry` and `PanelRegistry` both extend `BaseRegistry`, they inherit full hot-reload support. When a library is reloaded at runtime, its editors and panels are unregistered and re-registered automatically. Running editor instances are not automatically swapped — the user needs to navigate away and back to pick up the new implementation.

### The `@editor` / `@panel` Contract

Both decorators follow the same principle: **decorate first, register explicitly**. This
separation means a class can be inspected and tested without ever touching a registry, and the same class can be registered into multiple applications with different configurations.
