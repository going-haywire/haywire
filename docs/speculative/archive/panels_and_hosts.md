# Speculative: editors, panels, and how context-awareness should be told

> Status: speculative analysis, no code changes proposed yet.
> Audience: anyone building a new editor that hosts panels, or a new
> kind of context-popup, or trying to explain "what is a panel?" to a
> library author.
> Date: 2026-04-28, branch `code_refactoring_squashed`.
> Companion to but independent of `context_events_simplification.md`.
> Grounded in the *current code* — `panel/`, `properties_editor.py`,
> `graph_canvas/handlers/context_menu.py`, and the panel implementations
> in `barn/haybale-core/haybale_core/panels/`.

## 1. The job we are actually doing

> **A panel is a sub-tree of an editor. The editor decides where to
> render it (its main pane, a popup it opens, anywhere else it can
> draw) and hands the panel three things: session state, a layout
> scaffold, and the editor's own context.**

The mechanism splits along three axes:

1. **Hosting** — who renders whom. AppShell hosts editors; editors
   host panels (in their own UI, in popups they open, or both).
2. **Filtering** — when does a thing appear. Editors poll the signal
   bus; panels poll the session.
3. **Routing** — how does a panel author write `@panel(...)` and end
   up in the right place at the right time.

The current code does all three correctly *in the cases it covers*,
but tells the story unevenly: "context_menu" pretends to be a
generic host when it's the canvas's specifically; the panel
parameter `context` and the field `context.session` produce awkward
double-hops; popup-ephemeral state lives in a typed-nothing dict;
and the second key on `@panel` ("scope") means different things
depending on which host reads it.

There is one thing the current code gets quietly right that any
reframe has to preserve: a panel that only reads session state can
declare itself in two editors at once and be drawn in either. §2.4
walks through this.

---

## 2. What the code does today

### 2.1 The cast of types

| Type | Lives in | Role |
| --- | --- | --- |
| ``BaseEditor`` | `haywire/ui/editor/base.py` | Top-level workspace inhabitant. Slot-mounted. ``poll(signal)`` / ``draw(container)`` lifecycle. |
| ``BasePanel`` | `haywire/ui/panel/base.py` | Sub-unit drawn inside an editor or inside a popup. Class-method ``poll(context)`` / ``draw(context, layout)`` lifecycle. |
| ``PanelIdentity`` | `haywire/ui/panel/identity.py` | Class metadata: ``editor_keys: list[str]`` + ``scopes: list[str]`` + label/icon/order. Set by ``@panel`` decorator. |
| ``ScopeDescriptor`` | `haywire/ui/panel/scope.py` | Toolbar-tab metadata: ``scope_id`` + label/icon/order + ``poll(context)``. Registered by libraries via ``PanelRegistry.register_scope(editor_id, descriptor)``. |
| ``PanelRegistry`` | `haywire/ui/panel/registry.py` | Indexes panels by ``(editor_key, scope_id)``; also stores `ScopeDescriptor`s by ``(editor_id, scope_id)``. |
| ``Popup`` | `haywire/ui/components/popup.py` | Generic NiceGUI dialog wrapper. Used by the context-menu provider — and by other unrelated UI surfaces (error popups, haystack editor) — to host arbitrary content. Not panel-aware. |

### 2.2 The two real panel-rendering surfaces

A grep across `barn/` for `editors=` on `@panel` returns three
distinct values:

```
20  "properties"        ← PropertiesEditor's main pane (haybale-studio)
17  "test_inspector"    ← test-harness only, not a runtime editor
15+ "context_menu"      ← canvas's right-click popup
```

At runtime there are two surfaces panels render into:
PropertiesEditor's main pane, and the canvas's right-click popup.
They share `BasePanel` and the panel registry, but the second one
is named as if it were a generic host: `"context_menu"`. It isn't —
it's the canvas's. The provider is owned by the canvas, its state
is canvas-shaped (`pending_connection`, `edge_state`,
`edge_reconnect_end`), and its action callback fires canvas events.

