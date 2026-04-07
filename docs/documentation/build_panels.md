# Building Panels

Panels are context-sensitive sub-sections that appear inside panel-aware editors — most commonly the **Properties** editor on the right sidebar. Unlike editors, panels do not manage their own area; they are discovered at runtime from the `PanelRegistry` and rendered inside a host editor's layout. This guide covers everything you need to create, configure, and register a custom panel.

For background on how panels fit into the larger UI architecture, see [haywire_app.md](architecture/haywire_app.md). For building the editors that host panels, see [build_editors.md](build_editors.md).

## Table of Contents

1. [What Is a Panel?](#1-what-is-a-panel)
2. [Quick Start](#2-quick-start)
3. [The @panel Decorator](#3-the-panel-decorator)
4. [Implementing BasePanel](#4-implementing-basepanel)
5. [The PanelLayout API](#5-the-panellayout-api)
6. [Scopes](#6-scopes)
7. [Registering a Panel](#7-registering-a-panel)
8. [Panel Ordering and Grouping](#8-panel-ordering-and-grouping)
9. [Building a Custom Panel-Aware Editor](#9-building-a-custom-panel-aware-editor)
10. [Compact Field Styling](#10-compact-field-styling)
11. [Best Practices](#11-best-practices)
12. [Full Example: A Custom Node Metrics Panel](#12-full-example-a-custom-node-metrics-panel)
13. [Custom Context Menu Triggers](#13-custom-context-menu-triggers)
14. [Port Context Menu Triggers](#14-port-context-menu-triggers)

---

## 1. What Is a Panel?

A panel is a class that:

- Is decorated with `@panel(...)`, which stamps it with a `PanelIdentity` including the target editor and scope(s)
- Inherits from `BasePanel`
- Implements `poll(context) → bool` to declare when it should be visible
- Implements `draw(context, layout)` to render its content

Panels are rendered by a **panel-aware editor** (such as `PropertiesEditor`) that queries the `PanelRegistry` at runtime. The editor calls `poll()` on each candidate panel; those returning `True` are rendered inside a collapsible `ui.expansion` element, sorted by their `order` value.

This design means:

- Panel authors never worry about layout positioning
- Panels appear and disappear automatically as the selection changes
- Any number of panels from any library can contribute to the same editor section
- Hot-reload works: panels update in place when the library reloads

---

## 2. Quick Start

Here is a minimal panel that displays the active node's name and ID when a node is selected:

```python
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

@panel(
    registry_id='my_node_info',
    editor='properties',   # target editor registry_id
    scope='node',          # visible when a node is active
    label='My Node Info',
    icon='info',
    order=50,
)
class MyNodeInfoPanel(BasePanel):

    @classmethod
    def poll(cls, context) -> bool:
        return context.active_node is not None

    def draw(self, context, layout: PanelLayout) -> None:
        node = context.active_node
        layout.label(f'Name: {getattr(node, "name", "?")}')
        layout.label(f'ID:   {getattr(node, "node_id", "?")}')
        layout.separator()
        layout.label(f'Class: {type(node).__name__}')
```

After [registering it](#7-registering-a-panel), the panel appears automatically in the Properties sidebar whenever a node is selected and the **Node** scope tab is active.

---

## 3. The @panel Decorator

```python
@panel(
    registry_id:   str | None            = None,   # unique short ID, defaults to class name
    editor:        str,                            # REQUIRED — target editor registry_id
    scope:         str | list[str],                # REQUIRED — scope ID or list of scope IDs
    label:         str | None            = None,   # display label in expansion header
    icon:          str | None            = None,   # Material Design icon for expansion header
    order:         int                   = 100,    # sort order (lower = higher position)
    default_open:  bool                  = True,   # whether expansion starts open
    description:   str                   = '',
)
```

### Required parameters

**`editor`** is the `registry_id` (short form) of the editor that will host this panel.
For the built-in Properties sidebar use `'properties'`. For a custom panel-aware editor, use its own `registry_id`.

**`scope`** is a scope ID string (or list of IDs) that determines which toolbar tab(s) this
panel appears under. The built-in scopes for the Properties editor are listed in
[Section 6](#6-scopes). Pass a list to make the panel appear in multiple tabs:

```python
scope='node'                     # single scope
scope=['my_lib', 'node']         # appears in both tabs
```

The `scope` value is always stored internally as `list[str]` regardless of whether a string or list is passed.

### What the decorator does

- Sets `MyPanel.class_identity` (a `PanelIdentity` dataclass) containing all metadata
- Sets `MyPanel.class_library` derived from the module
- Computes the full `registry_key` as `{library_id}:panel:{registry_id}`
- Normalises `scope` to `list[str]`
- Validates that the class is a `BasePanel` subclass

The decorator does **not** register the class. Registration is always explicit.

### order

Lower `order` values appear higher in the panel list. Built-in panels use:

| Panel                 | Order |
| --------------------- | ----- |
| `NodePropertiesPanel` | 10    |
| `NodePortsPanel`      | 20    |
| `NodeSettingsPanel`   | 30    |
| `GraphInfoPanel`      | 10    |
| `EdgeInfoPanel`       | 10    |

Position your panels relative to these values. Use `order=50` as a safe default for
library panels that should appear after the built-in ones.

---

## 4. Implementing BasePanel

### `poll(cls, context) → bool` (classmethod)

Called before every render cycle to determine whether the panel should be shown. The method is a **classmethod** — no instance is created until `poll()` returns `True`. Keep it fast and side-effect free:

```python
@classmethod
def poll(cls, context) -> bool:
    # Show only when a node is selected AND it has output ports
    node = context.active_node
    if node is None:
        return False
    outlets = node.get_ports(is_port_type=PortType.OUTLET)
    return len(outlets) > 0
```

Expensive operations (database lookups, file reads) do not belong in `poll()`. If your
panel requires data that takes time to load, always show the panel and display a loading state inside `draw()`.

When a panel is registered under multiple scopes, `poll()` receives the full `SessionContext`
including `context.metadata['properties_scope']` (the active scope ID), which lets you
vary visibility per scope:

```python
@classmethod
def poll(cls, context) -> bool:
    active_scope = context.metadata.get('properties_scope')
    if active_scope == 'node':
        return context.active_node is not None and isinstance(
            context.active_node.node, MyLibNode
        )
    return True   # always visible in other scopes
```

### `draw(context, layout) → None`

Called when `poll()` returned `True`. Use the `PanelLayout` helper to build content.
An `ui.expansion` wrapper is provided automatically by the host editor — do not add one yourself:

```python
def draw(self, context, layout: PanelLayout) -> None:
    node = context.active_node
    with layout.column():
        layout.label(f'Outlets: {len(node.outlets)}')
        for outlet in node.outlets:
            with layout.row():
                layout.label(outlet.id)
                layout.label(outlet.flow_type.name).classes('text-xs text-gray-400')
```

When a panel appears in multiple scopes it can also branch its content on the active scope:

```python
def draw(self, context, layout: PanelLayout) -> None:
    active_scope = context.metadata.get('properties_scope')
    if active_scope == 'node':
        self._draw_node_overrides(context, layout)
    else:
        self._draw_library_defaults(context, layout)
```

### `on_context_changed(context, layout) → None`

Optional incremental update hook. Called when a context change event fires and the panel is already visible. The default implementation does nothing (the host editor does a full rebuild instead). Implement it when you want to update only specific elements without rebuilding the whole panel:

```python
def on_context_changed(self, context, layout) -> None:
    # Update the node name label without rebuilding the whole panel
    if self._name_label:
        node = context.active_node
        self._name_label.text = getattr(node, 'name', '?') if node else '?'
```

Note: `on_context_changed` is an advanced hook. Most panels do not need it — the host editor handles rebuilding by calling `poll()` + `draw()` on every relevant context change.

---

## 5. The PanelLayout API

`PanelLayout` is a thin wrapper around a NiceGUI container. It provides a stable, styled
interface that insulates panels from direct NiceGUI dependency.

### Available methods

```python
layout.label(text: str, **kwargs) -> ui.label
    # Adds a text label. Pass NiceGUI .classes() / .props() via kwargs.

layout.row() -> ContextManager
    # Returns a ui.row() context manager for horizontal arrangement.

layout.column() -> ContextManager
    # Returns a ui.column() context manager for vertical arrangement.

layout.separator() -> None
    # Adds a visual divider line.

layout.button(text: str, on_click=None, **kwargs) -> ui.button
    # Adds a button.

layout.expansion(title: str, icon: str = None) -> ContextManager
    # Adds a nested collapsible section inside the panel.

layout.widget(widget_key: str, port: Any, **config) -> Any
    # Renders a registered Haywire widget bound to a port.
```

### Composing layouts

```python
def draw(self, context, layout: PanelLayout) -> None:
    node = context.active_node

    # Simple labels
    layout.label(f'Class: {type(node).__name__}')
    layout.separator()

    # Row layout
    with layout.row():
        layout.label('Inlets:')
        layout.label(str(len(node.inlets)))

    # Nested collapsible section
    with layout.expansion('Advanced', icon='settings'):
        layout.label(f'Registry key: {node.class_identity.registry_key}')

    # Action button
    layout.button('Copy ID', on_click=lambda: ui.run_javascript(
        f'navigator.clipboard.writeText("{node.node_id}")'
    ))
```

### Using NiceGUI directly inside draw()

When `PanelLayout` does not provide a method you need, you can drop into NiceGUI directly inside a layout context:

```python
def draw(self, context, layout: PanelLayout) -> None:
    with layout.column():
        # PanelLayout method
        layout.label('Ports')
        layout.separator()
        # Raw NiceGUI
        ui.badge('3 inlets').props('color=blue')
        ui.badge('2 outlets').props('color=green')
```

This works because `PanelLayout` uses NiceGUI's standard slot context under the hood.

### Widget integration

The `layout.widget()` method renders a registered Haywire widget for a given port. This is the primary way to display interactive controls for node config ports in property panels:

```python
def draw(self, context, layout: PanelLayout) -> None:
    node = context.active_node
    for port in getattr(node, 'config_ports', []):
        layout.label(port.id)
        layout.widget(port.widget_key or 'default', port)
```

---

## 6. Scopes

A **scope** is a top-level navigation tab in a panel-aware editor. In the Properties editor
it appears as an icon button in the left toolbar. Each scope has a unique `scope_id` string
that panels reference via `@panel(scope=...)`.

Scopes are defined by `ScopeDescriptor` objects and registered into `PanelRegistry` via
`register_scope()`. The host editor queries the registry to build its toolbar and to know
which panels belong to each tab.

### Built-in scopes (Properties editor)

Registered by `haybale-studio` in its `register_components()`:

| scope_id    | Icon            | Label          | Available when                     |
| ----------- | --------------- | -------------- | ---------------------------------- |
| `app`       | `settings`      | Application    | always                             |
| `execution` | `play_circle`   | Execution      | always                             |
| `canvas`    | `grid_on`       | Canvas & Nodes | always                             |
| `debug`     | `bug_report`    | Debug          | always                             |
| `graph`     | `account_tree`  | Graph          | `context.active_graph` is not None |
| `node`      | `widgets`       | Node           | `context.active_node` is not None  |
| `edge`      | `cable`         | Edge           | `context.active_edge` is not None  |

The PropertiesEditor only auto-switches scope when the current scope becomes unavailable (e.g. the user deselects a node while on the `node` tab). Manual navigation always takes
priority.

### Context menu scopes (editor `'context_menu'`)

The canvas right-click popup uses a separate editor key — `'context_menu'` — with its own set of built-in scopes. These are **not** tabs; the scope is chosen automatically by the pipeline based on what the user right-clicked.

| hardcodeed scope_id      | Triggered when                                               |
| ------------- | ------------------------------------------------------------ |
| `canvas`      | Right-click on empty canvas space                            |
| `node`        | Right-click on a node                                        |
| `edge`        | Right-click on a connection                                  |
| `selection`   | Right-click while one ormultiple elements are selected             |
| `<custom scope>` | Right-click a node with (custom scope) |

See [Section 13](#13-custom-context-menu-triggers) for the custom scope mechanism.

Panels contributing to the context menu popup work identically to properties panels, except they use `editor='context_menu'` and do not get the expansion wrapper — the `SessionContextMenuProvider` renders them directly into a floating `Popup`:

```python
@panel(
    editors='context_menu',
    scopes='node',
    label='Delete Node',
    icon='delete',
    order=10,
)
class DeleteNodePanel(BasePanel):
    @classmethod
    def poll(cls, context) -> bool:
        return context.active_node is not None

    def draw(self, context, layout: PanelLayout) -> None:
        ...
```

### Registering a custom scope

To add a new tab to the Properties editor, register a `ScopeDescriptor` before scanning the panels folder:

```python
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.panel.scope import ScopeDescriptor

class MyLibrary(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent

        # 1. Register the scope tab first
        panel_registry = self.get_registry(PanelRegistry)
        panel_registry.register_scope('properties', ScopeDescriptor(
            scope_id='my_lib',
            label='My Library',
            icon='extension',
            order=80,
            poll=lambda ctx: True,   # always visible once library is loaded
        ))

        # 2. Then register the panels that reference it
        self.add_folder_to_registry(
            folder_path=str(base_path / 'panels'),
            registry_cls=PanelRegistry,
        )
```

`ScopeDescriptor.poll` is a callable `(SessionContext) -> bool` that controls whether the tab is available (shown at full opacity and clickable) or unavailable (dimmed, not clickable). Use it to hide the tab when the library has nothing meaningful to show.

### Multi-scope panels

A panel can appear in more than one scope tab by passing a list to `scope=`:

```python
@panel(
    registry_id='my_lib_render_settings',
    editor='properties',
    scope=['my_lib', 'node'],   # appears under both tabs
    label='Render Settings',
    order=50,
)
class MyLibRenderSettingsPanel(BasePanel):

    @classmethod
    def poll(cls, context) -> bool:
        active_scope = context.metadata.get('properties_scope')
        if active_scope == 'node':
            # Only show for nodes that belong to this library
            return context.active_node is not None and isinstance(
                context.active_node.node, MyLibNode
            )
        return True   # always visible in the my_lib tab

    def draw(self, context, layout: PanelLayout) -> None:
        active_scope = context.metadata.get('properties_scope')
        if active_scope == 'node':
            self._draw_node_overrides(context, layout)
        else:
            self._draw_library_defaults(context, layout)
```

---

## 7. Registering a Panel

### Library-level (ships inside a haybale library)

Place decorated panel classes in a folder and scan it in `register_components()`. If your
panels reference a custom scope, register that scope first:

```python
from haywire.ui.panel.registry import PanelRegistry

class MyLibrary(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent

        # Register custom scopes before panels
        panel_registry = self.get_registry(PanelRegistry)
        panel_registry.register_scope('properties', ScopeDescriptor(
            scope_id='my_lib',
            label='My Library',
            icon='extension',
            order=80,
        ))

        # Register panels (folder scan picks up all @panel-decorated classes)
        self.add_folder_to_registry(
            folder_path=str(base_path / 'panels'),
            registry_cls=PanelRegistry,
        )
```

Any `@panel`-decorated `BasePanel` subclass found in the folder (recursively) is registered. Non-decorated classes are silently ignored.

### Panels that only use built-in scopes

If your panels only reference built-in scopes (`node`, `edge`, `graph`, `app`, etc.) there
is no need to call `register_scope()` — just scan the folder:

```python
self.add_folder_to_registry(
    folder_path=str(base_path / 'panels'),
    registry_cls=PanelRegistry,
)
```

### Hot-reload behaviour

When a library is hot-reloaded, its panels are unregistered and re-registered automatically. The `PanelRegistry` index (keyed by `(editor_key, scope_id)`) is updated in place, so the next time the host editor rebuilds it picks up the new panel implementation. There is no need to navigate away or restart the server.

---

## 8. Panel Ordering and Grouping

### Order

The `order` parameter controls the top-to-bottom position of the panel within a scope. Panels with the same `order` value are sorted alphabetically by `registry_id`.

Recommended convention:

| Range    | Use                                    |
| -------- | -------------------------------------- |
| 0 – 29   | Identity / core info (name, ID, class) |
| 30 – 59  | Structural info (ports, connections)   |
| 60 – 89  | Configuration / settings               |
| 90 – 119 | Metrics / diagnostics                  |
| 120+     | Library-specific extras                |

### Grouping with nested expansions

Use `layout.expansion()` inside `draw()` to group related fields when a panel has many items:

```python
def draw(self, context, layout: PanelLayout) -> None:
    node = context.active_node

    layout.label(f'Name: {node.name}')

    with layout.expansion('Inlets', icon='input'):
        for port in node.get_ports(is_port_type=PortType.INLET):
            layout.label(port.id)

    with layout.expansion('Outlets', icon='output'):
        for port in node.get_ports(is_port_type=PortType.OUTLET):
            layout.label(port.id)
```

This avoids very long single panels and lets users collapse sections they don't need.

---

## 9. Building a Custom Panel-Aware Editor

If the built-in `PropertiesEditor` doesn't fit your use case — for example, you want panels
to appear in the Left area for a specific tool — you can build your own panel-aware editor.

### Querying the registry

Get the `PanelRegistry` and call `get_panels()` with your editor's `registry_id` and the
active scope ID:

```python
panel_registry = context.app.library_service.get_panel_registry()

panels = panel_registry.get_panels(
    editor_key='my_tool',   # your editor's registry_id
    scope_id='node',        # whichever scope is currently active
)
```

To build a scope toolbar, query `get_scopes()` and filter by `poll()`:

```python
all_scopes = panel_registry.get_scopes('my_tool')   # sorted by order
available  = [s for s in all_scopes if s.poll(context)]
```

### Calling poll() and draw()

For each panel class returned, call `poll()` and, if it returns `True`, instantiate the
class and call `draw()` with a `PanelLayout` wrapping your container:

```python
from haywire.ui.panel.base import PanelLayout

for PanelClass in panels:
    if not PanelClass.poll(context):
        continue

    panel_instance = PanelClass()
    with ui.expansion(
        PanelClass.class_identity.label,
        icon=PanelClass.class_identity.icon or 'chevron_right',
        value=PanelClass.class_identity.default_open,
    ).classes('w-full'):
        panel_layout = PanelLayout(ui.column().classes('w-full p-2 gap-1'))
        panel_instance.draw(context, panel_layout)
```

### Handling context change events

Rebuild your panel list on every relevant `on_context_changed` event:

```python
def on_context_changed(self, event, context) -> None:
    if event.change_type in (
        ContextChangeType.SELECTION_CHANGED,
        ContextChangeType.DATA_MUTATED,
    ):
        if self._panel_container is not None:
            self._panel_container.clear()
            with self._panel_container:
                self._render_panels(context)
```

---

## 10. Compact Field Styling

Haywire ships a shared CSS utility class called **`compact-fields`** that tightens
NiceGUI/Quasar field rendering for dense UI areas like settings panels and node widgets.
The class is injected once by `AppShell` — no per-panel `ui.add_css()` call is needed.

### Usage

Wrap the container that holds your form fields with the `compact-fields` class:

```python
with ui.column().classes('w-full gap-0 compact-fields'):
    ui.number(value=42).props('dense')
    ui.input(value='hello').props('dense')
```

The class reduces vertical gaps, removes Quasar's hidden validation space, compacts
input heights, and removes underline decorations. It scopes all changes to descendants
of the marked container so the rest of the application is unaffected.

### What it does

| Override | Effect |
| --- | --- |
| `--nicegui-default-gap` | Reduced from `1rem` to `0.25rem` (configurable) |
| `.q-field` | Padding/margin zeroed, vertical alignment centered |
| `.q-field__control` | Height clamped to 26 px |
| `.q-field__bottom` | Hidden (validation/hint space removed) |
| `.q-toggle` | Margin/padding zeroed |
| `.q-field__control::before/::after` | Underline border removed |

### Theme integration

The class uses CSS custom properties that themes can override:

```css
:root {
    --hw-compact-gap: 0.25rem;       /* gap between rows */
    --hw-compact-field-h: 26px;      /* input field height */
    --hw-compact-row-min-h: 28px;    /* minimum row height */
}
```

Override these in a `WorkbenchTheme.to_css_vars()` implementation to adjust compact
field sizing globally for your theme.

### Built-in usage

- **Settings panels** (`_settings_panel_base.py`) — all three render functions
  (`render_reactive`, `render_schema`, `render_sub_holder`) wrap their output in
  `ui.column().classes('w-full gap-0 compact-fields')`
- **Node skins** (`NodeSkin`) — port content columns (inlet, outlet, config) apply
  `compact-fields` so that inline node widgets render compactly

---

## 11. Best Practices

**Keep `poll()` side-effect-free and fast.** It is called on every context change for every
registered panel. Avoid I/O, registry lookups, or any stateful mutation inside `poll()`.

**Use `default_open=False` for heavy or secondary panels.** Users see important information first without scrolling. Config and diagnostic panels can start collapsed:

```python
@panel(..., default_open=False)
class NodeMetricsPanel(BasePanel): ...
```

**Prefer `on_context_changed` over full redraws for frequently-updating panels.** If a panel shows a node's live output value that changes on every `DATA_MUTATED` event, update the label text directly rather than clearing and rebuilding the whole panel.

**Do not store session state on the panel instance.** Panel instances may be created and destroyed frequently. All state should come from `context` or `context.metadata`, not from instance variables that might go stale.

**Guard `poll()` against None.** Always check that the required context attribute is not
`None` before accessing further properties:

```python
@classmethod
def poll(cls, context) -> bool:
    node = context.active_node
    return node is not None and hasattr(node, 'config_ports') and bool(node.config_ports)
```

**Register scopes before panels.** If your library introduces a custom scope, always call
`panel_registry.register_scope()` before `add_folder_to_registry()`. Panels that reference
an unregistered scope ID are still indexed and queryable, but the scope will not appear in
the toolbar until it is registered.

**Test panels in isolation.** Because `poll()` and `draw()` only depend on `SessionContext`
and `PanelLayout`, you can instantiate a panel and call these methods directly in unit tests
without standing up the full NiceGUI server.

**Use `order` intentionally.** Don't leave every library panel at the default `order=100`.
Think about where your panel belongs in the natural reading order (identity first, details
second, actions last) and choose a value accordingly.

---

## 12. Full Example: A Custom Node Metrics Panel

This example shows a panel that displays timing and execution metrics for the active node. It demonstrates `poll()`, `draw()`, nested expansions, and updating on context change.

```python
from typing import TYPE_CHECKING

from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id='node_metrics',
    editor='properties',
    scope='node',
    label='Execution Metrics',
    icon='speed',
    order=90,
    default_open=False,
    description='Shows timing and call-count statistics for the active node.',
)
class NodeMetricsPanel(BasePanel):
    """Displays execution stats stored on the node's execution context."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        """Only show when a node is selected and has execution metrics."""
        node = context.active_node
        if node is None:
            return False
        # Only show if the node has been executed at least once
        metrics = getattr(node, 'execution_metrics', None)
        return metrics is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node    = context.active_node
        metrics = getattr(node, 'execution_metrics', {})

        call_count   = metrics.get('call_count', 0)
        last_ms      = metrics.get('last_duration_ms', 0.0)
        avg_ms       = metrics.get('avg_duration_ms', 0.0)
        error_count  = metrics.get('error_count', 0)

        # Summary row
        with layout.row():
            layout.label(f'Calls: {call_count}')
            layout.separator()
            layout.label(f'Errors: {error_count}')

        layout.separator()

        # Timing section
        with layout.expansion('Timing', icon='timer'):
            layout.label(f'Last:    {last_ms:.1f} ms')
            layout.label(f'Average: {avg_ms:.1f} ms')

        # Error detail section (only when there are errors)
        if error_count > 0:
            last_error = metrics.get('last_error', '')
            with layout.expansion('Last Error', icon='error'):
                layout.label(last_error or '(no detail)')

        # Reset button
        layout.separator()
        layout.button(
            'Reset metrics',
            on_click=lambda: self._reset_metrics(node),
        )

    def _reset_metrics(self, node) -> None:
        metrics = getattr(node, 'execution_metrics', None)
        if metrics is not None:
            metrics.clear()
            metrics['call_count'] = 0
```

### Registering in a library

```python
# my_library/library.py
from pathlib import Path
from haywire.ui.panel.registry import PanelRegistry

class MyLibrary(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent
        # Register panels — no custom scope needed, 'node' is built-in
        self.add_folder_to_registry(
            folder_path=str(base_path / 'panels'),
            registry_cls=PanelRegistry,
        )
```

Place `node_metrics_panel.py` (containing `NodeMetricsPanel`) inside the `panels/` folder and it will be discovered and registered automatically. No further wiring is required — the `PropertiesEditor` will find it via the `PanelRegistry` the next time a node is selected and the **Node** scope tab is active.

---

## 13. Custom Context Menu Triggers

Node skins can attach a context-menu popup to **any rendered element** without writing JavaScript or subclassing any event handler. The mechanism uses a single HTML data attribute and a matching panel registration.

### How it works

1. **Skin stamps the attribute.** Any element inside a node card can carry
   `data-hw-custom-menu-scope="<scope>"`. When the user right-clicks that element, `canvas.vue` intercepts the event *before* the normal node/edge/canvas routing and emits a `contextMenuCustom` event carrying the scope string and the `node_id` (resolved by walking up to the nearest `[data-node-id]` ancestor).

2. **Python pipeline resolves the node.** `ContextMenuHandlers` dispatches the event to
   `IContextMenuProvider.on_custom_context(pos, node_id, scope)`. The
   `SessionContextMenuProvider` implementation sets `context.active_node` and then calls `_open_menu(scope, pos)` — the same path used by all other context menu triggers.

3. **PanelRegistry serves the panels.** `_open_menu` calls
   `panel_registry.get_panels('context_menu', scope)`, which returns all panels registered for that `(editor_key, scope_id)` pair. Panels that pass `poll()` are drawn into a floating `Popup`.

### Stamping the attribute from a skin

```python
# Inside a NodeSkin.render() or any _render_* helper:
btn = ui.button(icon='warning', color='red')
btn.props(f'data-hw-custom-menu-scope="my.scope" data-node-id="{node_id}"')
```

The `data-node-id` prop on the element itself is optional — `canvas.vue` also accepts it from any ancestor in the DOM tree. Adding it directly is a safe fallback.

### Writing the panel

```python
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

@panel(
    editors='context_menu',
    scopes='my.scope',
    label='My Custom Panel',
    icon='info',
    order=10,
)
class MyCustomPanel(BasePanel):

    @classmethod
    def poll(cls, context) -> bool:
        return context.active_node is not None

    def draw(self, context, layout: PanelLayout) -> None:
        from nicegui import ui
        node = context.active_node
        with layout._container:
            ui.label(f'Node: {node.node_id}')
```

Place the file anywhere inside your library's `panels/` folder. The folder scan picks it up automatically — no extra registration call is needed.

### Built-in example: node runtime errors

The default skin renders a warning badge when a node has runtime errors. It stamps:

```
data-hw-custom-menu-scope="node.errors"
```

`haybale-core` ships `NodeErrorsPanel` registered for `editor='context_menu', scope='node.errors'`. Right-clicking the badge opens a popup listing each error with its full detail, replacing the old inline `ui.menu()` that was self-contained inside the skin.

### Extending an existing scope

Because any number of panels can register for the same `(editor, scope)` pair, a library can contribute additional actions to an existing custom scope without modifying the skin:

```python
@panel(
    editors='context_menu',
    scopes='node.errors',     # same scope as the built-in error panel
    label='Report Error',
    icon='bug_report',
    order=20,
)
class ReportErrorPanel(BasePanel):
    @classmethod
    def poll(cls, context) -> bool:
        return (
            context.active_node is not None
            and bool(context.active_node.state.get_errors())
        )

    def draw(self, context, layout: PanelLayout) -> None:
        layout.button('Send crash report', on_click=lambda: ...)
```

All panels matching the scope are rendered together in `order` sequence inside the same popup, just as they would be in the Properties sidebar.

---

## 14. Port Context Menu Triggers

Any skin element can open a port-aware context menu popup by carrying `data-hw-port-menu-scope="<scope>"`. The mechanism is identical to the custom menu in chapter 13, but the Python pipeline additionally resolves the `DataPort` and exposes it as `context.active_port` so panels can inspect port metadata directly.

### Port menu pipeline

1. **Skin stamps the attribute.** Any element inside a node card can carry `data-hw-port-menu-scope="<scope>"`. When the user right-clicks that element, `canvas.vue` intercepts the event *before* the custom-menu check and before the normal node/edge/canvas routing, then emits a `contextMenuPort` event carrying the scope, `nodeId`, and `portId`.

2. **`portId` resolution.** `canvas.vue` reads `data-port-id` from the element first, then falls back to `data-pin-id` on the same element, then walks up to the nearest ancestor carrying either attribute. This means you can stamp the attribute directly on an existing `.connection-pin` element (which already carries `data-pin-id`) or on any wrapper element by adding `data-port-id` explicitly.

3. **`nodeId` resolution.** Same as the custom menu: `canvas.vue` walks up to the nearest `[data-node-id]` ancestor.

4. **Python pipeline resolves port and node.** `ContextMenuHandlers` dispatches to `IContextMenuProvider.on_port_context(pos, node_id, port_id, scope)`. `SessionContextMenuProvider` sets `context.active_node` and `context.active_port` (a `DataPort` from `wrapper.node.ports[port_id]`), then calls `_open_menu(scope, pos)`. When the popup closes, `context.active_port` is cleared automatically.

5. **PanelRegistry serves the panels.** Same as all other context menu types — `panel_registry.get_panels('context_menu', scope)`.

### Detection priority in `handleContextMenu`

```
data-hw-port-menu-scope   ← checked first
data-hw-custom-menu-scope
[data-node-id]  (node context menu)
edge path
canvas fallback
```

### Stamping the port menu attribute

**On an existing pin element** (no `data-port-id` needed — the existing `data-pin-id` is used as fallback):

```python
# Inside a NodeSkin.render() or any _render_* helper:
pin_el.props(
    f'data-hw-port-menu-scope="my.port.scope" '
    f'data-node-id="{node_id}"'
)
```

**On a widget wrapper inside the node body** (explicit `data-port-id` required):

```python
with ui.row().props(
    f'data-hw-port-menu-scope="my.port.scope" '
    f'data-node-id="{node_id}" '
    f'data-port-id="{port.id}"'
):
    ui.label(port.id)
    # ... widget content ...
```

The `data-node-id` prop is optional on the element itself if any ancestor already carries it (e.g. the node card).

### Writing a port menu panel

```python
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

@panel(
    editors='context_menu',
    scopes='my.port.scope',
    label='Port Actions',
    icon='cable',
    order=10,
)
class MyPortPanel(BasePanel):

    @classmethod
    def poll(cls, context) -> bool:
        return context.active_port is not None

    def draw(self, context, layout: PanelLayout) -> None:
        from nicegui import ui
        port = context.active_port
        node = context.active_node
        with layout._container:
            ui.label(f'Port: {port.id} on {node.node_id}')
```

Place the file anywhere inside your library's `panels/` folder. No extra registration call is needed.

### What `context.active_port` contains

`context.active_port` is a `DataPort` instance (`haywire.core.node.base.DataPort`). It exposes the full port metadata: `id`, `flow_type`, `port_type`, `color`, `widget_key`, and the underlying data descriptor. `context.active_node` is also set, so both the node and the port are available simultaneously in `poll()` and `draw()`.

### Extending an existing port scope

Multiple panels can register for the same `(editor, scope)` pair and are rendered together in `order` sequence:

```python
@panel(
    editors='context_menu',
    scopes='my.port.scope',
    label='Disconnect All',
    icon='link_off',
    order=20,
)
class DisconnectPortPanel(BasePanel):
    @classmethod
    def poll(cls, context) -> bool:
        return context.active_port is not None

    def draw(self, context, layout: PanelLayout) -> None:
        layout.button('Disconnect all edges', on_click=lambda: ...)
```
