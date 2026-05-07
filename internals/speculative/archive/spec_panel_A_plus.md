# Speculative: panels and hosts, the A+ design

> Status: speculative spec. No code changes proposed yet.
> Audience: anyone deciding whether to commit to a structural rewrite of
> the editor/panel architecture, or anyone trying to understand what
> "doing it right" would look like if migration cost were free.
> Companion to `panels_and_hosts.md`, which describes the smaller B+
> reframe. This document is the A+ version: stronger primitives,
> end-to-end types, one mental model.

---

## 1. The mental model

Haywire's UI is a tree of **hosts** and **children**.

A host is anything that contains other UI things. AppShell is a host —
it contains editors. PropertiesEditor is a host — it contains panels.
GraphCanvasEditor is a host — it contains its main canvas widget *and*,
when the user right-clicks, a popup that contains panels. Every host
contains zero or more children.

A child is anything contained by a host. Editors are children of
AppShell. Panels are children of editors. Children read state from the
session and call actions on their host.

The pattern is identical at every level:

1. The host **gathers** its children — by querying a registry keyed on
   *classes*, not strings.
2. The framework **subscribes** each child to the session fields it
   declares it reads.
3. When those fields change, the framework **re-renders** just the
   children that care.

Hosts come in two shapes. **Stack hosts** render their visible children
in order; visibility flips mount and unmount each child. **Tab hosts**
keep all children mounted in a tab-panels keep-alive container and
display one at a time. The lifecycle differs — *when* a child is
mounted, *whether* it stays mounted across switches — but the gather /
subscribe / render-on-change cycle is the same primitive.

This unification is grounded, not aspirational. Haywire's existing
[`Slot`](packages/haywire-core/src/haywire/ui/app/slot.py) is a tab
host today even though the code doesn't say so: it owns a list of
`EditorWrapper`s, mounts them all into `ui.tab_panels` with
`keep-alive`, captures the NiceGUI tab client to survive
background-thread redraws, routes signals into the active wrapper's
poll, and listens for registry batch events to auto-attach REQUIRED
editors. Promote that pattern to a `TabHost` ABC and PropertiesEditor's
flat panel list to a `StackHost` ABC, and most of the host machinery
this spec invokes is already written — what's missing is the reactive
subscription layer that replaces the `poll(signal)` gate.

There is no `poll(signal)` loop. There is no `metadata` dict. There is
no `Session` versus `SessionContext` split. There is no string-keyed
registration. There are no special cases for popups, dual-editor
panels, or "this panel is also an editor extension." Each of those
appears in the current code because the framework lacks a primitive
strong enough to express it cleanly. A+ provides the primitive and the
special cases dissolve.

Once you internalize "hosts and children, typed all the way down," every
decision in this spec follows mechanically.

---

## 2. The four primitives

The whole architecture is four concepts. Everything else is mechanism.

### 2.1 `Session`

One per browser session. Holds state *and* services. Selection,
active-graph, signal channel, lifecycle channel, library service —
all on one object. There is no `SessionContext`. The split that
existed in the legacy code is gone.

```python
class Session:
    session_id: str
    app: HaywireApp

    # State (reactive — see §5)
    active_graph: Reactive[BaseGraph | None]
    active_node: Reactive[NodeWrapper | None]
    active_edge: Reactive[EdgeWrapper | None]
    selected_nodes: Reactive[frozenset[str]]
    workspace_name: Reactive[str]
    # ...

    # Services
    def signal(self, s: ContextSignal) -> None: ...
    def lifecycle(self, c: LifecycleCommand) -> None: ...
```

### 2.2 `Host[C]`

A host is generic over the **child-context type** it provides. It owns
the gather → subscribe → render-on-change cycle, the registry-driven
child lookup, the NiceGUI client-context capture for background-thread
redraws, the hot-reload coordination, and the mount/redraw/unmount
lifecycle. The framework-internal ABC:

```python
class Host(Generic[C], ABC):
    """Base for anything that contains children. Owns lifecycle and subscription wiring."""
    context_type: ClassVar[type[C]]

    @abstractmethod
    def context(self, session: Session) -> C:
        """Build the typed context handed to each child at draw time."""

    @abstractmethod
    def gather(self, session: Session) -> Iterable[ChildBinding]:
        """Return the children to render, in order. Typically a registry query."""

    # Lifecycle implemented by the ABC, not subclassed
    def _mount_child(self, binding: ChildBinding, session: Session) -> None: ...
    def _redraw_child(self, child: Child) -> None: ...
    def _unmount_child(self, child: Child) -> None: ...
```

Two concrete specializations are useful enough to ship in the
framework:

```python
class StackHost(Host[C]):
    """Children rendered in order, all visible (gated by visible()).
    Mount/unmount when visibility flips. The default for editors that
    host panels."""

class TabHost(Host[C]):
    """Children kept alive in a ui.tab_panels keep-alive container.
    Exactly one is active at a time; switching is set_value, not
    mount/unmount. The default for the AppShell's slots."""
```

The two specializations differ in mount strategy, active-child
semantics, and whether they have layout chrome (tab bar / icon strip).
They share the registry lookup, subscription wiring, NiceGUI client
capture, and hot-reload coordination — that's the ABC's job.

Existing classes map cleanly:

- [`Slot`](packages/haywire-core/src/haywire/ui/app/slot.py) →
  `TabHost[SlotContext]`. The current `_capture_tab_client`,
  `_render_area_contents`, `_redraw`, `_on_class_added`, and
  `handle_signal` lift onto the ABC; the per-slot subclasses
  (`IconSlot`, `TabSlot`) keep only their bar-rendering specialization.
- `BaseEditor` (when hosting panels) → `StackHost[EditorContext]`. The
  current poll/draw cycle and panel-list iteration become the ABC's
  responsibility; the editor's own render code shrinks to "build my
  context" plus whatever main-pane content it has outside its panel
  list.

### 2.3 `Child[C]`

A child is generic over the **context type its host provides**. A panel
that lives in PropertiesEditor is a `Child[PropertiesEditorContext]`.
The class-level generic parameter is the panel's contract: "I expect
this kind of host to render me."

```python
class Child(Generic[C], ABC):
    """Base for anything contained by a host."""

    @abstractmethod
    def draw(self, session: Session, layout: Layout, ctx: C) -> None: ...
```

A child whose generic parameter is the bare `HostContext` ABC is
host-agnostic — it works under any host that knows its focus. That's
how display-only panels (`EdgeErrorsPanel`, `EdgeWarningsPanel`) are
expressed: by typing, not by convention.

Existing classes that become `Child` subclasses:

- `EditorWrapper` → `Child[SlotContext]`. Today's binding-management
  (label, payload, `on_focus`, per-key registry subscription for
  RELOADED/REMOVED) stays in the wrapper; the framework's `Child`
  lifecycle absorbs the mount/unmount and subscription-wiring half.
