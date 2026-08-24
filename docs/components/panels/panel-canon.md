---
status: draft
doc_template: canonical-example
scope: Authoring panels — BasePanel subclass, @panel decorator, actions annotation/surface contract, poll/draw lifecycle, PanelLayout API
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

You author a panel when you want to contribute UI to a panel-aware editor (Properties is the primary one) without writing a new editor. Define a class, decorate with `@panel(surface=..., label=...)`, implement `poll(ctx) → bool` to declare when it should be visible, and `draw(ctx, layout)` to render its content. The host editor handles the rest — layout positioning, ordering, collapsibility, hot-reload.

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
@panel(surface=...)                       PanelRegistry              Host editor
class MyPanel(BasePanel):                 registers                  (e.g. PropertiesEditor)
    actions: MyActionsProtocol            via @panel decorator         ↓ at render time:
    @classmethod                                                       get_panels(surface)
    def poll(cls, ctx): ...                                              → filter by Surface.id
    def draw(self, ctx, layout): ...                                     → sort by `order`
                                                                         for each returned class:
                                                                           if poll(ctx):
                                                                             instantiate, draw
                                                                             inside ui.expansion

                                                               Context-menu host at popup time:
                                                                       get_panels(surface)
                                                                         → filter by Surface.id
                                                                         (same query — no fork)
                                                                         inject host → panel.actions
                                                                         per surface.provides
```

Two registration paths feed `PanelRegistry`:

- **Library-side scan** — panels in your library's `panels/` folder, registered in `register_components(...)` via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)`.
- **`@panel` decorator** — runs at import time, attaches `class_identity` (a `PanelIdentity` carrying `surface`, `hosts`, `label`, `order`, etc.).

**Boundaries.** Editors that *host* panels — see [components/editors](../editors/editor-canon.md). The studio shell that owns the Properties editor — see [architecture/studio](../../architecture/studio/studio-arch.md). Library/session state read inside panels — see [components/states](../states/state-canon.md).

**One shared gate for every host.** No host implements the poll/draw loop itself. `haywire.ui.panel.host_rendering` owns it, and all three panel hosts funnel through the same functions:

| Function | Role |
| --- | --- |
| `visible_panels(classes, ctx)` | The visibility gate for hosts that only ever skip an inapplicable panel. Poll-filters a list down to what should show, in order. A panel whose `poll()` returns `False` — or raises — is dropped, with raises logged through the error boundary. |
| `partition_panels(classes, ctx)` | The superset: splits into `(applies, disabled)`, for hosts that render a panel's own inapplicable state via `draw_disabled()` (context menus). `access=`-denied panels are dropped from **both** lists — a greyed entry would advertise what the principal may not have. |
| `render_panel(cls, ctx, layout, actions_host=..., disabled=False)` | Instantiates one panel, injects `panel.actions`, and draws it (`draw()`, or `draw_disabled()` when `disabled=True`) under the same error boundary. A panel that raises renders an inline `error_label` instead of crashing its host. |

The three hosts are `PropertiesEditor` (persistent display panels), `BaseContextMenuProvider` (right-click menus), and the graph canvas `SelectionToolbarProvider`. Because the filter is shared, anything that decides *whether a panel may show* — `poll()`, and `access=` under [ADR 0027](../../adr/0027-studio-authentication.md) — is written once here and takes effect in all three at once.

Two consequences worth knowing when authoring a host: `_open_menu()` refuses to build a popup at all when nothing in either list would draw (so a menu with nothing to show never appears as an empty box — see §3, "Hosting a surface" below for how nesting complicates "nothing to show"), and `render_panel()` assumes its caller already filtered — a new host that calls it directly without `visible_panels()` / `partition_panels()` bypasses the gate.

## 3. Important concepts

**The `@panel` decorator.** Required on every panel class. Two parameters are mandatory: `surface=` (a `Surface` subclass that determines visibility) and `label=` (display label).

