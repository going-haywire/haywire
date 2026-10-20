# Edit route: one way in for every user edit

## Context

Slice 1 of the [editor modes](2026-10-12-editor-modes.md) added the `operate`
tier, the per-level lock and `NodeWriteGate`. A review on 2026-10-16 (an
inquisition, Q1–Q19) found that the gate solves a symptom.

**The gap.** Most structure edits go through `Editor`. An `Editor` action gives
undo, and its validation reason marks the graph unsaved. Value edits do not go
through `Editor`: card and stage widgets, the Ports panel, settings rows and skin
controls write the model directly. A few structure edits skip it too:

- the propagation toggle ([context_menu.py:533](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py#L533), [edge.py:184](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py#L184));
- port reorder ([node_ports.py:324](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py#L324));
- the promote/demote fallback in `render_settings` ([render_utils.py:727-743](../../../packages/haywire-core/src/haywire/ui/panel/render_utils.py#L727-L743)).

So access checks, the unsaved mark and undo are added one path at a time, and a
path that misses that wiring misses all three. `NodeWriteGate`, `GraphWriteGate`,
`_EachNodeWriteGate` and `_OuterGate` are that wiring. Two skin controls show the
result:

- The stacked skin's fold toggle ([stacked_skin.py](../../../barn/haybale-graph-editor/haybale_graph_editor/skins/stacked_skin.py)) and the annotation's text edit ([annotation_skin.py:224-244](../../../packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py#L224-L244)) work at `view`.
- Neither marks the graph unsaved: both only call `redraw()`, and `NODE_REDRAW_REQUESTED` is visual-only.
- Neither is undoable.

The missing undo for values is the same gap. [ADR 0049](../../adr/0049-selection-forms-and-verbs.md)
calls it "framework-wide"; the wire-types plan closed it (Q92) without building it.

**The goal** is simplicity and robustness. A developer of nodes, widgets and
skins gets correct access, unsaved marking and undo without doing anything.
Haywire is a development platform that can host several users, not a
multi-user editing product. Access tiers guard against accidents, not malice
([ADR 0027](../../adr/0027-studio-authentication.md)), and the docs must say no
more than that.

This design replaces slice 5b of the editor modes. Breaking changes are allowed.

---

## The model

### User edit and edit route

- A **user edit** is one change a person or an agent makes to something a
  document saves: a value, a setting, or the structure.
- The **edit route** is the one way every user edit reaches `Editor`. It is
  per session and per level. It decides three things in one place: whether the
  edit is allowed (level mode), whether it marks a document unsaved, and whether
  it is recorded on the undo history.
- Every surface uses it: cards, the stage, the Ports panel, settings rows, skin
  controls (as widgets) and Farmhand.
- Node, widget and skin authors write no access, unsaved or undo code.
- **Structure edits (Q21):** the route hands out the level's `Editor` only in
  level mode `edit`; `route.editor()` returns `None` below it. The 28 verbs stay
  on `Editor`, unmirrored.
  - The canvas manager holds the route instead of the `Editor`. The
    dispatcher's tier check stays, because it is what snaps a refused drag back.
  - `editor_for(context)` becomes `route_for(context).editor()`. Its "an
    `Editor`, or `None`" contract does not change, so its callers don't either.
- **Where it lives (Q23):** `LevelMode` sits in `haywire.core.access`, beside
  `AccessTier`. `EditRoute` is a concrete class in `haywire.core.graph.edit_route`.
  - The route reads its `Editor` and its mode through two callables, and knows
    nothing about levels or locks.
  - The graph editor builds one route per level and session (on `_Level`), with
    a `mode` that reads the lock and the tier. That callable is the only policy
    that reaches core, as `allows` does today.
  - Farmhand builds a route with the tool's mode.
  - No DI registration: a route is an ordinary per-level object, like the
    canvas manager.
- **Not user edits:** measured node sizes (`NodesMeasuredEvent`) are derived from
  the browser's layout and stay outside the route, written straight to props
  as today ([visual_layer.py:864-880](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py#L864-L880)).

### Level mode

**Level mode** is `view`, `operate` or `edit`: the mode a session has on one
graph level. It comes from the principal's tier, capped at `operate` while the
level is locked. The cap never raises a lower tier. `developer` (later) and
`admin` sessions get level mode `edit`. "Effective tier" is retired.

| Principal's tier | Level unlocked | Level locked |
| --- | --- | --- |
| `view` | `view` | `view` |
| `operate` | `operate` | `operate` |
| `edit`, `admin` | `edit` | `operate` |

Save, the haystack actions and agents use the principal's real tier, not level
mode. Agents have no level and no lock (ADR 0051 stays).

### What each level mode allows on the canvas

| | `view` | `operate` | `edit` |
| --- | --- | --- | --- |
| Pan, zoom | yes | yes | yes |
| Levels | document level only | Enter (double-click; a placement opens locked) | everything |
| Selection, copy | no | no | yes |
| Widgets on cards and stage | no | operable widgets only | yes |
| Context menus, toolbar, structure edits | no | no | yes |
| Properties editor's writable panels | not shown | not shown | yes |
| Undo/Redo | no | no | yes |

- **Selection needs `edit`.** Locking a level clears its selection.
- **Patch | Stage stays a `view` action (Q22).** `ToggleStageView` keeps
  `access=VIEW`: switching is per session and saves nothing, so it is looking,
  not touching. The graph's `open_view` stays a display default, never an
  access rule.
- **The Properties editor's writable panels show only in `edit`.** Node, edge
  and port panels need a selection. `GraphInspector.poll` (which today needs only an
  active graph, [surfaces/graph.py:21](../../../barn/haybale-graph-editor/haybale_graph_editor/surfaces/graph.py#L21))
  becomes false below `edit`. That covers graph settings, metadata and haystack's
  run settings. As a result, panels never need a read-only rendering, and
  `render_settings` loses its gate.

### Two layers of enforcement

1. **Server:** the edit route refuses any edit the level mode does not allow.
   That covers every surface that writes through it.
2. **Browser:** each canvas carries its level mode. Below `edit`, card content
   takes no pointer input. In `operate`, the containers of operable widgets take
   it again. This catches a skin or widget that writes the model directly
   anyway.

The docs state the limits plainly. The tiers are not a security boundary, and
code that deliberately goes around the route is outside what they promise.

### Undo

- **Only edits made in level mode `edit` are recorded.** An edit in `operate`
  is written and marks the document unsaved, but is not recorded. Performing on
  a locked level does not spend the edit history, as in a locked Max patch.
- **Merging (Q5):** consecutive writes to the same node and field, by the same
  session, merge into one step. The run ends at any other action, a write to
  another field, or an idle gap of `VALUE_EDIT_MERGE_IDLE_S = 3.0` seconds. That
  constant sits at the top of `core/undo/actions/graph_actions.py`. A slider drag
  is one step, and so is typing a word.
- **An unrecorded write ends the merge run** (the route adds a fence). Without
  it, a write in `edit` mode, a locked tweak, and another `edit` write within 3 s
  would merge across the tweak.
- **Undo replays the history as it was recorded (Q19).** An older recorded step
  on a field restores its old value, even over a later unrecorded `operate`
  value. A later recorded step captures the `operate` value as its old value,
  because `SetPropertyAction` reads the old value when it runs.
- A no-op write (the value did not change) records nothing and marks nothing.
- Undoing the first write to a mirrored or unset setting restores *unset*, not
  a local copy of the old value.
- A multi-node form's edit is one composite step.
- Structure edits only exist in `edit`, so they are always recorded.
  Propagation toggle, port reorder and promote/demote become `Editor` actions,
  so all of them become undoable.

### Unsaved

**An edit marks unsaved the document that saves the changed value.**

- A node value or setting, graph props, graph metadata and edge style all mark
  their graph unsaved. `GraphWriteGate`'s exemption for graph props and metadata
  is dropped: a user who edits one and closes the graph no longer loses it
  without a warning.
- A Group's interior is saved in the host, so an interior edit marks the host
  (`GraphNode` forwarding, unchanged).
- A placement's interior values are runtime state that no document saves, so
  they mark nothing ([ADR 0038](../../adr/0038-a-placements-interior-is-runtime-state.md)).
  Placement value overrides are deferred (slice-6 inquisition, 2026-10-19).
- An Inset widget on a host card follows the host level's mode. In `edit` it
  records an ordinary value step on the host's history (slice 6).

### Widgets: the host hands the widget a routed model

- The pattern exists already. [SettingWidgetModel](../../../packages/haywire-core/src/haywire/ui/panel/setting_widget_model.py)
  is a `WidgetModel` that reads a shared cell and sends writes to a callable.
  [`_widget_model_for`](../../../packages/haywire-core/src/haywire/ui/widget/factory.py#L16)
  is already the one place every port widget gets its model. The redesign
  generalizes both.
- The host (card, Ports panel, settings row) passes the route. The factory
  builds a **routed model**: it reads the cell, and its writes go through the
  route.
- A widget rendered with no route gets a read-only model. That fails closed.
- Widget code does not change: `self.set_value(...)` and `bind()` work as
  today. A refused write shows the model's value again, as now.
- A compound widget wraps the model it was given, so it is routed for free.
  `_OuterGate` goes away.
- No widget in the repo uses a nested binding path (`bind(to="a.b")`). That path
  builds a new value and calls `set_value`, as `VecWidget` already does. The
  in-place change at [binding.py:214](../../../packages/haywire-core/src/haywire/ui/widget/binding.py#L214)
  leaves undo no old value to restore.
- Deleted: `WriteGate` (`value_changed` stays), `BaseWidget.write_gate`, the
  binding's `owner.write_gate.written()`, `_OuterGate`, `render_settings(gate=)`,
  `NodeWriteGate`, `GraphWriteGate`, `_EachNodeWriteGate`,
  `UINode._apply_write_gates` and `session_allows`.

### Skins: a skin draws, widgets write

- A skin writes nothing. Every control on a card is a widget.
- `UINode` passes the route into `factory.render(...)`. `BaseSkin._render`
  keeps it per node id for that render, the way it keeps
  `_nodeids_widget_instances`; skin instances are app-wide singletons, shared
  by every session and canvas. `BaseSkin.render_widget` forwards it. The skin
  author's `render()` signature does not change.
- **Fold header (Q25):** the `FOLD` type declares a `FoldWidget`, replacing
  `widget_key=None`
  ([fold.py:14-15](../../../packages/haywire-core/src/haywire/barn/builtin/types/fold.py#L14-L15)).
  - The widget draws the triangle, the label and the checked/unchecked icon, and
    a click writes the value through the route. The open state is a saved value,
    so it can be toggled in `operate` and `edit` but not in `view`.
  - The stacked skin draws it with the usual `render_widget` inside its fold
    layout, and still owns the indentation and the children.
  - Every skin gets a working toggle. The split skin draws a fold as an
    ordinary row, so it gains the toggle it lacks today: a closed fold there
    hides its children with no control to reopen it (found by reading the code).
  - Agents can operate folds, since `graph_editor_operate` requires a widget
    key.
  - On stage the header follows the ordinary widget rule, so the special case at
    [stacked_skin.py](../../../barn/haybale-graph-editor/haybale_graph_editor/skins/stacked_skin.py)
    goes.
  - The Ports panel is unaffected: it checks `is_fold` before rendering a widget
    and shows only the label
    ([node_ports.py:267-270](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py#L267-L270)).
- **Annotation text:** a widget on the `text` setting. It keeps today's UX: the
  double-click opens an editor over the card, Tab types a tab, mouse and wheel
  events stay in the editor, blur or Ctrl+Enter commits and Esc cancels.
  - The double-click stays. canvas.vue's drag guard
    ([canvas.vue:3883-3891](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L3883-L3891))
    starts no drag or selection on a `.widget-container`, a textarea or a
    Quasar field. The text fills the card, so a single-click editor would leave
    the note grabbable only by its padding. While it is only showing the text,
    the widget's label sits outside `.widget-container`; only the open editor is
    interactive.
  - The double-click listener lives inside the widget, so the browser layer
    covers it. A card-level listener would open an editor in `operate` whose
    commit the route then refuses.
  - The skin keeps the look. It wraps the widget in a div carrying
    `_text_style(bag)`, and the label and textarea inherit font, colour,
    alignment and decoration.
  - `text` is a setting (`Promotable.NONE`), not a port. The skin needs a call
    to draw a setting's widget on the card, built on the same routed model.
  - New behaviour: a text edit is one undo step, and it marks the graph
    unsaved.

### `operable=False`

- A field or a port may declare `operable=False`. The route then needs level
  mode `edit` for that write, and in `operate` the browser layer leaves the
  widget without pointer input.
- The annotation `text` setting declares it.
- It is a boolean, not a tier, so `access=view` or `developer` cannot be written
  there by mistake. It is the escape hatch [ADR 0051](../../adr/0051-operate-tier-and-the-canvas-lock.md)
  noted, now with a real first case.

### Access defaults and the haystack editor

- **Editors and panels default to `access=edit`**, instead of `view`
  ([editor/identity.py:91](../../../packages/haywire-core/src/haywire/ui/editor/identity.py#L91),
  [panel/identity.py:71](../../../packages/haywire-core/src/haywire/ui/panel/identity.py#L71)).
  An editor that forgets to declare fails closed. Read-only editors declare
  `view` explicitly (candidates: component docs, log, errors, shortcuts,
  activity, file viewer). Every editor and panel is reviewed once in 5b-5.
- **Haystack actions by effect (Q12):**
  - `view`: select an entry to look at.
  - `operate`: also Start and Stop execution.
  - `edit`: everything else: New Graph, Load Graph, entry Rename and Remove,
    the haystack's Load, Rename and Save, and the run settings. Save and Save-as
    already need it.
  - Each handler checks the real tier, and the control is hidden below it.

### Agents

- Every Farmhand write goes through the route. The tool's tier sets the
  mode: `graph_editor_set_property` (`edit`) is recorded, and
  `graph_editor_operate` (`operate`) is not.
- The lock does not apply to agents.

### Tier ladder (noted, not built here)

`view` < `operate` < `edit` < `developer` < `admin`. **`developer`** is needed for
the code editors, so changing code in the browser needs `developer`. It is
enforced through those editors' own access levels, in later work. Two things to
settle then:

- `SessionContext.developer_mode`, a per-session toggle in the Account menu
  ([account.py:149](../../../barn/haybale-studio/haybale_studio/panels/account/account.py#L149)),
  clashes with the tier's name.
- ADR 0027 says `edit` is already `admin` at the machine level, because an
  `edit` principal can author a Python node. With `developer`, the code editors
  move out of `edit`. That is still only a guard against accidents: a library
  node that evaluates code still runs code at `edit`.

---

## Sketch

**The route** (core). It is per session and per level, and reads its `Editor`
and level mode at every write. Reading the editor through a callable lets a
route follow its level when `_ensure_document_level` swaps the level's
container in place. The caller states the surface's `minimum`: card and stage
widgets `operate`, panels `edit`. 5b-4's `operable=False` raises it to `edit`.

```python
class EditRoute:
    def __init__(self, editor: Callable[[], Editor], mode: Callable[[], LevelMode]) -> None: ...

    def set_port(self, node_id: str, port_id: str, value: Any, *, minimum: LevelMode) -> bool:
        if not self.allows(minimum):
            return False
        return self._editor().set_property(node_id, port_id, value, record=False)  # 5b-2: record in edit

    def set_setting(self, bag: Settings, name: str, value: Any, *, minimum: LevelMode) -> bool: ...
    def reset_setting(self, bag: Settings, name: str, *, minimum: LevelMode) -> bool: ...

    def editor(self) -> Editor | None:
        """The level's ``Editor`` for structure edits, or ``None`` below level mode ``edit``."""
        return self._editor() if self._mode() is LevelMode.EDIT else None
```

**Recording** (`Editor`):

```python
def set_property(self, node_id, name, value, *, record: bool = True) -> bool:
    action = SetPropertyAction(self.graph, node_id, name, value)
    if record:
        return self.history_manager.add_action(action)   # an undo step; merges per Q5
    action.execute()                                     # applied, marks unsaved, not recorded
    self.history_manager.add_fence()                     # ends any merge run
    return True
```

**The routed model** is the existing `SettingWidgetModel`: it reads a shared
cell and hands each write to a callable, whose `False` now means "refused". No
new class.

**The construction point** (the existing function, with a `route` added):

```python
def render_widget(self, registry_key, port, node_id, *, route=None, minimum=LevelMode.EDIT): ...

def _widget_model_for(port, route, minimum):
    if not isinstance(port, DataPort):
        return port                               # a model the host built itself
    if route is None or port._node is None:
        write = lambda _v: False                  # no route: read-only
    elif port.promoted:
        bag, descriptor = _resolve_promoted(port._node, port.id)
        write = lambda v: route.set_setting(bag, descriptor._attr_name, v, minimum=minimum)
    else:
        write = lambda v: route.set_port(port._node.node_id, port.id, v, minimum=minimum)
    return SettingWidgetModel(port.id, port.widget_config, port.data, write)
```

**`BaseWidget`** (the gate goes; the snap-back stays):

```python
def set_value(self, value: Any) -> None:
    if not self.accepts_write() or self.port.set_value(value) is False:
        self.on_model_changed(self.port.get_value())    # refused: show the model again
```

`PropertyBinding._sync_to_model` gets the same treatment. Hosts pass the route:

- the card through `factory.render(..., route=)`;
- the Ports panel through `render_widget(..., route=)`;
- settings rows through `render_settings(ctx, bag, route=)`, a required keyword
  where `route=None` means a bag outside any graph document. `_bag_on_edit`
  writes through the route. The multi-node form's fan-out writes each real bag
  through it; the form's neutral bag belongs to no document, so the route writes
  it directly after the mode check.

---

## Sequence

5b is built as five sub-plans. Each one merges into `feat/editor-modes-slice1`
and gets its own live check. 5c (stacking), 5d (control nodes) and 6 (Inset)
follow, all built on the route.

1. **5b-1, the edit route.**
   - `EditRoute` (with `editor()`) in `haywire.core.graph.edit_route`,
     `LevelMode` in `haywire.core.access`, the routed `SettingWidgetModel`, and `route=` through
     the factory, the skin render, the Ports panel and `render_settings`.
   - The graph editor builds a route per level and session. The canvas manager
     holds it instead of the `Editor`, and `editor_for` becomes
     `route_for(context).editor()`.
   - Values go through `Editor.set_property(record=False)`. Value undo stays off
     until 5b-2, so this slice changes no undo behaviour for values.
   - The route's mode maps from today's rule (`allows`): `edit` when it allows
     `edit`, `operate` when it allows `operate`, else `view`.
   - The unsaved rule (graph props, metadata and edge style mark unsaved; no-op
     writes mark nothing).
   - Propagation toggle, port reorder and promote/demote become `Editor`
     actions.
   - Farmhand writes go through the route.
   - Delete the write gates.
2. **5b-2, undo for values.**
   - Record in `edit` mode, and add the fence after an unrecorded write.
   - Same-field merging with `VALUE_EDIT_MERGE_IDLE_S`.
   - Restore unset on undo, and make the multi-node form one composite step.
3. **5b-3, level mode.**
   - `LevelMode` replaces `allows` and "effective tier".
   - Selection needs `edit`, and locking clears it.
   - `GraphInspector.poll` is false below `edit`, and the read-only panel
     rendering is removed.
   - `view` sees the document level only. Enter needs `operate`, and so does the
     error-ledger reveal of an interior level.
   - The browser layer: the canvas `locked` prop becomes a level-mode prop, and
     operable widget containers carry `data-hw-operable`.
4. **5b-4, skins write nothing.**
   - `FoldWidget` declared on the `FOLD` type, and the annotation text widget.
   - The skin call that draws a setting's widget.
   - `operable=False` on settings and ports.
   - Skin canon: "a skin draws, widgets write", and "skin instances are app-wide
     singletons".
   - Built (plan `2026-10-17-editor-modes-05b4-skins-write-nothing.md`): the route
     enforces `operable=False`, so callers pass only their surface's `minimum`; a
     promoted port inherits it; `FOLD._configure_port` gives every fold port the
     widget, its label and description (saved folds too) and a redraw on change;
     a fold row draws no separate label; `render_setting_widget(..., widget_key=)`
     lets the annotation skin pick `NoteTextWidget` while Properties keeps the plain
     text widget; the note's look reaches the widget by CSS inheritance and
     `--hw-note-*` custom properties; the fold widget hosts its own tooltip on the
     triangle.
5. **5b-5, access defaults and the haystack.**
   - Editors and panels default to `edit`, with explicit `view` declarations.
   - The haystack action tiers.
   - Panel and editor canons document the default.
   - security.md loses its known-gaps box.
   - Built (plan `2026-10-17-editor-modes-05b5-access-defaults-and-haystack.md`): the
     Properties editor takes the `edit` default (every tab writes or polls `edit`);
     every editor and panel is classified in one test; haystack controls below their
     tier are not drawn, Save included; Farmhand `start_graph`/`stop_graph` need
     `operate`; error triage and the log's Clear stay at `view`.

---

---

## Traps to carry into the sub-plans

- **A promoted port must write through its setting.** `SetPropertyAction`
  resolves a name against ports first. A write to the cell leaves the bag
  thinking nobody set it, so the edit does not save and Reset stays greyed (see
  the `_widget_model_for` docstring). The routed model targets the setting
  (5b-1).
- **The undo merge needs a new path.** `HistoryManager` merges only into
  `_pending_actions`, which are flushed once 500 ms have passed since the last
  fence ([history_manager.py:139-163](../../../packages/haywire-core/src/haywire/core/undo/history_manager.py#L139-L163)),
  so value writes almost never merge today. 5b-2 must let a value action merge
  into the newest history step while nothing is redoable. A `merge()` must still
  call `mark_executed()` on what it returns
  ([insight](../../../.insights/project_undo_merge_executed_state.md)).
- **The history is shared across sessions** (one `GraphEntry`, one `Editor`), so
  the merge key includes the session.
- **CSS pointer gating has to out-specify five layers.** canvas.vue and pan.vue
  set `pointer-events` explicitly at five layers below the canvas, some with
  `!important`. A gate keyed on a canvas attribute needs a universal selector
  with `!important` ([eventcensus.py:193-208](../../../.scratch/pan-perf/eventcensus.py#L193-L208)).
  `pointer-events` does not stop keyboard focus, so the route is the refusal
  that counts (5b-3).
- **The annotation label must stay non-interactive** (canvas.vue drag guard,
  above), or the note cannot be dragged by its body (5b-4).
- **Focusing the opened editor needs a timer.** A focus call made while an
  element is being shown is dropped
  ([insight](../../../.insights/feedback_nicegui_outbox_updatevalue_stomp.md)).
  The annotation skin already does this; keep it (5b-4).
- **The error-ledger reveal opens interior levels.** `_open_level_for_graph`
  ([graph_editor.py:853](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py#L853))
  must not open one for a `view` session (5b-3).
- **Interior forwarding.** `GraphNode` forwards a Group interior's value edits
  as `GRAPH_CONTENT_CHANGED` without redrawing the host card
  ([graph_node.py:122-137](../../../packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py#L122-L137)).
  Keep that, and keep a placement's interior unmarked.
- **An action per slider tick.** `SetPropertyAction._resolve` runs on every
  write. Measure a slider drag on a large graph before and after 5b-1 (the
  benchmark skill).

## Open after 5b-2

Each sub-plan that follows picks these up or names them as deferred.

- **A remote undo leaves the selection toolbar stale.** Done in 5b-3: each
  canvas re-renders its selection toolbar when a validation batch names a
  selected node or edge (`GraphCanvasManager._refresh_toolbar_for`), so any
  write, undo or redo, by another session or a Farmhand call, updates it.
- **Undo cannot restore an edge's propagation to `None`.** Deferred past 5b-3.
  `SetEdgePropagationAction`'s setter takes only a `Propagation` (parked since 5b-1).
- **A Farmhand tool run outside the MCP host gets no closing fence.** Deferred
  past 5b-3. The host calls `ctx.close_fences()` in its `finally`; a direct
  `run(ctx, ...)` must call it itself. No such caller exists yet.

Outside this sequence:

- **Ctrl+S does not save the graph.** The toolbar Save button works, and its tooltip
  says "Save (Ctrl+S)", but no `EditorCommand` binds the key.
- **Undo-history panel.** A panel in the context slot listing the document's
  undo steps (and the current one) would make merge runs, groups and
  cross-session steps visible. The 5b-2 live check could not verify the
  two-session case without it.

---

## Glossary and ADR candidates

These land with the code, in the sub-plan that builds each item.

**Glossary (new):**

- **User edit**: one change a person or agent makes to something a document saves.
- **Edit route**: the one way every user edit reaches `Editor`.
- **Level mode**: `view`, `operate` or `edit`, per session and level. Aliases
  to avoid: effective tier, mode (bare), canvas mode.
- **Operable**: whether operating a widget may change its field.

**Glossary (changed):**

- **Write gate** is removed.
- **Effective tier** is removed (it becomes an alias under Level mode).
- **Operate (tier)**: values on operable widgets on cards and the stage, plus
  Enter, and Start and Stop in the haystack.
- **Lock**: caps the level mode.
- **Enter**: double-click needs `operate`.
- **graph metadata**: a metadata edit marks the graph unsaved.
- **Access-Gated Surface**: the default is `edit`.

**ADR:** a new ADR 0055, "Every user edit takes the edit route". It is hard to
reverse, it would surprise a reader without context, and it chose between real
alternatives. It lands with 5b-1, and 5b-2 and 5b-3 correct it in place to
describe what landed. [ADR 0051](../../adr/0051-operate-tier-and-the-canvas-lock.md)
and [ADR 0027](../../adr/0027-studio-authentication.md) are corrected in place,
with no notes about their history.

## Docs corrections

Each one goes with the sub-plan that makes it true.

- [security.md:76](../../guides/security.md#L76): the tier list leaves out
  `operate`, and "full operator" clashes with the `operate` tier (5b-1).
- [security.md:482-500](../../guides/security.md#L482-L500): the tier
  descriptions and the enforcement paragraph (5b-3). The known-gaps box goes
  (5b-5), and so does the "apart from the known gaps" sentence at
  [:539-540](../../guides/security.md#L539-L540).
- [ADR 0051](../../adr/0051-operate-tier-and-the-canvas-lock.md):
  - :20, `view`'s description (5b-3);
  - :25, enforcement (5b-1, 5b-3);
  - :26, value edits mark unsaved, false for the fold and annotation today (5b-1);
  - :40, the known gaps (5b-4, 5b-5);
  - :42, "a new write path must ask the write gate" (5b-1).
- [ADR 0027:38-49](../../adr/0027-studio-authentication.md#L38-L49): "a `view`
  principal cannot mutate anything" (5b-3).
- [ADR 0049:35](../../adr/0049-selection-forms-and-verbs.md#L35) and
  [ADR 0047:40](../../adr/0047-edge-settings.md#L40): settings and style edits
  are not undoable (5b-2).
- [ports.md:218](../../guides/ports.md#L218): "Reordering is not undoable"
  (5b-1).
- [glossary.md:376-380](../../reference/glossary.md#L376-L380) and
  [:457](../../reference/glossary.md#L457): see the glossary list above.
- [panel-canon.md:129](../../components/panels/panel-canon.md#L129): the
  `access` default; the editor canon gets the same row (5b-5).
- [widget-canon.md](../../components/widgets/widget-canon.md): a widget's
  writes go through the host's route, and a widget without a route is read-only
  (5b-1).
- [skin-canon.md](../../components/skins/skin-canon.md): a skin draws, widgets
  write; skin instances are app-wide singletons; the call that draws a setting's
  widget (5b-4).
- The `fold()` docstring ("a port with no pin and no widget",
  [data.py:266-267](../../../packages/haywire-core/src/haywire/core/node/data.py#L266-L267))
  and the `FOLD` type's `widget_key=None` comment (5b-4).
- The `editor_for` docstring becomes `route_for` (5b-1).
- The `SetPropertyAction` docstring ("the one deliberate new core mutation
  surface mandated by the Farmhand spec") becomes the route's value action
  (5b-1).

---

## Not in scope

1. Protection against malice. The tiers guard against accidents, and the docs
   say so.
2. An ambient check of who is writing, at the model or cell level (a hidden
   scope).
3. The `developer` tier, including its clash with the `developer_mode` name.
4. Placement value overrides (slice 6). The unsaved rule is only made ready
   for them.
5. Persisting lock and view per principal (still blocked on
   `workspace_state.json` being per project).
6. Settings outside graph documents: framework, library, workspace and app
   settings. They get no undo and no unsaved mark; access comes from their
   panel's or editor's tier.
7. Writes from node code: runtime writes, `store` and outlet values. They are
   not user edits.
8. Per-graph, per-node or per-file permissions, and a lock for agents.

---

## Decision log

| Q | Decision |
| --- | --- |
| 1 | There is no single path for user edits. Every user edit takes one route into `Editor`, and the gate classes go away. |
| 2 | Tiers prevent accidents, with two layers: a server check in the route and level mode in the browser. |
| 3 | Ladder `view` < `operate` < `edit` < `developer` < `admin`. `developer` is noted, not built. |
| 4 | Values are recorded only in level mode `edit`. In `operate` they mark unsaved but are not recorded. |
| 5 | Same node, field and session merge until another action, another field, or 3 s idle (a module-top constant). |
| 6 | The host hands every widget a routed model, and `write_gate` goes. |
| 7 | A skin draws, widgets write. The fold header and annotation text become widgets, keeping the annotation's UX and its double-click. |
| 8 | Selection needs `edit`. `view` pans and zooms on the document level only. `operate` adds Enter and widgets. Writable panels show only in `edit`. Revised 2026-10-17 (5b-6): selection works in every level mode; acting on it needs `edit`, and locking keeps it. |
| 9 | A fold's open state is a saved value. |
| 10 | An edit marks unsaved the document that saves the value. |
| 11 | Editors and panels default to `edit`. The haystack editor is in scope. |
| 12 | Haystack: `view` selects, `operate` adds Start/Stop, `edit` does the rest. |
| 13 | `operable=False` on fields and ports; the annotation text declares it. |
| 14 | The term is **Level mode**. |
| 15 | The terms are **User edit** and **Edit route**. |
| 16 | This is 5b, built as 5b-1 to 5b-5, then 5c, 5d, 6. |
| 17 | The non-goals list above. |
| 18 | Two facts go into the canons: skin singletons, and the access default. |
| 19 | Undo restores the recorded old value, even over a later unrecorded `operate` value. |
| 20 | Shared understanding confirmed; this document written. |
| 21 | Structure edits: `route.editor()` returns the `Editor` only in level mode `edit`, and the verbs stay on `Editor`. |
| 22 | Patch \| Stage switching stays a `view` action. |
| 23 | `LevelMode` and `EditRoute` are concrete classes in core; the graph editor supplies the `mode` callable. |
| 25 | The `FOLD` type declares a `FoldWidget`. |