- `BasePanel` → `Child[EditorContext]`.
- `BaseDisplayPanel` → `Child[HostContext]` — the host-agnostic case.

### 2.4 `EditorContext` / `HostContext`

The typed object the host hands its children at draw time. Each host
defines its own concrete type. It contains:

- A typed **action API** (a `Protocol`) the children can call.
- Any host-local view state the children need to read.
- Optionally, a **rendering position** when the host is rendering into
  a popup or other transient surface — but this lives on the `Layout`,
  not the context (see §6.4).

```python
class GraphCanvasActions(Protocol):
    def remove_nodes(self, ids: list[str]) -> None: ...
    def add_node(self, registry_key: str, pos: CanvasPos) -> None: ...
    def reconnect_edge(self, edge_id: str, end: EdgeEnd) -> None: ...

@dataclass
class GraphCanvasEditorContext:
    actions: GraphCanvasActions
    selection: SelectionView
```

That's it. Four concepts. The rest of this document is showing what
falls out.

---

## 3. Walkthrough: seven examples a developer hits in their first week

### 3.1 "I want to show an error block when an edge has errors"

This is the dual-editor display-panel case — works in PropertiesEditor's
edge tab and in the canvas's edge-right-click popup. Today it requires
a list-typed `editors=` field and a "type against the base, don't read
it" convention.

A+:

```python
@panel(focus=EdgeFocus)
class EdgeErrorsPanel(DisplayPanel):
    """A display panel — works under any host that knows EdgeFocus."""

    @reads(Session.active_edge)
    def visible(self, edge):
        return edge is not None and edge.has_errors()

    @reads(Session.active_edge)
    def draw(self, edge, layout):
        layout.error_block(edge.errors())
```

What changed:

- `DisplayPanel` is a separate base class. It declares no host. It
  receives no `EditorContext`. The framework routes it to every host
  that has registered the focus.
- The panel doesn't say "I work in PropertiesEditor and the canvas
  popup" — it says "I attach to `EdgeFocus`." Whether one host renders
  that focus in a tab or another renders it in a popup is the host's
  concern, not the panel's.
- `@reads(Session.active_edge)` is the subscription declaration. The
  framework calls `visible()` only when `active_edge` changes; it calls
  `draw()` only when `active_edge` changes *and* the panel is visible.
  No `poll()` method, no host-wide redraw cycle.

The developer wrote 8 lines. The framework handles routing,
subscription, visibility gating, and re-render granularity.

### 3.2 "I want a context-menu action that deletes the right-clicked node"

Today: fish `on_emit_event` out of `metadata`, construct a
`UserRemoveEvent`, hope the canvas event vocabulary doesn't change.

A+:

```python
@panel(host=GraphCanvasEditor, focus=NodeFocus)
class DeleteNodePanel(Panel[GraphCanvasEditorContext]):

    @reads(Session.active_node)
    def visible(self, node):
        return node is not None

    @reads(Session.active_node)
    def draw(self, node, layout, editor):
        layout.button(
            "Delete",
            icon="delete",
            on_click=lambda: editor.actions.remove_nodes([node.node_id]),
        )
```

What changed:

- `host=GraphCanvasEditor` is a class reference. The decorator validates
  that the panel's `Panel[GraphCanvasEditorContext]` parameter matches
  the host's declared `context_type`. A typo or mismatch is a
  registration-time error, not a runtime crash.
- `editor.actions.remove_nodes(...)` is a typed method on a typed
  protocol. IDE autocomplete works. Refactoring the action API
  (renaming, adding a parameter) updates every call site at compile
  time.
- The panel never sees `UserRemoveEvent`. The event vocabulary is the
  editor's internal business. Library authors who write context-menu
  panels learn one API: `editor.actions.*`. They do not learn the event
  catalog.

### 3.3 "I want a panel that highlights when the selected port has incompatible connections"

A non-trivial reactive case — the panel reads `active_port` *and* the
graph's edge list, and re-renders when either changes.

A+:

```python
@panel(host=PropertiesEditor, focus=PortFocus)
class PortCompatibilityPanel(Panel[PropertiesEditorContext]):

    @reads(Session.active_port)
    def visible(self, port):
        return port is not None

    @reads(Session.active_port, Session.active_graph.edges)
    def draw(self, port, edges, layout, editor):
        incompatible = [e for e in edges if e.connects(port) and not e.is_valid()]
        if not incompatible:
            layout.label("All connections valid", style="success")
        else:
            for edge in incompatible:
                layout.error_row(edge.describe_incompatibility())
```

What changed:

- `@reads(Session.active_port, Session.active_graph.edges)` declares a
  *field-level* subscription. The framework re-runs `draw()` only when
  `active_port` *or* `active_graph.edges` changes. A change to
  `selected_nodes` or `workspace_name` doesn't even invoke this panel.
- The path-level subscription (`Session.active_graph.edges`) reaches
  through the reactive graph; if `active_graph` changes, the
  subscription rebinds to the new graph's edge list automatically.
- No imperative redraw loop. No "is this panel visible? then re-poll
  every other panel too." Each panel's read-set is its own concern.

### 3.4 "I want to add a new editor: a file browser with right-click context menus"

Today: impossible without core changes. The string `"context_menu"` is
already the canvas's; a second editor's context menu would collide.

A+:

```python
class FileBrowserActions(Protocol):
    def open_file(self, path: Path) -> None: ...
    def reveal_in_finder(self, path: Path) -> None: ...
    def delete_file(self, path: Path) -> None: ...

@dataclass
class FileBrowserEditorContext:
    actions: FileBrowserActions
    cwd: Path

@editor(slot="left", label="Files", icon=hui.icon.folder)
class FileBrowserEditor(Editor[FileBrowserEditorContext]):
    context_type = FileBrowserEditorContext

    actions: FileBrowserActionsImpl  # the host's own implementation

    def context(self, session):
        return FileBrowserEditorContext(actions=self.actions, cwd=self._cwd)

    def render_main(self, session, layout, ctx):
        # ... draws the file tree, raises FileSelected focus on click,
        # raises FileRightClicked focus on right-click which the
        # framework renders as a popup
        ...
```

A library now writes context-menu panels for the file browser exactly
the same way it writes panels for the canvas:

```python
@panel(host=FileBrowserEditor, focus=FileSelectedFocus)
class OpenFilePanel(Panel[FileBrowserEditorContext]):

    @reads(Session.active_file)
    def visible(self, file):
        return file is not None

    @reads(Session.active_file)
    def draw(self, file, layout, editor):
        layout.button("Open", on_click=lambda: editor.actions.open_file(file))
```

What changed:

- Adding a new editor with its own context menus required **zero new
  framework concepts**. The developer defined a context type, an
  actions protocol, and an editor class. Panels follow.