| Parameter | Required | Default | Purpose |
|---|---|---|---|
| `surface` | yes | — | `Surface` subclass discriminator (e.g. `NodeInspector`). The panel only appears while this Surface's `poll(ctx)` returns `True`, matched by `surface.id` — never by class object, since a class can go stale across hot-reload ([ADR-0009](../../adr/0009-surface-id-stable-key.md)). |
| `hosts` | no | `()` | Tuple of `Surface` subclasses this panel may itself render, via `self.render_surface(S, ctx)` inside `draw()`. The empty default makes the panel a *leaf*. See "Hosting a surface" below. |
| `label` | yes | — | Display label in the expansion header. |
| `icon` | no | `None` | Material icon for the expansion header. |
| `order` | no | `100` | Sort order within a surface (lower = higher position). |
| `default_open` | no | `True` | Whether the expansion starts open. |
| `description` | no | `''` | Tooltip / accessibility text. |
| `registry_id` | no | class name | Unique short ID within the library. |
| `redraw_on` | no | `()` | Tuple of `Signal` subclasses the panel wants its host editor to redraw on. |
| `access` | no | `AccessTier.VIEW` | Minimum `AccessTier` to see this panel — see [ADR 0027](../../adr/0027-studio-authentication.md). |

**Two orthogonal facets.** A panel has two independent facets that compose freely:

1. **Surface** (`surface=SurfaceClass` decorator argument) — routing topic; determines where the panel appears, and, for a Properties-editor Surface that declares `presentation`, under which toolbar tab.
2. **Host contract** (`actions: SomeProtocol` class-body annotation) — optional; type-checker visibility only, on what the *Surface* — via its `provides` — already promises will be injected as `self.actions`. The framework has never read this annotation; it exists purely so `self.actions.method(...)` type-checks. A Surface with no `provides` needs no `actions:` annotation at all, and `self.actions` stays `None`.

There used to be a third facet — a "verb surface" read from the class-body annotation itself, independent of the routing Surface. It no longer exists: `provides` moved onto the `Surface`, so a panel's host contract is now entirely a property of *where it is registered*, not something the panel separately declares. See "Hosting a surface" below for how the host that fills `self.actions` is decided.

**Host contract — `provides`.** Whether a panel receives a host in `self.actions`, and what type, is decided by the *Surface's* `provides` — a `runtime_checkable` `Protocol`, or `None` if the Surface asks nothing of its host. Panels on that Surface may declare a matching `actions:` annotation purely for the type-checker; the framework never reads it, and the query used to look panels up is the same one either way — `PanelRegistry.get_panels(surface)`, filtered by `surface.id`. There is no display/action fork any more: which panels a surface yields depends on the surface id alone, never on whether an `actions:` annotation is present.

A library that needs its panels to call back into a host defines its own Protocol and names it on the Surface:

```python
@runtime_checkable
class SelectionActions(Protocol):
    def delete_selection(self) -> None: ...

class SelectionMenu(Surface):
    id = "selection"
    provides = SelectionActions
```

**Built-in Surfaces.** Each is marked **inspector** (a Properties-editor tab, declares `presentation`) or **menu** (a context menu or toolbar, no `presentation`). Built-in Surfaces live in `haywire.barn.builtin.surfaces` (framework-wide) or a library's own `surfaces/` package (e.g. `haybale_graph_editor.surfaces`):

| Surface class | `id` | Kind | `poll(ctx)` |
|---|---|---|---|
| `AppSettings` | `app` | inspector | always true |
| `ExecutionInspector` | `execution` | inspector | always true |
| `CanvasSettings` | `canvas` | inspector | always true |
| `GraphInspector` | `graph` | inspector | active graph not None |
| `NodeInspector` | `node` | inspector | active node not None |
| `SettingsInspector` | `settings` | inspector | active node not None |
| `PortInspector` | `ports` | inspector | active node not None |
| `EdgeInspector` | `edge` | inspector | active edge not None |
| `EdgeMenu` | `edge-menu` | menu | active edge not None |
| `PinMenu` | `pin` | menu | active port not None |
| `SelectionMenu` | `selection` | menu | any nodes/edges selected |
| `SelectionToolbar` | `toolbar` | menu | any nodes/edges selected |
| `GraphContext` | `graph-context` | menu | active graph not None |
| `GraphToolBar` / `GraphContextBody` / `GraphMoreActions` | `graph-toolbar` / `graph-body` / `graph-more` | menu | hosted by `GraphContextPanel` / `GraphMorePanel` — see [guides/panels](../../guides/panels.md) |
| `FileMenu` | `file` | menu | right-clicked file has a matching extension |
| `AccountMenu` | `account` | menu | always true |

