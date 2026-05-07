# Spec: the panel contract

> Status: **Phase 1 + Phase 1.5 complete (2026-05-03 / 2026-05-04).**
> The contract described here — `Panel` base class,
> `@panel(action=, focus=, label=, ...)` decorator, `Focus` base class
> with `id` ClassVar, registry methods `get_panels_for` and
> `get_focuses_for`, error boundary helper, PropertiesEditor toolbar
> discovery via `default_focuses ∪ registry.get_focuses_for(self)` —
> is in place. All production panels and test fixtures run on the new
> contract. SessionContext fields are reactive cells via the descriptor
> pattern; `clipboard` is one of them. Five `ContextMenuActions`
> Protocols + `SessionContextMenuProvider` structurally implement
> them; per-popup gesture state lives in a private `_OpenMenuContext`
> dataclass on the provider. Dual-host panels (EdgeErrors,
> EdgeWarnings, NodeErrors) split into explicit per-host classes
> sharing module-private helpers. DOM attribute renamed
> `data-hw-*-menu-scope` → `data-hw-*-menu-focus-id`. Legacy framework
> code is gone: `BasePanel`, `ScopeDescriptor`, `register_scope`,
> `get_scopes`, `get_panels`, `get_all_for_editor`, dual-mode
> `_class_filter`, `_index`, `editors=`/`scopes=` decorator args.
> `PanelLayout` moved to `panel/layout.py`. `PropertiesEditorActions`
> moved to `haybale-core` (cross-package layering fixed).
>
> Reactive Subscriptions and auto-tracking remain pending Phase 2.
>
> This document supersedes the panel-related portions of
> `spec_panel_A_plus.md`.
>
> **Companion documents:**
>
> - [`spec_panel_reactivity.md`](../spec_panel_reactivity.md) — the
>   reactive mechanism that re-runs panels on state change. Phase 2.
> - [`spec_panel_migration.md`](../spec_panel_migration.md) — inventory
>   of legacy `BasePanel` subclasses, mapping to the new contract,
>   identified gaps, and suggested migration ordering.
>
> Scope: System A only — panels and their hosts. Editors, slots,
> AppShell, and EditorWrapper (System B) are explicitly out of scope.

---

## 1. Mental model

A **panel** is a self-contained UI fragment that displays state and
optionally calls back into its host. Panels are the primary extension
point for library developers: declaring a new panel is how you add a
view of data, an inspector for a selection, or a small interactive
widget that lives inside an editor or popup.

Panels are characterized by what they are **not**:

- A panel has no identity beyond its class plus the focus it
  discriminates on. Two instances of the same panel class under the
  same focus are interchangeable.
- A panel holds no durable state. Everything it displays is read from
  a context handed in at draw time. Anything it writes goes through a
  typed action contract.
- A panel is cheap to instantiate, cheap to throw away, cheap to
  redraw. Its DOM is an output, not a possession — if the framework
  decides to clear and re-render, nothing is lost.
- A panel's only outputs are DOM (rendered into a host-provided
  layout) and action invocations (through a typed Protocol/ABC).

A panel is, in short, a function of state at a moment in time,
expressed as DOM, with a side channel for invoking host capabilities.

Panels are distinct from editors. Editors hold lifetime and state —
canvas viewport, gesture in progress, error state from a failed
instantiation. Editors are stateful containers. Panels are stateless
views. The two systems meet at one seam: an editor (or any host) may
contain a panel host that mounts panels inside its own UI. This spec
describes only the panel half of that seam.

---

## 2. The panel contract

### 2.1 The `@panel` decorator

A panel is a class decorated with `@panel` that inherits from
`Panel`. The decorator carries the panel's metadata; the class
defines its behavior.

```python
@panel(
    action=GraphCanvasContextActions,
    focus=NodeFocus,
    label="Node Properties",
    icon=hui.icon.node_info,
    order=10,
    default_open=False,
)
class NodePropertiesPanel(Panel):

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        ...

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
        actions: GraphCanvasContextActions,
    ) -> None:
        ...
```