- The string `"context_menu"` doesn't exist in A+. The whole concept
  was a workaround for not having typed editor binding. Each editor is
  a distinct host class; their popups don't collide because they're
  different types.

### 3.5 "I want to test the DeleteNodePanel"

Today: construct a full Session, build a fake `on_emit_event` callable,
plant it in `metadata`, render the panel, assert on the callable's
call list.

A+:

```python
def test_delete_node_panel_calls_remove_nodes():
    actions = Mock(spec=GraphCanvasActions)
    session = make_test_session(active_node=make_node("n1"))
    ctx = GraphCanvasEditorContext(actions=actions, selection=...)
    layout = TestLayout()

    panel = DeleteNodePanel()
    panel.draw(session, layout, ctx)

    layout.click_button("Delete")
    actions.remove_nodes.assert_called_once_with(["n1"])
```

What changed:

- `Mock(spec=GraphCanvasActions)` builds a fake from the protocol. Mypy
  catches misuse against the spec.
- The test never constructs a `GraphCanvasManager`. The action protocol
  is the seam; the manager is the production implementation behind it.
- No `metadata` plumbing. No "remember to set `on_emit_event` before
  drawing." The dependency is in the panel's signature.

This is the test-ergonomics payoff of typed seams. Every protocol-typed
dependency is a test seam by construction.

### 3.6 "I want a hover menu that libraries can extend per node capability"

A node-hover menu is a small floating popover that appears when the
cursor lingers over a node. It shows two or three quick actions —
*not* the full right-click menu. The interesting twist: different
libraries contribute different actions, gated on what their nodes can
actually do. A node from `haybale-ai` should expose a "Regenerate"
button that nodes from `haybale-core` don't. A node from
`haybale-locking` should expose a "Lock/Unlock" toggle that no other
library knows about. A node from a library that depends on both should
show all three.

This is the real stress test: the framework has to compose
contributions from libraries that don't know about each other, gated
on properties only some nodes have, into one coherent surface.

#### The framework pieces

Three small additions, each consistent with primitives already
introduced.

```python
# Session gains gesture state for hover (per §6.2 — gesture state lives on Session)
class Session:
    hovered_node: Reactive[NodeWrapper | None]

# A focus that becomes available when a node is hovered
class NodeHoverFocus(Focus):
    label = "Hover"
    icon = "pan_tool"
    @classmethod
    @reads(Session.hovered_node)
    def available(cls, node):
        return node is not None

# The canvas editor opens a hover popup when hovered_node becomes non-None
# and closes it when it becomes None — same Layout-with-position machinery
# the right-click menu uses, just triggered by a different gesture.
```

That's the whole framework contribution. No new host kind, no new
registry, no new decorator. The hover menu is a popup the canvas opens
in response to a different gesture, surfacing panels that match a
different focus.

#### The core's contribution: a "Delete" button that works on every node

```python
@panel(host=GraphCanvasEditor, focus=NodeHoverFocus, order=10)
class HoverDeletePanel(Panel[GraphCanvasEditorContext]):
    @reads(Session.hovered_node)
    def draw(self, node, layout, editor):
        layout.icon_button(
            "delete",
            tooltip="Delete node",
            on_click=lambda: editor.actions.remove_nodes([node.node_id]),
        )
```

No `visible()` — the focus's `available()` already gates on
`hovered_node is not None`. The panel just draws.

#### A library adds a capability and a panel that reads it

```python
# In haybale-ai/

@runtime_checkable
class Regenerable(Protocol):
    """Nodes that can regenerate their output from current inputs."""
    def regenerate(self) -> None: ...

@panel(
    host=GraphCanvasEditor,
    focus=NodeHoverFocus,
    requires=Regenerable,
    order=20,
)
class HoverRegeneratePanel(Panel[GraphCanvasEditorContext]):
    @reads(Session.hovered_node)
    def draw(self, node: Regenerable, layout, editor):
        layout.icon_button("refresh", tooltip="Regenerate", on_click=node.regenerate)
```

The `requires=Regenerable` parameter is the key piece. It tells the
framework: *only route this panel to a hover surface where the
hovered node is an instance of `Regenerable`.* Internally it desugars
to a synthesized `visible()`:

```python
# What requires= compiles to
@reads(Session.hovered_node)
def visible(self, node):
    return isinstance(node, Regenerable)
```

But the panel author doesn't write that. They declare the requirement
at the decorator level and get a typed-narrowed `node: Regenerable` in
the body. Mypy verifies that the panel only calls
capability-protocol methods. No `cast()`, no runtime guard inside the
body.

#### Another library adds an unrelated capability

```python
# In haybale-locking/ — knows nothing about haybale-ai

@runtime_checkable
class Lockable(Protocol):
    is_locked: bool
    def toggle_lock(self) -> None: ...

@panel(
    host=GraphCanvasEditor,
    focus=NodeHoverFocus,
    requires=Lockable,
    order=30,
)
class HoverLockPanel(Panel[GraphCanvasEditorContext]):
    @reads(Session.hovered_node)
    def draw(self, node: Lockable, layout, editor):
        layout.icon_button(
            "lock" if node.is_locked else "lock_open",
            tooltip="Toggle lock",
            on_click=node.toggle_lock,
        )
```

`haybale-locking` and `haybale-ai` know nothing about each other.
Neither imports the other. They each contribute one panel and one
protocol.

#### A node author opts in by satisfying protocols

```python
# In haybale-ai/nodes/

class StableDiffusionNode(BaseNode):
    """Has both Regenerable and Lockable capabilities."""

    is_locked: bool = False

    def regenerate(self) -> None:
        self.invalidate_outputs()
        self.execute()

    def toggle_lock(self) -> None:
        self.is_locked = not self.is_locked
```

`StableDiffusionNode` satisfies `Regenerable` (has `regenerate()`) and
`Lockable` (has `is_locked` and `toggle_lock()`). It doesn't subclass
either protocol — protocols are structural in Python. The node author
writes the methods their domain calls for; the panel-side
`isinstance()` check picks them up.

#### What the user sees

Hovering over `StableDiffusionNode`:

```text
[ delete ]  [ refresh ]  [ lock_open ]
```

Hovering over a vanilla `BaseNode` from `haybale-core`:

```text
[ delete ]
```

Hovering over a node that is `Lockable` but not `Regenerable`:

```text
[ delete ]  [ lock_open ]
```

The framework composes the menu deterministically from whichever
panels apply. Order is by `order=` parameter; ties fall back to
registration order.

#### What this stress-tests in the architecture

1. **Library independence is structural, not coordinated.** Library A
   and Library B both target `(GraphCanvasEditor, NodeHoverFocus)`.
   Neither knows about the other. The registry's class-keyed index
   merges their contributions automatically. There is no coordination
   protocol, no manifest registration, no priority negotiation.