Surface matching is by `id`, not by class identity — class objects can drift after hot-reload, but ids remain stable ([ADR-0009](../../adr/0009-surface-id-stable-key.md)).

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

`poll` is a classmethod (no instance state needed for visibility decisions). `draw` is an instance method — the host editor instantiates the panel before calling it. A panel on a Surface with `provides` set accesses the injected host via `self.actions`; a panel on a Surface with `provides = None` leaves `self.actions` at its default `None`.

**Panel on a Surface with a host contract** (mounted by a context-menu host):

```python
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from my_lib.surfaces import SelectionActions, SelectionMenu

@panel(surface=SelectionMenu, label="Delete Selection", icon="delete")
class DeleteSelectionPanel(BasePanel):
    actions: SelectionActions   # type-checker visibility only; the framework never reads this

    def draw(self, ctx, layout):
        with layout:
            hui.button("Delete Selection", on_click=self.actions.delete_selection)
```

**Panel on a Surface with no host contract** (mounted by PropertiesEditor):

```python
@panel(surface=SettingsInspector, label="Workbench")
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

### Hosting a surface

A panel renders further Surfaces of its own by declaring them in `hosts=` and calling `self.render_surface(surface, ctx, actions=None)` inside `draw()`. This is the whole of nesting — menus, submenus, toolbars and inspector tabs are the same rule at different depths (ADR-0029). Rendering a Surface **not** named in `hosts=` is an authoring error: `render_surface` checks `surface.id` against the panel's declared `hosts` and refuses (an inline `error_label`, not a crash) if it isn't there. This is the one rule most likely to bite an author moving fast, because nothing forces the two to agree until render time — `hosts=` is what the registry walks to build the redraw union and the root/nested split *without rendering anything*, so a mismatch between what a panel declares and what it actually calls doesn't show up until someone opens that menu.

The `actions=` argument decides which host the nested panels receive — and it is **piped by default, never inferred**:

| Case | What the panel is | Call | Host passed |
| --- | --- | --- | --- |
| Pipe (common) | Arranges layout only; implements nothing itself | `self.render_surface(S, ctx)` | `self.actions` (whatever host this panel itself received) |
| Own | Implements the nested surface's `provides` Protocol itself | `self.render_surface(S, ctx, actions=self)` | `self` |
| Delegate | Neither implements it nor received it — knows of some other object that does | `self.render_surface(S, ctx, actions=obj)` | `obj` |

Pipe is the default and by far the most common case — most hosting panels are pure layout (a row of icons, a column of regions) and never implement an action Protocol themselves. Passing nothing simply relays whatever host this panel was given.

**Why never inferred.** An earlier draft of this mechanism tried to *detect* which case applied — prefer `self` if it happened to satisfy the nested Surface's Protocol, otherwise fall back to the received host. That breaks silently the moment a panel happens to structurally match a Protocol it was never meant to implement: a Protocol with no members (or one whose method names collide by coincidence) matches almost anything via `isinstance`, so inference would occasionally strand the real provider one hop up without any error at all. `render_surface`'s `isinstance` check still runs — but only to *validate* the object that was explicitly chosen, never to choose one. If you get the pipe/own/delegate call wrong, the failure is loud (an `error_label` reading "Host `X` does not satisfy `Y`"), not a silently-broken button three hops down.

### `draw()` and `draw_disabled()`

`draw()` may assume `poll()` just returned `True` — the surface applies, and (for a menu) the host has already resolved the actions object. It must not run for its own visibility check a second time; that decision was already made.

`draw_disabled()` is called instead of `draw()` when `poll()` returned `False`, on hosts that render `draw_disabled()` at all (the context-menu hosts, via `partition_panels`; the PropertiesEditor does not — an inapplicable display panel simply doesn't appear). Its default implementation is a no-op, so a panel that never overrides it keeps vanishing exactly as every panel does today — this is the zero-migration guarantee, not an oversight. Override it to follow the platform convention for a fixed-shape command menu: an inapplicable command greys rather than disappearing (see `DeleteSelectionMenuPanel` in [guides/panels](../../guides/panels.md) for a worked example).

**The rule that makes it a second method instead of a branch in `draw()`: `draw_disabled()` must not touch the state `poll()` gated on.** `poll()` decided the panel doesn't apply; `draw_disabled()` renders that fact, it does not re-derive or mutate it. A `draw_disabled()` that reads `ctx.data[EditState].active_node` because "it's probably fine" is one library update away from crashing on `None` the day `poll()`'s condition changes shape.

**The `access=` asymmetry.** A panel denied by `access=` (below the principal's `AccessTier`) renders **neither** method — it is filtered out before `poll()` even runs, by `partition_panels`'s access check. This is deliberate and different from the `poll()`-false case: a greyed disabled row still *advertises* the command exists ("Delete — you can't right now"), which is fine when the reason is selection state and wrong when the reason is the principal's access tier. Access denial must not leak "this command exists" information via a visible-but-disabled row.

### What a nested panel may not assume

A panel rendered via `render_surface` — at any depth — may not assume:

- **Its depth.** The same panel class can be a root panel today and end up nested three levels down tomorrow if some other library adds a `hosts=` edge above it. Nothing about a panel's own code can tell it how deep it sits.
- **Its siblings.** A nested panel does not know what else rendered into the same popup, menu level, or flyout — including panels from other libraries it has never heard of. `layout.state_bag` keys are namespaced for exactly this reason (see below).
- **Whether it sits in a flyout.** `hui.submenu_row` / `hui.flyout` bodies and a top-level popup scope both ultimately call the same `render_panel`; a panel's own `draw()` has no way to tell which box it landed in, and must not try to.
- **Whether its host honours `redraw_on`.** `redraw_on` is unioned and subscribed by *persistent* hosts (the PropertiesEditor) on mount. A transient host — a context menu, a flyout — is built fresh every time it opens and torn down on close; it never subscribes to anything, so a panel expecting a `redraw_on` signal to refresh its transient host's content will simply never see that refresh happen. If a panel needs to react to a signal while mounted in a transient host, it has to read current state on each `draw()`, not rely on the signal to trigger one.

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

**Ordering.** `order=` controls vertical position within a surface. Convention: 0–99 for built-in panels, 100+ for library panels, 1000+ for "always-last" panels (debug, advanced).

**`hb_*` methods are safe.** Custom helper methods on a panel class should start with `hb_`, `my_`, `custom_`, or `ext_` — same convention as nodes. Avoids future-framework name clashes.

**Imports:**

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

# Built-in surfaces live in haywire.barn.builtin.surfaces (framework-wide)
# or a library's own surfaces/ package (e.g. haybale_graph_editor.surfaces).
from haywire.barn.builtin.surfaces import AppSettings, ExecutionInspector
# For a panel that calls back into its host: import the Surface's own Protocol
# from my_lib.surfaces import MySurface, MyActions
```