#### Decorator arguments

Required:

- `action` — a class (Protocol or ABC recommended) declaring the host
  capability contract this panel requires. See §3.
- `focus` — a Focus subclass declaring the discriminator under which
  this panel appears. See §4.
- `label` — human-readable display label, used by the host when
  rendering chrome (panel headers, tab tooltips, etc.).

Optional:

- `icon` — Material Symbols icon name, used by the host when rendering
  chrome.
- `order` — integer sort priority. Lower values appear earlier in the
  panel list. Default: 100.
- `default_open` — whether the panel starts expanded. Default: True.
  Used by hosts that render collapsible chrome.
- `description` — human-readable description for tooltips.
- `registry_id` — unique ID for this panel; defaults to the class
  name.

The decorator validates each argument independently. `action` must be
a class; `focus` must subclass `Focus`. Cross-validation between
`action` and the host providing it is not performed at decoration —
mismatches surface at mount time (§8).

### 2.2 The `Panel` base class

`Panel` is the panel base class. Panels read from the universal
`SessionContext` — the single shared state object every host exposes
to its panels.

```python
from haywire.ui.panel import Panel

class NodePropertiesPanel(Panel):
    ...
```

A panel runs under any host that satisfies its declared action
contract (§3). Host-specific verbs are exposed via the action object;
host-specific UI state that genuinely needs to flow into a panel is
either lifted to `SessionContext` or exposed as a reactive property
on the action object. The framework does not provide a host-specific
context channel.

`Panel` provides two methods, both intended to be overridden:

- `poll(cls, ctx: SessionContext) -> bool` — classmethod returning
  whether the panel should currently be visible. Default: `True`.
- `draw(self, ctx: SessionContext, layout: PanelLayout, actions: A) -> None`
  — instance method rendering the panel's content. No default; panels
  must override.

`A` is the type declared via `action=` on the decorator.

`poll` is a classmethod so the host can decide whether to instantiate
the panel at all. If `poll` returns False, no instance is created and
no `draw` is ever called. Phase 2 (the reactive layer) changes this:
once panel methods are wrapped in Subscriptions, `poll` becomes an
instance method, and instances are long-lived across visibility flips.
See `spec_panel_reactivity.md`.

### 2.3 `poll(cls, ctx) -> bool`

`poll` returns whether the panel should appear given the current
state. Panels override it when their visibility depends on state
(e.g., "only when an edge is selected"). Panels with no conditional
visibility omit it; the default returns `True`.

`poll` is purely a function of state. It takes no signal parameter,
performs no side effects, and is expected to be cheap. The host
decides when to call it (§10).

`poll` is a classmethod. The host evaluates `poll` before deciding
whether to instantiate the panel; if `poll` returns False, no
instance is created. This keeps panel instantiation lazy: panels
that don't apply to the current state cost nothing.

### 2.4 `draw(ctx, layout, actions)`

`draw` renders the panel's content. It is called only when `poll`
returns `True`. It receives:

- `ctx: SessionContext` — the universal session state object. Panels
  read reactive state (selection, active graph, etc.) through ctx.
- `layout: PanelLayout` — a host-provided rendering contract. The
  panel renders its content using layout's helpers; the host decides
  the chrome around the content. See §5.
- `actions: A` — the host's actions object, typed against the panel's
  declared `action=` contract. The panel calls verbs on actions to
  effect host-domain changes (delete, focus-switch, reconnect, etc.).
  See §3.

`draw` is expected to be idempotent: calling it multiple times with
the same ctx produces the same DOM. The host clears the panel's body
and re-runs `draw` whenever state changes; panels must not assume
a draw call is the first.

### 2.5 What panels do not do

- Panels do not register themselves. The decorator records metadata;
  registration happens when the library is loaded by the framework.
- Panels do not enumerate their hosts. The contract is declared via
  `action=`; the registry brokers.