#### PropertiesEditor — the editor's main pane

```
context signal
   → properties_editor.poll(signal) returns True
     → editor.draw(context, container)
       → toolbar = scope tabs (each ScopeDescriptor has poll(context))
       → content = for each panel in registry.get_panels("properties", active_scope):
                     if panel.poll(context): draw it
```

State: ``context.metadata["properties_scope"]`` carries the active
scope id (which tab is selected). Read on first render, mutated on
toolbar click, otherwise sticky.

#### Context-menu — the canvas's popup

```
canvas right-click event
   → ContextMenuHandlers translates to provider intent
     → SessionContextMenuProvider._open_menu(trigger, pos):
       → set context.context_menu_trigger = trigger
       → stash popup-ephemeral state in context.metadata:
           "on_emit_event", "edge_state", "context_menu_screen_pos",
           "edge_reconnect_end", "pending_connection", "canvas_position"
       → build Popup
       → for each panel in registry.get_panels("context_menu", trigger):
           if panel.poll(context): draw into popup.content
       → on close: clear trigger, drain (some) metadata keys
```

State: ``context.context_menu_trigger`` is a top-level field on
``SessionContext``. The trigger space is **open** —
`on_port_context` and `on_custom_context` accept arbitrary scope
strings driven by `data-hw-port-menu-scope` /
`data-hw-custom-menu-scope` attributes on canvas DOM elements
(`context_menu.py:223,234`). Libraries can introduce new
context-menu kinds without core changes.

### 2.3 What flows back

A panel that wants to *do* something reaches out via either:

- ``context.session.signal(...)`` / ``context.session.lifecycle(...)``
  — the typed signal/lifecycle channels, accessed through the
  back-reference from `SessionContext` to its owning `Session`.
- ``context.metadata["on_emit_event"](event)`` — a callback the
  context-menu provider stuffs into metadata, used by panels to
  emit graph-canvas events back to the canvas.

The first works but reaches through the context to the session to
call something the context could expose directly. The second is a
popup-internal callback plumbed via a typed-nothing dict, and it
bakes in a hidden assumption: the only events such a panel can
fire are *canvas* events. A future file-browser context menu can't
reuse this channel — `on_emit_event` is informally typed against
the canvas's event vocabulary.

### 2.4 The dual-editor panel — an affordance worth preserving

Today, a panel that only reads session state can be hosted in *both*
``properties`` and ``context_menu`` with one declaration:

```python
# barn/haybale-core/haybale_core/panels/edge_panels.py:32
@panel(
    editors=["context_menu", "properties"],
    scopes="edge",
    label="Connection Errors",
    icon=hui.icon.error,
    order=10,
)
class EdgeErrorsPanel(BasePanel):
    @classmethod
    def poll(cls, context):
        state = _state(context)
        return state is not None and state.get_error() is not None

    def draw(self, context, layout):
        ...   # reads context.active_edge, draws an error block
```

This works because:

1. ``editor_keys`` is a *list*, so the registry indexes the panel
   under both ``("context_menu", "edge")`` and
   ``("properties", "edge")``.
2. The string ``"edge"`` happens to mean the same focus in both
   places — what the user/event has zeroed in on.
3. The panel body only reads ``context.active_edge`` — host-agnostic
   state. It never touches popup-ephemeral metadata.

Two such panels exist (`EdgeErrorsPanel`, `EdgeWarningsPanel`). The
pattern is small but real: *display* panels can live in two
editors that share a focus vocabulary; *action* panels can't,
because actions are typed against a specific editor's command
vocabulary.

The reframe in §4 takes "one declaration, two editors" as a hard
constraint — but tightens what "two editors" means. It's not "any
two editors in the system"; it's "two editors that share a focus
vocabulary." `EdgeErrorsPanel` makes sense in PropertiesEditor and
on the canvas because both know what an "edge" is.

---

## 3. The smells

### 3.1 ``editor_keys`` says less than it pretends

