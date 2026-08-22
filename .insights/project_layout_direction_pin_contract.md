---
name: A pin's CSS side and its direction vector must come from one source
description: render_pin emits both a `{side}: -Npx` offset and data-pin-dir-x/y; before LayoutDirection these were computed independently in three places. A mismatch is invisible — pins sit on the right edge while their edges curve the wrong way.
type: project
---

# A pin's CSS side and its direction vector must come from one source

## The shape of the bug that isn't there any more

`render_pin` emits two things that describe the same physical fact:

1. a CSS offset, `f"{side}: -{offset_px}px"`, which decides which card edge the pin
   straddles;
2. `data-pin-dir-x` / `data-pin-dir-y`, the unit vector `canvas.vue` reads in
   `_getPinDirectionVector` to shape the bezier's control points.

Before `LayoutDirection` they were derived **independently**: `side` came from a caller
argument (`direction="left"`), the vector from `pin.is_inlet()`. With only left and right
in play they could not disagree, so nothing forced them together. Adding top and bottom
made them able to disagree — and the failure mode is silent. Pins render on exactly the
right edge; only the curves are wrong, which reads as a bezier tuning problem rather than
a data problem, in a different file and a different language from the actual cause.

There were **three** independent hardcoded copies of the `(-1,0)/(1,0)` pair:
`render_pin`, `NodeSkin._render_root_ghost_pins`, and the ghost-pin literals inline in the
default skin's header row.

The fix is structural, not vigilance: `LayoutDirection.side_for(port)` and
`.vector_for(port)` are the only places either value is produced, and `render_pin` calls
both. `tests/ui/skin/test_pin_render_layout.py::test_side_and_vector_never_disagree`
asserts the axis agreement for all four directions x both port directions, so a future
hand-rolled vector fails a test instead of shipping.

## Corollaries worth keeping in your head

- **Nothing may assume both ends of an edge share an axis.** Direction resolves per node
  (framework < graph < node), so a `t2b` node can legally feed an `l2r` one. `canvas.vue`
  already handles this correctly *because* each end uses its own vector — the projection
  in `_createBezierPath` (`dx*startDir[0] + dy*startDir[1]`) is per-end.
- **`_createBezierPath` used to measure control distance on X only**
  (`Math.abs(endPos.x - startPos.x)`). Vertically stacked nodes have `dx ≈ 0`, so every
  vertical edge collapsed to the 50px floor and rendered as a flat stub. The projection
  form reduces to `|dx|` exactly when `startDir` is `[1,0]`, so horizontal graphs are
  bit-identical — worth knowing before "simplifying" it back.
- **`card_padding` is axis-specific.** `render_pin`'s `offset_px = card_padding +
  gutter//2 + protrusion` assumes the padding on the axis the pin crosses. The caller
  picks it (`CARD_H_PADDING` vs `CARD_V_PADDING`) because only the caller knows which
  padding its card paints — and a vertical card must actually paint
  `padding-top`/`padding-bottom`, not merely read the setting.
- **Skins hold no per-node state.** `SkinFactory` caches one instance per registry key
  across every node in every open graph, so direction is resolved from the wrapper on each
  render and never stored on `self`.

## The edge cache assumed orientation was immutable

`_createEdge` captured each pin's direction vector once; `_updateEdge` refreshed position
and colour on every update but *not* the vector. Safe only while every node was L2R. After
a direction switch the curve still aimed the old way — visibly, an outlet's edge doubling
back into its own node. `_updateEdge` now re-reads both vectors from the live pins.

Separately, `_syncNodeRedraw` re-attached the hover observer and refit the resize gadget
but never redrew the node's edges, even though a redraw *replaces* the pin elements. Edges
kept describing dead DOM until something incidental (a hover, a drag) refreshed them. It
now calls `_scheduleEdgeUpdates`, whose immediate-plus-repeat-over-300ms shape also removes
any dependency on whether the new DOM has landed when the event arrives.

These two are jointly load-bearing: a corrected vector that is never repainted is
invisible. Verified by disabling each independently against
`tests/ui/harness/test_graph_layout_direction.py`.

Neither is really about LayoutDirection — any future change that re-renders a node with
differently-oriented pins would have hit both.

## `transform` is one property, so the pin rotation has to compose

Vertical layouts rotate the pin glyph. That rotation is published as
`--hw-pin-rotate: rotate(90deg)`, never as `transform` directly, because `canvas.vue`
scales pins in at least three states (`:hover`, drag anchor, `.connection-invalid`) and
each writes the whole `transform` property. A raw rotation is silently *replaced* by any
of them. Every such rule composes `var(--hw-pin-rotate, ) scale(...)`; the empty fallback
resolves to nothing horizontally. Add a new pin transform and you must compose it too.

Skin-authoring guidance (what a skin must do to cooperate — strip ordering by card edge,
ghost pins belonging in the strips) lives in `docs/components/skins/skin-canon.md`; this
file is about `render_pin` and the canvas edge cache.