- Panels do not subscribe to signals or buses. State propagation is
  the framework's responsibility (§10).
- Panels do not own their chrome (headers, expansion sections, tabs).
  Chrome is host-provided via `layout`.
- Panels do not own their lifecycle. Instantiation, visibility flips,
  and disposal are managed by the host (§7).

---

## 3. The action contract

A panel declares `action=SomeClass`. `SomeClass` is the type contract
the host must satisfy for this panel to be usable. It is conventionally
a `Protocol` or `ABC`, though any class is accepted.

### 3.1 Why a contract instead of a host class

A panel declares "I work with anything that satisfies this contract,"
not "I belong to this specific host." This inverts the registration
direction:

- The panel declares its capability requirements (one direction).
- Hosts implement contracts (one direction).
- The registry brokers the match.

This gives polymorphism for free. A `DeleteNodePanel(action=Deletable)`
appears in any host that implements `Deletable` — context menu,
properties editor, future hosts. The panel never enumerates its hosts;
the host never enumerates its panels.

### 3.2 Typing the contract

A Protocol is the recommended shape:

```python
from typing import Protocol

class GraphCanvasContextActions(Protocol):
    def delete_node(self, node: NodeWrapper) -> None: ...
    def reconnect_edge(self, edge: EdgeWrapper) -> None: ...
    def focus_node(self, node: NodeWrapper) -> None: ...
```

Hosts satisfy the Protocol structurally. The panel's `actions: GraphCanvasContextActions`
parameter is type-checked against the Protocol, giving panels IDE
autocomplete and refactor-safety against the host's verb surface.

ABCs are also accepted. Use an ABC when a host hierarchy genuinely
shares an inheritable implementation; use a Protocol when the contract
is purely structural. The framework treats both uniformly at the
registry level (§8).

### 3.3 Hosts implement contracts directly

A host satisfies its own actions Protocol. There is no separate
"actions impl" object by default — when a panel calls
`actions.delete_node(node)`, the host itself receives the call. This
keeps hosts simple: a host with one action surface implements one
Protocol; a host with multiple action surfaces implements multiple
Protocols.

A host with a large action surface MAY split actions into a separate
implementation object for organizational reasons. This is a host-side
decision and invisible to panels.

### 3.4 What actions cover

Actions cover host-domain verbs: deleting, reconnecting, focus-switching,
opening a sub-editor, etc. They are **not** a chokepoint for all writes.
Panels write to the data model directly through the settings system
(or other domain APIs); actions are for verbs the host owns.

A panel that edits a node's settings calls into the settings registry
directly — no action invocation needed. A panel that deletes a node
calls `actions.delete_node(node)` — the action exists because deletion
is a host concern (it affects selection, undo state, edge cleanup, etc.).

### 3.5 Testing the contract

Panels are tested by mocking the action Protocol:

```python
from unittest.mock import MagicMock

def test_delete_button_invokes_actions():
    actions = MagicMock(spec=GraphCanvasContextActions)
    panel = NodePropertiesPanel()
    ctx = ...  # built test context
    layout = ...  # captured layout
    panel.draw(ctx, layout, actions)
    # simulate user clicking the delete button
    actions.delete_node.assert_called_once()
```

No host instance, no editor, no slot. The Protocol is the testing seam.

---

## 4. The focus system

### 4.1 Focus as a discriminator

A `Focus` is a class that discriminates which panels apply to the
current state. NodeFocus selects panels relevant when a node is
selected; EdgeFocus when an edge is selected; AppFocus is always
available (used for non-selection-driven panels).

Focuses are classes, not strings. A panel declares `focus=NodeFocus`
in its decorator; the registry indexes panels by focus class.

### 4.2 The Focus base

```python
from haywire.ui.panel import Focus

class NodeFocus(Focus):
    label = "Node"
    icon = "account_tree"
    order = 60

    @classmethod
    def available(cls, ctx) -> bool:
        return ctx.active_node.value is not None
```