A panel declares ``editors=["properties"]`` or
``editors=["context_menu"]``. The most heavily-used target
(``"context_menu"``) is not a ``BaseEditor`` and never will be —
it's the canvas's popup. The field name lies about its value
space, and `"context_menu"` is the *canvas's* context menu
pretending to be generic. A second editor that wants context
menus (file-browser, terminal) can't reuse the host id without
colliding. The design is locked to "exactly one popup-rendering
editor."

### 3.2 ``scopes`` carries two semantics

A scope is selected differently per editor:

- **In PropertiesEditor**: the user clicks a toolbar tab. Sticky
  across signals.
- **In the context menu**: the right-click event determines it.
  Lives only for the popup's lifetime.

Same name, two selection mechanisms. The *invariant* is the same in
both: it's the focus the editor is currently displaying — what the
user/event has zeroed in on. The two-semantics smell is in the
name; the underlying concept is one.

### 3.3 ``context.metadata`` is several unnamed things

The keys that appear in ``context.metadata`` today, by lifetime and
owner:

| Key | Lifetime | Set by | Read by |
| --- | --- | --- | --- |
| ``properties_scope`` | session | PropertiesEditor on first render / toolbar click | PropertiesEditor on every refresh |
| ``on_emit_event`` | popup-open duration | SessionContextMenuProvider | most context-menu panels |
| ``edge_state`` | popup-open duration | provider on edge right-click | edge-action panels |
| ``context_menu_screen_pos`` | popup-open duration | provider | a few panels |
| ``edge_reconnect_end`` | popup-open duration | provider on edge right-click | reconnect panel |
| ``pending_connection`` | popup-open duration | provider on canvas right-click w/ drag | create-node panel; visual_layer.handle_pending |
| ``canvas_position`` | popup-open duration | provider on canvas right-click | create-node panel |
| ``recent_nodes`` | session-ish | (not set by provider) | create-node panel |
| ``clipboard`` | session | selection-actions panels | selection-actions panels |
| ``canvas_x`` / ``canvas_y`` | popup-open duration | (set elsewhere) | selection-actions paste |
| ``_hui_expansion`` | session | hui.expansion_section helper | hui.expansion_section helper |

Three lifetimes (session-state, popup-ephemeral, hui-widget-state),
several owners, one dict-of-Any. ``properties_scope`` is *true
session-state*. The ``on_emit_event`` cluster is *the canvas's
popup-ephemeral state*. ``_hui_expansion`` is *widget-internal
persistence* riding the same dict because it was the only object
reachable from `hui.expansion_section`.

There's also a small consistency bug: ``_open_menu`` clears
``edge_state``, ``context_menu_screen_pos``, ``edge_reconnect_end``,
and (conditionally) ``pending_connection`` on close, but **doesn't
clear ``canvas_position``** (set at `context_menu.py:199`, never
popped). Evidence that hand-coordinated cleanup across an untyped
dict drifts.

### 3.4 ``context_menu_trigger`` is a sentinel

Top-level on ``SessionContext``: ``context_menu_trigger:
Optional[str]``. Set on popup open, cleared on popup close. At
runtime *nothing reads it* — a grep finds writes from the provider,
clears in the close callback, and reads only in tests. Dead state.

### 3.5 ``on_emit_event`` is a hidden, canvas-specific dependency injection

A context-menu panel that wants to emit a canvas event has to:

```python
fn = context.metadata.get("on_emit_event")
if fn:
    fn(event)
```

The call is dict-keyed, untyped, may-be-None, and informally typed
against the canvas's event vocabulary. There's no way for a future
file-browser popup to use the same key with a different event type
— they'd collide.

### 3.6 Two poll() shapes

Editor poll: ``editor.poll(self, context, signal) -> bool`` — runs
on every signal.
Panel poll: ``panel.poll(cls, context) -> bool`` — runs on every
host-redraw, no signal.

