---
name: node-detail-and-collapse
description: Scattered per-node display flags collapse into two inherited axes — a boolean Node collapse (graph < node) and an ordinal NodeDetail (framework < graph < node) — both construction gates resolved through one skin-facing visibility object; selection stops changing how a node renders, and zoom-driven LOD is left untouched as a separate paint-only concern
status: accepted
level: architectural
---

# Node collapse and NodeDetail: two inherited axes, resolved once, gating construction

A node card's appearance was governed by an accumulation of unrelated booleans:
`collapsed`, `condensed`, `show_comment` on `NodeProperties`, `show_labels` and
`show_tooltips` on `NodeSkinSettings`, and — invisibly — the selection state,
which was the *only* thing that ever revealed a node's inline widgets. Four of
those flags were read by no skin at all. None of them were inheritable, so there
was no way to say "this graph draws lean" or to make a 300-node graph cheap in
one gesture.

This ADR replaces all of them with two axes that resolve through the settings
tier chain the way `skin`, `layout_direction` and `node_theme` already do.

## Decision

**1. Two axes, not one.**

| | tiers | type | default |
|---|---|---|---|
| **Node collapse** | graph < node | `bool` | `False` |
| **NodeDetail** | framework < graph < node | StrEnum | `FULL` |

Collapse is a response to *this graph* being large; detail is a legibility
preference. Folding them into a single ordinal forced "the graph's default
detail is COLLAPSED" to be a meaningful setting, and made a per-node fold
compete with an inherited density preference. They are different verbs.

**2. The ranks.**

- **COLLAPSED** — card, title, badges, pins of linked ports, root ghost pins
- **COMPACT** — + all pins
- **STANDARD** — + inline widgets
- **FULL** — + port labels, and the inline "alternate versions" diagnostics notice

Uncollapsed content is COLLAPSED's content plus the detail rank's. Labels sit
*above* widgets because identification is already carried by the pin and
config-row tooltips, and 20 labels on a 20-port node is the larger element cost.

**3. Both axes gate construction, not CSS.**

Omitted elements are never built; both fields join `REDRAW_FIELDS`. Hiding with
CSS was the initial design and is wrong for the stated goal: per ADR 0006, *"LOD
class tuning changes paint cost only, not element count"*, and element count is
what drives graph-open time and NiceGUI's whole-page render walk. A CSS gate
would leave every element built, mounted and re-walked.

**4. Selection does not change how a node renders.**

Previously it was the sole reveal for inline widgets. It now surfaces the
*controls* instead — a `SelectionToolbar` panel carrying a collapse toggle and a
detail selector. The property this buys: you can tune a density axis without the
act of selecting the node changing what you are looking at.

**5. `NodeDetail` is a StrEnum, twinning `AccessTier`.**

`rank` property, `includes()` predicate, `coerce` that degrades to the default
rather than raising on the render path. Not an `IntEnum` — for the reason
`AccessTier` records: wire values stay strings, so adding a rank later renumbers
nothing in saved graphs. A density scale is exactly the kind that gains a member.

**6. Skins resolve both axes through one visibility object.**

```python
show = self.show_of(wrapper)
for port in show.ports(node):
    ...
if show.label:
    ui.label(port.label).classes("text-xs zoom-pan-lod2")
```

Intent-named **properties**, never methods — `if show.label:` on a method is
silently always true. `show.ports(node)` is a filter rather than a boolean
because "which ports get a pin" is where Node collapse, Group collapse and link
state meet, and that three-way composition must have one owner. `show.detail`
and `show.collapsed` remain exposed as the escape hatch for a skin drawing
something this vocabulary never anticipated.

The mapping from rank to element lives only in the resolver. Skins never compare
ranks, so re-tiering later is a one-line framework change.

**7. Skins honour the axes; the framework does not enforce them.**

There is no framework-owned collapsed skin substituting for the node's own. A
skin that ignores the axes renders everything: slower, never broken — the same
"make ignoring it safe" posture `render_pin` takes for `LayoutDirection`.
Backed by a source-inspection test over in-repo skins (the pattern from
`test_node_skin_settings.py`) and a contract section in skin-canon. The error
skin and the reroute skin both ignore the axes deliberately: a failed render
must show its failure, and a reroute dot is already smaller than a collapsed
card.

**8. LOD is untouched, and is a different concern.**

`NodeDetail` decides what **exists**; LOD decides what is **painted** of it, by
zoom, in CSS, per frame. Nothing composes them — no rank arithmetic, no `min()`.
LOD keeps a measured ~2× pan win on dense graphs and, now that selection is
inert, `.hw-lod-hover` is the only peek gesture in the app.