Each Focus subclass declares:

- `label`, `icon`, `order` — class attributes used by the host when
  rendering toolbar chrome.
- `available(ctx) -> bool` — classmethod returning whether this focus
  is reachable given current state. Used by hosts to decide which
  focus tabs to show or enable.

### 4.3 Selection focuses vs. mode focuses

Two natural shapes of focus emerge:

- **Selection focuses** — NodeFocus, EdgeFocus, GraphFocus, PortFocus.
  `available()` reads from selection state. A selection focus is
  available when its target is selected.
- **Mode focuses** — AppFocus, ExecutionFocus, CanvasFocus,
  SettingsFocus. `available()` returns True (or close to it). These
  represent always-reachable views grouped by purpose.

Both shapes use the same `Focus` base. The framework treats them
uniformly.

### 4.4 Toolbar contents: default focuses + registry discovery

A host renders one tab per focus it knows about. A focus enters the
host's toolbar through one of two channels:

**Channel 1: the host's `default_focuses`.** The host declares a
baseline set of focuses it always renders, regardless of whether any
panel currently uses them. This is the host's UX commitment — the
tabs the host itself wants to ensure exist.

```python
class PropertiesEditor:
    default_focuses: ClassVar[tuple[type[Focus], ...]] = (
        AppFocus, ExecutionFocus, CanvasFocus,
        GraphFocus, NodeFocus, SettingsFocus, EdgeFocus, PortFocus,
    )
```

**Channel 2: registry discovery.** The panel registry tracks the
`focus=` class on every registered panel. The host queries:

```python
focuses = registry.get_focuses_for(actions_provider=self)
```

The registry returns every focus class referenced by at least one
panel whose action contract `self` satisfies. Library-introduced
focuses appear here automatically: a library that registers a panel
with `focus=AudioEffectFocus, action=PropertiesEditorActions` causes
`AudioEffectFocus` to be returned by PropertiesEditor's query — no
host code change required.

The host's toolbar contents are the union of `default_focuses` and
`registry.get_focuses_for(self)`, sorted by `Focus.order`.

This replaces the legacy `register_scope` mechanism: defining a
`Focus` subclass and registering a panel that uses it *is* the
declaration. There is no separate "register this focus with the
editor" call. Focus existence is a side effect of having panels,
plus the host's own baseline.

> **Migration note.** The current `PanelRegistry.register_scope` API
> and `ScopeDescriptor` plumbing are deprecated by this design. Once
> all libraries migrate to class-keyed `focus=` panel registration,
> remove `register_scope`, `get_scopes`, and `ScopeDescriptor` from
> the panel registry. See out-of-scope §11 for legacy migration
> tracking.

Focus and action are orthogonal. A panel under `focus=NodeFocus,
action=Deletable` appears in any Deletable-implementing host whenever
NodeFocus is the active tab. The two filters are independent.

### 4.5 Focus.available — Phase 1 vs. Phase 2

The `available(cls, ctx) -> bool` contract is fully usable in Phase 1:
hosts re-evaluate `Focus.available()` for each focus in their toolbar
on relevant state changes (selection moved, active graph moved, etc.)
and update the toolbar accordingly.

Phase 2 (the reactive layer) wraps each `available()` call in a
Subscription so toolbar buttons refresh surgically on dependency
change. Whether Focus authors should declare `@reads(...)` on
`available()` (matching the panel contract for drift verification) is
an open question deferred to Phase 2 design. See
`spec_panel_reactivity.md` §7.1.

---

## 5. Layout: the host's rendering contract

The third parameter to `draw` is `layout: PanelLayout`. Layout is the
host's rendering contract for this panel — it provides a container to
render into and host-appropriate helpers for common patterns.

### 5.1 What layout provides