The reason is real: editors decide whether to redraw based on *what
changed*; panels decide whether to be visible based on *current
state*. But the divergence shows up in the mental model: the same
word "poll" means two different things, and a panel author has no
signal-shaped affordance even when one would be clarifying.

### 3.7 ScopeDescriptor lives in the wrong registry

`ScopeDescriptor` is library-contributed editor-extension metadata
(label, icon, order, availability poll) — what a library declares
when it wants a new toolbar tab on PropertiesEditor. It's stored in
`PanelRegistry._scope_index`, but PanelRegistry's job is *panel
routing*. Scope descriptors are sidecar data riding along because
they happen to share a key shape.

The string `"properties"` passed to `register_scope` is unvalidated
(PanelRegistry has no way to check it names a real editor); the
intent ("extend that editor with a tab") is hidden behind generic
panel-registry vocabulary; lifecycle is split (a hot-reloaded
editor's scopes don't follow it).

The `(editor_key, scope_id) → panels` index is panel routing and
*does* belong in PanelRegistry. The descriptors are a different
job.

### 3.8 ``context.session.signal(...)`` reaches through

Panels and editors that want to emit a signal write
`context.session.signal(SelectionMoved())`. The hop through
`context.session` is reaching from "the contextual state" back to
"the owning session" to invoke a method that's logically *available
through the context*. The back-reference exists precisely because
panels need this — but the call shape exposes the indirection
instead of hiding it.

---

## 4. The reframe

### 4.1 Vocabulary

Three params to every panel `draw()`, named for what they hold:

- **`session: SessionContext`** — session state (selection, active
  graph, etc.). What used to be `context`.
- **`layout: PanelLayout`** — rendering scaffold.
- **`editor: EditorContext | None`** — the editor's own contribution
  at draw time. Subclassed per editor.

Two strings on `@panel`:

- **`editor`** — *which editor* hosts the panel. `properties`,
  `graph_canvas`, future `file_browser`. Replaces `editors`.
- **`display_focus`** — *when* the panel is relevant. The focus the
  editor is currently displaying: `node`, `edge`, `app`,
  `file_selected`, custom port-scope strings, etc. Replaces
  `scopes`. Selected by the user (PropertiesEditor toolbar) or by
  an event (canvas right-click); selection mechanism is the
  editor's business.

The popup-vs-pane distinction goes away as a public concept:
panels declare which *editor* they belong to and which *focus*
they apply to. The editor decides whether to draw a given focus's
panels in its main pane, in a popup it opens, or somewhere else.

### 4.2 Editors hand panels their own context

Three things flow into a panel's `draw()`:

- `session` — comes from the session. Universal.
- `layout` — comes from the panel framework. Universal.
- `editor` — comes from the editor. Typed per editor.

`EditorContext` is an ABC. Each editor that hosts panels defines
its own concrete subclass with whatever it wants its panels to be
able to read or call:

```python
class EditorContext(ABC):
    """What an editor passes to its panels at draw time."""

class PropertiesEditorContext(EditorContext):
    """PropertiesEditor doesn't currently need to hand panels anything
    beyond what's on SessionContext. Concrete subclass kept for
    symmetry; fields can be added when a panel needs them."""

class GraphCanvasEditorContext(EditorContext):
    canvas_manager: GraphCanvasManager
    # Popup-only — None when the panel is rendering somewhere else
    popup: PopupState | None = None

@dataclass
class PopupState:
    display_focus: str
    screen_pos: tuple[float, float]
    canvas_pos: tuple[float, float] | None = None
    pending_connection: PendingConnection | None = None
    edge_state: EdgeState | None = None
    edge_reconnect_end: bool | None = None
```

The `editor` parameter is mandatory in the panel signature with a
default of `None`:

```python
def draw(
    self,
    session: SessionContext,
    layout: PanelLayout,
    editor: EditorContext | None = None,
) -> None: ...
```

The default of `None` exists for migration and for panels that
never need editor-specific access. Once the reframe is done, every
editor passes its own `EditorContext` whenever it draws a panel —
the `None` is the contract for "I don't read editor state."

