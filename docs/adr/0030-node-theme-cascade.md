---
name: node-theme-cascade
description: Node styling travels as a CSS custom-property cascade across four tiers, so a skin consumes vars and never reads a theme, a graph, or a node in Python
status: accepted
level: architectural
---

# Node styling is a CSS cascade, not a Python merge

A node card's look is decided by CSS custom properties, layered by the
browser across four tiers:

```text
:root            WorkbenchTheme                    every token
:root            global NodeTheme                  node tokens, clear-then-set
.graph-canvas    graph's  props.node_theme         only if ≠ global
.ui-node-slot    node's   props.node_theme         only if ≠ graph
.ui-node-slot    node's   props.color_override     --hw-node-bg, composed last
```

A skin emits `background: var(--hw-node-bg)` once, at render time, and never
branches. It does not know what theme is active, whether the graph overrode it,
or whether this node carries a colour. When a tier's declarations change the
browser re-resolves the `var()`; nothing re-renders.

`NodeTheme` is the **node-scoped subset** of the workbench token vocabulary,
sharing one `_CSS_TOKEN_MAP` so it cannot name a token the workbench lacks.
Reading a theme in Python is not merely discouraged — `get_color()` was deleted,
leaving `to_css_vars()` as the only accessor.

## Why

Four per-node appearance props had landed (`body_fill`, `border_color`,
`border_thickness`, `border_roundness`) with a `card_style()` helper that merged
them over each skin's declared defaults. It worked, and the cost was visible in
every direction:

- **The props needed non-`None` defaults** to survive the widget layer, so their
  value could no longer answer "did the user set this?" — `is_locally_set` had
  to. Overriding became a question about the settings layer rather than about
  the value.
- **`body_fill` needed a `FILL` type** to express gradients, which needed
  `to_dict`/`from_dict` on `NodeProperties` and a two-hop rename migration.
- **Every edit redrew the card**, because the props sat in `REDRAW_FIELDS`.
  That destroyed the input being typed into, which produced a further fix
  (`is_visual_only()`) one layer downstream.
- **A skin's own look became unreachable** to any future theme, since
  `card_style()` merged props over skin literals with no tier in between.

Meanwhile `NodeTheme` had existed for a long time — registered, selectable in
settings, documented as *"read by the canvas-side node renderer"* — and was
entirely inert. `get_color()` had no caller outside its own tests. The shipped
skin read `var(--hw-node-bg)`, a **WorkbenchTheme** token, and hardcoded its
border. A user picking a node theme changed nothing on screen.

Both problems have one cause: **node appearance was being assembled in Python**
when CSS already provides assembly. Custom properties inherit and cascade; that
is precisely the "several tiers, most specific wins" semantics the props were
reimplementing by hand, minus the redraws.

## Consequences

**A colour change is a style-write, not a redraw.** `color_override` and
`node_theme` are deliberately outside `REDRAW_FIELDS`; they compose into the
same authoritative `replace=` write on `.ui-node-slot` that already carried
per-node size. The focus-loss problem dissolves at its root rather than being
patched downstream.

**Unset means inherit, with no set-or-unset question.** `color_override`
defaults to `None`; emptiness contributes no declaration, so the tier above
shows through. No `is_locally_set` anywhere in the chain.

**A tier writes nothing unless it diverges**, decided by comparing resolved
values against the parent tier rather than by asking whether a field was locally
set. Identical values produce identical CSS, so writing them is waste however it
arose — on a 200-node graph, one declaration set instead of two hundred.

**Tier 2 is asymmetric, and this is load-bearing.** `node_selected`,
`node_active`, and `node_shadow` are consumed by `canvas.vue` on
`[data-node-id]`, an *ancestor* of `.ui-node-slot`. Custom properties inherit
downward only, so the global and graph tiers can restyle a selection ring and
the node tier cannot. `NODE_TIER_TOKENS` lists only what a node tier can
actually reach, so the API does not promise an override that silently fails.

**Skins declare their own look as a `var()` fallback**, not as a direct
property: `var(--hw-node-bg, <the skin's gradient>)`. Defining the var *on the
card* would shadow the slot above it and make the skin permanently
un-overridable — the fallback form reads the inherited value and supplies its
own only when no tier has spoken.

**Every consumer must use `background`, never `background-color`.** A token may
hold a gradient, which is an `<image>`; a `background-color` declaration
carrying one is invalid and is dropped silently, taking the card's colour with
it.

**`FILL` moved to `haybale-example`** with a demo node. It remains a good worked
example of a compound type with a custom widget, but a registered-and-inert
core component is the exact pattern this ADR exists to remove.

## Alternatives considered

**Keep `card_style()`, feed it a theme object.** Would have made `NodeTheme`
live with a much smaller diff. Rejected: it keeps appearance assembly in Python,
so every override still costs a redraw, and a skin still cannot be overridden
without cooperating explicitly.

**Give `NodeTheme` its own token map.** Would have preserved the existing field
names (`body_bg`, `border`) with no rename churn. Rejected: two maps can drift
on a var name, and the failure is silent — a node theme that overrides nothing.
Sharing one map makes "subset" structural rather than conventional.

**Write per-node vars via a JS bridge to `[data-node-id]`,** making all ten
tokens per-node overridable. Rejected: it buys uniformity with a JS write path
for three tokens whose per-node meaning is dubious — a per-node selection colour
is a strange thing to want — and `.ui-node-slot` is already the element that
owns per-node size.

**Emit the theme into a stylesheet rule per node** instead of an inline style.
Rejected: rules must be tracked and removed when a node is deleted, and NiceGUI
head-HTML injection is append-mostly. An inline style needs no cleanup — the
element carrying it is the thing being deleted.
