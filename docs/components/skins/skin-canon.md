---
status: placeholder
doc_template: canonical-example
scope: Authoring node skins (visual variants of a node's rendering)
see-also:
  - ../widgets/widget-canon.md
---

# Skin — Canonical Example

*This is a placeholder — the worked example below has not been written yet. One section
is filled in: [The card's class list is a contract](#the-cards-class-list-is-a-contract),
because omitting a class from it fails silently and has already cost real debugging time.*

**Template:** `canonical-example` — when filled in, this file will follow the four-part shape:

1. **What it solves.** Capability statement: "you can do X with this."
2. **How it fits.** Where this component sits in the system; what it depends on; what depends on it.
3. **Important concepts.** The named entities and rules an author needs in their head.
4. **One comprehensive example.** A single worked example exercising every concept above.

**Scope.** Authoring node skins (visual variants of a node's rendering).

## The card's class list is a contract

A skin's `render()` receives a `ui.card` and decides its classes. Some of the classes it
must apply are **not** styling choices — the canvas and pan layers key behaviour off them,
so a card that omits one loses that behaviour with no error, no console warning, and
usually no visible symptom until a user does something specific.

```python
main_card.classes("w-full min-w-64 max-w-sm node-card zoom-pan-lod0 my-skin-card")
```

| Class | Owner | What it buys | Symptom if omitted |
| --- | --- | --- | --- |
| `node-card` | `canvas.vue`, `pan.vue` | Manual-resize clamp release; `pointer-events` / `user-select` restored inside the pan container | Card stops growing partway through a resize drag; text selection and pointer behaviour fall back to the pan container's suppression |
| `zoom-pan-lod0` | `pan.vue` | Hover box-shadow, magnifier transform transition, and the hover tracking that drives `zoom-pan-lod1..3` reveal on descendants | No hover affordance; nested LOD elements may not reveal on hover |
| `drag-handle` | `canvas.vue` | Makes the element (or a child carrying it) the drag grip | Node cannot be dragged by that region |

### `node-card` is a literal token, not a prefix

CSS class selectors match **whole tokens**. `my-skin-card`, `math-node-card`, and
`error-node-card` do *not* match `.node-card` — they are sibling classes, not variants.
Name your skin's own class whatever you like, but apply `node-card` **alongside** it.

The rule that bites is the manual-resize clamp release in `canvas.vue`:

```css
--8<-- "packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:node-card-manual-resize"
```

Manual size axes are user **minimums** written onto the host slot; content needing more
space expands the node, and nothing clips. For the card to track the slot, the skin's own
clamps (`min-w-64 max-w-sm`) have to be released — which is what that rule does, and only
for elements carrying `node-card`.

So a skin without the class renders correctly at rest and **caps at `max-w-sm` (384px)
the moment someone drags the resize grip**, while the slot underneath keeps expanding.
Nothing reports it. If you are debugging "my node stops growing", check the class list
first.

> Related: a node's minimum size is not computed in Python at all — it is whatever CSS
> intrinsic sizing produces from the card subtree. Measuring it in `auto` mode measures
> the clamp rather than the content. See `.insights/feedback_css_containment_node_floor.md`.

### Do not style `.widget-container`

Inline-widget sizing is owned by the framework, not by the skin. `canvas.vue` declares:

```css
--8<-- "packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:widget-container-sizing"
```

A skin's own `max-height` / `overflow` rules on `.widget-container` are silently
outranked by those `!important` declarations. Per-widget ceilings are declared on the
widget instead, through `@widget(min_width=, min_height=, max_height=)`. See
[widget-canon.md](../widgets/widget-canon.md).

**Visibility is not decided here.** A widget that exists is visible; whether it exists is
decided in Python by the node's `NodeDetail` rank (see below). Until ADR 0032 this block
was a *reveal* — every node built its widgets and only the **selected** one showed them,
via `.node-selected` on the `[data-node-id]` container. If you find a skin or a doc still
describing that, it is stale.

## Respecting the node's detail and collapse

A card's density is not fixed either. Two axes decide how much of a node is drawn, both
resolved per node through the settings tier chain, exactly like `skin` and
`layout_direction`. See [ADR 0032](../../adr/0032-node-detail-and-collapse.md).

| | tiers | what it says |
| --- | --- | --- |
| **Node collapse** (`props.collapsed`) | graph < node | fold to title, badges and the pins of *linked* ports |
| **NodeDetail** (`props.detail`) | framework < graph < node | `COMPACT` (pins) < `STANDARD` (+ widgets) < `FULL` (+ labels, diagnostics detail) |

### Ask the resolver, never the rank

```python
def render(self, main_card: ui.card, wrapper: NodeWrapper):
    show = self.show_of(wrapper)          # NodeSkin helper

    for port in show.ports(node):
        ...
    if show.label:
        ui.label(port.label).classes("text-xs zoom-pan-lod2")
```

`show.label`, `show.widget` and `show.diagnostics` are **properties, not methods** —
`if show.label():` would be a bug you cannot see, since a bound method is always truthy.
`show.detail` and `show.collapsed` are there for anything the vocabulary does not cover.

The point of asking rather than comparing is that the rank→element mapping has one owner.
A skin that writes `if detail == NodeDetail.FULL` has copied policy that will drift the
next time a tier moves. Standalone skins (not subclassing `NodeSkin`) call
`resolve_node_visibility(wrapper)` from `haywire.ui.skin.visibility` directly.

### These are construction gates, not CSS

Do not build what the rank excludes. Hiding it instead defeats the entire purpose:
per [ADR 0006](../../adr/0006-node-render-performance.md) the cost driver is element
*count* — every element is built on the Python side and re-walked by NiceGUI on every
page update, whether or not it is painted. This is the one hard rule of the contract.

It is also what separates these axes from **LOD**, which is zoom-driven, lives entirely
in CSS, and decides only what is *painted* of what already exists. The two do not
compose and there is no arithmetic between them — keep tagging elements
`zoom-pan-lod1..3` as before.

### Ignoring it is safe, and measurable

Nothing enforces this. A skin that never calls `show_of` renders everything at every
rank: slower, never broken — the same posture `render_pin` takes for `LayoutDirection`.
The cost is that graph-level collapse silently does nothing for nodes using that skin, so
a user pulling the lever on a 300-node graph gets a partial result with no explanation.

Two skins ignore the axes **on purpose**: the error skin (a failed render must show its
failure at any density) and the reroute skin (already smaller than a folded card would
be). `tests/ui/skin/test_node_visibility.py` holds that exemption list; in-repo skins not
on it must consult the resolver.

## Respecting the node's layout direction

A node's flow direction is **not** fixed left-to-right. `LayoutDirection` resolves per
node through the framework < graph < node chain, exactly like `skin` does, and takes four
values: `l2r`, `r2l`, `t2b`, `b2t`. The execution engine imposes no directionality — this
is purely how a card is drawn.

### Resolve it per render, never store it

`SkinFactory` caches **one skin instance per registry key**, shared across every node in
every open graph. A skin therefore has no per-node state, and direction must be read off
the wrapper on each render:

```python
def render(self, main_card: ui.card, wrapper: NodeWrapper):
    layout = self.layout_of(wrapper)          # NodeSkin helper
    ...
```

Standalone skins (those not subclassing `NodeSkin`) call
`resolve_layout_direction(wrapper)` from `haywire.ui.skin.pin_render` directly — or
`resolve_graph_layout_direction(wrapper)` to follow the *graph* while ignoring a per-node
override, which is what `RerouteSkin` does: a dot on a wire should follow the wire.

Both resolvers degrade to `l2r` rather than raising. They run on the render path, so a
stale or unrecognised stored value must never take a card down.

### Pass it to `render_pin` — and let it derive both halves

```python
render_pin(port, node_id, layout=layout, pin_gutter=..., card_padding=..., pin_protrusion=...)
```

`render_pin` derives **both** the pin's CSS side and its `data-pin-dir-x/y` vector from
that one argument. Never compute them separately: the vector is what the edge layer reads
to shape its bezier, so a side/vector mismatch draws pins on the correct edge with edges
curving the wrong way, and nothing reports it. `layout` defaults to `l2r`, so a skin that
ignores it keeps the historical behaviour rather than breaking.

`card_padding` must be the padding on the axis **this pin crosses** — the caller picks it,
because only the caller knows which padding its card actually paints. `NodeSkin` exposes
`CARD_H_PADDING` and `CARD_V_PADDING` for the two axes.

> **Trap.** In a vertical layout the card must actually *paint* `padding-top`/
> `padding-bottom` matching what you hand to `render_pin`. Reading the setting without
> applying it seats every pin slightly off its edge — identically on every node, which
> reads as a design choice rather than a bug.

### Vertical layouts are a different layout, not a mirrored one

`r2l` is a true mirror of `l2r`: the same rows, pins on the opposite side. `t2b`/`b2t` are
not. Pins move to the card's top and bottom edges, where there is no room for a label or
an inline widget, so `NodeSkin.render_pin_strip()` lays out **bare pins** and inlet/outlet
values are reached through the properties editor instead. Consequences:

- Port labels and inline widgets do not render for inlets/outlets. The node's
  `NodeDetail` rank still governs config labels.
- Tooltips matter more here — a tooltip is the only thing identifying a pin. They are
  unconditional since ADR 0032, for exactly this reason.
- **Groups are skipped.** A collapsible hierarchy has no meaning in a flat strip, so group
  control ports and everything nested under one are left out of the strip entirely.
- Config ports are unaffected in every direction: they carry no pin, so they have no edge
  to move to and keep rendering in the card body.
- The card's `min-w-64 max-w-sm` clamps size a label+widget content column that a vertical
  card does not have — drop them on that branch.

**A multi-column skin's columns follow the flow direction.** If your skin lays ports out in
side-by-side columns rather than one stack, the inlet column belongs on whichever side
inlets' pins protrude from — so under `r2l` the columns swap along with the pins. Flipping
only the pins strands each pin on the far side of its own label, and edges arriving from
one side cross back over the whole card to reach the column their labels live in. Derive it
from `layout.inlet_side` rather than hardcoding an order.

**Order the strips by edge, not by direction.** Whichever port direction belongs on the
card's *top* edge must be rendered first. Under `t2b` that is the inlets; under `b2t` it is
the outlets. A strip placed at the top of the card while its pins are sided `bottom`
offsets them *downward* — i.e. inward, and the pins render inside the card. Drive it off
`layout.inlet_side == "top"` rather than hardcoding a direction.

**Ghost pins belong in the strips.** The root ghost pins are inline flex items, so their
offset is relative to wherever they sit in the flow. Left in a mid-card header row, a
`top: -16px` moves a ghost 16px further *into* the card instead of out to an edge. In
vertical layouts render each one into the matching edge strip — that strip *is* the card
edge — and give it the same offset a real pin gets (`CARD_V_PADDING + PIN_GUTTER // 2 +
PIN_PROTRUSION`), since the strip's height comes from the real pins, not from the ghost's
smaller box.

**A pin strip must take no part in the card's layout.** Its pins are pushed outside the
border by `position: relative`, which leaves them *in flow* — so an in-flow strip reserves
a whole pin row of empty space inside the card, showing up as a gap between the border and
the node title. Collapsing that with a negative margin is not enough: the strip is still a
flex item, so the card's `row-gap` keeps allocating a slot beside it. `render_pin_strip`
positions the strip **absolutely** against the card's padding box, which removes it from
flex layout entirely while leaving every pin's static position — and therefore
`render_pin`'s offset — unchanged. Style the card through `NodeSkin.vertical_card_style()`
so it is a containing block and paints the block padding the offsets are measured against.

Icons need no work: the built-in `CONTROL`/`CALLBACK` glyphs and every library author's
per-type `icon_in`/`icon_out` are drawn pointing left/right, and `render_pin` rotates the
pin element 90° in vertical layouts rather than requiring a second axis of icon constants.
Rotation is about the centre, so `getBoundingClientRect()` — which the edge layer reads —
is unchanged.

> **The rotation is a custom property, not a `transform`.** `render_pin` emits
> `--hw-pin-rotate: rotate(90deg)`, and every rule that scales a pin composes it:
> `transform: var(--hw-pin-rotate, ) scale(1.4)`. `transform` is a single property, so a
> rule writing a bare `scale()` *replaces* the rotation rather than adding to it — which
> is what made vertical pins snap back to horizontal while hovered, dragged, or marked as
> an invalid target. If you add a new pin transform anywhere, compose the variable. The
> empty fallback (`var(--hw-pin-rotate, )`) resolves to nothing in horizontal layouts.

### One graph can mix directions

Because direction resolves per node, a `t2b` node can sit beside an `l2r` one and be wired
together. Nothing may assume both ends of an edge share an axis; each end contributes its
own vector. This is also why `NodeSkinSettings` declares geometry for *both* axes
(`card_padding`/`card_padding_block`, `pin_row_height`/`pin_column_width`) rather than one
reinterpreted set — that bag is library-global, so there is no single "current direction"
to reinterpret against.

## Context menus: `data-hw-menu-surface-id`, and what a skin cannot address

A skin can add its own right-click menu on any element it renders, by writing one DOM
attribute:

```text
data-hw-menu-surface-id="<your-surface-id>"
```

The canvas detects this declaratively (`closest('[data-hw-menu-surface-id]')`, so the
*innermost* annotated ancestor wins if you nest them) and fires a `ContextMenuSurfaceEvent`
carrying the id. Whatever `Surface` your library registered under that id — with panels
registered against it — opens as the menu. **The surface is entirely your library's to
declare and own; the framework does not pre-create anything for an id it hasn't seen.** An
id that resolves to nothing (no registered `Surface` with that `id`) opens nothing at all,
silently, and logs a warning server-side — there is no error rendered on the canvas, so if
your menu never appears, check the server log for "no menu opened" before suspecting the
DOM attribute.

**This is the only menu a skin controls.** The pin, node, edge, and canvas (right-click on
empty space) menus are **structural or framework-declared**, not reachable through this
attribute:

- **Pin menu** — detected structurally from `data-pin-id`, which `render_pin` emits on
  every pin from every skin. A skin therefore neither opts a pin into having a menu nor can
  suppress the built-in one; that stopped being a skin decision entirely (see ADR-0029,
  "Routing"). Writing `data-hw-menu-surface-id` on a pin element has no effect — the
  structural pin check runs first and wins.
- **Node, edge, canvas menus** — all framework-declared `Surface`s (`NodeInspector`'s
  sibling menus, `EdgeMenu`, `GraphContext`), reached by their own structural/declarative
  paths independent of this attribute.

Use `data-hw-menu-surface-id` for a menu on some *other* element your skin renders — a
custom badge, an inline control, a region of the card that isn't the node or a pin — that
you want right-clickable with commands only your library knows about.

### Ghost pins are excluded from pin detection

The structural pin detector is `[data-pin-id]:not([data-pin-flow-type="ghost"]), [data-port-id]`
— note the exclusion. A ghost pin is a drop affordance (the temporary target shown while
dragging a connection to an empty area of a node), not a real port: its id names no entry in
`node.ports`, so a menu opened there would both resolve nothing *and* swallow the click that
would otherwise fall through to the node's own context menu. If you author a skin that emits
ghost pins with `data-pin-flow-type="ghost"` (the convention `render_pin` itself follows),
right-clicking one correctly falls through past the pin check to whatever is next —
normally the node. Do not expect a ghost pin to carry a menu; it is deliberately excluded,
not an oversight to work around.

## TODO

- [ ] Write content
- [ ] Document `@skin(hidden=True)` — registers a skin normally but excludes it from the skin picker (used by the error/fallback skin, which sets `_is_error=True, hidden=True`). See glossary term **Hidden component**.
- [ ] Verify against codebase
- [ ] Archive source files
