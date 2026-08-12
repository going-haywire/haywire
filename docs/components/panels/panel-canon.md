---
status: draft
doc_template: canonical-example
scope: Authoring panels — BasePanel subclass, @panel decorator, actions annotation/focus contract, poll/draw lifecycle, PanelLayout API
see-also:
  - ../editors/editor-canon.md
  - ../states/state-canon.md
  - ../../guides/signals.md
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Panel — Canonical Example

## 1. What it solves

A **panel** is a context-sensitive sub-section that appears inside a **panel-aware editor** — most commonly the Properties editor on the right sidebar. Unlike editors, panels do not manage their own slot. They are discovered at runtime from `PanelRegistry`, polled for visibility, and rendered inside a host editor's layout.

You author a panel when you want to contribute UI to a panel-aware editor (Properties is the primary one) without writing a new editor. Define a class, decorate with `@panel(focus=..., label=...)`, implement `poll(ctx) → bool` to declare when it should be visible, and `draw(ctx, layout)` to render its content. The host editor handles the rest — layout positioning, ordering, collapsibility, hot-reload.

This separation means:

- Panel authors never worry about layout positioning.
- Panels appear and disappear automatically as the selection changes.
- Any number of panels from any library can contribute to the same editor section.
- Hot-reload works: panels update in place when the library reloads.

## 1.5. Panels vs. Editors — Choosing the Right Abstraction

**Panels and editors are intentionally separate concerns.** Understanding when to use each is critical to writing maintainable code.

| Aspect | Panel | Editor |
| --- | --- | --- |
| **Purpose** | Display read-only information from session state | Build an interactive workspace with mutable state |
| **Lifecycle** | Ephemeral; recreated on every redraw | Persistent per session |
| **Instance state** | None; panels are stateless across redraws | Owns local state (unsaved changes, form drafts, interaction mode) |
| **Visibility** | Polled dynamically via `poll(ctx)` on each redraw | Always shown when active (slot-managed) |
| **Slot** | Hosted inside another editor; no slot of its own | Occupies one of the four workspace slots (Left/Right/Main/Bottom) |
| **Signals** | Subscribed by host editor via `redraw_on=` | Subscribed directly via `@redraw_on()` or `@react_on()` |
| **Use case** | Properties panel, debug info, metadata display | Code editor, library browser, graph editor, file explorer |

**Decision tree:**

1. **Does your feature need to hold mutable state across user interactions?** (Form with unsaved changes, multi-step workflow, edit drafts, undo stack)
   → **Build an editor.** See [components/editors](../editors/editor-canon.md).

2. **Is your feature a read-only display that changes when the selection or context changes?**
   → **Build a panel.** (This document.)

3. **Does your feature need its own slot in the workspace layout?**
   → **Build an editor.** Panels don't manage slots; they appear inside editors.

4. **Would your feature be useful in multiple contexts?** (Visible in Properties sidebar AND context menus)
   → **Can be a panel** if both contexts are read-only. Action panels appear in context menus; display panels appear in Properties.

**Examples:**

- **NodeSettingsPanel** — read-only display of a node's settings. When you select a different node, it re-renders. **Panel.** ✅
- **CodeEditor** — holds file content, tracks dirty state (unsaved changes), persists scroll position. **Editor.** ✅
- **NodePropertiesPanel** — displays key/value metadata about the selected node. Stateless. **Panel.** ✅
- **LibraryComponentEditor** — allows editing a library component with unsaved changes. **Editor.** ✅
- **Delete Node context-menu action** — button that calls `delete_node()` on its host. Read-only display. **Action panel.** ✅

**Why the boundary exists:**

Panels are intentionally stateless so that:
- **Selection changes are clean.** Switching nodes clears and rebuilds panels automatically; no stale state to clean up.
- **Hot-reload is simple.** Panels reload their class definition; no instance state survives, so stale state never leaks through.
- **Composition is easy.** Any library can contribute panels to the same editor without coordinating internal state.

If you need to hold state, you need a proper container (an editor) that manages the full lifecycle.

## 2. How it fits

```text
@panel(focus=...)                         PanelRegistry              Host editor
class MyPanel(BasePanel):                 registers                  (e.g. PropertiesEditor)
    actions: MyActionsProtocol            via @panel decorator         ↓ at render time:
    @classmethod                                                       get_panels_for_focus(focus)
    def poll(cls, ctx): ...                                              → filter by Focus.id
    def draw(self, ctx, layout): ...                                     → sort by `order`
                                                                         for each returned class:
                                                                           if poll(ctx):
                                                                             instantiate, draw
                                                                             inside ui.expansion

                                                               Context-menu host at popup time:
                                                                       get_panels_for_action(
                                                                           action_protocol, focus)
                                                                         → filter by action +
                                                                             Focus.id
                                                                         inject host → panel.actions
```