Single-editor panels declare the type they expect:

```python
@panel(editor="graph_canvas", display_focus="node")
class DeleteNodePanel(BasePanel):
    def draw(self, session, layout, editor: GraphCanvasEditorContext):
        node_id = session.active_node.node_id
        layout.button("Delete", on_click=lambda: editor.canvas_manager.handle_event(
            UserRemoveEvent(nodes=[node_id], edges=[]),
        ))
```

The panel calls a method on the canvas manager directly. No
closure-captured callback, no metadata bag, no None-check on a
dict lookup. The action vocabulary is whatever
`canvas_manager.handle_event(...)` accepts — typed by the manager,
not by an informal convention.

Dual-editor display panels type against the base `EditorContext`
and never read editor-specific fields:

```python
@panel(editor=["graph_canvas", "properties"], display_focus="edge")
class EdgeErrorsPanel(BasePanel):
    def draw(self, session, layout, editor: EditorContext | None = None):
        # never reads editor.* — works in either editor
        ...
```

### 4.3 `PanelFactory` shares the gather-and-poll loop

The two surfaces today (PropertiesEditor, canvas popup) each
hand-roll the same loop: query the registry, filter by `poll()`,
log poll-exceptions, draw the survivors. Only the gather-and-poll
half is genuinely identical — the wrap (expansion section vs flat
stack), the empty-state UX (placeholder label vs don't-open),
and the draw-error UX (error label in layout vs log-and-skip)
are editor-specific.

Factor out only the shared half:

```python
class PanelFactory:
    def __init__(self, panel_registry: PanelRegistry):
        self._registry = panel_registry

    def gather(
        self,
        editor_id: str,
        focus_id: str,
        session: SessionContext,
    ) -> list[type[BasePanel]]:
        """Return panel classes for (editor_id, focus_id) that pass poll()."""
        result = []
        for cls in self._registry.get_panels(editor_id, focus_id):
            try:
                if cls.poll(session):
                    result.append(cls)
            except Exception as exc:
                logger.warning(f"poll() error in {cls.__name__}: {exc}")
                continue
        return result
```

Eager `list` rather than a lazy iterator: every caller wants the
collection up front (to check emptiness, to count, to iterate),
and eager evaluation avoids interleaving `poll()` calls with
`draw()` calls — which matters because NiceGUI's slot stack is
sensitive to what's active when widget code runs.

Editors that host panels hold a `PanelFactory` (DI'd) and iterate
the returned list. PropertiesEditor:

```python
panels = self._panel_factory.gather("properties", focus_id, session)
if not panels:
    hui.empty_state("No properties available", ...)
    return

editor_context = self.build_editor_context(session)
for cls in panels:
    with hui.expansion_section(cls.class_identity.label, ...):
        layout = PanelLayout(ui.column().classes("w-full gap-1"))
        try:
            cls().draw(session, layout, editor_context)
        except Exception as exc:
            logger.exception(f"draw() error in {cls.__name__}")
            hui.error_label(f"Error: {exc}")
```

Canvas popup:

```python
panels = self._panel_factory.gather("graph_canvas", trigger, session)
if not panels:
    return  # don't open the popup

popup = Popup(...)
editor_context = GraphCanvasEditorContext(
    canvas_manager=self._canvas_manager,
    popup=PopupState(...),
)
layout = PanelLayout(popup.content)
for cls in panels:
    try:
        cls().draw(session, layout, editor_context)
    except Exception as exc:
        logger.exception(f"draw() error in {cls.__name__}")
popup.open()
```

Each editor owns its own UX decisions. The factory contributes the
typed gather-and-poll and the cross-cutting concern (poll-exception
logging) so each editor doesn't reinvent it.

There's no separate "popup host" class. Popups are a surface the
editor renders into; the editor decides whether a given focus's
panels go in the main pane or in a popup. The framework doesn't
need to model that distinction.

### 4.4 The decorator

```python
@panel(editor="properties", display_focus="node")
class NodeStatusPanel(BasePanel): ...

@panel(editor="graph_canvas", display_focus="node")
class DeleteNodePanel(BasePanel): ...

# Dual-editor display panel — works in two editors that share the "edge" focus
@panel(editor=["graph_canvas", "properties"], display_focus="edge")
class EdgeErrorsPanel(BasePanel): ...
```

The registry index becomes `(editor, display_focus) → [panels]`.
Same shape as today's `(editor_key, scope_id)`, just renamed and
properly namespaced per editor.

### 4.5 FocusDescriptor moves to EditorTypeRegistry

`ScopeDescriptor` becomes `FocusDescriptor` and moves out of
`PanelRegistry` into `EditorTypeRegistry`:

```python
# Library bootstrap
editor_registry.register_focus("properties", FocusDescriptor(
    id="edge",
    label="Edge",
    icon=hui.icon.edge,
    order=70,
    poll=lambda session: session.active_edge is not None,
))

# PropertiesEditor render
focuses = editor_registry.get_focuses("properties")
panels = panel_registry.get_panels("properties", active_focus_id)
```

What this buys:

- **Validation.** EditorTypeRegistry knows what editor keys exist;
  registering a focus for a non-existent editor can fail loudly.
- **Lifecycle alignment.** When an editor is hot-reloaded or
  unregistered, its registered focuses follow.
- **Honest intent.** `editor_registry.register_focus("properties", ...)`
  reads as "extend the properties editor with this focus tab."
- **Pattern for future editor extensions.** Toolbar buttons,
  status-bar items, editor-menu entries — same shape, same
  registry.

`PanelRegistry` keeps the `(editor, display_focus) → [panels]`
index unchanged. Two registries, two jobs:

- **EditorTypeRegistry**: editor classes and their UI extensions
  (focuses; future toolbar buttons, etc.).
- **PanelRegistry**: panel routing.

A note on "focus": the registered list covers both
selection-driven focuses (`node`, `edge` — gated by SessionContext
state via `poll`) and editor-mode focuses (`app`, `execution` —
always available). Both are "what view the user has selected"; the
`poll` decides availability.

Editors that don't surface focuses to a user (e.g. an editor whose
panels are always context-menu-only) just don't register any. The
registry handles "no registered focuses" cleanly.

### 4.6 Lift signal/lifecycle onto SessionContext

Today's `context.session.signal(...)` reaches through the context
to the session. Add facade methods on `SessionContext` so the
common-case calls don't require the indirection:

```python
class SessionContext:
    session: "Session" = field(init=False)  # back-reference, kept

    def signal(self, s: ContextSignal) -> None:
        self.session.signal(s)

    def lifecycle(self, cmd: LifecycleCommand) -> None:
        self.session.lifecycle(cmd)
```

After this, panels and editors call `session.signal(...)` /
`session.lifecycle(...)` directly. The `Session` object is still
reachable via `session.session` for code that genuinely needs it
(rare — mostly cross-session broadcasting machinery), but the
common case loses the hop.

This is a precondition for the parameter rename: without it, the
panel's `session: SessionContext` parameter would expose
`session.session.signal(...)` as the visible API.

### 4.7 Drop ``context_menu_trigger``

Nothing reads it at runtime (§3.4). The canvas's popup state lives
on `GraphCanvasEditorContext.popup.display_focus`. Tests that
assert on `context.context_menu_trigger` are rewritten to assert
on the canvas editor's popup state.

### 4.8 Lift `properties_scope` onto PropertiesEditor

```python
class PropertiesEditor(BaseEditor):
    def __init__(self, panel_factory: PanelFactory):
        self._panel_factory = panel_factory
        self._active_display_focus: Optional[str] = None
```

Per-editor-instance state, where it belongs. No panel reads it
today, so the move is safe. Other metadata keys move to typed
homes:

- **`recent_nodes`** — canvas state. Lives on
  `GraphCanvasEditorContext` (or its `PopupState` if it's
  popup-scoped).
- **`clipboard`** — session-scoped state shared across canvas
  operations. Lives on a typed `SessionState` object on the
  session.
- **`_hui_expansion`** — widget-internal persistence. Lives on a
  `WidgetState` object, or on `hui`'s own per-client state.

After this, ``session.metadata`` either disappears or becomes a
documented escape hatch for true ad-hoc state.

### 4.9 The story you tell a new panel author

> **A panel is a sub-tree of an editor. You declare a panel with
> ``@panel(editor="...", display_focus="...")``. The editor key
> says which editor hosts you (`properties`, `graph_canvas`, etc.);
> the display_focus says when you're relevant (`node`, `edge`,
> `app`, …). A panel can declare multiple editors in one decorator
> if it only reads session state and the editors share a focus
> vocabulary.**
>
> **You write `poll(session) -> bool` to gate visibility on session
> state. You write `draw(session, layout, editor)` to render —
> `session` carries selection and active-graph info, `layout` is
> the rendering scaffold, `editor` is what the editor hands you
> (typed per editor: a properties panel gets
> `PropertiesEditorContext`; a graph-canvas panel gets
> `GraphCanvasEditorContext` with the canvas manager and, when in
> a popup, a `PopupState`).**
>
> **To act on the world: `session.signal(...)` for observations,
> `session.lifecycle(...)` for workspace commands, or call methods
> on the editor directly through `editor.canvas_manager.*` (or
> whatever each editor exposes).**
>
> **To extend an editor with a new tab, register a `FocusDescriptor`
> against EditorTypeRegistry. Panels then attach via
> `display_focus="<your_id>"`.**

