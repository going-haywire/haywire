# CLAUDE.md — Haywire UI Architecture Implementation Plan

## Project Context

You are implementing a multi-editor workspace system for the Haywire visual node-based programming framework. Haywire is a Python project using NiceGUI (a Python web UI framework built on Vue.js/Quasar) for its interface.

**Read the full specification first:** `docs/documentation/architecture/haywire-ui-architecture-spec.md` — it contains the complete architecture, class designs, and rationale. This file is the step-by-step execution plan.

**Key codebase locations (uv workspace monorepo):**

- Framework source: `packages/haywire-core/src/haywire/`
- Framework UI code: `packages/haywire-core/src/haywire/ui/`
- Existing graph canvas: `packages/haywire-core/src/haywire/ui/editor/` (will be renamed to `graph_canvas/` in Phase 2)
- Existing renderers: `packages/haywire-core/src/haywire/ui/renderer/`
- Existing widgets: `packages/haywire-core/src/haywire/ui/widget/`
- Core node system / DI: `packages/haywire-core/src/haywire/core/`
- Base registry: `packages/haywire-core/src/haywire/core/registry/base.py`
- DI config: `packages/haywire-core/src/haywire/core/di/config.py`
- App source: `packages/haywire-app/src/haywire_app/`
- Prototypical library UI reference: `packages/haywire-app/src/haywire_app/library_manager_ui.py`
- Tests: `tests/`

**Technology stack:**

- Python 3.11+
- NiceGUI (latest)
- Vue.js (via NiceGUI)
- Quasar Framework (via NiceGUI)
- Tailwind CSS (via NiceGUI)

**Coding conventions (match existing codebase):**

- Type hints everywhere
- Dataclasses for data structures
- ABC for abstract base classes
- `@decorator` pattern for component marking (see existing `@renderer`, `@widget`, `@node`) — decorators set `class_identity` only; they do NOT self-register
- `BaseRegistry` pattern for all registries — extend `haywire.core.registry.base.BaseRegistry`, implement `_class_filter()` and `_register_class()`. Registries are DI-managed singletons, never bare Python singletons.
- DI integration: all registries are provided via `HaywireModule` in `core/di/config.py`
- f-strings for formatting
- logging module for debug/info/warning output
- `__init__.py` files with explicit public API exports
- Docstrings on all public classes and methods

---

## Execution Order

Execute phases in order. Each phase should result in a working (or at least non-breaking) state. Run existing tests after each phase to verify nothing is broken.

---

### PHASE 1: Foundation — Abstract Framework

Create the core abstractions. No UI rendering yet — just classes, registries, decorators, and DI wiring.

**Step 1.1: Create `packages/haywire-core/src/haywire/ui/context.py`**

Implement:

- `InteractionMode` enum (IDLE, EDITING, CONNECTING, SELECTING, PANNING)
- `SessionContext` dataclass with all fields from spec Section 2.1, including:
  - session_id, active_graph, active_node, active_edge
  - selected_nodes (Set[str]), selected_edges (Set[str])
  - interaction_mode, active_editor, workspace_name
  - `active_library: Optional[Any]` — library selected in LibraryBrowser (InstalledLibrary | MarketplaceEntry)
  - `active_component: Optional[Any]` — node/widget/renderer selected in LibraryBrowser
  - metadata (Dict[str, Any])

See spec Section 2.1 for the complete class definition.

**Step 1.2: Create `packages/haywire-core/src/haywire/ui/context_events.py`**

Implement:

- `ContextChangeType` enum — all values from spec Section 2.2:
  - SELECTION_CHANGED, ACTIVE_GRAPH_CHANGED, MODE_CHANGED, EDITOR_FOCUSED,
    WORKSPACE_CHANGED, DATA_MUTATED, ACTIVE_LIBRARY_CHANGED, ACTIVE_COMPONENT_CHANGED, CUSTOM
- `ContextChangedEvent` dataclass: change_type, source_editor (Optional[str]), detail (Optional[Any])