**9. Scope: the canvas card only.**

The Ports panel, properties editor, node inspector and Farmhand tools ignore
both axes. The properties editor is what makes lowering detail *safe* — it is
already the designated way to reach inlet/outlet values a card cannot show.
Lowering detail changes how a node looks; it never changes what is reachable.

**10. Five flags retire.**

`condensed`, `show_comment`, `show_labels`, `show_tooltips` are deleted;
`collapsed` is finally read. The first three were declared-but-unread, and
`Settings.from_dict` skips unknown value keys, so no saved graph needs
migration. `show_tooltips` goes because lazy tooltips already removed its
performance rationale and, with labels at FULL, a tooltip is now the only thing
identifying a port at COMPACT and STANDARD — a toggle that can render an
unreadable node has become load-bearing. `muted` and `pinned` stay: they are
state, not density.

A comment now surfaces as a badge beside the diagnostics badge whenever the text
is non-empty, at the COLLAPSED tier, with the text on hover — so an annotation
stays reachable on a folded node, which is when you most want it.

**What `show.diagnostics` actually gates**, narrower than "diagnostics detail"
suggests: the inline *alternate-versions* notice, and nothing else. The badge
and its click-through menu draw at every rank, folded included — hiding an error
indicator at low density is the silent-failure pattern, and a badge that opens
nothing is a broken affordance. The menu body only costs elements on nodes that
have diagnostics at all, which is near zero on the large graphs this exists for.

## Considered and declined

- **One ordinal with COLLAPSED as rank 0.** See decision 1.
- **A CSS gate (`data-hw-detail` + LOD-style selectors).** Elegant, zero skin
  changes, third-party skins get it free — and it delivers none of the
  element-count win the feature exists for. Declined on ADR 0006's measurement.
- **Selection as a `+1` rank bump.** Reproduced today's behaviour exactly at
  `detail=COMPACT` and gave every rank selection feedback. Declined because it
  makes the axis impossible to tune: selecting the node to change its density
  changes its density.
- **A framework-owned collapsed skin** substituted the way the error skin is.
  Would have made the element floor a guarantee rather than a per-skin promise.
  Declined in favour of skins keeping their identity when folded; the cost is
  that graph-level collapse is only as good as the skins in play.
- **`IntEnum` for the rank.** Better comparison ergonomics, but stores integers
  in graph JSON and fights CHOICES being a STRING subtype.
- **Labels below widgets** (`STANDARD` = widgets + labels). Declined: pin and
  config-row tooltips already carry identification, and labels are the cheaper
  half of the pair, so cheap-first makes both steps of the ladder meaningful.
- **A framework tier for collapse.** Symmetric with the other tiered props, and
  a persisted studio setting that opens every graph showing nothing. The graph
  tier already persists the answer where it belongs — in the file.
- **Panels following detail.** Would turn a display preference into a capability
  loss.

## Consequences

- **No default reproduces today's appearance.** Today is a hybrid — labels
  always, widgets only when selected — and selection is now inert. `FULL`
  defaults toward legibility, so cards get taller on open because widgets are
  revealed on every node rather than one.
- **The widget reveal CSS is re-scoped, not deleted.** The `opacity: 0` /
  `max-height: 0` default and the four `.node-selected` max-height rules in
  `canvas.vue` become unconditional; the `contain` rules are untouched. Those
  four carry the `@widget(min_width=, min_height=, max_height=)` declared-size
  contract, so each rule's value must survive verbatim. The reveal transition
  cannot fire under a construction gate anyway — a rank change remounts the
  element, and CSS transitions do not run on initial render.
- **Graph-level collapse skips nodes the user has touched.** Graph mirrors are
  "unset tracks, set ignores" per hop. A "Clear node overrides" command
  (`props.reset("collapsed")`) restores the tier's authority.
- **Third-party skins silently opt out.** Accepted under decision 7; the failure
  is degraded performance, never a broken card.

## Vocabulary corrected en route

`glossary.md` defined **Ghost pin** as the indicator on an *unconnected* port.
It is neither: `--hw-ghost-pin` colours only the always-present `root_in` /
`root_out` drop anchors, whose ids name no entry in `node.ports` — which is why
the canvas excludes them from structural pin detection. A port hidden by a
collapsed group renders an ordinary pin. Corrected, along with new entries for
**Node collapse**, **Group collapse**, **NodeDetail**, **Node visibility** and
**LOD** — the last three of which exist to stop "detail" and "LOD" being used
for each other.