**Hot-reload.** `PanelRegistry` extends `BaseRegistry`. New panel classes are picked up at the host editor's next render boundary. Existing panel instances are re-instantiated on the next `poll → draw` cycle. Surface ids are the stable lookup key, so reloads don't break surface tabs.

## 4. Live examples from the codebase

Source: [`barn/haybale-testing/haybale_testing/panels/graph/menu/`](../../../barn/haybale-testing/haybale_testing/panels/graph/menu/)

**Simple action panel** — `TestDeleteNodeMenuPanel` from `barn/haybale-testing/haybale_testing/panels/graph/menu/node/node.py`. Demonstrates the minimal action-panel skeleton: `@panel` decorator, `actions: TestNodeActions` class-body annotation, `poll()` checking `EditState`, `draw()` rendering with `with layout: hui.button(...)` and dispatching through `self.actions`:

```python
--8<-- "barn/haybale-testing/haybale_testing/panels/graph/menu/node/node.py:22:53"
```

from: `TestDeleteNodeMenuPanel` — registry_key: `haybale-testing:panel:TestDeleteNodeMenuPanel`

**SessionState-reading panel** — `TestSessionStateMenuPanel` from `barn/haybale-testing/haybale_testing/panels/graph/menu/canvas/canvas.py`. Demonstrates `poll()` reading a `SessionState` signal field and `draw()` displaying it with `with layout: hui.label(...)`:

```python
--8<-- "barn/haybale-testing/haybale_testing/panels/graph/menu/canvas/canvas.py:55:76"
```

from: `TestSessionStateMenuPanel` — registry_key: `haybale-testing:panel:TestSessionStateMenuPanel`

