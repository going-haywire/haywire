# Editor modes: lock, stage, instance edit and Inset

## Context

The graph editor has one mode: edit. Four things are missing, all modelled on
Max/MSP:

- **Looking without editing.** A user cannot open a graph without being able to
  change it. The `view` access tier is meant to give exactly that, but the canvas
  does not enforce it: [security.md:482](../../guides/security.md) admits that
  menus and gestures are ungated. The real gap is wider. The header
  Undo/Redo/Save, widget edits and every Properties settings row are ungated too,
  so [ADR 0027](../../adr/0027-studio-authentication.md)'s claim that "a `view`
  principal cannot mutate anything" is false today.
- **Looking inside a running macro.** Entering a placement is refused
  (`GraphEditor.descend_into`); [ADR 0038](../../adr/0038-a-placements-interior-is-runtime-state.md)
  says it "waits on a read-only editor mode". There is also no way to experiment
  inside one running placement and then write the result back to the macro.
- **A presentation layer.** In Max you mark UI objects for presentation, arrange
  them at a second position, and switch to a view that shows only them, with no
  patch cords. The result is a hand-built UI.
- **bpatcher.** A Max object that shows a sub-patch's presentation inside a box in
  the parent patch.

This document is the outcome of a design interview (29 decisions, 2026-10-12).
It records the decisions and the build sequence. Each slice gets its own step
plan, numbered by its place in the sequence.

---

## The model

### Two switches per open level

Every open graph level (a document, or a Group/placement entered inside it) has
two independent switches:

| | **Patch view** | **Stage view** |
| --- | --- | --- |
| **Unlocked** | today's editor | the same editor, showing the stage |
| **Locked** | look and operate | perform |

- **Two keep-alive views per level (Q2c, 2026-10-14).** Each level holds a canvas
  per view in an inner keep-alive `ui.tab_panels`. The stage canvas mounts on the
  first switch and both then stay mounted: no re-render on switch, and a detached
  deactivated panel keeps page-global pin uuids unique. Switching clears the
  selection.
- **The switch sits in the editor header (Q8a)**, next to the lock button. The
  level bar stays hidden while only one level is open.
- **Lock** belongs to the session and the level. It is not saved and does not
  affect other sessions viewing the same graph, because the graph and its
  `Editor` are shared across sessions.
- **The graph saves only defaults.** `GraphProperties` gets `open_view`
  (`patch` | `stage`) and `open_locked` (bool), applied when a level first opens
  in a session. This mirrors Max's "Open in Presentation".