Two registration paths feed `PanelRegistry`:

- **Library-side scan** — panels in your library's `panels/` folder, registered in `register_components(...)` via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)`.
- **`@panel` decorator** — runs at import time, attaches `class_identity` (a `PanelIdentity` carrying `focus`, `label`, `order`, `action_protocol`, etc.).

**Boundaries.** Editors that *host* panels — see [components/editors](../editors/editor-canon.md). The studio shell that owns the Properties editor — see [architecture/studio](../../architecture/studio/studio-arch.md). Library/session state read inside panels — see [components/states](../states/state-canon.md).

## 3. Important concepts

**The `@panel` decorator.** Required on every panel class. Two parameters are mandatory: `focus=` (a `Focus` subclass that determines visibility) and `label=` (display label).

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `focus` | yes | — | `Focus` subclass discriminator (e.g. `NodeFocus`). The panel only appears when this focus is the active one *and* its `available(ctx)` returns `True`. |
| `label` | yes | — | Display label in the expansion header. |
| `icon` | no | `None` | Material icon for the expansion header. |
| `order` | no | `100` | Sort order within a focus (lower = higher position). |
| `default_open` | no | `True` | Whether the expansion starts open. |
| `description` | no | `''` | Tooltip / accessibility text. |
| `registry_id` | no | class name | Unique short ID within the library. |

**Three orthogonal facets.** A panel has three independent facets that compose freely:

1. **Focus** (`focus=FocusClass` decorator argument) — routing topic; determines where the panel appears and under which toolbar tab.
2. **Verb surface** (`actions: SomeProtocol` class-body annotation) — optional; declares the actions this panel calls on its host. The framework reads the `actions:` annotation at decoration time via `typing.get_type_hints` and stores it on `PanelIdentity.action_protocol`. At mount time, the framework sets `panel.actions = host` if the host satisfies the Protocol; the panel accesses the host as `self.actions.method(...)`. Display panels (no host needed) simply omit the annotation — `panel.actions` stays `None`.
3. **Refresh** (`redraw_on=(...)` tuple of Signal subclasses on the decorator) — signals that should trigger a host-editor redraw when this panel is mounted.

**Action contract — `actions:` annotation.** An `actions:` annotation is a Protocol class that names the methods the panel may call on its host. The host supplies the implementations; matching is structural. `PanelRegistry.get_panels_for_action(action_protocol, focus)` returns panels whose annotated Protocol is satisfied by the host, filtered by focus — this is the query used by context-menu hosts. Display panels (e.g. Properties-sidebar panels) have no `actions:` annotation and are queried with `get_panels_for_focus(focus)` instead.

A library that needs its panels to call back into the host defines its own Protocol and annotates the class body:

```python
@runtime_checkable
class NodeContextActions(Protocol):
    def delete_node(self, node_id: str) -> None: ...
```

**Focus contract — `focus=`.** A `Focus` is a class with a stable `id`, a `label`, an `icon`, and an `available(ctx)` classmethod. The Properties editor's ScopeToolbar lists every focus referenced by any display panel; clicking a tab makes that focus active. Built-in focuses live in `haybale_studio.focuses`:

| Focus class | `id` | `available(ctx)` |
|---|---|---|
| `AppFocus` | `app` | always true |
| `ExecutionFocus` | `execution` | always true |
| `CanvasFocus` | `canvas` | always true |
| `GraphFocus` | `graph` | active graph not None |
| `NodeFocus` | `node` | active node not None |
| `EdgeFocus` | `edge` | active edge not None |
| `PortFocus` | `ports` | active node not None |
| `PinFocus` | `pin` | active port not None |
| `SelectionFocus` | `selection` | any nodes/edges selected |
| `SettingsFocus` | `settings` | active node not None |

Focus matching is by `id`, not by class identity — class objects can drift after hot-reload, but ids remain stable.

**Two lifecycle methods.** Every panel implements:

```python
@classmethod
def poll(cls, ctx: SessionContext) -> bool:
    """Should this panel be visible right now? Cheap and fast."""
    return ctx.data[EditState].active_node is not None

def draw(
    self,
    ctx: SessionContext,
    layout: PanelLayout,
) -> None:
    """Render the panel content. Called only when poll() returned True."""
    with layout:
        hui.label(f'Active: {ctx.data[EditState].active_node.name}')
```

`poll` is a classmethod (no instance state needed for visibility decisions). `draw` is an instance method — the host editor instantiates the panel before calling it. Action panels access the injected host via `self.actions`; display panels leave `self.actions` at its default `None`.

**Action panel** (has an `actions:` annotation; mounted by a context-menu host):