#### Step 1.3: Create editor framework — temporary location

**IMPORTANT:** There is an existing `packages/haywire-core/src/haywire/ui/editor/` folder containing graph canvas code. Do NOT touch it. Phase 2 handles the rename. For now, create the editor framework in a temporary location:

`packages/haywire-core/src/haywire/ui/editor_framework/`

Phase 2 will move it to its final location (`editor/`) after the canvas code is renamed to `graph_canvas/`.

Create these files in `packages/haywire-core/src/haywire/ui/editor_framework/`:

- **`identity.py`** — `EditorIdentity` dataclass with fields: `registry_id`, `label`, `icon`, `canvas_area`, `description`, `registry_key`. See spec Section 2.3.
- **`base.py`** — `BaseEditor` ABC. Single class attribute: `class_identity: ClassVar[EditorIdentity]`. Abstract methods: `render(container, context)`, `on_context_changed(event, context)`. Non-abstract: `cleanup()`, `get_tab_label(context)`. See spec Section 2.3 for complete class definition.
- **`decorator.py`** — `@editor(registry_id, label, icon, canvas_area, description)` decorator. Validates subclass of BaseEditor, calls `derive_library_identity()` and `reg_key()` (from `haywire.core.library.utils`), creates an `EditorIdentity`, assigns it to `inner_cls.class_identity`. Does NOT register with the registry — that happens via `add_folder()`. See spec Section 2.3.
- **`registry.py`** — `EditorTypeRegistry(BaseRegistry)`. Implements `_class_filter()` (checks `issubclass(cls, BaseEditor)` and `hasattr(cls, 'class_identity')`), `_register_class()` (reads `cls.class_identity.registry_key`, calls `super()._register()`), `_unregister_class()` (calls `super()._unregister()`). Extra method: `get_by_default_area(area)`. See spec Section 2.3.
- **`__init__.py`** — export BaseEditor, EditorIdentity, editor decorator, EditorTypeRegistry

**Step 1.4: Create panel framework — `packages/haywire-core/src/haywire/ui/panel/`**

Can go in its final location immediately (no naming conflict with existing code).

Create:

- **`identity.py`** — `PanelIdentity` dataclass with fields: `registry_id`, `editor_key`, `context`, `label`, `icon`, `order`, `default_open`, `description`, `registry_key`. See spec Section 2.4.
- **`base.py`** — `BasePanel` ABC. Single class attribute: `class_identity: ClassVar[PanelIdentity]`. Methods: classmethod `poll(context) → bool` (default True), abstract `draw(context, layout)`, optional `on_context_changed(context, layout)`. Also `PanelLayout` class (thin wrapper around a NiceGUI container). See spec Section 2.4.
- **`decorator.py`** — `@panel(registry_id, editor, context, label, icon, order, default_open, description)` decorator. Same pattern as `@editor`: sets `class_identity: PanelIdentity` only, does NOT register. See spec Section 2.4.
- **`registry.py`** — `PanelRegistry(BaseRegistry)`. Extends BaseRegistry. Maintains a secondary index `_index: Dict[tuple, List[type]]` keyed by `(editor_key, context)`. `_register_class()` calls `_index_panel()` after `super()._register()`. `_unregister_class()` calls `_deindex_panel()` before `super()._unregister()`. Methods: `get_panels(editor_key, context)`, `get_all_for_editor(editor_key)`. See spec Section 2.4.
- **`__init__.py`** — export BasePanel, PanelLayout, PanelIdentity, panel decorator, PanelRegistry

**Step 1.5: Create workspace system — `packages/haywire-core/src/haywire/ui/workspace/`**

Create:

- **`__init__.py`**
- **`workspace_state.py`** — Dataclasses: `AreaState(editor_key, visible, size)`, `TabState(editor_key, label, metadata)`, `MiddleAreaState(tabs, active_tab_index, bottom_visible, bottom_size, bottom_editor_key)`, `WorkspaceState(name, left_bar_active, left, middle, right, right_bar_active)`. See spec Section 2.5.
- **`manager.py`** — `WorkspaceManager`. Import all four dataclasses at top of file (needed for DEFAULT_PRESETS). Holds `presets` dict and `active` workspace. Methods: `switch(name)`, `save_current(name)`, `get_preset_names()`, `_load_user_presets(project_path)`, `_persist_presets()`. See spec Section 2.5.

**Step 1.6: Create session — `packages/haywire-core/src/haywire/ui/session.py`**

Implement `Session` class. Holds session_id (uuid), `SessionContext`, `WorkspaceManager`, dict of active editor instances keyed by area slot, list of context change subscriber callbacks. Methods: `notify_context_changed(event)`, `subscribe_context_changes(callback)`, `unsubscribe_context_changes(callback)`, `cleanup()`. See spec Section 2.6.

**Step 1.7: Wire into DI — update `packages/haywire-core/src/haywire/core/di/config.py`**

Add two providers to `HaywireModule`:

```python
from ...ui.editor_framework.registry import EditorTypeRegistry  # temp import
from ...ui.panel.registry import PanelRegistry

@provider
@singleton
def provide_editor_type_registry(self) -> EditorTypeRegistry:
    registry = EditorTypeRegistry()
    # register_builtin_editors(registry)  # stub — uncomment in Phase 4
    return registry

@provider
@singleton
def provide_panel_registry(self) -> PanelRegistry:
    registry = PanelRegistry()
    # register_builtin_panels(registry)  # stub — uncomment in Phase 5
    return registry
```

Create stub files:

- `packages/haywire-core/src/haywire/ui/editors/builtins.py` — empty `register_builtin_editors(registry)` function
- `packages/haywire-core/src/haywire/ui/panels/builtins.py` — empty `register_builtin_panels(registry)` function

**Step 1.8: Create `__init__.py` files**

Ensure all new packages have `__init__.py` with appropriate exports.

**Step 1.9: Write tests**

Create `tests/ui/test_editor_registry.py`:

- Test that `@editor` decorator sets `class_identity` correctly (registry_key, label, icon, canvas_area)
- Test that `@editor` does NOT auto-register (registry must be empty until `_register_class()` is called)
- Test `_register_class()` adds the class; `get()` retrieves it
- Test `_unregister_class()` removes it and clears the registry entry
- Test `get_by_default_area()` filters correctly
- Test `_class_filter()` returns True only for proper BaseEditor subclasses with class_identity

Create `tests/ui/test_panel_registry.py`:

- Test that `@panel` decorator sets `class_identity` correctly
- Test `_register_class()` adds the class and indexes it by (editor_key, context)
- Test `get_panels()` returns sorted by `class_identity.order`
- Test `get_all_for_editor()` groups by context
- Test `_unregister_class()` removes from both primary store and index
- Test `_class_filter()` returns True only for proper BasePanel subclasses with class_identity

Create `tests/ui/test_workspace_state.py`:

- Test WorkspaceState serialization to dict (via `dataclasses.asdict`) and back
- Test WorkspaceManager default presets exist and are valid WorkspaceState instances
- Test WorkspaceManager.switch() changes active workspace

---

### PHASE 2: Rename Existing Editor Folder

**Goal:** Free up the `editor/` namespace for the new framework. Must be a single atomic commit.

#### Step 2.1: Rename canvas folder

```
packages/haywire-core/src/haywire/ui/editor/
  → packages/haywire-core/src/haywire/ui/graph_canvas/
```

Use `git mv` to preserve history:
```
git mv packages/haywire-core/src/haywire/ui/editor packages/haywire-core/src/haywire/ui/graph_canvas
```

**Step 2.2: Update all imports**

Do a project-wide search for `haywire.ui.editor.` and replace with `haywire.ui.graph_canvas.`. Also check:

- `from haywire.ui.editor import ...`
- `from .editor import ...`
- `from haywire.ui.editor.graph_canvas_manager import ...`
- `from haywire.ui.editor.graph_canvas_vue import ...`
- `from haywire.ui.editor.popup_context_menu import ...`
- `from haywire.ui.editor.event_definitions import ...`
- `from haywire.ui.editor.event_handlers import ...`
- Any string references in configuration or `__init__.py` re-exports

**Step 2.3: Move editor framework to final location**

```
packages/haywire-core/src/haywire/ui/editor_framework/
  → packages/haywire-core/src/haywire/ui/editor/
```

Update the temporary DI import in `config.py`:

```python
# Before (Step 1.7):
from ...ui.editor_framework.registry import EditorTypeRegistry
# After:
from ...ui.editor.registry import EditorTypeRegistry
```

Update any other imports that referenced `editor_framework` to now use `editor`.

**Step 2.4: Verify**

Run all existing tests. Verify the application starts and the graph editor works as before.

---

### PHASE 3: App Shell & Layout

**Goal:** Implement the workspace layout using NiceGUI. Editors are placeholders at this stage.

**Step 3.1: Create `packages/haywire-core/src/haywire/ui/app_shell.py`**

Implement the `AppShell` class that renders the full layout:

```
TopBar | ActivityBar | Left Area | Middle Area (tabs + bottom split) | Right Area | ContextBar | StatusBar
```

**NiceGUI implementation approach:**

Use a combination of `ui.row()`, `ui.column()`, and `ui.splitter()` with Tailwind classes and inline styles:

```python
# Pseudocode layout structure:
with ui.column().classes('w-full h-screen'):  # full viewport
    # TopBar
    with ui.row().classes('w-full h-12 bg-gray-800'):
        pass

    # Main content area
    with ui.row().classes('w-full flex-grow overflow-hidden'):
        # ActivityBar (narrow icon column)
        with ui.column().classes('w-12 bg-gray-900'):
            pass

        # Left Area (collapsible)
        if ws.left.visible:
            with ui.column().style(f'width: {ws.left.size}px'):
                pass  # editor container

        # Middle + Bottom (takes remaining space)
        with ui.column().classes('flex-grow'):
            with ui.tabs() as tabs:
                for tab in ws.middle.tabs:
                    ui.tab(tab.label)
            with ui.tab_panels(tabs):
                for tab in ws.middle.tabs:
                    with ui.tab_panel(tab.label):
                        pass  # editor container

            if ws.middle.bottom_visible:
                with ui.column().style(f'height: {ws.middle.bottom_size}px'):
                    pass  # editor container

        # Right Area (collapsible)
        if ws.right.visible:
            with ui.column().style(f'width: {ws.right.size}px'):
                pass  # editor container

        # ContextBar (narrow icon column)
        with ui.column().classes('w-12 bg-gray-900'):
            pass

    # StatusBar
    with ui.row().classes('w-full h-6 bg-gray-800'):
        pass
```

AppShell responsibilities:

- Read active `WorkspaceState` for layout dimensions and editor keys
- Create named containers for each area slot
- Wire ActivityBar icon clicks to swap the Left Area editor
- Wire ContextBar icon clicks to swap the Right Area editor
- Support tab creation/removal in the Middle Area
- Support toggling Bottom Area visibility

**Step 3.2: Wire into NiceGUI app**

Modify `packages/haywire-app/src/haywire_app/app.py` — wherever the NiceGUI `@ui.page('/')` handler is defined:

1. Create a `Session(project_state, project_path)`
2. Create `AppShell(session)`
3. Call `app_shell.render()`

At this stage, all areas show placeholder content (`ui.label(f'Editor: {editor_key}')`) since actual editors are not yet wired.

**Step 3.3: Validate**

Layout renders correctly. Areas visible/hidden per workspace state. Tabs work. ActivityBar/ContextBar switch placeholder content.

---

### PHASE 4: Wrap Existing Graph Editor

