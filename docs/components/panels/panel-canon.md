---
status: draft
doc_template: canonical-example
scope: Authoring panels — BasePanel subclass, @panel decorator, action/focus contract, poll/draw lifecycle, PanelLayout API
see-also:
  - ../editors/editor-canon.md
  - ../states/state-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Panel — Canonical Example

## 1. What it solves

A **panel** is a context-sensitive sub-section that appears inside a **panel-aware editor** — most commonly the Properties editor on the right sidebar. Unlike editors, panels do not manage their own slot. They are discovered at runtime from `PanelRegistry`, polled for visibility, and rendered inside a host editor's layout.

You author a panel when you want to contribute UI to a panel-aware editor (Properties is the primary one) without writing a new editor. Define a class, decorate with `@panel(action=..., focus=..., label=...)`, implement `poll(ctx) → bool` to declare when it should be visible, and `draw(ctx, layout, actions)` to render its content. The host editor handles the rest — layout positioning, ordering, collapsibility, hot-reload.

This separation means:

- Panel authors never worry about layout positioning.
- Panels appear and disappear automatically as the selection changes.
- Any number of panels from any library can contribute to the same editor section.
- Hot-reload works: panels update in place when the library reloads.

## 2. How it fits

```text
@panel(action=..., focus=...)             PanelRegistry              Host editor
class MyPanel(BasePanel):                 registers                  (e.g. PropertiesEditor)
    @classmethod                          via @panel decorator         ↓ at render time:
    def poll(cls, ctx): ...                                            get_panels_for(self, focus)
    def draw(self, ctx,                                                  → filter by structural
             layout, actions): ...                                          isinstance(self, action)
                                                                        → filter by Focus.id
                                                                        → sort by `order`
                                                                        for each returned class:
                                                                          if poll(ctx):
                                                                            instantiate, draw
                                                                            inside ui.expansion
```

Two registration paths feed `PanelRegistry`:

- **Library-side scan** — panels in your library's `panels/` folder, registered in `register_components(...)` via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)`.
- **`@panel` decorator** — runs at import time, attaches `class_identity` (a `PanelIdentity` carrying `action`, `focus`, `label`, `order`, etc.).

**Boundaries.** Editors that *host* panels — see [components/editors](../editors/editor-canon.md). The studio shell that owns the Properties editor — see [architecture/studio](../../architecture/studio/studio-arch.md). Library/session state read inside panels — see [components/states](../states/state-canon.md).

## 3. Important concepts

**The `@panel` decorator.** Required on every panel class. Three parameters are mandatory: `action=` (the actions Protocol/ABC the host editor satisfies), `focus=` (a `Focus` subclass that determines visibility), and `label=` (display label).

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `action` | yes | — | Protocol or ABC class describing the actions this panel calls on its host. The host editor must structurally satisfy this Protocol. |
| `focus` | yes | — | `Focus` subclass discriminator (e.g. `NodeFocus`). The panel only appears when this focus is the active one *and* its `available(ctx)` returns `True`. |
| `label` | yes | — | Display label in the expansion header. |
| `icon` | no | `None` | Material icon for the expansion header. |
| `order` | no | `100` | Sort order within a focus (lower = higher position). |
| `default_open` | no | `True` | Whether the expansion starts open. |
| `description` | no | `''` | Tooltip / accessibility text. |
| `registry_id` | no | class name | Unique short ID within the library. |

**Action contract — `action=`.** An `action` is a Protocol (or ABC) class that names the methods the panel may call on its host editor. The host editor itself supplies the implementations; matching is *structural* — `PanelRegistry.get_panels_for(actions_provider=self, focus=...)` filters with `isinstance(actions_provider, action)`. So panels typed against `PropertiesEditorActions` only mount in editors that satisfy that Protocol, regardless of class hierarchy.

The minimal Properties contract today:

```python
@runtime_checkable
class PropertiesEditorActions(Protocol):
    def clear_selection(self) -> None: ...
```

A library wanting different actions defines its own Protocol; panels typed against it will mount only in editors that implement those methods.

**Focus contract — `focus=`.** A `Focus` is a class with a stable `id`, a `label`, an `icon`, and an `available(ctx)` classmethod. The Properties editor's ScopeToolbar lists every focus referenced by any panel whose action matches; clicking a tab makes that focus active. Built-in focuses live in `haybale_studio.focuses`:

| Focus class | `id` | `available(ctx)` |
|---|---|---|
| `AppFocus` | `app` | always true |
| `ExecutionFocus` | `execution` | always true |
| `CanvasFocus` | `canvas` | always true |
| `GraphFocus` | `graph` | active graph not None |
| `NodeFocus` | `node` | active node not None |
| `EdgeFocus` | `edge` | active edge not None |
| `PortFocus` | `port` | active port not None |
| `SelectionFocus` | `selection` | any nodes/edges selected |
| `SettingsFocus` | `settings` | active node not None |