2. **Capability-based filtering is one decorator parameter.**
   `requires=Regenerable` is the entire opt-in. The framework
   synthesizes the visibility predicate. The panel body gets a typed
   `node: Regenerable` parameter.

3. **The capability protocol is the seam between node author and
   panel author.** Once `Regenerable` exists, *any* node — even from a
   third library that never imported `haybale-ai` — can satisfy it by
   defining `regenerate()`. The "Regenerate" button appears for that
   node automatically. Plugin authors can extend each other's UIs by
   satisfying each other's protocols.

4. **No new framework concepts were needed.** `NodeHoverFocus` is a
   `Focus` subclass. `Regenerable` is a `Protocol`. `requires=` is a
   decorator parameter that desugars to `visible()`. The hover popup
   is the same `Layout`-with-position the right-click menu uses,
   triggered by a different gesture. Every piece was already in the
   architecture.

5. **The pattern generalizes immediately.** Hover menus on edges? Add
   `EdgeHoverFocus` and `Session.hovered_edge`. Hover menus on ports?
   Add `PortHoverFocus`. Hover menus on something a future library
   invents? That library subclasses `Focus`, registers a gesture-state
   field on `Session`, and contributes the popup-trigger logic in its
   editor. No core changes.

#### Where the design has to be honest

Two limits worth naming:

**Capability conjunction is AND, not OR.** `requires=(Regenerable,
Lockable)` means "satisfies both." For OR semantics, either define a
common parent protocol or write the predicate explicitly:

```python
@reads(Session.hovered_node)
def visible(self, node):
    return isinstance(node, (Regenerable, Lockable))
```

OR is rare enough that requiring explicit code is the right trade.

**Runtime-conditional availability needs an explicit `visible()`.**
"Regenerable, but only when an input port has data" isn't a type-level
property. `requires=` is class-level filtering; for state-level
filtering the panel author writes `visible()` directly:

```python
@panel(host=GraphCanvasEditor, focus=NodeHoverFocus, requires=Regenerable, order=20)
class HoverRegeneratePanel(Panel[GraphCanvasEditorContext]):
    @reads(Session.hovered_node)
    def visible(self, node: Regenerable):
        return node.has_required_inputs()  # extra runtime gate

    @reads(Session.hovered_node)
    def draw(self, node: Regenerable, layout, editor): ...
```

Both `requires=` and `visible()` apply: the panel must satisfy the
type *and* the runtime predicate. Composable, no special case.

### 3.7 "I want to open a graph file in the main slot, with a dirty marker on its tab title that updates as the user types"

The previous six examples are panel-layer scenarios. This one is the
*slot-layer* scenario — same architecture, one level up. The main slot
is a `TabHost[SlotContext]`; its children are editors. Today this
already works: `TabSlot` ([`tab_slot.py`](packages/haywire-core/src/haywire/ui/app/tab_slot.py))
extends [`Slot`](packages/haywire-core/src/haywire/ui/app/slot.py),
keeps every open editor mounted inside `ui.tab_panels` with
`keep-alive`, captures the NiceGUI tab client for background-thread
redraws, and refreshes the whole tab bar whenever any wrapper's dirty
state changes. A+ keeps that lifecycle and replaces the bar-wide
refresh with field-level subscriptions.

#### The slot's typed contract

```python
class SlotActions(Protocol):
    def open_tab(self, editor_cls: type[Editor], payload: PayloadKey | None, label: str) -> None: ...
    def close_tab(self, editor_cls: type[Editor], payload: PayloadKey | None) -> None: ...
    def switch_to(self, editor_cls: type[Editor], payload: PayloadKey | None) -> None: ...

@dataclass
class SlotContext:
    actions: SlotActions
    slot_id: Literal["left", "right", "main", "bottom"]
    bindings: BindingsView
    active_binding: Reactive[BindingId | None]
```

`SlotContext` is the typed object the slot hands its child editors at
draw time, exactly like `GraphCanvasEditorContext` is the one
`GraphCanvasEditor` hands its child panels. The slot is itself an
editor's host — and the editor's host is itself a child of AppShell.
The pattern recurses cleanly.

#### The graph editor declares itself

```python
@editor(slot="main", payload_kind="graph_path")
class GraphEditor(Editor[SlotContext]):
    context_type = SlotContext

    @reads(Session.dirty_graphs)
    def tab_title(self, dirty_set, ctx: SlotContext) -> str:
        prefix = "• " if self.payload in dirty_set else ""
        return f"{prefix}{Path(self.payload).name}"

    @reads(Session.active_graph_path)
    def render_main(self, active_path, layout, ctx: SlotContext) -> None:
        self._canvas.render(layout, dimmed=active_path != self.payload)
```

What changes from today:

- `slot="main"` is the editor's typed declaration of which slot hosts
  it. The decorator validates against
  `Literal["left","right","main","bottom"]`, so a typo is a
  registration-time error rather than a workspace-state lookup miss.
