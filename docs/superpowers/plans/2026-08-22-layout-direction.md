---
title: "LayoutDirection — framework/graph/node flow orientation"
status: ready
created: 2026-08-22
depends_on: none
---

# LayoutDirection

Node cards currently hardwire left-to-right flow: inlets render on the left edge,
outlets on the right. Nothing in the execution engine requires that. This plan adds
`LayoutDirection` — a four-way orientation (`L2R`, `R2L`, `T2B`, `B2T`) resolved through
the **framework < graph < node** chain that already carries `skin`, and read by the
default skin at render time.

Horizontal directions (`L2R`/`R2L`) are a mirror of today's layout. Vertical directions
(`T2B`/`B2T`) are a *different* layout: inlets and outlets become bare pin strips on the
card's top/bottom edges with no labels and no widgets; only CONFIG ports render in the
card body. Inlet/outlet values stay reachable through the properties editor.

## Settled decisions

| # | Decision |
|---|---|
| 1 | Name is `LayoutDirection` — not `FlowDirection`, which would read as a property of the existing `FlowType` (control/data/callback). |
| 2 | Vertical mode **skips groups**: no collapsible group rendering in a pin strip. |
| 3 | `RerouteSkin` follows the **graph's** `LayoutDirection`, not a per-node override. |
| 4 | The framework-tier field is a **new field on the existing `NodeDefaultSkinSettings`** (namespace `ui.node.default.skin`), not a new settings class. |
| 5 | Ghost pins move to the **top/bottom edges of the header row** in vertical mode. |

## Invariants this plan establishes