---

## 5. What stays the same

- The poll/draw cycle on ``BasePanel`` is unchanged in shape; the
  third `editor: EditorContext | None` arg is added, and the
  parameter rename `context` → `session` is mechanical.
- ``PanelRegistry`` keeps its `(editor, display_focus)` index;
  only field names on ``PanelIdentity`` change.
- The ``Popup`` widget stays. The canvas builds a popup, queries
  the registry, draws panels into it — same flow as today, just
  with a typed `EditorContext` instead of a metadata bag.
- ``SessionContext`` shrinks (loses ``context_menu_trigger``, loses
  popup-ephemeral metadata keys, may lose `metadata` entirely)
  *and* grows two facade methods (`signal`, `lifecycle`). The
  `session` back-reference stays for code that genuinely needs the
  Session object. Selection/active-graph fields are unchanged.
- The signal/lifecycle channels themselves are unchanged. Editor
  command vocabularies are exposed directly through the typed
  `EditorContext` instead of through closure-captured callbacks.
- `PanelFactory` is added (gather-and-poll iterator) but the
  per-editor draw loops stay editor-local — each editor keeps its
  own wrapping, empty-state UX, and draw-error UX.

---

## 6. Implementation order

Steps 1–3 are independently valuable mechanical refactors; step 4
is the structural reframe that depends on them landing first.

