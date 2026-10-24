---
name: level-mode-press-filter
description: Handoff — replace the canvas's pointer-events level-mode gate with one capture-phase press filter, so hover (tooltips, cursors) works in every mode and only presses are gated; removes three of the gate's five traps and fixes follow-up #5 part 1 without a new marker
metadata:
  type: project
  status: superseded
---

# Handoff — A press filter in place of the pointer-events gate

**Status:** superseded by the browser access layer (ADR 0060); kept as history. Was: not started. Analysis agreed with the user on 2026-10-23; needs a design round and
an update to ADR 0055's "browser layer" paragraph before code. No branch.

**Raised during:** follow-up #5 part 1 of `docs/superpowers/plans/2026-10-22-open-follow-ups.md`
(tooltips with a separate trigger do not respond in level mode `view`). Option (a) there, a
third marker `data-hw-hover-only` plus a JS press block, was **not** built: it would add a second
mechanism beside the gate that does the same job.

## The assessment

**The model side is sound and central (ADR 0055).** Every user edit goes through one `EditRoute`;
the mode comes from one function (`level_mode`, `haybale_graph_editor/access.py`: tier × lock ×
level); `operable=False` is enforced at the route; a widget without a route is read-only (fails
closed); Farmhand builds the same route. Surface visibility (`required_access`, panel and menu
polls) reads the same route. This is not the problem.

**The browser layer is where the tangle is.** ADR 0055 calls it "a second layer against
accidents, not access control". It consists of:

- The CSS gate, `ui/components/graph/canvas.vue:4509-4517` (line refs 2026-10-23): negative
  selectors per mode (`*:not([data-hw-readable]):not([data-hw-readable] *)…`), `!important` to
  beat `.connection-pin`'s own `pointer-events: all !important`, and a `:where()` rule giving
  exempt roots their `pointer-events` back (the property inherits).
- A second gate of the same kind for the Inset body, `canvas.vue:4523-4527`.
- `keepsPress` exceptions in `handleMouseDown`, `canvas.vue:~1797`, and the refusal in
  `_enterActiveEdge` (`~2877`).
- Cursor overrides below edit, `canvas.vue:4519` (pins) and `:4531-4534` (cards).
- Two markers stamped in three places: `data-hw-readable` (`add_pin_tooltip` in
  `ui/skin/pin_render.py`, the studio skin's diagnostics and comment badges in
  `haybale_graph_editor/skins/node_skin.py:821,856`), `data-hw-operable`
  (`BaseSkin.render_widget` / `render_setting_widget`).
- `.insights/project_level_mode_pointer_gate.md` needs **five traps** to explain it.

**Root cause:** `pointer-events: none` conflates **hover** (harmless: tooltips, cursor) with
**press** (can write). To stop presses the gate also kills hover; #5 part 1 is the direct
result: a config widget's and a fold triangle's tooltip cannot show in `view`, and marking the
trigger `data-hw-readable` would let a click through (the fold header toggles: a write).

**Why the gate is CSS:** cost. A lock toggle is one attribute flip on the canvas root, whatever
the graph size. Letting every widget render its read-only state from its route (Quasar
`readonly`/`disable`) would need a message per widget on every mode change; with the Vue
full-tree render walk on large graphs (`.insights/project_nicegui_component_vs_native_tag.md`)
that is too expensive. Any replacement must keep the O(1) mode change.

## The proposal

Below `edit`, card content keeps `pointer-events` (hover, tooltips, cursors work everywhere).
**One** capture-phase listener on the canvas root decides each press:

```js
// Below edit a press inside a card reaches only what the mode allows; hover is never gated.
_filterPress(e) {
    if (this.editing) return;
    const target = e.target instanceof Element ? e.target : null;
    if (!target || !target.closest('.ui-node-slot')) return;
    if (target.closest('[data-hw-readable]')) return;
    if (this.levelMode === 'operate' && target.closest('[data-hw-operable]')) return;
    e.preventDefault();      // also keeps focus out
    e.stopPropagation();     // capture phase: never reaches the target or its handlers
},
// mounted: for each press type, this.$el.addEventListener(type, this._filterPress, true)
```

- The canvas's own handlers on the root still run (`stopPropagation` does not stop listeners on
  the same element), so selecting by click, Shift-click and box keeps working in every mode.
- `keepsPress` in `handleMouseDown` folds into the same decision; one place says what a press
  may reach.
- The Inset body's rule ("only its operable widgets take input; any other press lands on the
  host card") likely becomes a case of the same filter.
- A cursor rule (`cursor: default` on gated card content below edit) keeps the look honest; the
  existing pin and card cursor rules are special cases of it.
- The markers stay as they are; their meaning becomes "may take presses" instead of "may take
  pointer input".

**What goes away:** #5 part 1 (no new marker); trap 2 (the `!important` fight with
`.connection-pin`); trap 3 (inheritance and the `:where()` re-enable); likely the separate
Inset gate. **What stays:** trap 1 in a new form (key on `.ui-node-slot` content so the card
root keeps its double-click Enter), trap 4 (keyboard focus is not stopped; the route is the
refusal), trap 5 (the manager pushes the mode at construction; `view` default fails closed).

## Risks and open questions

1. **Press-type coverage.** Every event a widget starts an interaction from must be filtered:
   `pointerdown`, `mousedown`, `touchstart`, `click`, `dblclick`, at least. `number/drag.vue`
   uses `@mousedown.prevent` (lines 17, 30, 59) and then document-level `mousemove`/`mouseup`;
   Quasar controls (`q-slider`, `q-knob`) use touch-pan directives. Check `wheel` (does any
   widget change a value on wheel?) and `contextmenu` (the canvas's own context menu must keep
   working). A missed type lets a gesture start in `view`: the route still refuses the write,
   and the widget shows its value move and snap back.
2. **Hover styling on gated widgets.** A button's hover highlight would show in `view`,
   suggesting interactivity. Decide whether the cursor rule is enough or hover styles need
   neutralizing.
3. **Order with other capture listeners.** `KeymapListener` uses document-level capture
   `pointerdown` to track the active slot and target editor; it must still see presses that the
   filter swallows (it listens on `document`, which is earlier in the capture path than the
   canvas root, so it should). Verify.
4. **ADR 0055** "The browser layer" paragraph and the glossary entries for the markers change
   with this.

## Tests

`tests/ui/harness/test_level_mode_gate.py` (30 tests, `/graph-level-mode` harness) is the safety
net. Tests that probe `document.elementFromPoint(...)` for "takes no pointer input" change to
"a press there changes nothing" (no toggle, no focus, no value change). New:

- `view`: hovering a config widget and a fold triangle shows the tooltip.
- `view`: clicking the fold triangle does not toggle (`data-hw-fold-open` unchanged); dragging
  a number widget does not change its value.
- `operate`: the same presses work.
- `view`: a click on card content still selects the card.

Other suites touching the gate or `elementFromPoint`: `test_inset.py`, `test_stacking.py`,
`test_graph_swinglet_connect.py`, `test_edge_appearance.py`, `test_edge_drag_cost.py`.

## Related

- Backlog #5 part 1 waits for this; part 2 (pin cursor) landed as `2835eacd`.
- `.insights/project_level_mode_pointer_gate.md`: rewrite with the new mechanism.
- `docs/components/skins/skin-canon.md` § "Pointer input below level mode `edit`".