```python
class PanelLayout:
    @property
    def container(self) -> Element: ...

    def __enter__(self) -> "PanelLayout": ...
    def __exit__(self, *args) -> None: ...

    def section_label(self, text: str) -> Element: ...
    def separator(self) -> None: ...
    def empty_state(self, message: str, *, icon: str = ...) -> Element: ...
    def expansion_section(self, label: str, ...) -> ContextManager: ...
    def label(self, text: str) -> Element: ...
    def button(self, text: str, *, on_click: Callable) -> Element: ...
    # ...
```

Panels call layout helpers directly, or use layout as a context manager
to render arbitrary content into its container:

```python
def draw(self, ctx, layout, actions):
    with layout:
        hui.label("Custom rendering")
        hui.button("Action", on_click=lambda: actions.do_thing())
```

### 5.2 Hosts decide chrome via layout

The panel never sees the chrome around its content. A panel inside a
PropertiesEditor sees a layout whose container is the body of an
expansion section; the expansion's header (with the panel's label and
icon, read from the decorator metadata) is rendered by the host.

A panel inside a context menu popup sees a layout whose container is
a flat row in the popup; no expansion at all.

The same panel renders identically into both layouts. The panel
contract is "render content using layout's helpers"; the host contract
is "decide what chrome wraps the content."

### 5.3 Host-specific layouts

Hosts MAY subclass `PanelLayout` to add host-specific helpers:

```python
class PropertiesPanelLayout(PanelLayout):
    def setting_row(self, key: str, value: Any) -> Element: ...
```

Panels typed against the base `PanelLayout` work under any host.
Panels typed against a host-specific subclass work only under that
host (and break the polymorphism win — usually undesirable, but
sometimes necessary for host-specific UI patterns).

The base `PanelLayout` contract should be rich enough that most
panels never need a subclass.

---

## 6. Error handling at the host boundary

Panels are user-authored. `poll` and `draw` may raise — bad cast,
missing attribute on a hot-reloaded type, panel author bug. The
framework's contract:

- The host catches all exceptions raised by panel methods.
- The host wraps the exception as a `HaywireException` with context
  (panel class, method, ctx snapshot).
- The host renders an inline error widget in place of the panel's
  content, preserving sibling panels.

This is a framework guarantee. Library authors do not write try/except
around their own panel code; the framework provides the boundary.

The principle generalizes: any registry-managed library class whose
methods are invoked by the framework has its exceptions caught at the
framework boundary, wrapped, and surfaced as visible errors. Silent
failure is not acceptable; whole-editor crashes are not acceptable;
inline visible failure is the default.

The existing `haywire_exception.py` + `error_info.py` infrastructure
provides the rendering. Hosts integrate with it; panels need not know
it exists.

---

## 7. Panel state and lifecycle

### 7.1 Panel state on `self`

Panels MAY hold ephemeral UI-local state on `self`. Examples: the
currently-typed text in an autocomplete dropdown, the locally-selected
sub-tab inside a panel, the open/closed state of a nested expansion
that the panel renders itself.

This is best-effort, not durable. Hot-reloading the panel class
discards the instance and any state on it. State that should survive
hot-reload, or that should be shared across panel instances, lives on
the session — not on `self`.

### 7.2 What the host commits to

The host's lifecycle commitments to a panel:

- `poll(cls, ctx)` is called whenever the host needs to (re)evaluate
  visibility. The exact trigger depends on the state-propagation
  layer; see §10.
- The panel is instantiated only when `poll` returns True. `__init__`
  runs once per instance.
- `draw(self, ctx, layout, actions)` is called when the host renders
  the panel's body. The host clears the body before each `draw`.
- Disposal happens when `poll` flips back to False, when the panel's
  focus is no longer active, or when the host unmounts. Panels with
  cleanup needs MAY expose a `dispose()` method, but most panels —
  being stateless — need neither.

The panel instance's lifetime is the host's responsibility, not the
panel's. Phase 1 hosts may dispose-and-recreate on every visibility
flip; Phase 2 hosts keep the instance alive across flips and toggle
only the rendered DOM. Panel authors write to the contract above and
do not depend on either lifetime model.