1. **Lift `signal()` / `lifecycle()` onto `SessionContext`** as
   facade methods; migrate the existing `context.session.signal/
   lifecycle` callsites. Independent of everything else.
2. **Rename the panel/editor parameter** `context: SessionContext`
   → `session: SessionContext`. Mechanical, type-checker-verified.
3. **Update other `context.*` reads** to `session.*` in the renamed
   bodies (`session.active_node`, `session.metadata`, etc.).
4. **The structural reframe**: `editor`/`display_focus` rename on
   `@panel`; `EditorContext` ABC with per-editor subclasses; add
   `PanelFactory` and migrate the two existing draw loops to
   iterate it; `FocusDescriptor` move to `EditorTypeRegistry`;
   drop `context_menu_trigger`; lift `_active_display_focus` onto
   PropertiesEditor; replace the `on_emit_event` callback with
   direct calls through `editor.canvas_manager`.

---

## 7. Open questions

1. **`test_inspector`.** Make it a real test-only editor that
   iterates `PanelFactory.gather(...)` like the production editors
   do (so the test path exercises the same loop), or rename to
   `test_harness` to admit its harness-only nature. Affects the
   `haybale-testing` library only.

2. **Dual-editor typing.** Panels that span two editors type
   against the base `EditorContext` because they don't read
   editor-specific fields. The type system can't *prove* the panel
   won't read subclass fields — it could be enforced via a marker
   (a `DualEditorPanel` mixin? a panel-class-level Generic?) but
   probably not worth the ceremony. Document the convention:
   dual-editor panels type against the base and don't read it.