- **A pin's CSS side and its direction vector derive from one source.** Today
  [pin_render.py:92-114](../../../packages/haywire-core/src/haywire/ui/skin/pin_render.py#L92-L114)
  computes `direction` (a CSS property name) from the caller and `dir_x/dir_y` from
  `pin.is_inlet()`, independently. They cannot disagree today; with four sides they can,
  and the failure is silent — pins draw on the correct edge with edges curving the wrong
  way. One derivation, both consumers.
- **Nothing in the edge layer may assume both ends share an axis.** `LayoutDirection`
  resolves per node, so a `T2B` node feeding an `L2R` node is legal by construction and
  must render correctly.
- **Skins hold no per-node render state.** `SkinFactory` caches one instance per registry
  key across every node in every open graph
  ([factory.py:182-186](../../../packages/haywire-core/src/haywire/ui/skin/factory.py#L182-L186)).
  Direction is read from the wrapper on each render — never stored on the skin, the way
  `self._ui_settings` is.
- **A card-level skin's root element must carry the literal class `node-card`** (and
  `zoom-pan-lod0`). Behavioural contract, not a style hook, and it fails silently — a skin
  naming its class `math-node-card` or `error-node-card` does not match, because CSS class
  selectors match whole tokens. Canonical write-up now lives in
  [`docs/components/skins/skin-canon.md`](../../components/skins/skin-canon.md#the-cards-class-list-is-a-contract);
  every phase below that touches a card's class list must preserve the token. Verified
  against `ExampleNodeSkin` on 2026-08-22; `ErrorNodeSkin` is still affected — see
  [Follow-up A](#follow-up-a--errornodeskin-defects--landed).

---

## Phase 0 — Baseline

Per CLAUDE.md, this is a multi-file change touching the type system and a settings
hierarchy. Establish the baseline before editing:

```sh
uv run ruff check packages/haywire-core/src/haywire/core/types/ \
  packages/haywire-core/src/haywire/core/skin/ \
  packages/haywire-core/src/haywire/core/graph/ \
  packages/haywire-core/src/haywire/core/node/ \
  packages/haywire-core/src/haywire/ui/skin/ \
  barn/haybale-studio/haybale_studio/ \
  barn/haybale-example/haybale_example/
uv run mypy packages/haywire-core/src/ barn/haybale-studio/haybale_studio/ \
  barn/haybale-example/haybale_example/
```

Expect clean. Anything new after the edits is ours.

---

## Phase 1 — Vocabulary

**File:** [`packages/haywire-core/src/haywire/core/types/enums.py`](../../../packages/haywire-core/src/haywire/core/types/enums.py)

Add `LayoutDirection` alongside `PortType` / `FlowType`, string-valued so it serializes
and reaches the DOM unchanged:

```python
class LayoutDirection(Enum):
    """Orientation of flow across a node card. Purely presentational — the
    execution engine imposes no directionality."""

    LEFT_TO_RIGHT = "l2r"
    RIGHT_TO_LEFT = "r2l"
    TOP_TO_BOTTOM = "t2b"
    BOTTOM_TO_TOP = "b2t"
```

Derived helpers on the enum — these are the single source the invariant above demands:

- `is_vertical -> bool`
- `inlet_side -> str` / `outlet_side -> str`, returning `"left" | "right" | "top" | "bottom"`
  (also valid CSS property names, which is what `render_pin` consumes)
- `inlet_vector -> tuple[int, int]` / `outlet_vector -> tuple[int, int]`, the
  `(dir_x, dir_y)` pair the Vue bezier layer reads
- `side_for(port)` / `vector_for(port)` convenience, keyed off `port.is_inlet()`

Mapping:

| Direction | inlet side / vector | outlet side / vector |
|---|---|---|
| `L2R` | `left` / `(-1, 0)` | `right` / `(1, 0)` |
| `R2L` | `right` / `(1, 0)` | `left` / `(-1, 0)` |
| `T2B` | `top` / `(0, -1)` | `bottom` / `(0, 1)` |
| `B2T` | `bottom` / `(0, 1)` | `top` / `(0, -1)` |

**Tests** — `tests/core/test_types/test_layout_direction.py`: side/vector tables, the
invariant that `inlet_side != outlet_side` for every member, and that `L2R` reproduces
today's `(-1,0)/(1,0)` exactly.

---

## Phase 2 — Settings

Two independent settings bags, in different packages, with different tier behaviour.
**2a** is the direction itself — core, three-tier, mirroring the `skin` chain field-for-field.
**2b** is the pin geometry that renders it — a barn library bag, single-tier.

### 2a — Direction tiers (core)

Three declarations. No new machinery.

**a.** [`core/skin/settings.py`](../../../packages/haywire-core/src/haywire/core/skin/settings.py)
— add to `NodeDefaultSkinSettings` (decision 4):

```python
studio_layout_direction = setting[CHOICES](
    LayoutDirection.LEFT_TO_RIGHT.value,
    label="Default Layout Direction",
    description="Direction flow reads across node cards in the studio",
    category=CATEGORY_NODE_SKINS,
    widget_config={"options": _layout_direction_choices},
)
```

plus a module-level `_layout_direction_choices()` returning
`{d.value: <human label> for d in LayoutDirection}`. Unlike `_node_skin_choices` this
needs no registry lookup and no `try/except` — the options are static.

The module docstring explains why this file lives in core: `NodeProperties` and
`GraphProperties` shadow it and core must never import from `ui`. `LayoutDirection`
lives in `core.types.enums`, so that constraint holds.

**b.** [`core/graph/properties.py`](../../../packages/haywire-core/src/haywire/core/graph/properties.py):

```python
layout_direction = shadow(
    src=NodeDefaultSkinSettings.studio_layout_direction,
    label="Layout Direction",
    description=(
        "Flow direction for nodes in THIS graph. Overrides the studio "
        "default; a node's own layout direction overrides this."
    ),
    category="appearance",
    order=20,
    widget_config={"options": _layout_direction_choices},
)
```

Mirrors inherit `IType` from `src` but **not** `widget_config` — the options must be
re-supplied, exactly as `default_skin` re-supplies `_node_skin_choices`.

**c.** [`core/node/properties.py`](../../../packages/haywire-core/src/haywire/core/node/properties.py):

```python
layout_direction = graph(
    src=GraphProperties.layout_direction,
    label="Layout Direction",
    category="appearance",
    order=15,
    widget_config={"options": _layout_direction_choices},
)
```

and add `"layout_direction"` to `REDRAW_FIELDS`. That single entry buys live re-render at
all three tiers: `NodeWrapper._subscribe_props_redraw`
([node_wrapper.py:647](../../../packages/haywire-core/src/haywire/core/node/node_wrapper.py#L647))
subscribes the field, and a graph-tier write propagates through the mirror into every
tracking node's cell, firing the same subscription.

**Resolution helper.** Callers need a `LayoutDirection`, but the cell stores its `str`
value (CHOICES is a STRING subtype). Add one place that converts, tolerating an
unrecognised string by falling back to `LEFT_TO_RIGHT` rather than raising mid-render:

```python
def resolve_layout_direction(wrapper: NodeWrapper) -> LayoutDirection: ...
```

Put it next to `render_pin` in
[`ui/skin/pin_render.py`](../../../packages/haywire-core/src/haywire/ui/skin/pin_render.py)
— that module is already the shared helper surface for skins that do not subclass
`NodeSkin`, and `RerouteSkin` (Phase 6) needs the graph-tier variant from the same place.
Two functions: one reading `wrapper.node.props`, one reading `wrapper.graph.props`.

**Tests** — `tests/core/test_node/test_node_layout_direction_graph_tier.py`, modelled on
the existing [test_node_skin_graph_tier.py](../../../tests/core/test_node/test_node_skin_graph_tier.py):
unset node tracks graph default; node override wins and `reset()` falls exactly one tier;
round-trip preserves all three tiers; a pre-feature graph JSON with no `layout_direction`
key loads and reports `is_locally_set() is False`.

### 2b — Pin geometry per axis (haybale-studio)

**File:** [`barn/haybale-studio/haybale_studio/settings/node_skin_settings.py`](../../../barn/haybale-studio/haybale_studio/settings/node_skin_settings.py)

`NodeSkinSettings` is a **`LibrarySettings`** bag (`@settings(namespace="ui.node.skin")`)
owned by haybale-studio — not `FrameworkSettings`, and not in core. Its geometry fields
were all written for horizontal flow, and two of them are genuinely axis-specific.

**Why the values must coexist rather than be reinterpreted.** The tempting alternative is
to rename the existing fields to flow-relative names ("padding along the flow axis",
"pitch across it") and keep one set. That cannot work here: `LayoutDirection` resolves
**per node** (three tiers), while this bag is **single-tier, library-global**. One graph
can hold a `T2B` node beside an `L2R` one, both reading the same bag — so there is no
"current direction" at the bag level to reinterpret against. Both axes' values have to be
live simultaneously, and each node picks the pair matching its own direction.

Audit of the existing fields:

| Field | Under vertical flow | Action |
| --- | --- | --- |
| `card_padding` | Double duty — applied as `padding-left/right`, **and** feeds `render_pin`'s `offset_px = card_padding + gutter//2 + protrusion`. Vertically the pin exits the top/bottom edge, so the offset needs block padding, which `DefaultNodeSkin` never sets (it inherits the q-card default) | **Add counterpart** |
| `pin_row_height` | Spacing between consecutive stacked pins — a height. The strip analogue is spacing between pins along a row — a width | **Add counterpart** |
| `pin_gutter` | Double duty too: grid track size **and** the pin icon's `size`. The icon is square, so it is axis-agnostic; the track just becomes the strip's thickness | Share |
| `pin_protrusion` | "How far outside the edge" is the same semantic on any axis | Share |
| `content_gap` | Gap between gutter and label/widget; strips have neither. Still live for configs — `_render_config` uses `gutter + gap` as its indent | Share; becomes config-only |
| `show_labels` | Pin labels do not exist vertically by construction; config labels still obey it | Share; partially inert |
| `show_tooltips` | Matters *more* vertically — the only thing identifying a pin | Share |

So two new fields, no renames, and no migration of persisted keys (`card_padding`'s
description already says "Horizontal", so it stays accurate as-is):

```python
card_padding_block = setting[INT](
    16,
    label="Card Padding (vertical)",
    description="Vertical padding applied to the node card in pixels. Used as the "
    "pin offset baseline when the node's layout direction is T2B or B2T",
    category="layout",
    min=4,
    max=32,
)
pin_column_width = setting[INT](
    24,
    label="Pin Column Width",
    description="Width of each pin cell in a vertical pin strip (px)",
    category="layout",
    min=16,
    max=48,
)
```

Defaults match the existing horizontal values (16 / 24) so vertical mode is consistent out
of the box. `NodeSkinSettingsPanel` renders through `render_schema(NodeSkinSettings,
registry)`, so both fields surface in the settings panel automatically — no panel work.

`NodeSkin` gains the matching accessors next to `CARD_H_PADDING` / `PIN_ROW_HEIGHT`, and
Phases 3-5 select the pair by `layout.is_vertical`.

> **Trap.** The vertical branch must *apply* `card_padding_block` as explicit
> `padding-top`/`padding-bottom` on the card, not merely read it. `render_pin`'s offset
> formula assumes it knows the padding on the axis the pin crosses; if the setting says 16
> while the q-card default paints something else, every pin seats wrong on the edge —
> consistently, subtly, and identically on every node, which is exactly the kind of wrong
> that reads as "the design just looks like that".

---

## Phase 3 — `render_pin`: one derivation, both consumers

**File:** [`ui/skin/pin_render.py`](../../../packages/haywire-core/src/haywire/ui/skin/pin_render.py)

Replace the `direction: str = "left"` parameter with `layout: LayoutDirection`, and
derive **both** outputs from `layout.side_for(pin)` / `layout.vector_for(pin)`. The
existing `f"{direction}: -{offset_px}px"` offset trick keeps working unchanged — the
enum's side values are CSS property names — so `top`/`bottom` need no new code path.

Keep the parameter keyword-only and give it a `LEFT_TO_RIGHT` default so any skin that
does not cooperate keeps today's behaviour verbatim.

`render_pin` keeps taking `card_padding` / `pin_gutter` / `pin_protrusion` as explicit
numbers — it stays settings-agnostic, which is the whole reason standalone skins can call
it with literals. Choosing *which* padding to pass (`card_padding` vs Phase 2b's
`card_padding_block`) is the caller's job, because only the caller knows whether its card
actually paints that padding.

**Icons.** `_resolve_pin_icon` returns L/R-directional glyphs for CONTROL
(`JOIN_LEFT`/`JOIN_RIGHT`) and CALLBACK (`SWIPE_LEFT_ALT`/`SWIPE_RIGHT_ALT`).
[icons.py](../../../packages/haywire-core/src/haywire/ui/themes/icons.py) has **no**
up/down variants. Rather than add a second axis of icon constants — which would double
the authoring surface for every library author's per-type `icon_in`/`icon_out` override —
apply `transform: rotate(90deg)` to the pin element when `layout.is_vertical`. This covers
built-in glyphs and every custom type override for free. Rotation about the element centre
leaves `getBoundingClientRect()` centre unchanged, so the edge layer is unaffected.

Emit the resolved direction as a data attribute (`data-hw-layout="t2b"`) for debugging and
for future consumers; nothing reads it in this plan.

**Callers to update** (grepped, complete): `NodeSkin._render_pin` and
`_render_root_ghost_pins` (Phase 4), `RerouteSkin._render_reroute_pin` (Phase 6).

---

## Phase 4 — `NodeSkin`

**File:** [`barn/haybale-studio/haybale_studio/skins/node_skin.py`](../../../barn/haybale-studio/haybale_studio/skins/node_skin.py)

**a. Merge the mirrored methods.** `_render_left` (L72) and `_render_right` (L109) are
exact mirrors — grid column order, and which margin gets `gap` versus the full gutter.
Collapse into `_render_port_horizontal(port, wrapper, side, widget_classes)` where
`side ∈ {"left", "right"}` picks column order, `align-items`, and margin assignment. This
is the whole of `L2R` ↔ `R2L`.

> **Call-site fixes required.** Two skins call the mirrored methods from outside:
>
> - `ErrorNodeSkin.render` calls `self._render_right(...)` directly
>   ([error_skin.py:97](../../../barn/haybale-studio/haybale_studio/skins/error_skin.py#L97)).
>   Update to the merged signature. The pre-existing double-render on the line above it is
>   handled by [Follow-up A](#follow-up-a--errornodeskin-defects--landed), not here.
> - `ExampleNodeSkin.render` calls `self.render_port(...)` for inlets, outlets, and
>   configs ([example_skin.py](../../../barn/haybale-example/haybale_example/skins/example_skin.py)).
>   The signature is unchanged, but `render_port` gains the resolved direction — see
>   Phase 5b for what this skin needs.

**b. Route by direction.** `render_port` (L63) dispatches on `port.is_inlet()` /
`is_outlet()` / `is_config()`. It gains the resolved `LayoutDirection` and, for horizontal
directions, calls `_render_port_horizontal` with `layout.side_for(port)`. Config ports are
unchanged in every direction — `_render_config` (L144) already renders pinless and stays
as-is.

**c. Add the pin strip.** `_render_pin_strip(ports, wrapper, side)`: a `ui.row` of bare
pins along one card edge, ordered by `port.order`, no labels, no widgets, `flex-wrap:
nowrap`. Each pin goes through `_render_pin` with the resolved layout, so it picks up the
right offset side, vector, and rotation. Tooltips stay wired (they are the only remaining
affordance identifying a pin in vertical mode, so `show_tooltips` matters more here) —
`add_pin_tooltip` is already lazy-on-first-hover and costs nothing at render.

**d. Ghost pins (decision 5).** `_render_root_ghost_pins` (L191) hardcodes `left: -16px` /
`right: -16px`, `order: 999`, and a third copy of the `(-1,0)/(1,0)` vectors. Parameterize
by side from the resolved layout; in vertical mode place both on the top/bottom edges of
the header row instead of its left/right ends, and drop the `order: 999` trick (it exists
to push the outlet to the end of a horizontal flex row). Take vectors from the enum — never
re-literal them.

The docstring's note about inline flex items keeping `getBoundingClientRect()` correct for
the edge-drawing code still holds and must survive the change: no absolute positioning.

---

## Phase 5 — Card skins

### 5a — `DefaultNodeSkin`

**File:** [`barn/haybale-studio/haybale_studio/skins/default_skin.py`](../../../barn/haybale-studio/haybale_studio/skins/default_skin.py)

Resolve the direction once at the top of `render` and branch.

**Horizontal path** — today's body verbatim. Note the class docstring claims a
"two-column layout (inlets left, outlets right)" but the code (L84-105) is a *single*
`ui.column` rendering OUTLET → CONFIG → INLET; sidedness comes entirely from
`_render_left`/`_render_right`. Fix the docstring while here.

**Vertical path** — three bands:

1. inlet pin strip on the inlet edge (`top` for `T2B`, `bottom` for `B2T`)
2. header (title, diagnostics badge, ghost pins) + CONFIG ports via the existing
   `_render_port_hierarchy(..., PortType.CONFIG)`
3. outlet pin strip on the opposite edge

For `B2T` the outlet strip renders first in DOM order so it lands visually on top.

**Groups (decision 2).** `_render_group` does collapsible nesting with child ports, which
has no meaning in a flat strip. In vertical mode, do not call `_render_group` for
INLET/OUTLET: take `node.get_visible_ports()`, filter to the port type, skip
`port.is_group`, and skip children (`port.parent_group is not None`) — group members do not
appear in the strip at all. CONFIG ports keep full group rendering in the body, unchanged.

**Card sizing.** `w-full min-w-64 max-w-sm` (L36) are horizontal-layout numbers: a 256px
floor and a 384px cap sized for a label+widget content column. In vertical mode width is
driven by pin count × gutter plus the config body, and the meaningful floor is on height.
Drop `min-w-64`/`max-w-sm` on the vertical path.

> **Read [`.insights/feedback_css_containment_node_floor.md`](../../../.insights/feedback_css_containment_node_floor.md)
> before touching these classes.** A node's size floor is CSS `max-content` and
> percentages evaporate during intrinsic sizing; `contain: size` fixes the floor but kills
> aspect-driven growth. Measure the floor in manual mode — auto mode reads `max-w-sm`.
> The `size_adapt` resize gadget is already axis-agnostic and needs no change.

### 5b — `ExampleNodeSkin`

**File:** [`barn/haybale-example/haybale_example/skins/example_skin.py`](../../../barn/haybale-example/haybale_example/skins/example_skin.py)

This skin rendered no pins at all until 2026-08-22 — inlets were labels plus a widget,
outlets were labels only, so nothing on an example-library node could be connected by
dragging. It now renders every port through `render_port` in a **two-band layout**: config
ports span the full card width on top, then inlets and outlets sit side by side beneath
(an empty column is omitted). That makes it a pin-bearing skin and therefore subject to
this plan.

Its layout is the reason it is worth carrying rather than deleting: it is the only in-repo
skin whose horizontal arrangement is *not* the default's single stack, so it proves the
direction contract is a property of `render_port` and not of any one card layout. The
full-width config band also makes it the only skin that visibly separates pinless ports
from pin-bearing ones — which is exactly the separation vertical mode turns into a hard
structural split, so 5a and 5b collapse to the same shape there.

> Configs were briefly given their own middle column and it did not work: squeezed to a
> third of the card, config widgets were unusably narrow. Pinless ports have no edge to
> anchor them to a side and their widgets are the ones that need room — full width is the
> right home. Do not reintroduce the three-column form.

Required work here is small, because the skin delegates all pin placement:

- **Horizontal.** `render_port` resolves the side, so `R2L` swaps which card edge each
  column's pins straddle for free. The column *order* swaps with them (Follow-up B), keyed
  off `layout.inlet_side`, so a pin and its own label stay on the same side of the card.
- **Vertical.** Side-by-side columns are meaningless when pins live on the top/bottom
  edges. Take the same branch shape as 5a: inlet strip, then the header and the config
  band, then the outlet strip. The config band is already full width, so it needs no
  rearranging — only the inlet/outlet row collapses into strips. The example skin has no
  group handling to strip out, so decision 2 costs nothing here.
- **Card sizing.** Same `min-w-64 max-w-sm` treatment as 5a. Two things on this skin's
  class list must survive any edit: the literal `node-card` token (see the class-list
  invariant — without it manual resize silently caps at 384px) and `min-w-0` on each flex
  column, which stays in horizontal mode and is irrelevant vertically.

---

## Phase 6 — `RerouteSkin`

**File:** [`core/barn/builtin/skins/reroute_skin.py`](../../../packages/haywire-core/src/haywire/barn/builtin/skins/reroute_skin.py)

Subclasses `BaseSkin` directly with literal geometry, and calls `render_pin` with
`"left"`/`"right"` literals. Per decision 3 it reads the **graph** tier
(`wrapper.graph.props.layout_direction`) via the graph-tier resolver from Phase 2 — a
per-node override on a reroute is deliberately ignored. In vertical mode the inner
`ui.row` becomes a `ui.column` so the two pins straddle the top/bottom edges of the little
box instead of its left/right.

---

## Phase 7 — Bezier control distance

**File:** [`ui/components/graph/canvas.vue`](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue) — `_createBezierPath` (L2907)

```js
const distance = Math.abs(endPos.x - startPos.x);
```

Control-point distance measured on X only. Two vertically stacked `T2B` nodes have ~0 X
delta, so `controlDistance` clamps to the 50px floor and every vertical edge renders as a
flat stub. Project the endpoint delta onto each end's own direction vector instead:

```js
const dx = endPos.x - startPos.x, dy = endPos.y - startPos.y;
const span = Math.abs(dx * startDir[0] + dy * startDir[1]) || Math.hypot(dx, dy);
const controlDistance = Math.max(50, span * 0.5);
```

For `L2R` (`startDir = [1, 0]`) this reduces to `Math.abs(dx)` exactly — **no visual
regression on existing graphs**. The `|| Math.hypot(...)` fallback covers a purely
perpendicular run, where the projection is 0 but the endpoints are far apart. Because each
end uses its own vector, mixed-direction graphs curve correctly for free.

**Nothing else in canvas.vue changes.** `_isValidEdge` (L3013) keys off `pinDir` and
`pinFlowType` with zero geometry, and `_getPinDirectionVector` (L3072) already reads the
data attributes generically — validity, hit-testing, snapping, and proximity suggestion
are all direction-agnostic today. This is the only axis-locked line in the edge layer.

---

## Phase 8 — Docs, insights, verification

- **Glossary** — add `LayoutDirection` to [`docs/reference/glossary.md`](../../reference/glossary.md).
- **Skin canon** — [`docs/components/skins/skin-canon.md`](../../components/skins/skin-canon.md)
  is still a placeholder overall, but its *class list is a contract* section is written and
  is where card-level skin requirements now live. Add the layout-direction skin contract as
  a sibling section there: which method resolves the direction, that `render_port` places
  pins from it, and that a skin ignoring it degrades to `L2R` rather than breaking. Do not
  duplicate the rule into `.insights/` — skin-authoring knowledge belongs on this page,
  where a skin designer will look for it.
- **Insight file** — add `.insights/project_layout_direction_pin_contract.md` and a
  one-line entry to CLAUDE.md's trap list for the *framework-internal* half only: a pin's
  CSS side and its `data-pin-dir-x/y` vector must derive from one source, because a
  mismatch fails silently (pins on the right edge, curves pointing the wrong way) and the
  two were independently hardcoded in three places before this change. That one is about
  `render_pin`'s implementation, not about authoring a skin.
- **Full gate**, per CLAUDE.md:

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
  barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
  barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ \
  barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ \
  barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
  barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
```

Then the browser tier, since Phase 7 changes rendered edge geometry and Phases 4-6 change
node DOM.

> **Trap** — `tests/studio/test_docs/test_generate.py` teardown runs
> `git checkout -- barn/haybale-testing`, discarding uncommitted edits there. Nothing in
> this plan touches that directory, but commit before a full-suite run regardless.

---

## Files touched

| File | Phase |
| --- | --- |
| `core/types/enums.py` | 1 |
| `core/skin/settings.py` | 2a |
| `core/graph/properties.py` | 2a |
| `core/node/properties.py` | 2a |
| `ui/skin/pin_render.py` | 2a, 3 |
| `barn/haybale-studio/.../settings/node_skin_settings.py` | 2b |
| `barn/haybale-studio/.../skins/node_skin.py` | 2b (accessors), 4 |
| `barn/haybale-studio/.../skins/error_skin.py` | 4 (call-site only) |
| `barn/haybale-studio/.../skins/default_skin.py` | 5a |
| `barn/haybale-example/.../skins/example_skin.py` | 5b |
| `core/barn/builtin/skins/reroute_skin.py` | 6 |
| `ui/components/graph/canvas.vue` | 7 |

All four in-repo pin-bearing skins are covered: `DefaultNodeSkin`, `ErrorNodeSkin`,
`ExampleNodeSkin`, `RerouteSkin`.

---

## Follow-ups

Independent of this plan; neither blocks it nor is blocked by it.

### Follow-up A — `ErrorNodeSkin` defects — **LANDED**

Two independent pre-existing bugs, both fixed together with the first
error-skin DOM coverage (`tests/ui/harness/test_error_skin.py`, route
`/graph-error-skin` — a healthy node pinned to the error skin via `props.skin`,
since a real render failure is hard to provoke deterministically). Kept below
for the record.

**A1 — the card omits `node-card`.** Its class list is
`w-full min-w-64 max-w-sm error-node-card {node_id} zoom-pan-lod0`
([error_skin.py:66](../../../barn/haybale-studio/haybale_studio/skins/error_skin.py#L66)) —
`error-node-card` is a sibling token, not a variant, so none of the `.node-card` rules
match. An error-skinned node therefore stops growing at 384px when resized, per the
class-list invariant above. One-token fix; the same defect was found and fixed in
`ExampleNodeSkin` on 2026-08-22. Not fixed here only because Phase 4 does not otherwise
touch that line and the fix wants its own regression test.

**A2 — outlets render twice.**
[error_skin.py:89-98](../../../barn/haybale-studio/haybale_studio/skins/error_skin.py#L89-L98)
loops `node.ports.values()` through `render_port` for **every** port — which already places
inlets left, outlets right, configs pinless — and then loops again over the same ports
rendering each outlet a second time through `_render_right`. Outlets therefore appear
twice on any node that falls back to the error skin, and the duplicate pin re-uses the
port's `generate_pin_uuid(node_id, port.id)`, so two DOM elements share one `id`. The
connection layer resolves pins by id; which of the two it finds is document-order luck.

Pre-existing and unrelated to direction — it reproduces on `master` today. Called out
here because Phase 4 edits the very line that causes it and a reviewer will otherwise
assume the merge introduced it.

Fix is to drop the second loop and let the single `render_port` pass stand. Worth a
regression test asserting one pin element per port id on an error-skinned node — there is
no coverage of error-skin DOM today.

### Follow-up B — column order under `R2L` — **LANDED (columns swap)**

Resolved: a multi-column skin's columns follow the flow direction. Rule stated in
skin-canon, enforced by `tests/ui/harness/test_two_column_skin.py`. Original
write-up kept for the record.

Phase 5b deliberately leaves `ExampleNodeSkin`'s columns in inlets-left order under `R2L`,
so pins flip to the outer edges while the columns stay put. Whether a two-column skin
should also mirror its *columns* is a genuine design question — it affects reading order,
not just pin placement — and it applies to any future multi-column skin, not just this
one. Decide once, apply to all.

### Follow-up C — dead fields in `NodeSkinSettings` — **LANDED (deleted)**

Resolved by deleting both fields. The Ports panel already serves the need, and
`tests/ui/skin/test_node_skin_settings.py` now asserts the bag's fields and the
skins' reads match in *both* directions, so the docstring's claim is checked
rather than asserted. Original write-up kept for the record.

`show_node_ids` and `show_port_ids`
([node_skin_settings.py](../../../barn/haybale-studio/haybale_studio/settings/node_skin_settings.py))
are **never read by any skin** — grep for `_ui_settings.` returns `card_padding`,
`pin_gutter`, `pin_protrusion`, `content_gap`, `pin_row_height`, `show_labels`,
`show_tooltips` and nothing else. They have been dead since introduction, while the class
docstring asserts "All fields are wired to actual rendering logic."

They also render in the settings panel, so a user can toggle them and watch nothing
happen — worse than absent, because it reads as a broken feature rather than a missing one.

Two defensible resolutions, and the choice is not obvious: **wire them** (both are
plausible debug affordances a skin author would want, and `show_port_ids` in particular
earns its keep in vertical mode where pins carry no labels), or **delete them** and let the
Ports panel serve that need. Phase 2b adds two fields to this bag, which is a natural
moment to settle it — but it is a product call, not a refactor, so it stays out of the
plan proper. Either way, fix the docstring.

## Out of scope

- **Auto-arrange.** [`.scratch/node-arrange/research.md`](../../../.scratch/node-arrange/research.md)
  specs a Sugiyama layered layout; when built it should consume `LayoutDirection` to pick
  its rank axis rather than assuming L2R. Noted, not built here.
- **Per-edge routing styles** (orthogonal/step edges), which vertical layouts often want.
- **Migrating existing graph files** — the field is absent from every saved graph and
  resolves to the framework default, which is `L2R`, which is today's behaviour.