```python
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from my_lib.actions import SelectionContextActions
from my_lib.focuses import SelectionFocus

@panel(actions=SelectionContextActions, focus=SelectionFocus, label="Delete Selection", icon="delete")
class DeleteSelectionPanel(BasePanel):
    actions: SelectionContextActions   # framework injects host at mount

    def draw(self, ctx, layout):
        with layout:
            hui.button("Delete Selection", on_click=self.actions.delete_selection)
```

**Display panel** (no `actions:` annotation; mounted by PropertiesEditor):

```python
@panel(focus=SettingsFocus, label="Workbench")
class ThemeSettingsPanel(BasePanel):
    def draw(self, ctx, layout):
        ...
```

**`poll` runs on every relevant context change.** Keep it cheap. Common patterns:

```python
return ctx.data[EditState].active_node is not None  # any node selected
return isinstance(ctx.data[EditState].active_node, MySpecialNode)
return ctx.data[MyLibState].is_active               # AppState/SessionState driven
return False                                              # never visible (debugging)
```

Library-owned reactive state lives on a `SessionState` subclass (`ctx.data[Cls]`) or `AppState` subclass (`ctx.app_data[Cls]`). For the canvas, that state is `EditState`. See [components/states](../states/state-canon.md).

**`PanelLayout` API — what `draw` gets.** `PanelLayout` is **not** a façade over `hui`. It is the panel's container, bound as a context manager. Render by activating it with `with layout:` and calling `hui.*` functions directly — `hui` ([reference/design-guide](../../reference/design-guide.md) §8) is the single rendering vocabulary:

```python
def draw(self, ctx, layout):
    with layout:
        hui.section_label("PORTS")
        hui.info_row("Inlet", "Image")
        hui.button("Delete Node", icon=hui.icon.delete, on_click=self._delete)
```

It exposes exactly two members:

| Member | Purpose |
| --- | --- |
| `with layout:` / `layout.container` | Activates / returns the panel's container element. |
| `layout.state_bag` | Host-owned dict for panel UI state persistence (or `None` for ephemeral panels). Pass to `hui.expansion_section(..., state=layout.state_bag, panel_key=...)` or use directly for any UI state tracking (collapsed sections, scroll position, form selections, etc.). |

**`layout.state_bag` — the one stateful injection.** Panels are stateless, but the Properties editor holds a dict (`_state_bag`) that tracks panel UI state (which sections are collapsed, scroll positions, etc.). This dict is passed to every panel on every redraw via `PanelLayout`. Your panel reads from and writes to this shared dict *via* UI components like `hui.expansion_section()`:

```python
def draw(self, ctx, layout):
    with layout:
        # This section's collapsed/expanded state persists across redraws
        # because the host editor owns the dict and passes it every time.
        with hui.expansion_section(
            "My Section",
            state=layout.state_bag,             # host-owned dict
            panel_key="expansion:my_section",   # namespaced key
            default_open=True,
        ):
            hui.label("Content here")
```

On the next redraw (when `SelectionMoved` fires), the editor clears the panel DOM, recreates the panel instance, calls `draw()` again, and passes the *same* `state_bag` dict. The section remembers whether it was collapsed. This is the **only state that survives across panel redraws** — and it's owned by the host editor, not the panel. The panel never stores state directly; it just consults the dict it's given.

**Use namespaced keys to avoid collisions.** When storing UI state in the bag, prefix keys with the feature they belong to:

- `"expansion:section_name"` — for section collapse state
- `"scroll:container_id"` — for scroll position
- `"tab:tab_name"` — for active tab
- Custom namespaces for custom state

**Why this pattern exists:** Panels need to remember UI state for good UX (e.g., which sections are collapsed), but panels must be stateless (for clean hot-reload and composition). The solution: the host owns the state dict and loans it to panels. Panels are ephemeral; the dict is persistent.

**Rule:** Do not look for `layout.label()` / `layout.button()` / `layout.empty_state()` style helpers — they no longer exist. Use the `hui.*` function of the same name inside `with layout:`. For key/value metadata prefer `hui.info_row()` over `hui.label("Key: value")` (see design-guide §8.6).

**Ordering.** `order=` controls vertical position within a focus. Convention: 0–99 for built-in panels, 100+ for library panels, 1000+ for "always-last" panels (debug, advanced).

**`hb_*` methods are safe.** Custom helper methods on a panel class should start with `hb_`, `my_`, `custom_`, or `ext_` — same convention as nodes. Avoids future-framework name clashes.

**Imports** (verified against codebase 2026-05):

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