Focus matching is by `id`, not by class identity — class objects can drift after hot-reload, but ids remain stable.

**Two lifecycle methods.** Every panel implements:

```python
@classmethod
def poll(cls, ctx: SessionContext) -> bool:
    """Should this panel be visible right now? Cheap and fast."""
    return ctx.data[EditState].active_node.value is not None

def draw(
    self,
    ctx: SessionContext,
    layout: PanelLayout,
    actions: PropertiesEditorActions,
) -> None:
    """Render the panel content. Called only when poll() returned True."""
    layout.label(f'Active: {ctx.data[EditState].active_node.value.name}')
```

`poll` is a classmethod (no instance state needed for visibility decisions). `draw` is an instance method — the host editor instantiates the panel before calling it. The `actions` argument is whatever the host passed as `actions_provider` to `get_panels_for`; it's typed against the panel's `action=` Protocol.

**`poll` runs on every relevant context change.** Keep it cheap. Common patterns:

```python
return ctx.data[EditState].active_node.value is not None  # any node selected
return isinstance(ctx.data[EditState].active_node.value, MySpecialNode)
return ctx.data[MyLibState].is_active.value               # AppState/SessionState driven
return False                                              # never visible (debugging)
```

Library-owned reactive state lives on a `SessionState` subclass (`ctx.data[Cls]`) or `AppState` subclass (`ctx.app_data[Cls]`). For the canvas, that state is `EditState`. See [components/states](../states/state-canon.md).

**`PanelLayout` API — what `draw` gets.** A thin wrapper over the `hui` design-system primitives ([reference/design-guide](../../reference/design-guide.md) §8) bound to the panel's container. Common methods:

| Method | Purpose |
|---|---|
| `layout.label(text)` | Body-tier text label (`--hw-text-body`). |
| `layout.section_label(text)` | Uppercase tracking label that separates groups. |
| `layout.section_divider(text=None)` | Visual break between sections, optional label. |
| `layout.separator()` | Plain themed horizontal rule. |
| `layout.panel_header(title, icon=...)` | Slim header bar; context manager for trailing action buttons. |
| `layout.expansion_section(label, icon=..., default_open=True, panel_key=...)` | Collapsible context manager with persisted open/closed state. |
| `layout.button(text, icon=..., on_click=...)` | Flat labelled action button. |
| `layout.icon_action(icon, tooltip=..., on_click=...)` | Icon-only action button. |
| `layout.empty_state(message, icon=..., hint=...)` | Centred placeholder for panels with no content. |
| `layout.error_label(text)` / `layout.warning_label(text)` | Tinted message labels. |

`PanelLayout` also works as a context manager — `with layout:` activates the underlying container so you can call `hui.*` functions directly inside it for full design-system access.

**Ordering.** `order=` controls vertical position within a focus. Convention: 0–99 for built-in panels, 100+ for library panels, 1000+ for "always-last" panels (debug, advanced).

**`hb_*` methods are safe.** Custom helper methods on a panel class should start with `hb_`, `my_`, `custom_`, or `ext_` — same convention as nodes. Avoids future-framework name clashes.

**Imports** (verified against codebase 2026-05):

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

# Built-in focuses live in haybale-studio
from haybale_studio.focuses import NodeFocus, GraphFocus, EdgeFocus
# The Properties editor's actions contract
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
```

**Hot-reload.** `PanelRegistry` extends `BaseRegistry`. New panel classes are picked up at the host editor's next render boundary. Existing panel instances are re-instantiated on the next `poll → draw` cycle. Focus ids are the stable lookup key, so reloads don't break scope tabs.

## 4. One comprehensive example

A worked example exercising every authoring concept: a `NodeMetricsPanel` that mounts in any editor satisfying `PropertiesEditorActions`, appears under the Node focus, polls for visibility based on active node, displays cached metrics with a custom collapsible section, exercises `PanelLayout` thoroughly, and reads both `EditState` and a custom `AppState`.

```python
# my_lib/panels/node_metrics.py

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_studio.focuses import NodeFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.state.edit_state import EditState