**Goal:** Make the existing graph canvas work as a proper BaseEditor inside the new layout.

**Step 4.1: Create `packages/haywire-core/src/haywire/ui/editors/graph_editor.py`**

Implement `GraphEditor(BaseEditor)` using the `@editor` decorator:

```python
@editor(
    registry_id='graph_editor',
    label='Graph Editor',
    icon='account_tree',
    canvas_area='middle',
    description='Visual node graph editor.',
)
class GraphEditor(BaseEditor):
    def render(self, container, context):
        from haywire.ui.graph_canvas.graph_canvas_manager import GraphCanvasManager
        self._canvas_manager = GraphCanvasManager(...)
        # render into container
        # wire selection callbacks → session.notify_context_changed()
        ...

    def on_context_changed(self, event, context):
        # handle ACTIVE_GRAPH_CHANGED, DATA_MUTATED from other sessions
        ...
```

Key integration points:

- GraphCanvasManager selection callbacks → update `session.context.active_node` / `active_edge`, then call `session.notify_context_changed(ContextChangedEvent(SELECTION_CHANGED))`
- GraphCanvasManager graph mutation callbacks → `session.notify_context_changed(ContextChangedEvent(DATA_MUTATED))`

**Step 4.2: Update `editors/builtins.py` to register GraphEditor**

```python
def register_builtin_editors(registry: EditorTypeRegistry) -> None:
    from haywire.ui.editors.graph_editor import GraphEditor
    registry._register_class(GraphEditor, library_identity=None)
```

Uncomment the `register_builtin_editors(registry)` call in the DI provider (Step 1.7).

#### Step 4.3: Update AppShell to instantiate real editors

Modify AppShell to:

1. Look up the editor class from `EditorTypeRegistry` using the WorkspaceState's `editor_key`
2. Instantiate the editor
3. Call `editor.render(container, session.context)`
4. Subscribe the editor to context changes via `session.subscribe_context_changes(editor.on_context_changed)`

**Step 4.4: Validate**

The graph editor works exactly as before, now rendered inside the AppShell layout.

---

### PHASE 5: Properties Editor & Panels

**Goal:** Implement the context-sensitive properties sidebar.

**Step 5.1: Flesh out PanelLayout**

Implement PanelLayout methods in `packages/haywire-core/src/haywire/ui/panel/base.py`:

```python
class PanelLayout:
    def __init__(self, container):
        self._container = container

    def label(self, text, **style):
        with self._container:
            return ui.label(text)

    def row(self):
        return ui.row()

    def column(self):
        return ui.column()

    def separator(self):
        ui.separator()

    def widget(self, widget_key, port, **config):
        from haywire.ui.widget.factory import WidgetFactory
        # render a registered widget into the panel
        ...

    def button(self, text, on_click=None, **style):
        return ui.button(text, on_click=on_click)

    def expansion(self, title, icon=None):
        return ui.expansion(title, icon=icon)
```

**Step 5.2: Create `packages/haywire-core/src/haywire/ui/editors/properties_editor.py`**

```python
@editor(
    registry_id='properties',
    label='Properties',
    icon='tune',
    canvas_area='right',
    description='Context-sensitive property panels for the active selection.',
)
class PropertiesEditor(BaseEditor):
    def __init__(self):
        self._panel_instances = {}
        self._panel_containers = {}
        self._container = None

    def render(self, container, context):
        self._container = container
        self._rebuild_panels(context)

    def on_context_changed(self, event, context):
        self._rebuild_panels(context)

    def _rebuild_panels(self, context):
        active_contexts = self._resolve_contexts(context)
        # for each context: query PanelRegistry, run poll(), render passing panels
        # as ui.expansion() with PanelLayout, hide/remove failing panels
        ...

    def _resolve_contexts(self, context):
        contexts = []
        if context.active_node:
            contexts.append('node')
        if context.active_edge:
            contexts.append('edge')
        if context.active_graph:
            contexts.append('graph')
        return contexts
```

