---
status: draft
doc_template: canonical-example
scope: Authoring panels — Panel subclass, @panel decorator, poll / draw lifecycle, scopes, PanelLayout API, Focus-based hosting
see-also:
  - ../editors/editor-canon.md
  - ../states/state-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Panel — Canonical Example

## 1. What it solves

A **panel** is a context-sensitive sub-section that appears inside a **panel-aware editor** — most commonly the Properties editor on the right sidebar. Unlike editors, panels do not manage their own slot. They are discovered at runtime from `PanelRegistry`, polled for visibility, and rendered inside a host editor's layout.

You author a panel when you want to contribute UI to a panel-aware editor (Properties is the primary one) without writing a new editor. Define a class, decorate with `@panel(editor='properties', focus=...)`, implement `poll(context) → bool` to declare when it should be visible, and `draw(context, layout)` to render its content. The host editor handles the rest — layout positioning, ordering, collapsibility, hot-reload.

This separation means:

- Panel authors never worry about layout positioning.
- Panels appear and disappear automatically as the selection changes.
- Any number of panels from any library can contribute to the same editor section.
- Hot-reload works: panels update in place when the library reloads.

## 2. How it fits

```text
@panel(editor=..., focus=...)        PanelRegistry              Host editor
class MyPanel(Panel):             registers                  (e.g. PropertiesEditor)
    @classmethod                      via @panel decorator        ↓ at render time:
    def poll(cls, context): ...                                   for each registered panel:
    def draw(self, context,                                         if poll(context): True
             layout): ...                                              draw inside ui.expansion
                                                                     ordered by `order`
                                                                     scoped by `focus`
```

Two registration paths feed `PanelRegistry`:

- **Library-side scan** — panels in your library's `panels/` folder, registered in `register_components(...)` via `add_folder_to_registry(..., PanelRegistry)`.
- **`@panel` decorator** — runs at import time, attaches `class_identity` (a `PanelIdentity` with editor, scope, order, etc.).

**Boundaries.** Editors that *host* panels — see [components/editors](../editors/editor-canon.md). The studio shell that owns the Properties editor — see [architecture/studio](../../architecture/studio/studio-arch.md). Library/session state read inside panels — see [components/states](../states/state-canon.md).

## 3. Important concepts