What these examples exercise:

| Concept | Where |
|---|---|
| `@panel(surface=..., label=..., order=...)` | both panels |
| `actions: SomeProtocol` class-body annotation (only where the Surface's `provides` is set) | `TestDeleteNodePanel` |
| `poll(cls, ctx)` as `@classmethod` | both panels |
| `ctx.data[Cls].signal_field` (bare attribute) in `poll` | both panels |
| `draw(self, ctx, layout)` 2-arg signature | both panels |
| `with layout: hui.button(label, icon, on_click)` | `TestDeleteNodePanel` |
| Dispatching through the host contract via `self.actions` | `self.actions.test_delete_node(node_id)` |
| `with layout: hui.label(text)` | `TestSessionStatePanel` |
| Reading `SessionState` via `ctx.data[Cls]` | `TestSessionStatePanel` |
| `TYPE_CHECKING` guard for `SessionContext` import | both panels |

For the host Properties editor (a panel-aware editor in `haybale-studio`), see [components/editors](../editors/editor-canon.md). For the AppState that backs the metrics, see [components/states](../states/state-canon.md). For the `hui.*` design-system primitives a panel renders with, see [reference/design-guide](../../reference/design-guide.md) §8.

---

## Quick reference

### Authoring checklist

- [ ] `@panel(surface=SurfaceClass, label='...')` — both required
- [ ] Inherit from `BasePanel`
- [ ] Where the Surface declares `provides`: add `actions: MyActionsProtocol` as a class-body annotation (type-checker visibility only, no decorator argument)
- [ ] For a panel that renders further Surfaces of its own: declare them in `hosts=(...)` and call `self.render_surface(surface, ctx)` inside `draw()` — never render a Surface not listed in `hosts=`
- [ ] Implement `poll(cls, ctx) -> bool` — fast visibility check (`@classmethod`)
- [ ] Implement `draw(self, ctx, layout)` — render content; access host as `self.actions.method(...)`
- [ ] For a panel in a fixed-shape command menu (context menu, toolbar overflow): implement `draw_disabled(self, ctx, layout)` too, without touching the state `poll()` gated on
- [ ] Set `order=` deliberately (100+ for library panels)
- [ ] Render via `with layout:` then call `hui.*` directly (`hui.info_row`, `hui.button`, `hui.empty_state`, …); drop to raw `ui.*` only for patterns `hui` doesn't cover
- [ ] Custom helpers: `hb_*` prefix
- [ ] Place in `panels/` folder; register via `add_folder_to_registry(folder_path=..., registry_cls=PanelRegistry)` in `register_components`

### Imports

```python
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.barn.builtin.surfaces import AppSettings, ExecutionInspector, CanvasSettings
```

### Built-in Surfaces

See §3, "Built-in Surfaces" above for the full table (id, inspector/menu kind, `poll(ctx)`).

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Slow `poll()` (I/O, AppState walks, expensive computations) | Runs on every context change — keep it under a millisecond |
| Forgetting `@classmethod` on `poll` | The host calls it as a classmethod before instantiation |
| `draw(self, ctx, layout, actions)` (old 3-arg signature) | Current contract is 2-arg: `draw(self, ctx, layout)`; access host via `self.actions` instead |
| Calling `self.actions` in a panel on a Surface with `provides = None` | `self.actions` is `None` there; only annotate `actions:` where the Surface's `provides` is actually set |
| Caching panel state in `__init__` | Panels are re-instantiated on hot-reload; use AppState/SessionState for cross-render state |
| Calling `ui.*` outside `draw()` (e.g. in `__init__`) | NiceGUI elements need a slot context; only `draw` provides one via `layout` |
| Hosting a Surface not declared in `hosts=` | `render_surface` refuses and renders an inline `error_label` — the check is against `hosts=`, not against what actually gets called |
| Expecting `redraw_on` to fire under a transient host (a context menu, a flyout) | Transient hosts never subscribe to signals — they are built fresh on open and torn down on close. Only a persistent host (the PropertiesEditor) unions and subscribes to `redraw_on` |
| Expecting a greyed panel's `draw()` to run | A greyed row was rendered by `draw_disabled()`, not `draw()` — `poll()` returned `False`, so `draw()` never ran at all for that mount |