**Step 5.3: Create built-in panels in `packages/haywire-core/src/haywire/ui/panels/`**

Create `__init__.py` and these panels. Note: use `registry_id=` (not `key=`) in the decorator.

**`node_properties_panel.py`:**
```python
@panel(registry_id='node_properties', editor='properties', context='node',
       label='Node Properties', icon='info', order=10)
class NodePropertiesPanel(BasePanel):
    @classmethod
    def poll(cls, ctx): return ctx.active_node is not None
    def draw(self, ctx, layout):
        node = ctx.active_node
        layout.label(f"Name: {node.node.identity.label}")
        layout.label(f"Class: {node.node.__class__.__name__}")
        layout.label(f"ID: {node.node_id}")
```

**`node_ports_panel.py`:**
```python
@panel(registry_id='node_ports', editor='properties', context='node',
       label='Ports', icon='settings_input_component', order=20)
class NodePortsPanel(BasePanel):
    @classmethod
    def poll(cls, ctx): return ctx.active_node is not None
    def draw(self, ctx, layout):
        node = ctx.active_node
        # list inlets, outlets, config ports with types and current values
        ...
```

**`node_settings_panel.py`:**
```python
@panel(registry_id='node_settings', editor='properties', context='node',
       label='Settings', icon='settings', order=30)
class NodeSettingsPanel(BasePanel):
    @classmethod
    def poll(cls, ctx): return ctx.active_node is not None
    def draw(self, ctx, layout):
        # display node settings (LOCAL_ONLY flags, renderer selection, etc.)
        ...
```

**`graph_info_panel.py`:**
```python
@panel(registry_id='graph_info', editor='properties', context='graph',
       label='Graph Info', icon='info', order=10)
class GraphInfoPanel(BasePanel):
    @classmethod
    def poll(cls, ctx): return ctx.active_graph is not None
    def draw(self, ctx, layout):
        graph = ctx.active_graph
        layout.label(f"Nodes: {len(graph.nodes)}")
        layout.label(f"Edges: {len(graph.edges)}")
```

**`edge_info_panel.py`:**
```python
@panel(registry_id='edge_info', editor='properties', context='edge',
       label='Edge Info', icon='link', order=10)
class EdgeInfoPanel(BasePanel):
    @classmethod
    def poll(cls, ctx): return ctx.active_edge is not None
    def draw(self, ctx, layout):
        edge = ctx.active_edge
        layout.label(f"From: {edge.source_node_id}.{edge.source_port}")
        layout.label(f"To: {edge.target_node_id}.{edge.target_port}")
```

**Step 5.4: Update `panels/builtins.py` and uncomment DI call**

```python
def register_builtin_panels(registry: PanelRegistry) -> None:
    from haywire.ui.panels.node_properties_panel import NodePropertiesPanel
    from haywire.ui.panels.node_ports_panel import NodePortsPanel
    from haywire.ui.panels.node_settings_panel import NodeSettingsPanel
    from haywire.ui.panels.graph_info_panel import GraphInfoPanel
    from haywire.ui.panels.edge_info_panel import EdgeInfoPanel
    for cls in [NodePropertiesPanel, NodePortsPanel, NodeSettingsPanel,
                GraphInfoPanel, EdgeInfoPanel]:
        registry._register_class(cls, library_identity=None)
```

Also register PropertiesEditor in `editors/builtins.py`.

**Step 5.5: Wire GraphEditor selection → PropertiesEditor update**

When user selects a node in GraphEditor:

1. GraphEditor sets `session.context.active_node = selected_wrapper`
2. GraphEditor calls `session.notify_context_changed(ContextChangedEvent(SELECTION_CHANGED))`
3. PropertiesEditor receives event via `on_context_changed()` and calls `_rebuild_panels()`

**Step 5.6: Validate**

Select a node → Properties Editor shows node panels. Select an edge → edge panel. Clear selection → graph-level panels. Test that poll() filtering works.