**The `@panel` decorator.** Required on every panel class. Two parameters are mandatory: `editor` (the host editor's `registry_id`) and `scope` (the scope ID — typically a `Focus` class — that determines visibility).

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `editor` | yes | — | Target editor `registry_id`. For Properties: `'properties'` |
| `scope` | yes | — | Scope ID or list of scope IDs (typically a `Focus` class) |
| `label` | no | class name | Display label in the expansion header |
| `icon` | no | — | Material icon for the expansion header |
| `order` | no | `100` | Sort order within scope (lower = higher position) |
| `default_open` | no | `True` | Whether the expansion starts open |
| `description` | no | `''` | Tooltip / accessibility text |
| `registry_id` | no | class name | Unique short ID within the library |

**Two lifecycle methods.** Every panel implements:

```python
@classmethod
def poll(cls, context) -> bool:
    """Should this panel be visible right now? Cheap and fast."""
    return context.active_node is not None

def draw(self, context, layout: PanelLayout) -> None:
    """Render the panel content. Called only when poll() returned True."""
    layout.label(f'Active: {context.active_node.name}')
```

`poll` is a classmethod (no instance state needed for visibility decisions). `draw` is an instance method — the host editor instantiates the panel before calling it.

**`poll` runs on every relevant context change.** Keep it cheap. Common patterns:

```python
return context.active_node is not None                   # any node selected
return isinstance(context.active_node, MySpecialNode)    # specific node type
return context.app_data[MyState].is_active.value         # AppState-driven
return False                                             # never visible (debugging)
```

**`PanelLayout` API — what `draw` gets.** A thin wrapper over the `hui` design-system primitives ([reference/design-guide](../../reference/design-guide.md) §8) bound to the panel's container. Common methods:

| Method | Purpose |
|---|---|
| `layout.label(text)` | Body-tier text label (`--hw-text-body`) |
| `layout.section_label(text)` | Uppercase tracking label that separates groups |
| `layout.section_divider(text=None)` | Visual break between sections, optional label |
| `layout.separator()` | Plain themed horizontal rule |
| `layout.panel_header(title, icon=...)` | Slim header bar; context manager for trailing action buttons |
| `layout.expansion_section(label, icon=..., default_open=True, panel_key=...)` | Collapsible context manager with persisted open/closed state |
| `layout.button(text, icon=..., on_click=...)` | Flat labelled action button |
| `layout.icon_action(icon, tooltip=..., on_click=...)` | Icon-only action button |
| `layout.empty_state(message, icon=..., hint=...)` | Centred placeholder for panels with no content |
| `layout.error_label(text)` / `layout.warning_label(text)` | Tinted message labels |

You can also drop into raw NiceGUI or call `hui.*` helpers directly inside `draw()` — `PanelLayout` doesn't restrict you, it just binds common helpers to the panel's container so you don't have to enter it manually.

**Scopes — Focus classes.** A scope is the visibility filter. The Properties editor's `ScopeToolbar` shows tabs (Node / Graph / Edge); each tab is a scope. A panel's `scope=NodeFocus` means "show me when the Node tab is active." Multiple scopes: `scope=[NodeFocus, GraphFocus]`.

Built-in scopes (Properties editor):

| Scope class | When the tab is active |
|---|---|
| `NodeFocus` | A node is selected |
| `EdgeFocus` | An edge is selected |
| `GraphFocus` | The graph itself (no specific selection) |

Custom scopes are possible — register a Focus subclass in your library and use it as the `scope=` value. The host editor's ScopeToolbar will show a tab for it.

**`focus=` vs `scope=`.** The codebase has been migrating from string-based `scope='node'` to class-based `focus=NodeFocus`. The `@panel(focus=NodeFocus, ...)` form is canonical going forward; `scope=` strings still work but are legacy. Use `focus=` in new code.

**Ordering.** `order=` controls vertical position within a scope. Convention: 0–99 reserved for built-in panels, 100+ for library panels, 1000+ for "always-last" panels (debug, advanced).

**`hb_*` methods are safe.** Custom helper methods on a panel class should start with `hb_`, `my_`, `custom_`, or `ext_` — same convention as nodes. Avoids future-framework name clashes.

**Imports** (verified against codebase 2026-05):

```python
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel

# Built-in focuses
from haybale_studio.focuses import NodeFocus, EdgeFocus, GraphFocus
```

**Hot-reload.** `PanelRegistry` extends `BaseRegistry`. New panel classes are picked up at the host editor's next render boundary. Existing panel instances are re-instantiated on the next `poll → draw` cycle.

## 4. One comprehensive example

A worked example exercising every authoring concept: a `NodeMetricsPanel` that lives in the Properties editor's Node scope, polls for visibility based on node type, displays computed metrics with a custom `Focus`-driven section, exercises `PanelLayout` thoroughly, and reads both direct context and AppState.

```python
# my_lib/panels/node_metrics.py

from nicegui import ui

from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haybale_studio.focuses import NodeFocus

# A Focus-aware AppState (see components/states/state-canon.md)
from ..state.metrics_cache import MetricsCache

@panel(
    editor='properties',     # Host editor's registry_id
    focus=NodeFocus,         # Visible when a node is selected (Node scope tab)
    label='Node Metrics',
    icon='analytics',
    order=200,               # After the built-in node panels (which are 0–99)
    default_open=False,      # Collapsed by default — metrics are advanced
    description='Computed performance metrics for the active node',
)
class NodeMetricsPanel(Panel):
    """Sub-section of the Properties editor. Visible when a node is
    selected; renders cached metrics from MetricsCache (AppState)."""

    @classmethod
    def poll(cls, context) -> bool:
        """Visibility check — runs on every context change.
        Keep it cheap: no I/O, no AppState computations."""
        if context.active_node is None:
            return False
        # Optional narrowing: only show for nodes the metrics cache covers
        return getattr(context.active_node, 'metrics_eligible', True)

    def draw(self, context, layout: PanelLayout) -> None:
        """Render the panel. Only called when poll() returned True.
        The host editor wraps this in a ui.expansion automatically."""
        node = context.active_node
        cache = context.app_data[MetricsCache]
        metrics = cache.for_node(node.node_id)

        # ── Empty state — no metrics yet ──────────────────────────────
        if metrics is None:
            layout.empty_state(
                f'No metrics yet for {node.name}',
                icon='hourglass_empty',
            )
            return

        # ── Section 1: Execution stats (collapsible, persisted) ──────
        with layout.expansion_section('Execution', icon='timer', panel_key='execution'):
            with ui.row():
                layout.label('Runs:')
                layout.label(str(metrics.run_count))
            with ui.row():
                layout.label('Avg. duration:')
                layout.label(f'{metrics.avg_duration_ms:.2f} ms')
            with ui.row():
                layout.label('p99:')
                layout.label(f'{metrics.p99_ms:.2f} ms')

        # ── Section 2: Data flow (flat label — short list) ───────────
        layout.section_label('Data flow')
        with ui.row():
            layout.label('Inlets dirty:')
            layout.label(str(metrics.inlet_dirty_count))
        with ui.row():
            layout.label('Outlets fired:')
            layout.label(str(metrics.outlet_fire_count))

        layout.separator()

        # ── Action: clear the cache for this node ────────────────────
        layout.button(
            'Clear metrics',
            icon='clear',
            on_click=lambda: self.hb_clear_for(node, cache),
        )

    # hb_* prefix → safe across framework updates
    def hb_clear_for(self, node, cache: MetricsCache) -> None:
        """Custom helper. Note: clearing AppState mutations propagate
        automatically because MetricsCache.entries is a reactive_field."""
        cache.clear_for(node.node_id)
        # No need to redraw manually — the parent editor's
        # on_context_changed will re-poll/draw via the reactive bus.
```

What this example exercises:

| Concept | Where |
|---|---|
| `@panel(editor='properties', focus=NodeFocus, …)` | top of class |
| `order=200` placing after built-in node panels | decorator |
| `default_open=False` for advanced/secondary content | decorator |
| `poll(cls, context)` as classmethod, fast visibility check | `poll` |
| Filtering on `context.active_node` and a custom node attribute | `poll` body |
| Reading AppState with `context.app_data[Cls]` | `draw` body |
| `layout.expansion_section('...', icon=..., panel_key=...)` for collapsible sub-sections | `draw` |
| `layout.section_label('...')` for flat group separators | `draw` |
| Raw `ui.row()` for inline horizontal layout | `draw` |
| `layout.label(...)` for text rows | `draw` |
| `layout.separator()` for visual division | `draw` |
| `layout.empty_state(...)` for the empty/loading state | `draw` |
| `layout.button(label, icon, on_click)` for actions | `draw` |
| `hb_*` private helper convention | `hb_clear_for` |
| Mutating AppState from a panel callback (auto re-render) | `hb_clear_for` |

For the host Properties editor (a panel-aware editor in `haywire-core`), see [components/editors](../editors/editor-canon.md). For the AppState that backs the metrics, see [components/states](../states/state-canon.md). For the `PanelLayout` design-system primitives in detail, see [reference/design-guide](../../reference/design-guide.md) §8.

---

## Quick reference

### Authoring checklist

- [ ] `@panel(editor='...', focus=FocusClass)` — both required
- [ ] Inherit from `Panel`
- [ ] Implement `poll(cls, context) -> bool` — fast visibility check
- [ ] Implement `draw(self, context, layout)` — render content
- [ ] Set `order=` deliberately (100+ for library panels)
- [ ] Use `PanelLayout` methods first; drop into raw `ui.*` when needed
- [ ] Custom helpers: `hb_*` prefix
- [ ] Place in `panels/` folder; register via `PanelRegistry` in `register_components`

### Imports

```python
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haybale_studio.focuses import NodeFocus, EdgeFocus, GraphFocus
```

### Built-in scopes (Properties editor)

| Focus class | Active when |
|---|---|
| `NodeFocus` | A node is selected |
| `EdgeFocus` | An edge is selected |
| `GraphFocus` | The graph (no specific selection) |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Slow `poll()` (I/O, AppState walks, expensive computations) | Runs on every context change — keep it under a millisecond |
| Forgetting `@classmethod` on `poll` | Decorator complains; the host calls it as a classmethod |
| Using `scope='node'` (string) instead of `focus=NodeFocus` | Legacy form; works but deprecated |
| Caching panel state in `__init__` | Panels are re-instantiated on hot-reload; use AppState/SessionState for cross-render state |
| Calling `ui.*` outside `draw()` (e.g. in `__init__`) | NiceGUI elements need a slot context; only `draw` provides one via `layout` |