### 7.3 What panels must not assume

- Panels must not assume `__init__` has access to ctx. Ctx is passed
  to `poll` and `draw`, not to the constructor.
- Panels must not assume `draw` runs only once. The host may redraw
  many times against the same instance.
- Panels must not assume the same instance is reused across visibility
  flips. Phase 1 hosts may instantiate fresh on each show; Phase 2
  hosts keep instances long-lived.
- Panels must not assume their state on `self` survives any
  particular event (hot-reload, focus switch, navigation). Treat
  `self`-state as ephemeral.

---

## 8. Registry resolution

### 8.1 Hosts query the registry explicitly

A host queries for panels by passing what it has:

```python
panels = registry.get_panels_for(
    actions_provider=self,            # the host's actions object (often `self`)
    focus=self.active_focus,          # the currently active Focus class
)
```

The registry filters panels by:

- `isinstance(actions_provider, panel.action)` — does the host
  satisfy the action contract? (Protocols require `@runtime_checkable`;
  ABCs and concrete classes work directly via `isinstance`.)
- `panel.focus is focus` (or compatible) — does the panel's focus
  match the host's current focus?

Panels that pass both filters are returned, sorted by `order`. The
host then passes its `SessionContext` to each returned panel at
draw time; no per-panel context-type matching is required because
the context type is uniform across the framework.

### 8.2 Mismatches surface at mount

Cross-validation between `action` and `focus` is not performed at
decoration. The decorator validates each argument independently.
Mismatches surface naturally at runtime: a host that doesn't satisfy
a panel's `action` contract simply doesn't get that panel from the
query.

If a panel is registered with a coherent declaration but no host ever
matches it, it's effectively dead code — surfaced through tooling
(linters, registry diagnostics) rather than through framework errors.

### 8.3 Discovering focuses

Hosts also query the registry to discover which focuses to render in
their toolbar:

```python
focuses = registry.get_focuses_for(actions_provider=self)
```

The registry returns the set of focus classes referenced by panels
whose `action` contract `actions_provider` satisfies. The host
unions this with its own `default_focuses` (per §4.4) and renders
the merged set, sorted by `Focus.order`.

This is how library-introduced focuses appear in compatible hosts'
toolbars without any host-side configuration: registering a panel
with a new focus class is the only step the library takes.

### 8.4 Hot-reload

Panels are hot-reloadable like other registry-managed library classes.
The registry handles class reloads; hosts re-query as needed. Panel
authors do not write hot-reload-aware code; the framework provides
the lifecycle.

When a library that introduced a new focus is reloaded or unloaded,
the registry's tracked focus set updates accordingly. Hosts re-query
`get_focuses_for(...)` and the toolbar reflects the change.

---

## 9. Worked example

A panel that shows the active node's connection errors, lives in
the EdgeFocus tab of any host that supports a "Deletable" surface:

```python
from typing import Protocol, runtime_checkable
from haywire.ui.panel import Panel, panel
from haybale_core.focuses import EdgeFocus
from haywire.ui import elements as hui

@runtime_checkable
class Deletable(Protocol):
    def delete_edge(self, edge_id: str) -> None: ...

@panel(
    action=Deletable,
    focus=EdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=10,
)
class ConnectionErrorsPanel(Panel):

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        edge = ctx.active_edge.value
        return edge is not None and edge.get_state().get_error() is not None

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
        actions: Deletable,
    ) -> None:
        edge = ctx.active_edge.value
        with layout:
            hui.error_label(str(edge.get_state().get_error()))
            hui.button(
                "Delete connection",
                on_click=lambda: actions.delete_edge(edge.edge_id),
            )
```

Properties of this panel:

- It works in any host that implements `Deletable` — context menu,
  properties editor, anywhere. No dual-class workaround.
- It declares its dependency on the active edge through reading
  `ctx.active_edge.value`. (How the framework knows to re-run
  `poll`/`draw` when this changes is the reactivity layer; see
  `spec_panel_reactivity.md`.)