# A custom AppState (see components/states/state-canon.md)
from ..state.metrics_cache import MetricsCache

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,  # mount in any editor satisfying this Protocol
    focus=NodeFocus,                 # visible when the Node focus is active
    label='Node Metrics',
    icon='analytics',
    order=200,                       # after the built-in node panels (which are 0–99)
    default_open=False,              # collapsed by default — metrics are advanced
    description='Computed performance metrics for the active node',
)
class NodeMetricsPanel(BasePanel):
    """Sub-section of the Properties editor. Visible when a node is
    selected; renders cached metrics from MetricsCache (AppState)."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Visibility check — runs on every context change.
        Keep it cheap: no I/O, no AppState computations."""
        node = ctx.data[EditState].active_node.value
        if node is None:
            return False
        # Optional narrowing: only show for nodes the metrics cache covers
        return getattr(node, 'metrics_eligible', True)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        """Render the panel. Only called when poll() returned True.
        The host editor wraps this in a ui.expansion automatically."""
        node = ctx.data[EditState].active_node.value
        cache = ctx.app_data[MetricsCache]
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

        # ── Action: clear the cache for this node, then call back into
        #    the host to clear selection (uses the action contract) ───
        layout.button(
            'Clear metrics & deselect',
            icon='clear',
            on_click=lambda: self.hb_clear_for(node, cache, actions),
        )

    # hb_* prefix → safe across framework updates
    def hb_clear_for(
        self,
        node,
        cache: MetricsCache,
        actions: PropertiesEditorActions,
    ) -> None:
        """Custom helper. Note: clearing AppState mutations propagate
        automatically because MetricsCache.entries is a reactive_field.
        Then we call back into the host through the action contract."""
        cache.clear_for(node.node_id)
        actions.clear_selection()
        # No need to redraw manually — selection change emits a signal
        # the parent editor uses to re-poll/draw.
```

What this example exercises:

| Concept | Where |
|---|---|
| `@panel(action=..., focus=NodeFocus, …)` | top of class |
| `order=200` placing after built-in node panels | decorator |
| `default_open=False` for advanced/secondary content | decorator |
| `poll(cls, ctx)` as classmethod, fast visibility check | `poll` |
| Reading `ctx.data[EditState].active_node.value` | `poll` body |
| Reading `AppState` with `ctx.app_data[Cls]` | `draw` body |
| `draw(self, ctx, layout, actions)` 3-arg signature | `draw` |
| `layout.expansion_section('...', icon=..., panel_key=...)` for collapsible sub-sections | `draw` |
| `layout.section_label('...')` for flat group separators | `draw` |
| Raw `ui.row()` for inline horizontal layout | `draw` |
| `layout.label(...)` for text rows | `draw` |
| `layout.separator()` for visual division | `draw` |
| `layout.empty_state(...)` for the empty/loading state | `draw` |
| `layout.button(label, icon, on_click)` for actions | `draw` |
| `actions.clear_selection()` — calling back into the host through the action Protocol | `hb_clear_for` |
| `hb_*` private helper convention | `hb_clear_for` |

For the host Properties editor (a panel-aware editor in `haybale-studio`), see [components/editors](../editors/editor-canon.md). For the AppState that backs the metrics, see [components/states](../states/state-canon.md). For the `PanelLayout` design-system primitives in detail, see [reference/design-guide](../../reference/design-guide.md) §8.

---

## Quick reference

### Authoring checklist

- [ ] `@panel(action=ActionsProtocol, focus=FocusClass, label='...')` — all three required
- [ ] Inherit from `BasePanel`
- [ ] Implement `poll(cls, ctx) -> bool` — fast visibility check (`@classmethod`)
- [ ] Implement `draw(self, ctx, layout, actions)` — render content
- [ ] Set `order=` deliberately (100+ for library panels)
- [ ] Use `PanelLayout` methods first; drop into raw `hui.*` / `ui.*` when needed
- [ ] Custom helpers: `hb_*` prefix
- [ ] Place in `panels/` folder; register via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)` in `register_components`

### Imports

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haybale_studio.focuses import NodeFocus, EdgeFocus, GraphFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
```

### Built-in focuses (`haybale_studio.focuses`)

| Focus class | `id` | `available(ctx)` |
|---|---|---|
| `AppFocus` | `app` | always |
| `ExecutionFocus` | `execution` | always |
| `CanvasFocus` | `canvas` | always |
| `GraphFocus` | `graph` | active graph not None |
| `NodeFocus` | `node` | active node not None |
| `EdgeFocus` | `edge` | active edge not None |
| `PortFocus` | `port` | active port not None |
| `SelectionFocus` | `selection` | any nodes/edges selected |
| `SettingsFocus` | `settings` | active node not None |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Slow `poll()` (I/O, AppState walks, expensive computations) | Runs on every context change — keep it under a millisecond |
| Forgetting `@classmethod` on `poll` | The host calls it as a classmethod before instantiation |
| `draw(self, ctx, layout)` (2-arg, legacy) | New contract requires a third `actions` parameter |
| Caching panel state in `__init__` | Panels are re-instantiated on hot-reload; use AppState/SessionState for cross-render state |
| Calling `ui.*` outside `draw()` (e.g. in `__init__`) | NiceGUI elements need a slot context; only `draw` provides one via `layout` |
