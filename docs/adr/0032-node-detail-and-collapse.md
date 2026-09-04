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

## Superseded in part (2026-08-31): `muted` removed, `pinned` renamed `locked`

Decision 10 above kept two flags — "`muted` and `pinned` stay: they are state,
not density." That reasoning was right about the *category* and wrong about the
*fields*: being state is what spared them from this ADR's density cleanup, but
neither ever grew a reader, so both sat in the panel promising behaviour the
engine has not got.

- **`muted` is deleted.** It advertised execution skipping, which is a VM-level
  feature nobody has scoped. A checkbox that does nothing is worse than an
  absent one, so it goes rather than waits.
- **`pinned` becomes `locked`.** The old name and description scoped it to
  "prevent auto-layout from moving this node" — a layout pass that does not
  exist. `locked` is the promise actually wanted: protection from accidental
  drag, resize and delete.

`locked` is enforced **client-side**, in `canvas.vue`, off a `data-node-props-locked`
attribute. A server-side check was designed first and abandoned: the canvas
moves nodes in the browser during a drag and reports positions only at the end,
so the core could refuse to *persist* a move but not to *perform* one — the node
would slide under the cursor and snap back, which reads as a glitch rather than
a rule. With Farmhand tools deliberately exempt (an agent's call is always
deliberate), no caller was left for a core filter to catch.

Consequently `locked` is a **guardrail, not access control**: agents bypass it
and any user can untick it. It covers geometry and existence only — settings,
widgets and edges stay editable.

**Protection runs through the Selection axis** (the rule Miro uses): a locked
node is skipped by marquee-select and never joins a multi-selection in either
direction — neither shift-clicking one into a selection, nor adding anything to
a lone selected locked node. A node that cannot enter a selection cannot be
reached by a batch command, so drag, delete and fold are all protected by one
rule instead of a filter re-stated per verb. Selecting a locked node **alone**
stays possible and is the point: its properties panel is the only way to unlock
it, so a lock that could not be clicked would be a trap.

Two consequences worth naming. Locking applies to one node at a time, so a
selection is never *partly* locked and no mixed-state toggle has to be
designed — at the cost of no bulk unlock. And the per-verb filters that remain
(drag pickup, delete) are backstops for the lone-locked-node case rather than
the primary guard.

No migration either way: `Settings.from_dict` skips unknown value keys, so a
saved graph carrying `props.muted` or `props.pinned` drops the key silently and
`locked` starts at its default — the same mechanism decision 10's five retired
flags relied on.

## Superseded in part (2026-09-02): NodeDetail becomes a CSS filter, not a construction gate

Decision 3 above — "Both axes gate construction, not CSS... A CSS gate would
leave every element built, mounted and re-walked" — was right about **Node
collapse** and wrong about **NodeDetail**, for a reason ADR 0006 later
measured directly: NodeDetail's construction-gate cost was never the
mounted-element re-walk this decision worried about. It was the pan-time
paint/layout cost of what those elements render, and `display: none` removes
that cost identically to never building them — measured at 0.98x/1.02x of
constructed WIDGETS-equivalent (see `.scratch/pan-perf/RESULTS.md` and
`internals/handoff/node-detail-and-lod-classes.md`, decision A).

**What changed:**

- `NodeDetail` grew from 3 ranks (`COMPACT`/`STANDARD`/`FULL`) to 5
  (`PINS`/`PINS_ALL`/`WIDGETS`/`LABELS`/`FULL`) — a floor step for "unlinked
  pins" is now distinct from "linked pins only", where the old COMPACT
  conflated them.
- Every element a rank could exclude is now always built, and unconditionally
  carries its `.hw-detail-*` class — a plain string literal at each skin
  `_render_*` call site, matched by `[data-node-props-detail]` rules in
  `canvas.vue` — the SAME mechanism `locked` already used for its own
  attribute, and the same TECHNIQUE (attribute-selector + `display:none`) the
  zoom-driven LOD system uses, though the two remain conceptually separate
  (ADR 0006).
- `detail` left `NodeProperties.REDRAW_FIELDS`; `collapsed` did not. **Node
  collapse is unaffected by this supersession** — it stays a real
  construction gate, exactly as decision 3 originally specified, because
  nothing in the pan measurement touched it.

**Correction (2026-09-02, same day): `NodeVisibility` does not carry the
rank.** The first cut of this redesign gave `NodeVisibility` a `detail`
field and four rank-derived properties (`pins_all`/`widget`/`label`/
`diagnostics`) that a skin was meant to consult to decide which
`.hw-detail-*` class to add. In practice every skin call site ended up
writing the class **unconditionally** — there was no per-rank branching left
to do once "hide it" moved entirely into CSS — which left those four
properties, and the `detail` field itself, with no reader anywhere but their
own tests. `NodeVisibility` was cut back to just `collapsed: bool` and
`ports()`, the two things still genuinely construction-time decisions.
`UINode._apply_detail_attr` already read `props.detail` directly (not
through `NodeVisibility`) to stamp the DOM attribute, so nothing downstream
of the CSS rule needed the deleted properties either. A `BaseWidget.
_is_detail_hidden` model→view dispatch suppression was tried in the same
pass and dropped for the same reason plus its own: the settings-chain
resolution it required cost more per dispatched value change than the
traffic it saved, on the hot path rather than the render path.

**Breaking change, no migration.** Old saved-graph values `"compact"`/
`"standard"` are unrecognised strings under the new enum and degrade to
`FULL` via `NodeDetail.coerce()`'s existing (unchanged) fallback. No shim was
built — there is no external install base to protect at the time of this
change.

**Not reopened:** decision 1 (two axes, not one). Collapse and NodeDetail
remain independently composable exactly as originally decided; the 5-rank
ladder lives entirely inside the NodeDetail axis.

## Superseded in part (2026-09-04): `.hw-lod-hover` is gone, and with it the "peek gesture"

Decision 8 above closes with "now that selection is inert, `.hw-lod-hover` is
the only peek gesture in the app". That sentence was true when written and
stopped being true in `6d787d0e`, which removed LOD's `display:none`
zoom-crossing rules (recorded in ADR 0006's Superseded bullet). The class was
only ever a hook for the hover-persistence rules that re-admitted a hovered
card's hidden descendants; once nothing was hidden, nothing read the class.

`canvas.vue` kept writing it anyway — `classList.add` on `mouseenter`,
`classList.remove` on `mouseleave`, on the single hottest path the canvas has.
Both calls are removed. There is no peek gesture in the app now, because there
is nothing left to peek at: every rank's elements are painted at every zoom,
and `NodeDetail` decides what exists rather than what is revealed.

Found while attributing a pan-performance defect: hovering a card during a pan
costs ~7x the framerate on a 300-node graph, and the hover path was being
audited consumer by consumer (`.scratch/pan-perf/eventcensus.py`; the class
mutation itself measured free — it is removed as dead code, not as a fix).

**Still standing from decision 8:** LOD and `NodeDetail` remain different
concerns that nothing composes, and `data-lod-level` is still computed by
`pan.vue` as a deliberate dormant hook with the debug overlay as its only
reader.