3. **Should ``BasePanel.poll`` take signals?** Today it's
   `poll(session)` — context-only, signal-blind. Adding
   `poll(session, signal)` would bring symmetry with editors but
   doubles the API surface for panel authors. Not worth it until a
   real consumer asks.

4. **Confirm the `canvas_position` cleanup bug isn't load-bearing.**
   It's set on canvas right-click and never cleared. Probably
   nothing reads it after popup close in current code, but verify
   before lifting it into `PopupState`.

---

## 8. TL;DR

What's wrong today:

- ``@panel(editors=...)`` claims panels target *editors*, but
  ``"context_menu"`` is a popup, not an editor — the canvas's
  popup specifically. A second editor can't add its own context
  menu without colliding.
- ``@panel(scopes=...)`` carries two selection semantics. The
  invariant is one thing — the focus the editor is displaying —
  but the name doesn't say so.
- `ScopeDescriptor` is editor-extension metadata stored in the
  wrong registry. PanelRegistry is panel routing; descriptors
  belong with the editor they extend.
- ``context.metadata`` is a dict-of-Any holding three lifetimes'
  worth of state. `on_emit_event` is implicitly canvas-typed but
  lives in a generic dict.
- ``context.context_menu_trigger`` is dead state — nothing reads
  it at runtime.
- ``context.session.signal(...)`` reaches through; the channels
  could be exposed directly on `SessionContext`.

The reframe:

- **Lift `signal()` / `lifecycle()` onto `SessionContext`** as
  facade methods. Unblocks the rename below; useful on its own.
- **Rename the panel/editor parameter** `context: SessionContext`
  → `session: SessionContext`. Three params named for what they
  hold: `session`, `layout`, `editor`.
- **Editors hand panels their own context.** `EditorContext` is
  an ABC; each editor that hosts panels defines its own concrete
  subclass (`PropertiesEditorContext`, `GraphCanvasEditorContext`
  with `canvas_manager` and optional `PopupState`) and passes it
  to every panel it draws.
- **`@panel(editor=..., display_focus=...)`** — editor says which
  editor hosts the panel; display_focus says when it's relevant.
  Dual-editor panels stay one decorator when the focus vocabulary
  overlaps.
- **`FocusDescriptor` moves to EditorTypeRegistry.** Two
  registries, two jobs: EditorTypeRegistry owns editor extensions;
  PanelRegistry owns panel routing.
- **`PanelFactory` shares the gather-and-poll loop.** Editors hold
  one (DI'd) and iterate it; the per-editor draw loop stays
  editor-local because wrapping, empty-state, and error UX differ.
- **Direct method calls replace the callback.** A canvas-context
  panel calls `editor.canvas_manager.handle_event(...)` instead of
  fishing `on_emit_event` out of metadata. The action vocabulary
  is whatever the editor exposes — typed by the editor.
- **Drop `context_menu_trigger`.** Lift the active focus onto
  PropertiesEditor instance state. Move `recent_nodes` onto the
  canvas's editor context, `clipboard` to typed session state,
  `_hui_expansion` to widget state.

The popup-vs-pane distinction goes away as a public concept.
Panels declare which editor and which focus; the editor decides
where to draw them. Each editor owns its own command vocabulary
through a typed context object; library panels and the editor's
own author share trust because they're typically the same author.