---

### PHASE 6: Console Editor

**Step 6.1: Create `packages/haywire-core/src/haywire/ui/editors/console_editor.py`**

```python
@editor(
    registry_id='console',
    label='Console',
    icon='terminal',
    canvas_area='bottom',
    description='Python console and execution log output.',
)
class ConsoleEditor(BaseEditor):
    def render(self, container, context):
        with container:
            self._log = ui.log(max_lines=500).classes('w-full h-full')
            # subscribe to execution engine log stream

    def on_context_changed(self, event, context):
        pass  # console doesn't react to selection changes
```

Register in `editors/builtins.py`.

---

### PHASE 7: Library Browser & Detail Editors

**Goal:** Implement the three library-browsing editors in haywire-app. These are fresh, proper `BaseEditor` subclasses that implement the same functionality as the prototypical `LibraryManagerPage` in `library_manager_ui.py`, split into three separate editors.

**Before implementing:** Study both `library_manager.py` (data model: `InstalledLibrary`, `MarketplaceEntry`, service operations) and `library_manager_ui.py` (`LibraryManagerPage`: three-panel monolith that defines the full feature set). The left/center/right panels of `LibraryManagerPage` map directly to the three new editors below.

**Step 7.1: Create `packages/haywire-app/src/haywire_app/editors/__init__.py`**

**Step 7.2: Create `packages/haywire-app/src/haywire_app/editors/library_browser.py`**

Fresh implementation of the **left panel** of `LibraryManagerPage`.

```python
@editor(
    registry_id='library_browser',
    label='Library Browser',
    icon='library_books',
    canvas_area='left',
    description='Browse available node libraries and marketplace.',
)
class LibraryBrowser(BaseEditor):
    """
    Searchable / filterable library list with tabs: Enabled / Disabled / Available.
    Emits ACTIVE_LIBRARY_CHANGED and ACTIVE_COMPONENT_CHANGED context events.
    """
    def render(self, container, context):
        # Build tabbed list; wire selections to emit context changes
        ...

    def on_context_changed(self, event, context):
        # React to library system changes (installs, hot-reloads)
        ...
```

When user clicks a library: update `session.context.active_library`, emit `ContextChangedEvent(ACTIVE_LIBRARY_CHANGED)`. When user clicks a component within a library: update `session.context.active_component`, emit `ContextChangedEvent(ACTIVE_COMPONENT_CHANGED)`.

**Step 7.3: Create `packages/haywire-app/src/haywire_app/editors/library_detail_editor.py`**

Fresh implementation of the **center panel** of `LibraryManagerPage` (marketplace header + installed-library tabs).

```python
@editor(
    registry_id='library_detail',
    label='Library Detail',
    icon='info',
    canvas_area='middle',
    description='Detail view for the selected library.',
)
class LibraryDetailEditor(BaseEditor):
    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        if event.change_type == ContextChangeType.ACTIVE_LIBRARY_CHANGED:
            # re-render for context.active_library
            ...
```

Content mirrors the center panel of `LibraryManagerPage`: marketplace header (description, author, version, tags, source, docs link, install/uninstall button) + for installed libraries: tabbed inventory of nodes/widgets/renderers/types/adapters + enable/disable/rename controls.

**Step 7.4: Create `packages/haywire-app/src/haywire_app/editors/component_detail_editor.py`**

Fresh implementation of the **right panel** of `LibraryManagerPage` (per-component docs, hidden until a component is clicked).

```python
@editor(
    registry_id='component_detail',
    label='Component Detail',
    icon='widgets',
    canvas_area='right',
    description='Documentation for the selected node or widget.',
)
class ComponentDetailEditor(BaseEditor):
    def render(self, container, context):
        ...

    def on_context_changed(self, event, context):
        if event.change_type == ContextChangeType.ACTIVE_COMPONENT_CHANGED:
            # re-render for context.active_component
            ...
```