# Built-in focuses live in haybale-studio
from haybale_studio.focuses import NodeFocus, GraphFocus, EdgeFocus
# For action panels: import your library's own Protocol
# from my_lib.actions import MyContextActions
```

**Hot-reload.** `PanelRegistry` extends `BaseRegistry`. New panel classes are picked up at the host editor's next render boundary. Existing panel instances are re-instantiated on the next `poll → draw` cycle. Focus ids are the stable lookup key, so reloads don't break scope tabs.

## 4. Live examples from the codebase

Source: [`barn/haybale-testing/haybale_testing/panels/graph/menu/`](../../../barn/haybale-testing/haybale_testing/panels/graph/menu/)

**Simple action panel** — `TestDeleteNodeMenuPanel` from `barn/haybale-testing/haybale_testing/panels/graph/menu/node/node.py`. Demonstrates the minimal action-panel skeleton: `@panel` decorator, `actions: TestNodeContextActions` class-body annotation, `poll()` checking `EditState`, `draw()` rendering with `with layout: hui.button(...)` and dispatching through `self.actions`:

```python
`TestDeleteNodeMenuPanel` — registry_key: `testing:panel:TestDeleteNodeMenuPanel`

--8<-- "barn/haybale-testing/haybale_testing/panels/graph/menu/node/node.py:23:53"
```

**SessionState-reading panel** — `TestSessionStateMenuPanel` from `barn/haybale-testing/haybale_testing/panels/graph/menu/canvas/canvas.py`. Demonstrates `poll()` reading a `SessionState` signal field and `draw()` displaying it with `with layout: hui.label(...)`:

```python
`TestSessionStateMenuPanel` — registry_key: `testing:panel:TestSessionStateMenuPanel`

--8<-- "barn/haybale-testing/haybale_testing/panels/graph/menu/canvas/canvas.py:58:82"
```

What these examples exercise:

| Concept | Where |
|---|---|
| `@panel(focus=..., label=..., order=...)` | both panels |
| `actions: SomeProtocol` class-body annotation (action panels only) | `TestDeleteNodePanel` |
| `poll(cls, ctx)` as `@classmethod` | both panels |
| `ctx.data[Cls].signal_field` (bare attribute) in `poll` | both panels |
| `draw(self, ctx, layout)` 2-arg signature | both panels |
| `with layout: hui.button(label, icon, on_click)` | `TestDeleteNodePanel` |
| Dispatching through the action contract via `self.actions` | `self.actions.test_delete_node(node_id)` |
| `with layout: hui.label(text)` | `TestSessionStatePanel` |
| Reading `SessionState` via `ctx.data[Cls]` | `TestSessionStatePanel` |
| `TYPE_CHECKING` guard for `SessionContext` import | both panels |

For the host Properties editor (a panel-aware editor in `haybale-studio`), see [components/editors](../editors/editor-canon.md). For the AppState that backs the metrics, see [components/states](../states/state-canon.md). For the `hui.*` design-system primitives a panel renders with, see [reference/design-guide](../../reference/design-guide.md) §8.

---

## Quick reference

### Authoring checklist

- [ ] `@panel(focus=FocusClass, label='...')` — both required
- [ ] Inherit from `BasePanel`
- [ ] For action panels: add `actions: MyActionsProtocol` as a class-body annotation (no decorator argument needed)
- [ ] Implement `poll(cls, ctx) -> bool` — fast visibility check (`@classmethod`)
- [ ] Implement `draw(self, ctx, layout)` — render content; access host as `self.actions.method(...)`
- [ ] Set `order=` deliberately (100+ for library panels)
- [ ] Render via `with layout:` then call `hui.*` directly (`hui.info_row`, `hui.button`, `hui.empty_state`, …); drop to raw `ui.*` only for patterns `hui` doesn't cover
- [ ] Custom helpers: `hb_*` prefix
- [ ] Place in `panels/` folder; register via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)` in `register_components`

### Imports

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haybale_studio.focuses import NodeFocus, EdgeFocus, GraphFocus
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
| `PortFocus` | `ports` | active node not None |
| `PinFocus` | `pin` | active port not None |
| `SelectionFocus` | `selection` | any nodes/edges selected |
| `SettingsFocus` | `settings` | active node not None |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Slow `poll()` (I/O, AppState walks, expensive computations) | Runs on every context change — keep it under a millisecond |
| Forgetting `@classmethod` on `poll` | The host calls it as a classmethod before instantiation |
| `draw(self, ctx, layout, actions)` (old 3-arg signature) | Current contract is 2-arg: `draw(self, ctx, layout)`; access host via `self.actions` instead |
| Putting `action=` in `@panel(...)` decorator | The verb surface is a class-body annotation (`actions: MyProtocol`), not a decorator argument |
| Calling `self.actions` in a display panel (no annotation) | `self.actions` is `None` for display panels; only annotate when a host is actually needed |
| Caching panel state in `__init__` | Panels are re-instantiated on hot-reload; use AppState/SessionState for cross-render state |
| Calling `ui.*` outside `draw()` (e.g. in `__init__`) | NiceGUI elements need a slot context; only `draw` provides one via `layout` |