- `tab_title` is reactive. Today, [`tab_slot.py:74-92`](packages/haywire-core/src/haywire/ui/app/tab_slot.py#L74-L92)
  reads `wrapper.state.is_dirty` during a full bar refresh — every
  signal that touches any open graph rebuilds the entire tab row.
  Under A+ each tab cell is its own subscription on
  `Session.dirty_graphs`; only the affected cell re-runs `tab_title`,
  only that one DOM node updates.
- `render_main` runs once per binding because `TabHost` keeps panels
  alive. Switching tabs is `ui.tab_panels.set_value()` — the editor's
  DOM is preserved, scroll position survives, the canvas's WebGL
  context isn't torn down. The `dimmed=` flag is reactive cosmetic
  gating; the canvas itself is not rebuilt.

#### Opening a file is a slot action

A library or toolbar that wants to open a graph file calls
`slot.actions.open_tab(...)`. The slot is the host; opening a tab is
its job:

```python
slot_ctx.actions.open_tab(
    editor_cls=GraphEditor,
    payload=str(picked_path),
    label=picked_path.name,
)
```

Today, the equivalent goes through workspace-state plumbing,
`EditorWrapper.split_id` / `make_id` string encoding, and a
slot-specific mutator chain. Under A+ the caller doesn't need to know
about `EditorWrapper`, `binding_id` strings, or whether the slot is a
`TabSlot` vs `IconSlot`. Each slot specialization defines its own
`actions` protocol (a tabbed slot exposes `open_tab`/`close_tab`; an
icon slot exposes `attach`/`set_visible`). A "File → Open" command
written against `SlotActions` works against any slot that satisfies
the protocol — including a future split-pane slot.

#### REQUIRED editors auto-attach via the same gather

Some editors should appear as soon as a library that provides them is
loaded — a console editor that should always sit in the bottom slot
the moment `haybale-logging` registers, for instance. Today,
[`slot.py`](packages/haywire-core/src/haywire/ui/app/slot.py)
implements this by listening for the registry's CLASS_ADDED batch
event and re-running its attach logic. Under A+ the same outcome
falls out of the host's gather subscription:

```python
class MainSlot(TabHost[SlotContext]):
    def gather(self, session: Session) -> Iterable[ChildBinding]:
        for entry in self._workspace_state.bindings_for(self.slot_id):
            yield ChildBinding(cls=entry.editor_cls, payload=entry.payload)
        for cls in self._editor_registry.required_for(self.slot_id):
            if not self._has_binding(cls):
                yield ChildBinding(cls=cls, payload=None)
```

`gather()` reads two reactive sources: the workspace state's
per-slot bindings list and the editor registry's REQUIRED set. When
a library registers a new REQUIRED editor, the registry invalidates
the gather subscription; the host's `_flush()` re-runs `gather()`,
diffs the result against the currently mounted children, and mounts
the new one. The "class added" listener and the initial mount are
the same code path, not two parallel ones.

#### What this stress-tests at the slot layer

1. **The same primitive scales up.** A panel under PropertiesEditor
   and a graph editor under the main slot are both `Child[C]` for
   some context `C`. The gather → subscribe → render-on-change cycle
   is identical; only the context type and the host's bar layout
   differ. AppShell, slots, editors, panels — one mental model all
   the way down.

2. **Reactive granularity earns its keep at this layer too.** Saving
   a graph mutates `Session.dirty_graphs`; only the affected tab
   cell's `tab_title` re-runs. The full bar is not re-rendered, the
   tab panels are not re-mounted, the canvas is not redrawn. The
   legacy code's "every signal redraws the whole bar" smell — the
   slot-level twin of the panel-level "every signal re-polls every
   panel" smell — dissolves under the same primitive that fixes it
   for panels.

3. **The action protocol decouples callers from slot internals.**
   `SlotActions` is the seam. Callers don't construct `EditorWrapper`s,
   don't encode `binding_id`s, don't know the difference between
   `TabSlot` and `IconSlot`. Adding a new bar feature (drag-to-reorder,
   pinned tabs, tab groups) doesn't ripple to callers.

4. **The slot-vs-editor poll-shape divergence dissolves.** Today
   `Slot` and `BaseEditor` each have their own poll/redraw cycles —
   the slot polls the signal bus, the editor polls the context.
   Under A+ both are hosts; both gather children and subscribe via
   `@reads`. The "two poll shapes" smell from the legacy doc is a
   panel-level symptom of a framework-wide cause, and the cure is
   the same at every level.

5. **Keep-alive is a host property, not a slot property.** The
   single biggest payoff at this layer is that `_capture_tab_client`,
   `_render_area_contents`, `_redraw`, and the `keep-alive` mount
   strategy lift onto the `Host` ABC once. The slot subclasses
   (`IconSlot`, `TabSlot`) shrink to just their bar layout — vertical
   icon strip vs horizontal tab row. A future split-pane slot
   inherits keep-alive, hot-reload routing, and tab-client capture
   for free.

#### Where the slot-layer design has to be honest

**Payload identity is still string-encoded.** A `GraphEditor` whose
payload is a path is identified by `(GraphEditor, "/abs/path.haywire")`.
Renaming the file (Save As) means the payload changes; the host has
to repayload the binding without remounting the editor. The current
code does this via [`tab_slot.py:177-192`](packages/haywire-core/src/haywire/ui/app/tab_slot.py#L177-L192)
`repayload_tab`; A+ keeps the same operation but exposes it on
`SlotActions` as `repayload(editor_cls, old, new)`. The payload
itself is still a string — the framework can't fully type the space
of "things a graph editor can be parameterized by."

**Cross-slot moves need a cross-slot action.** Dragging an editor
from main to bottom is *not* one slot's `actions` business — both
slots have to coordinate. Either model it on `Session` (a
`Session.move_binding(from_slot, to_slot, ...)` that both slots
`@reads`) or on AppShell as the parent host. Both work; the spec
defers the choice to the first real consumer, but flags that the
slot-as-self-contained-host model has this seam.

---

## 4. The shape of a focus

Focuses are classes, not registered string IDs.

```python
class Focus(ABC):
    """A discriminator for which children apply to the current state."""

    label: ClassVar[str]
    icon: ClassVar[str]
    order: ClassVar[int] = 100

    @classmethod
    @abstractmethod
    def available(cls, session: Session) -> bool:
        """Is this focus reachable given current session state?"""

class NodeFocus(Focus):
    label = "Node"
    icon = "memory"
    order = 10

    @classmethod
    @reads(Session.active_node)
    def available(cls, node):
        return node is not None
```

What this gets you:

- A panel declares `focus=NodeFocus` as a class reference. The
  registry's index is `(HostClass, FocusClass) → [PanelClass]`. No
  string keys. No `register_focus(...)` plumbing.
- A library introducing a new focus subclasses `Focus`. The decorator
  on its panels picks it up. No bootstrap call.
- A host renders a focus toolbar by enumerating `Focus.__subclasses__()`
  filtered by which it knows about (declared via class-level
  `accepted_focuses: ClassVar[tuple[type[Focus], ...]]`).
- `available()` participates in the reactive system. The toolbar
  enables/disables tabs reactively without the host polling.

---

## 5. The reactive cycle

The framework provides a small reactive subsystem. State on `Session`
is wrapped in `Reactive[T]`. Decorated methods declare which reactive
fields they depend on. When a field changes, the framework re-runs only
the dependents.

### 5.1 The `@reads` decorator

```python
@reads(Session.active_node)
def visible(self, node):
    return node is not None
```

The decorator does three things:

1. Records the read-set on the method.
2. Rewrites the call signature so the host calls `visible(node)` —
   the reactive value is unboxed. Inside the method, `node` is the
   current value, not a `Reactive[T]`.
3. Subscribes the method to the read-set when the child mounts.
   Unsubscribes when the child unmounts.

### 5.2 Path-level reads

```python
@reads(Session.active_graph.edges)
def draw(self, edges, layout, editor): ...
```

The path is interpreted reactively: if `active_graph` itself changes,
the subscription rebinds to the new graph's `edges`. The developer
writes the path they conceptually mean and the framework handles the
indirection.

### 5.3 Why this matters

The current code's coarse-grained refresh — every relevant signal
re-polls every panel in the active scope — is the source of three
distinct smells the legacy doc lists:

- The two `poll()` shapes (panel vs editor)
- The "redraw on every signal" performance ceiling
- The need for hosts to know which signals their children care about

All three dissolve under field-level reactivity. The host doesn't know
which signals matter; each child declares its own. The framework
schedules redraws at exactly the granularity needed.

The reactive primitive is the same one Haywire's *node* layer already
uses for its props system. Extending it to the UI layer is consistency
with the engine, not a new framework idea bolted on.

---

## 6. The state placement rule

There is one rule:

> **State lives at the lifetime of its longest reader, owned by the
> entity that produces it.**

This collapses to four levels:

| Lifetime | Owner | Examples |
| --- | --- | --- |
| Browser session | `Session` | selection, active-graph, clipboard, recent-nodes-in-canvas |
| Editor instance | the editor's own fields | active focus tab, scroll position, expansion state |
| Transient interaction | a typed gesture-state on the session, or local var | mid-drag pending connection, edge-reconnect end, popup screen position |
| Single render | local var | computed lists, formatted strings |

Three changes follow:

### 6.1 No `metadata` dict

Every key the legacy `metadata` dict carried has a typed home:

- `properties_scope` (active focus tab) → `PropertiesEditor._active_focus`
- `clipboard` → `Session.clipboard: Reactive[Clipboard]`
- `recent_nodes` → `GraphCanvasEditor._recent_nodes`
- `pending_connection` → `Session.pending_connection: Reactive[PendingConnection | None]`
- `edge_state`, `edge_reconnect_end`, `context_menu_screen_pos` → see §6.4 (these
  are *gesture state*, not host state)
- `_hui_expansion` → widget-internal store, owned by the widget

There is no escape hatch because the rule covers every case.

### 6.2 Gesture state is session state

A right-click that opens a popup is the start of a **gesture**. The
gesture has state: where the user clicked, whether they were
mid-drag-connect, whether they right-clicked at the source or sink end
of an edge. That state has session-scoped lifetime (it ends when the
gesture ends), one reader (the panels rendered into the popup), and
one producer (the editor that opened the popup).

```python
@dataclass
class CanvasGesture:
    kind: Literal["right_click_canvas", "right_click_node", "right_click_edge"]
    screen_pos: ScreenPos
    canvas_pos: CanvasPos | None = None
    pending_connection: PendingConnection | None = None
    edge_reconnect_end: EdgeEnd | None = None

class Session:
    canvas_gesture: Reactive[CanvasGesture | None]
```

When the canvas opens a context-menu popup, it sets
`session.canvas_gesture`. Panels in the popup `@reads` it. When the
popup closes, the canvas clears it. There is no popup-internal state.

This unifies a category of state the legacy code modeled as
"popup-internal metadata." It's not popup-internal — it's the gesture
the popup is a UI for.

### 6.3 Editors own their toolbar/tab state

`PropertiesEditor._active_focus` is a `Reactive[type[Focus]]` on the
editor instance. The toolbar reads it; clicking a tab writes it. The
editor persists it across sessions if it wants to (via the existing
preferences system). No special framework support needed — it's just
state that follows the placement rule.

### 6.4 `Layout` carries the rendering position

A popup is a *rendering surface*, not a kind of host. The editor
opens the popup and constructs a `Layout` whose root widget is the
popup body and whose metadata includes the screen position. Panels
read `layout.position` if they need it (e.g., a tooltip-style panel
that points at the click site).

```python
class Layout:
    root: Element
    position: ScreenPos | None  # None when rendered in a pane
    # ... rendering helpers (button, label, error_block, ...)
```

`EditorContext` becomes purely "the editor's action API + view state."
It carries no rendering concerns. The popup-vs-pane distinction is
visible only to the host (which decides which surface to use) and to
panels that genuinely care about screen position. A panel that doesn't
care never sees the distinction.

---

## 7. What the framework no longer needs

Counted by removed concepts:

1. **`SessionContext`** — merged into `Session`.
2. **`metadata: dict[str, Any]`** — no escape hatch needed.
3. **`context_menu_trigger`** — replaced by `session.canvas_gesture`.
4. **`on_emit_event`** — replaced by `editor.actions.*`.
5. **`ScopeDescriptor.register_scope(...)`** — replaced by `Focus`
   subclasses.
6. **`scopes` and `editor_keys` as string lists** — replaced by class
   references.
7. **`BasePanel.poll(context)` returning bool** — replaced by `@reads`
   subscriptions on a `visible()` predicate.
8. **`BaseEditor.poll(context, signal)` returning bool** — replaced by
   `@reads` subscriptions on the editor's render method.
9. **The "context_menu" pseudo-editor host id** — replaced by every
   editor having its own popup story via `Layout.position`.
10. **The `EditorContext | None = None` weak-typing escape hatch for
    dual-editor panels** — replaced by `DisplayPanel` as a separate
    class.
11. **`PanelFactory`** — the gather-and-poll loop is replaced by the
    reactive subscription system, which doesn't need a separate factory.

Counted by added concepts:

1. **`Reactive[T]`** and **`@reads(...)`** — the subscription primitive.
2. **`Focus` as a class hierarchy** — replaces string-id descriptors.
3. **`DisplayPanel`** — a sibling base class to `Panel[C]` for
   host-agnostic panels.
4. **Editor `actions: Protocol`** — the typed action API.

Net: −11, +4.

---

## 8. The story you tell a new contributor

> "Haywire's UI is a tree of hosts and children. AppShell is a host;
> editors are its children. Each editor is itself a host; panels are
> its children. The pattern is the same all the way down."
>
> "A child declares which host it lives under: `@panel(host=MyEditor)`.
> That host hands the child a typed context with an action API. To act
> on the world, the child calls `editor.actions.something(...)`. The
> action vocabulary is whatever that editor exposes, typed by the
> editor."
>
> "A child declares which session fields it reads: `@reads(Session.x)`.
> The framework subscribes the child to those fields and re-runs only
> the affected children when those fields change. There is no poll
> loop and no redraw cascade."
>
> "If your panel doesn't need to act — only display — extend
> `DisplayPanel` and skip the host parameter. The framework will route
> you to every host that knows your focus."
>
> "If you're adding a new editor, define an actions protocol, a
> context, and an editor class. Panels follow. There are no other
> integration points to learn."
>
> "If you need state, place it by lifetime: session-lived state on
> `Session`, editor-lived state on the editor's instance fields,
> gesture-lived state on `Session` as a typed gesture object,
> render-lived state in a local variable. There is no fifth case."

That story is six paragraphs and covers the entire architecture. A new
contributor who has read it can write a panel, an editor, or a focus
on day one without asking anyone what `metadata["on_emit_event"]` is
or why `editors=` is a list.

---

## 9. Where the simplicity comes from

The architecture is small because each concept solves exactly one
problem and the concepts don't overlap.

- **Session** holds session-lived state and provides session-lived
  services. One object, one lifetime.
- **Reactive + @reads** specify when work runs. The framework knows
  what depends on what.
- **Host[C] / Child[C]** specify what flows up and down. Types enforce
  the contracts.
- **Focus classes** specify when a child is reachable. Subclassing is
  the registry.
- **EditorContext + actions protocol** specify the editor's interface
  to its children. Protocols are the seam.
- **Layout** specifies how rendering happens. Position is part of
  layout, not part of context.

There are no orthogonal concerns living on the same primitive: today's
`metadata` carries widget state, gesture state, and session state;
today's `editor_keys` carries hosting and routing; today's `scopes`
carries focus and selection mechanism. A+ separates each.

There are no places where "this works but only because" — the
dual-editor panel works because of class hierarchy, not list-typed
fields; the popup works because of `Layout.position`, not because the
framework pretends a popup is a kind of editor; visibility works
because of subscriptions, not because hosts know which signals matter.

---

## 10. Where it gets harder

Honest costs of A+ over the legacy or B+ designs:

1. **The reactive subsystem is real infrastructure; the host
   machinery is mostly consolidation.** `Reactive[T]`, path-level
   subscriptions, the `@reads` decorator, and the mount/unmount
   subscription lifecycle are new — roughly 200-300 lines, the same
   shape the node-prop system already uses. The host lifecycle
   (gather, redraw, NiceGUI client capture, hot-reload coordination,
   tab-panels keep-alive) is *not* new — it lives in
   [`slot.py`](packages/haywire-core/src/haywire/ui/app/slot.py) today.
   Promoting it to a `Host` ABC is mostly consolidation of code that
   already works rather than greenfield invention. See §12 for the
   concrete shape.

2. **Class-keyed registries are fragile under hot-reload.** When a
   library reloads, its panel classes are *new class objects* with the
   same name. The registry's index keyed on `(HostClass, FocusClass)`
   has to coordinate with the BaseRegistry's identity-by-registry-key
   to deduplicate correctly. Solvable, but not free.

3. **Protocol-typed action APIs are only as good as the editor's
   discipline in defining them.** If an editor's `actions` protocol
   grows to 80 methods, panels are coupled to a wide surface again. The
   architecture doesn't enforce "one action per logical operation" —
   that's design discipline.

4. **`@reads` against deep paths (`Session.active_graph.edges`) needs
   careful semantics.** What happens when `active_graph` changes from
   `g1` to `g2`? The subscription must unbind from `g1.edges` and bind
   to `g2.edges`, atomically, without losing intermediate updates. This
   is solvable (see Vue's `watch` or Solid's `createMemo`) but worth
   being honest that it's nontrivial.

5. **The `DisplayPanel` / `Panel[C]` split adds a class hierarchy
   choice for the developer.** They have to decide upfront whether
   their panel might ever want to act. Promoting a `DisplayPanel` to a
   `Panel[C]` later is a class-base change. The current convention
   (one `BasePanel` for both) doesn't have this.

These are real costs. They are the price of types. The trade is:
upfront design effort and runtime infrastructure in exchange for the
framework getting out of the way at the application level. Whether
it's worth it depends on how many editors and panels you expect over
the lifetime of the project.

---

## 11. Open questions

1. **Reactive granularity.** Field-level subscription is the obvious
   target, but `Session.active_graph.edges` is a list whose *contents*
   matter, not just identity. Do reads on `edges` fire on append? On
   reorder? On per-edge mutation? The answer affects how panels are
   written. Vue's reactivity defaults to deep, Solid's defaults to
   shallow with explicit deep. Pick before building.

2. **Should `Host` itself be a `Child`?** In principle, an editor is
   AppShell's child. If `Host` extends `Child`, then editors-hosting-
   editors (split views, tabbed sub-editors) work for free. The cost is
   one more layer of generic parameters. Worth it only if sub-editors
   are real planned UX.

3. **Where does shared/cross-editor coordination live?** Two editors
   that need to coordinate (selection in canvas highlights row in
   properties) do so through `Session` reactivity today. For more
   complex cases (one editor wants to push a "please show this" hint
   to another), is `Session.lifecycle` enough or do we need a typed
   inter-editor message channel? Defer until a real use case appears.

4. **Hot-reload of the action protocol itself.** If a library reloads
   and its `Editor.actions` protocol changes, every panel typed
   against the old protocol is now stale. Detect at re-registration
   time? Reload all dependent panels? Punt and require a full
   workspace reload? Pick a policy.

5. **Does `Focus` need a per-editor narrowing?** `EdgeFocus` is the
   same focus everywhere — but a hypothetical `SelectionFocus` might
   mean different things to canvas (multi-node selection) and to file
   browser (multi-file selection). Either accept that focuses are
   editor-scoped (subclass per editor) or that they're inherently
   shared vocabulary (one global namespace). Both have precedent. Pick
   before building.

---

## 12. Framework machinery

The previous sections have described what the framework *does* from
the application's point of view. This section shows what it *is*.
Roughly four pieces of new code plus consolidation of existing
machinery from `slot.py` and the editor lifecycle.

### 12.1 The reactive primitive

`Reactive[T]` is a value with a subscriber set. Reading it inside a
tracking context auto-subscribes the current `Subscription`. Writing
invalidates all subscribers.

```python
class Reactive(Generic[T]):
    def __init__(self, initial: T):
        self._value = initial
        self._subscribers: set[Subscription] = set()

    @property
    def value(self) -> T:
        if (sub := _current_tracking_subscription()) is not None:
            self._subscribers.add(sub)
            sub.add_dependency(self)
        return self._value

    @value.setter
    def value(self, new: T) -> None:
        if new == self._value:
            return
        self._value = new
        for sub in list(self._subscribers):
            sub.invalidate()
```

`_current_tracking_subscription()` is a `ContextVar` the framework
sets when it's recording a method's read-set. Read-during-tracking →
auto-subscribed. The same pattern Solid.js, Vue 3 refs, and MobX use.

### 12.2 The `@reads` decorator

`@reads(Session.x)` declares which reactive paths a method reads. The
decorator records the paths and, at call time, resolves them to
current values that get passed in as positional arguments.

```python
def reads(*paths: ReactivePath):
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            values = [resolve_path(self.session, p) for p in paths]
            return method(self, *values, *args, **kwargs)
        wrapper._reactive_paths = paths
        return wrapper
    return decorator
```

Path-level reads (`Session.active_graph.edges`) re-resolve every call.
If `active_graph` changes, the next resolution naturally walks to the
new graph's `edges` Reactive, and the auto-subscription rebinds.

### 12.3 `Subscription` — binding a method to its read-set

A `Subscription` is one method bound to its current dependency set.
The first call records dependencies as side effects of reading
reactive values; the framework re-runs it when any dependency
invalidates.

```python
class Subscription:
    def __init__(self, child: Child, method: Callable):
        self._child = child
        self._method = method
        self._dependencies: set[Reactive] = set()
        self.last_result: Any = None

    def run(self) -> Any:
        # Tear down old subscriptions before re-recording — paths
        # may have changed shape since last run.
        for dep in self._dependencies:
            dep._subscribers.discard(self)
        self._dependencies.clear()

        token = _set_tracking_subscription(self)
        try:
            self.last_result = self._method()
        finally:
            _reset_tracking_subscription(token)
        return self.last_result

    def add_dependency(self, r: Reactive) -> None:
        self._dependencies.add(r)

    def invalidate(self) -> None:
        # Coalesce on the host's next tick.
        self._child.host._mark_dirty(self._child)

    def dispose(self) -> None:
        for dep in self._dependencies:
            dep._subscribers.discard(self)
        self._dependencies.clear()
```

Each child has up to two subscriptions: one for `visible()` and one
for `draw()`. The host's `_mark_dirty` coalesces invalidations onto a
single deferred `_flush()` per tick.

### 12.4 The Host's mount/render loop

A host's job at mount is: gather children, build each child's
visibility subscription, draw the visible ones inside a draw
subscription, and listen for invalidations.

```python
class Host(Generic[C], ABC):
    def __init__(self):
        self._mounted: dict[type[Child], _MountedChild] = {}
        self._dirty: set[Child] = set()
        self._tab_client: Any = None  # captured once, reused on background-thread redraws

    def mount(self, session: Session, layout: Layout) -> None:
        self._capture_tab_client()  # see §12.5
        ctx = self.context(session)
        for binding in self.gather(session):
            child = binding.cls()
            child._host = self
            child._session = session

            vis = Subscription(child, lambda c=child: c.visible())
            visible = vis.run()

            mounted = _MountedChild(child=child, ctx=ctx, layout=layout, vis_sub=vis)
            self._mounted[binding.cls] = mounted
            if visible:
                self._draw(mounted)

    def _draw(self, m: _MountedChild) -> None:
        m.layout.clear_region(m.region)
        m.draw_sub = Subscription(
            m.child,
            lambda: m.child.draw(m.child._session, m.layout, m.ctx),
        )
        m.draw_sub.run()
        m.was_visible = True

    def _mark_dirty(self, child: Child) -> None:
        self._dirty.add(child)
        if not self._scheduled:
            self._scheduled = True
            asyncio.get_event_loop().call_soon(self._flush)

    def _flush(self) -> None:
        with self._client_context():
            for child in self._dirty:
                m = self._mounted[type(child)]
                now_visible = m.vis_sub.run()
                if now_visible and not m.was_visible:
                    self._draw(m)
                elif not now_visible and m.was_visible:
                    m.layout.clear_region(m.region)
                    if m.draw_sub: m.draw_sub.dispose()
                    m.was_visible = False
                elif now_visible:
                    self._draw(m)  # something draw reads changed
            self._dirty.clear()
            self._scheduled = False

    def unmount(self) -> None:
        for m in self._mounted.values():
            m.vis_sub.dispose()
            if m.draw_sub: m.draw_sub.dispose()
        self._mounted.clear()
```

`StackHost` is essentially this. `TabHost` overrides `_draw` to use
`ui.tab_panels.set_value()` and `_ensure_drawn` (lazy first-draw),
matching the existing `Slot._activate` / `Slot._ensure_drawn` shape.

### 12.5 What already exists in `slot.py`

The host machinery isn't greenfield. Specifically:

- **NiceGUI client-context capture.** `Slot._capture_tab_client`
  snapshots `ui.context.client` during the page-handler chain so
  background-thread redraws (hot-reload via the file watcher) can
  re-enter the right slot stack. `Host._capture_tab_client` and the
  `with self._client_context():` wrap in `_flush` lift this verbatim.
- **Tab-panels keep-alive mount.** `Slot._render_area_contents` builds
  a `ui.tab_panels(value=initial_value, animated=False).props("keep-alive")`
  container; per-wrapper panels are `ui.tab_panel(binding_id)`.
  `TabHost._draw` uses the same shape.
- **Lazy first-draw.** `Slot._ensure_drawn` defers `wrapper.draw(panel)`
  until a wrapper is first activated. `TabHost._activate` keeps this
  pattern.
- **Per-key registry subscription for hot-reload.** `EditorWrapper`'s
  RELOADED/REMOVED subscription becomes the Child ABC's lifecycle
  hook; the slot's batch CLASS_ADDED subscription becomes the Host
  ABC's.
- **Dead-client error handling.** `Slot._redraw` wraps `panel.update()`
  in a try/except for the "client gone away" case. `Host._draw` keeps
  this.

The slot-stack reentrancy concern from earlier drafts is therefore
**not** an open problem — it's a solved problem whose solution is
already in the codebase and just needs lifting.

### 12.6 Honest size

| Component | New lines | Lifted from existing code |
| --- | ---: | ---: |
| `Reactive[T]` + `ContextVar` + path resolver | ~120 | 0 |
| `@reads` + `ReactivePath` | ~50 | 0 |
| `Subscription` | ~60 | 0 |
| `Host` ABC (mount/flush/dispose) | ~80 | ~150 (from slot.py) |
| `TabHost` / `StackHost` specializations | ~80 | ~200 (from slot.py + properties_editor.py) |
| `Child` ABC + per-key reload hooks | ~40 | ~80 (from EditorWrapper) |
| Class-keyed registry index | ~80 | ~80 (replaces existing string-keyed) |
| **Total** | **~510** | **~510** |

Roughly 500 lines of new framework code, plus consolidating ~500
existing lines into the ABC layer. The reactive subsystem is the
genuinely new part; the host lifecycle is mostly relocation.

### 12.7 The remaining real edge case

Hot-reload class identity is the one concern that doesn't dissolve.
When `haybale-ai` reloads, `Regenerable` is a *new class object* with
the same name. Existing subscriptions hold the old class via
`isinstance(node, Regenerable)`; the registry index keyed on
`(HostClass, FocusClass)` holds the old `HostClass`. Two strategies:

- **Re-wire on reload.** When the registry signals a class reload, the
  framework walks the index, replaces old class references with new
  ones, and re-evaluates all `requires=` / `isinstance` checks. The
  existing per-key reload subscription pattern in `EditorWrapper`
  generalizes to this.
- **Identity-by-registry-key.** Index by `class_identity.registry_key`
  (a string) instead of by class identity. Lose static type
  guarantees; gain reload robustness.

The codebase has chosen the first strategy elsewhere (per-key reload
subscriptions, `EditorWrapper`'s pattern); A+ should follow suit.

---

## 13. The one-paragraph version

Hosts contain children. Children read session state reactively and
call typed actions on their host. Hosts are class-keyed in the
registry; focuses are classes; action APIs are protocols. State
lives at the lifetime of its longest reader. There is no `metadata`,
no string-keyed routing, no poll loop, no special case for popups or
dual-editor panels. The framework provides four primitives (`Session`,
`Host[C]`, `Child[C]`, `EditorContext` with `actions`) and one
subscription mechanism (`Reactive[T]` + `@reads`); everything the
application does is composed from those.