Content mirrors the right panel of `LibraryManagerPage`: node identity, port listing, live widget preview (for widget components), QUICKREF.md block. Adapts by component type (node / widget / renderer / type / adapter).

#### Step 7.5: Register library editors in haywire-app startup

In `packages/haywire-app/src/haywire_app/app.py`, after creating the injector, register the library editors directly into the `EditorTypeRegistry`:

```python
from haywire_app.editors.library_browser import LibraryBrowser
from haywire_app.editors.library_detail_editor import LibraryDetailEditor
from haywire_app.editors.component_detail_editor import ComponentDetailEditor

editor_registry = injector.get(EditorTypeRegistry)
for cls in [LibraryBrowser, LibraryDetailEditor, ComponentDetailEditor]:
    editor_registry._register_class(cls, library_identity=None)
```

Note: these editors are NOT registered via `register_builtin_editors()` (that's framework-only). They are app-level registrations done at startup.

#### Step 7.6: Validate

Clicking a library in the left panel → LibraryDetailEditor updates in the middle area. Clicking a node in the detail view → ComponentDetailEditor updates in the right area.

---

### PHASE 8: Multi-Session Support

**Step 8.1: Create `packages/haywire-core/src/haywire/ui/session_manager.py`**

```python
class SessionManager:
    """Tracks all active sessions for cross-session notifications."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create_session(self, project_state, project_path=None) -> Session:
        session = Session(project_state, project_path)
        self._sessions[session.session_id] = session
        return session

    def remove_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].cleanup()
            del self._sessions[session_id]

    def broadcast_data_mutation(self, source_session_id: str, detail=None):
        """Notify all OTHER sessions that graph data changed."""
        event = ContextChangedEvent(
            change_type=ContextChangeType.DATA_MUTATED,
            source_editor=None,
            detail=detail,
        )
        for sid, session in self._sessions.items():
            if sid != source_session_id:
                session.notify_context_changed(event)
```

#### Step 8.2: Wire into NiceGUI lifecycle in haywire-app

- `app.on_connect` → `SessionManager.create_session()`
- `app.on_disconnect` → `SessionManager.remove_session()`
- Graph mutations → `SessionManager.broadcast_data_mutation()`

---

### PHASE 9: Workspace Persistence

**Step 9.1:** Implement `WorkspaceManager._persist_presets()` and `_load_user_presets()` (see spec Section 2.5 for the complete implementation).

**Step 9.2:** Add workspace switcher dropdown to TopBar in AppShell.

**Step 9.3:** Add "Save Workspace As..." dialog and "Reset Workspace" control.

**Step 9.4:** Ship default presets: "Graph Editing", "Development", "Debugging".

---

## Important Notes for Implementation

1. **Do not break existing functionality.** The graph editor, renderers, and widgets must continue to work throughout the refactoring. Wrap existing code rather than rewriting it.

2. **Follow existing patterns.** Look at how `@renderer` and `SkinRegistry` work — `@renderer` only sets `class_identity`, never auto-registers. `SkinRegistry` extends `BaseRegistry`. The `@editor` and `@panel` decorators must follow the identical pattern. Look at `WidgetFactory` for how factories consume registries.

3. **Registry instances come from DI.** Never access `EditorTypeRegistry` or `PanelRegistry` via a bare `instance()` singleton. Always retrieve them through the injector (or inject via constructor). The `register_builtin_*` bootstrap functions call `registry._register_class()` directly and are only called from the DI provider.

4. **Imports matter.** Use relative imports within packages. Use absolute imports for cross-package references. Always check for circular import risks and use `TYPE_CHECKING` guards.

5. **NiceGUI specifics.** NiceGUI uses a context-manager pattern (`with ui.card() as card:`). Elements are created by instantiation and automatically added to the current parent. Use `.classes()` for Tailwind, `.style()` for inline CSS, `.props()` for Quasar props.

6. **Test after each phase.** Run `uv run pytest` and verify the app starts after each phase.