- It writes through a typed action (`actions.delete_edge`); the
  edge id comes from local state.
- Its chrome is the host's choice. PropertiesEditor wraps it in an
  expansion; a popup might render it flat.

---

## 10. Reactivity

The contract above describes what panels look like and how they
interact with hosts. It does not describe **when** `poll` and `draw`
re-run — that is the concern of the reactivity layer.

The reactive layer is specified separately in
[`spec_panel_reactivity.md`](../spec_panel_reactivity.md). The two specs
are intended as Phase 1 (contract) and Phase 2 (reactivity) for
implementation. Panels written against this contract can be mounted
under any state-propagation mechanism that re-runs `poll` and `draw`
on relevant changes; the reactivity spec describes the framework's
chosen mechanism.

The contract assumes:

- `SessionContext` exposes reactive fields (`active_node`,
  `active_edge`, etc.) that panels read during `poll` and `draw`.
- Some framework-level mechanism re-runs `poll` and `draw` when the
  state they read changes.
- The mechanism coalesces multiple state changes within one event-
  loop tick into a single re-render pass.

How that mechanism is implemented (auto-tracking, declared `@reads`,
the host's dirty queue and flush loop) is the reactivity spec's
concern.

---

## 11. Out of scope

The following are deliberately outside this spec:

- **Editors, slots, AppShell, EditorWrapper (System B).** Panel hosting
  inside editors is a seam the editor implements; how the editor
  itself is structured is a separate design concern.
- **The reactive mechanism.** Specified in `spec_panel_reactivity.md`.
- **Host-internal scheduling and flush mechanics.** Specified in
  `spec_panel_reactivity.md`.
- **The settings system, hot-reload internals, registry hot-reload
  events.** Panels interact with these; the contracts of those systems
  are documented elsewhere.
- **Legacy `BasePanel` migration.** The current codebase has 33
  `BasePanel`-based panels still in service. The inventory, scope→
  focus mappings, identified gaps (no `ContextMenuActions` Protocol;
  unclear `selection` / `node.errors` / `port.info` scopes) and a
  suggested migration ordering are in
  [`spec_panel_migration.md`](../spec_panel_migration.md).
- **Removal of the legacy `register_scope` API.** The class-keyed
  focus design (§4.4) replaces `PanelRegistry.register_scope`,
  `get_scopes`, and the `ScopeDescriptor` plumbing. Removal happens
  post-migration — see `spec_panel_migration.md` §5.

---

## 12. Glossary

- **Panel**: a class decorated with `@panel`, inheriting from
  `Panel`, providing `poll(ctx)` and `draw(ctx, layout, actions)`.
- **Host**: an object that mounts panels. Implements one or more
  action contracts; provides the universal `SessionContext` and a
  `PanelLayout` to its panels; manages panel lifecycle.
- **Action**: a class (typically Protocol) declaring host capability
  verbs. Panels declare which action they require via `action=`.
- **Focus**: a class discriminating which panels apply to current
  state. Panels declare which focus they appear under via `focus=`.
  Hosts declare a baseline set via `default_focuses`; additional
  focuses appear automatically via registry discovery
  (`registry.get_focuses_for(...)`).
- **SessionContext**: the universal session state object. Carries
  reactive fields (selection, active graph, etc.) that panels read
  during `poll` and `draw`. The single context type panels are
  written against.
- **Layout**: a host-provided rendering contract passed to panels at
  draw time. Provides a container and rendering helpers; the host
  decides chrome around the content.
- **Reactive**: a value holder that auto-subscribes readers and
  notifies subscribers on writes. The mechanism behind state-driven
  re-renders.
- **Subscription**: a binding of one method to its current dependency
  set. Re-runs on dependency change.
- **`@reads`**: declarative metadata on a panel method declaring which
  reactive paths the method reads. Documentation + drift verification;
  not the subscription mechanism itself.