- **Controls:** a lock toggle and a Patch | Stage switch in each level's bar, plus
  two editor commands: `ToggleLock` (Mod+E, `access=EDIT`) and `ToggleStageView`
  (Mod+Shift+E since 05a-3; originally Mod+Alt+E, Firefox's developer tools; `access=VIEW`).

### Tiers: view < operate < edit < admin

- **OPERATE** is a new tier. An operate principal may **change values on widgets
  that are shown** (on cards, and on the stage), and nothing else: no context
  menus, no selection toolbar, no edit actions (paste, cut, delete, duplicate),
  no Reset Node, no Revalidate, no Properties writes, no Undo/Redo, no unlock.
- **A locked canvas caps the session's effective tier at OPERATE** for that
  canvas. Locking is how an editor protects structure while still playing the
  graph. The cap lowers the tier and never raises it, so a VIEW session stays
  VIEW.
- **VIEW** can pan, zoom, select, copy, enter levels, switch views and read the
  Properties panels. It cannot change values.
- **No per-port tier.** A widget that reshapes its node (an `on_change` handler
  that calls `rejig()`) stays operable. Ghost pins make the reshape reversible:
  edges on a removed pin reattach when a port with that id returns. An author who
  wants a widget out of operators' reach hides it on the card
  (`ShowWidgetStrategy.NEVER`). It then lives only in the Properties panel, which
  needs EDIT. An opt-in `access=` on a port spec is the noted escape hatch if
  that ever proves insufficient.
- **The Properties editor is read-only below EDIT.** Settings rows render
  disabled; Ports-panel widgets render disabled. The guard is **server-side** at
  the write paths, because `BaseWidget.set_enabled()` only changes how the widget
  looks and leaves the model writable.
- **Save needs the principal's real EDIT tier and ignores the lock.** An editor
  performing in a locked stage can save tuned values without unlocking. Undo/Redo
  are canvas actions and the lock blocks them.

### Macros: Enter, Edit Instance, and three verbs

- **Enter** replaces "Enter Group" and works for every Graph-node. A placement
  opens **locked**; double-clicking an Inset enters too. **Edit Macro…** (open
  the `.hwm` as its own document) stays.
- **Unlocking a placement asks first:** "Edit this instance? It becomes a
  modified instance of Blur until you Update or Revert." Confirming runs the
  detach (one undo step) and unlocks.
- **A modified instance** is a Group that carries an **origin**: the macro's
  registry key and the template's content hash at the moment of divergence.
  Edits are ordinary Group edits: saved with the host, undoable, untouched by
  `.hwm` reloads. ADR 0038 stays true: a placement never saves its interior, and
  a modified instance is no longer a placement.
- **Three verbs** on a modified instance:
  - **Update Macro…** overwrites the origin `.hwm`. A confirmation names how many
    placements in how many open graphs it updates. If the template's hash no
    longer matches the origin, it warns that saving replaces changes made since
    the divergence. Afterwards the card is a placement again. Needs an editable
    (`pip -e`) install, like Edit Macro….
  - **Save new Macro…** writes a new `.hwm` and makes the card a placement of it.
    It replaces the label "Promote to Macro…" on plain Groups too: one action.
  - **Revert to Macro** discards the instance's changes and makes the card a
    placement of the *current* template. Writes nothing.
- **Placement value overrides.** A placement saves the own values its interior
  holds that differ from the template, as a sparse recursive map keyed by
  template node id:
  `{template_node_id: {"ports": {port_id: value}, "interior": {...}}}`. On load
  and on `.hwm` reload they are re-applied through the template-id→minted-id map
  that `SubgraphDefinition.instantiate()` already returns; targets that no longer
  exist are dropped silently. Structure is still never saved. **Update Macro…**
  writes current values into the template as its new defaults.

### Stage

- **Name:** *stage*. "Presentation" is taken: it is a Surface's chrome
  ([ADR 0029](../../adr/0029-surface-model.md)).
- **The unit is the node.** A node is on stage or not, and has one **stage rect**:
  `stage_x`, `stage_y`, `stage_width`, `stage_height`, `stage_size_adapt` on
  `NodeProperties`, with the patch rect's rules (manual size is a minimum).
- **Skin contract (Decision 6, 2026-10-15; supersedes the `render_stage()` face).**
  A node on stage is drawn by its normal `render()`:
  `BaseSkin.render(main_card, wrapper, *, on_stage: bool)`, with the keyword
  required. `render_pin(..., on_stage: bool)` is required too and returns `None`
  for a port that is not on stage when `on_stage` is true; ghost pins are
  unchanged. A collapsed node is drawn expanded on stage. `render_stage()` and the
  frameless default face are deleted. See
  [ADR 0054](../../adr/0054-the-stage-view.md).
- **On-stage wires.** A wire type sets the class attribute `on_stage = True`;
  `AnnotationWire` does. Pins and edges derive it like they derive the wire key.
  Stage view draws an edge only if its wire is on stage and both end nodes are on
  stage.
- **Stage origin.** The stage has a fixed (0,0) at its top-left, and
  `stage_x`/`stage_y` are relative to it (Decision 3). An L-shaped corner bracket
  marks the origin, and drags stop at it, so nothing sits above or left of it. **Add to Stage** places a node at the next free
  spot near the origin (below the lowest stage item, at a margin), not at its
  patch position.
- **Stage view is the existing canvas in stage mode:** a node filter (on stage
  only), the stage **layout channel**, the filtered edge set, and `render(...,
  on_stage=True)`.
- **The stage is a display, not a mode (Decision 1, 2026-10-15; supersedes
  "unlocked stage view only arranges").** Editing in stage view is exactly editing
  in patch view: every edit, context menu, toolbar panel and editor command, at the
  same tier; the lock and the tiers apply to both views alike. **Delete is not
  remapped** (Decision 7, 2026-10-14): in stage view it deletes the node from the
  graph; Remove from Stage is its own verb.
- **Q7a:** a node created, pasted or duplicated while stage view is active lands
  on stage at the gesture position (stage coordinates); its patch position takes
  the same numbers; one undo step with the creation. Collapse to Group, macro
  placement and detach are selection-driven and do not.
- **Control nodes** in haybale-core: Slider, Number (int/float), Toggle, Text and
  Menu. Each has an inlet and an outlet of its type, with the widget on the
  outlet set to `ALWAYS`: it shows what flows through, and a user edit sends it
  on. Button is deferred: it fires execution, which makes it an event source.
- **Stacking order (Decision Q4, 2026-10-14).** Stacking order exists in both
  views, each with its own field: `z` for the patch, `stage_z` for the stage. The
  verbs are Bring to Front, Send to Back, Forward and Backward. It lands in slice
  5 as a channel field.

### Inset (bpatcher)

- **An Inset** is a Graph-node card (Group or placement) whose body shows its
  interior's stage. Its layout cannot be edited; its widgets can be operated.
- **A hidden `InsetSkin`**, set on the node tier by the Graph-node menu toggle
  "Show as Inset" (an undoable EDIT action). `render()` draws the border pins
  (the card stays wireable) and a body that draws each staged interior node with the skin's
  `render(..., on_stage=True)` at its stage rect, in stage-origin coordinates. On a node
  without an interior it falls back to the default card.
- **Size:** auto-fits from the stage origin to the stage's bottom-right extent.
  A manual size adds space and never crops. Offset and clipping are a later
  opt-in.
- **Enablers:** a composition hook that hands the inset skin a way to draw an
  interior node (the skin factory's `render(..., on_stage=True)`; the hook
  design is to be settled in slice 6, since a skin today only has a widget
  factory), and inset
  widgets registered under the **host** card's node id, so they are built,
  reloaded and cleaned up with the card.
- **Connectors:** the edge path and marker code moves out of `canvas.vue` into a
  shared JS module. An Inset component uses it to draw a read-only SVG layer from
  pins measured inside its own box.

### Agents (Farmhand)

- **`graph_editor_operate`** (`access=OPERATE`) writes a value to a port whose
  widget is shown, using the same server-side check as the UI.
- Stage fields need no tool: `graph_editor_set_property` (EDIT) writes any
  `NodeProperties` field.
- Lock does not apply to agents: they have no canvas and act at their own tier.
- The instance verbs need a dry-run/confirm design of their own and are deferred.

### Node position

- **Props are the single source.** `NodeWrapper._initial_position` goes; the
  wrapper reads and writes `props.posX/posY`.
- **The `"position"` key is dropped from saved files**, with no upgrader and no
  `format_version` bump. This is a breaking change by decision. Every node in the
  repo's tracked graph files (1,826) already carries `posX/posY` in props.
  Readers that move to props: the graph loader, macro instantiation and paste.
- **The layout channel** then names the fields a canvas reads and writes:
  patch = `posX/posY/width/height/size_adapt`, stage = the `stage_*` fields.
  `MoveNodesToAction`, `graph.move_node`, `NODE_MOVED`, the canvas-size check,
  resize and the visual layer take the channel as a parameter.

---

## Sequence

Each slice ships on its own. Plans are written one at a time, as the previous
slice lands.

1. **Lock and the operate tier:** [2026-10-12-editor-modes-01-lock-and-operate.md](2026-10-12-editor-modes-01-lock-and-operate.md)
   - The `OPERATE` tier, the per-level lock, and the effective-tier cap.
   - Gate every mutation path, including the ~13 that bypass `Editor`.
   - Server-side checks at the value write paths.
   - User value edits mark the graph unsaved, through a reason that does not
     reassemble a running graph.
   - The `open_locked` default (`open_view` arrives with stage in slice 5), the
     level-bar lock toggle, `ToggleLock`, and `graph_editor_operate`.
2. **Enter and look inside:** [2026-10-13-editor-modes-02-enter-and-look-inside.md](2026-10-13-editor-modes-02-enter-and-look-inside.md)
   - "Enter" for placements, opening locked; the error-ledger reveal takes the
     same route.
   - Double-click a Graph-node card to enter. This is the VIEW path, since
     menus need effective EDIT.
   - An open placement level follows a `.hwm` reload.
3. **Edit Instance.** Detach-with-origin on unlock, and the three verbs.
4. **Position.** Single source, then the layout channel.
5. **Stage.** Fields, the `on_stage` skin keyword, on-stage wires, stage view, origin,
   gestures, Add/Remove, annotation exceptions, control nodes, `open_view`,
   the Patch | Stage switch, `ToggleStageView`. Split into four plans (Q1,
   2026-10-14), each merging into `feat/editor-modes-slice1` as it lands:
   - **5a Stage core:** [2026-10-14-editor-modes-05a-stage-core.md](2026-10-14-editor-modes-05a-stage-core.md).
     Fields, channel, stage view, origin, Add/Remove, `open_view`, the switch,
     `ToggleStageView`. Revised by [5a-2](2026-10-15-editor-modes-05a2-stage-is-a-display.md):
     the stage is a display, not a mode (Decisions 1 and 6, Q7a).
   - **5b Stage content:** on-stage connector editing, annotation text editing, Add Annotation.
   - **5c Stacking order:** `z`/`stage_z` and the four verbs.
   - **5d Control nodes.**
6. **Inset.** The skin, the two enablers, placement value overrides, and the
   shared edge-drawing module.

---

## Traps to carry into the slices

- **Interior changes restart a running graph.** `GraphNode._on_definition_validated`
  forwards every save-relevant interior change to the host as
  `GRAPH_REQUIRE_REASSEMBLY`, and `HaystackState` stops and restarts execution on
  that reason. A value change must travel under a reason that marks the host
  unsaved without reassembling (slice 1).
- **The same handler redraws the host card.** Once value changes are
  save-relevant, an Inset would rebuild on every slider move and destroy the
  slider mid-drag. The redraw must be limited to structure and layout changes
  (slices 1 and 6).
- **A disabled widget is not a guard.** `BaseWidget.set_enabled()` only changes
  how the widget looks. Every tier rule is enforced where the write lands (slice 1).
- **Detach re-keys the definition.** `DetachPlacementFromMacroAction` moves the
  interior from `macro_<id>` to a Group key, so an open level must follow it
  (slice 3).
- **The error-ledger reveal already opens interiors.** `_open_level_for_graph`
  walks `macro_*` definitions without checking `is_macro_placement`, so it may
  open a placement's interior as an editable level today. Found by reading the
  code, not verified (slice 2).
- **Position lives in two places until slice 4.** Writing `posX` through
  `set_property` or Farmhand does not update `_initial_position`, which wins on
  the next rebuild. **Resolved by slice 4:** props are the single source
  ([ADR 0053](../../adr/0053-position-lives-in-props.md)).
- **`canvas_width`/`canvas_height` are the patch's** (slice 5). Decide where the
  stage's extent lives before `move_node` runs with `STAGE`. **Resolved by slice
  5a:** one extent per channel, `BaseGraph.canvas_extent(channel)`, carried per
  channel name on `ValidationResult.canvas_sizes`
  ([ADR 0054](../../adr/0054-the-stage-view.md)).
- **Pins inside an Inset** must be measured with queries scoped to the Inset's
  box, never `document`-wide, and converted for the host canvas's zoom (slice 6;
  see `.insights/project_multi_canvas_dom_globals.md`).
- **Mod+E** focuses the address bar in Chrome on Windows and Linux. It is not a
  reserved key, so the keymap's `preventDefault` should take it. Check live.

---

## Glossary and ADR candidates

Glossary and ADRs land with the code (see `feedback_glossary_adr_after_landing`),
in the slice that builds each item.

**Glossary:** lock, patch view, stage view, open-in default, operate (tier),
effective tier, modified instance, origin, stage, on stage, stage rect, stage
origin, on-stage wire, Inset, control node, layout channel. Rename "Enter Group"
to **Enter**; replace "Promote to Macro" with **Save new Macro**.

**ADRs:**

- **Operate tier and the lock cap** (amends 0027): slice 1.
- **Instance edit by detach with origin** (amends 0038): slice 3.
- **Placement value overrides** (amends 0038): slice 6.
- **Stage: its own origin and the layout channel:** slice 5.
- **Dropping `"position"` from saved files:** slice 4.

**Docs corrections**, each in the slice that makes them true:

- `security.md:482` "Known gap" warning and ADR 0027's claim: slice 1.
- Widget value edits do not mark a graph unsaved: fixed in slice 1, nothing to
  document afterwards.
- Stale comments in `core/node/properties.py`: "fires on every drag tick" (drag
  updates are sent once, at drag end) and "not shown in settings panels" (the
  node properties panel renders every category): slice 4.
- The `SubgraphContainer` docstring example registers the container in
  `GraphAppState`, which `GraphEditor` never does: slice 2.

---

## Not in scope

- Presets or snapshots (a values-only save for operators).
- A Button control node (event-source design).
- Port-level stage items.
- Persisting lock and view per principal (blocked on
  `workspace_state.json` being per project).
- Per-port access tiers (escape hatch noted above).
- Inset offset and clipping.
- Agent tools for Edit Instance, Update Macro…, Save new Macro… and Revert to
  Macro (need a dry-run/confirm design).
- A fullscreen perform mode for a stage.
- Two views of one graph side by side in one session.
