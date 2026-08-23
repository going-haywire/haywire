---
name: surface-model
description: Panels attach to a Surface and may themselves host Surfaces, so one recursive rule — host renders surface renders panel renders host — covers menus, submenus, toolbars, and inspector tabs alike
status: accepted
level: architectural
---

# The surface model

A **Surface** is a place Panels appear: a properties tab, a context menu, a
region within one, a flyout. It owns a stable `id` the registry routes on, a
`poll()` predicate deciding whether it applies, and — when its panels need verbs
from whatever renders them — a `provides` Protocol naming what its host must
implement. Inspector surfaces read state and declare none.

A **Panel** names one surface, adds its own `poll()`, and draws. A Panel may
also **host** surfaces of its own, declaring them with `hosts=`.

The render hierarchy is therefore recursive:

```text
host → surface → panel → host → surface → panel → …
```

## Why this shape

Panel hosts nest, and the nesting is not uniform. A context menu wants a row of
icon shortcuts, a flyout of secondary commands, and a prime area below for
something richer like a search field. A properties tab wants a flat stack of
sections. A toolbar wants icons and an overflow.

Making the Panel the unit of nesting covers all of these with one rule. A panel
that owns a region renders that region's surface; a panel that opens a flyout
renders the flyout's surface. Regions, submenus, and overflows stop being
separate concepts — each is a surface some panel renders.

## Composition

**Visibility composes by AND.** A host evaluates a surface's `poll()` before
querying its panels. A false gate means the surface contributes no panels —
whether its chrome stays behind, greyed, is a separate question answered under
Routing. A panel's own `poll()` then refines what its surface established. A
panel hosting a further surface repeats the same two steps one level down.

**`poll` means one thing everywhere** — Surface and Panel use the same verb and
the same contract: *does this apply right now*. It runs on every relevant context
change, so it stays cheap: a state read, not a computation. `poll` is the only
*state* predicate at either level; a panel's `access=` tier is an orthogonal
*principal* gate that runs first, so a denied panel's `poll()` never executes
(ADR-0027).

**A panel decides what inapplicable looks like.** `poll()` answers whether the
panel applies; the panel answers what to render either way. `draw()` runs when it
applies, `draw_disabled()` when it does not, and the default `draw_disabled()`
renders nothing — so a panel with no opinion vanishes, which is the whole of
today's behaviour.

Two methods rather than one branch inside `draw()`, because the inapplicable path
must not touch the state that is absent. Panel bodies dereference
`active_node.settings` freely precisely because `poll()` guaranteed it was there;
folding both states into one method puts every such body one empty selection away
from an exception where a greyed row belongs.

Nothing about the panel is drawn by its host, so a panel declares no `label` or
`icon` for chrome and keeps the dynamic part of its row — "Copy 3 nodes" — that a
static declaration could not carry.

`access=` denial is not a kind of inapplicability. A denied panel renders nothing
at all, never a disabled view, because a greyed entry advertises what the
principal may not have.

**Nesting is declared, then realised.** A hosting panel names the surfaces it may
host in `hosts=`, and calls `render_surface` inside `draw()` to actually render one.
The declaration is what the registry can read without rendering: it is a
panel → surface edge, so a surface reached by two different panels is two edges
rather than a contested parent. Rendering a surface not in the panel's `hosts=`
is an authoring error.

**Every surface states its own contract.** A surface's Protocol is its demand on
whatever hosts it, and no surface inherits one.

**A hosting panel pipes the host it was given, unless it says otherwise.** The
common case is a panel that owns an arrangement, not the verbs: it passes down
the host it received without naming it. A panel that means to serve as the host
itself says so explicitly, as does one delegating to a third object. Whichever
object is chosen is checked against the target surface's Protocol, so a mismatch
fails at the point of nesting rather than reaching panels as a host missing the
verbs they call.

Resolution is never inferred from whether the panel happens to satisfy the
Protocol. A structural check cannot tell "I implement this" from "I accidentally
match", and a marker Protocol with no members matches everything — inferring
would silently make a layout panel the host and strand the real provider one hop
up.

## Presentation

**`presentation` belongs to surfaces, and only to surfaces.** It is `label` plus
`icon`, declared by a surface whose host draws chrome around it. Today that is
the properties editor, which draws a tab per surface. A menu surface declares
none.

Panels do not have it. A panel already carries `label` and `icon` as component
identity — what the properties editor titles its expansion sections with, and
what listings and generated docs read — and in a menu the panel draws its own
row. Adding a second, chrome-shaped declaration would duplicate that and still
could not express the dynamic half of what `draw()` renders.

Ordering among siblings is separate from chrome: panels and surfaces carry it
whether or not they present anything.

**`presentation` is therefore also the discriminator for the properties strip.**
Every other host names the surface it opens — a context-menu provider passes one
explicitly. Only the strip *discovers* its list, and what it lists is exactly
**root surfaces that declare `presentation`**: a root surface with no chrome to
draw (a menu, the floating toolbar) is not a tab, and a surface some panel hosts
is drawn by that panel, not by the strip. This holds as long as the properties
editor is the only host drawing chrome around a surface; a second one would need
an explicit marker rather than this derivation.

## Redraw

**A host redraws its whole tree.** Panels are stateless and rebuilt on every
draw, so there is no preserved subtree state that partial redraw would protect,
and no accounting worth the complexity. A long-lived host subscribes to the union
of redraw signals across every panel in its tree and redraws all of it when any
of those fires.

That union is computed from `hosts=`, by walking surface → its panels → their
`hosts=` transitively. It has to be static: the host subscribes on mount, before
anything has rendered, so a union that could only be discovered by rendering
would miss every nested panel — silently, since a missing subscription looks
exactly like a signal that never fired.

Transient hosts subscribe to nothing. A context menu is built per gesture and
dismissed, so it is never live when a signal arrives.

**A long-lived host may also be event-driven, and then `redraw_on` is inert in
its tree.** The floating toolbar is the case: it is rebuilt when the canvas emits
new selection bounds, and its surface is *defined* by the selection, so its panels
have no trigger their host does not already answer. Subscribing it would buy a
signal none of them declare, at the cost of a hazard — a signal arriving
mid-gesture would re-show a toolbar the user hid by starting a pan.

This is a real hole in an otherwise uniform contract, so it is guarded rather than
left to be discovered: a test asserts the union across that host's tree is empty,
and fails the moment a panel declares one. That failure is the prompt to subscribe
the host properly, with the mid-gesture problem in view.

## Routing

Routing is by `id`, a string. Panels name their surface; hosts query by surface;
they meet on that string. See [ADR-0009](0009-surface-id-stable-key.md) for why
the id rather than the class object is the durable key.

**Whatever keeps a place, greys; whatever has no place, omits.** Stable position
is what makes a surface learnable, so anything the user can point at stays put
when it stops applying:

- A surface with `presentation` — a properties tab — keeps its position and greys
  when `poll()` is false. Its host drew that chrome, so its host greys it.
- A surface without `presentation` — a menu surface, a menu region, the floating
  toolbar's surface — has no chrome of its own. A false gate means it contributes
  nothing.
- A panel renders its own inapplicable state through `draw_disabled()`, or
  nothing. That is where a greyed menu row lives, the row that opens a submenu
  included: the panel drew the row, so the panel greys it.
- A panel denied by `access=` vanishes without trace, whatever it implements.
- A root context menu whose tree draws nothing does not open at all. The gesture
  is over, so the host runs its close cleanup and no popup appears. What counts
  as "nothing" is the next rule.

Note the symmetry this rests on: *whoever draws a thing is who greys it*. A
surface never draws, so a host greys it; a panel always draws, so it greys
itself. Nothing needs to declare which of the two applies.

**Emptiness is a property of the tree, not of the root surface.** With nesting,
the root's panel list stops answering the question: a panel that owns regions
polls true and draws its arrangement whether or not anything lands inside it, so
a menu built that way would always open, sometimes around nothing.

The host therefore builds its popup hidden, renders the tree into it, and keeps
it only if a **leaf panel** — one declaring no `hosts=` — drew. Otherwise it
deletes the popup and runs its close cleanup, exactly as it does when nothing
polls true. The leaf rule asks nothing of panel authors: a region-owner is
already distinguishable from a leaf by its `hosts=` declaration, and a panel that
both hosts a surface and draws content of its own mis-reports toward opening
rather than toward swallowing the menu.

A leaf that rendered its disabled state counts as having drawn. A menu of greyed
rows is a menu, and opening it is correct — so the no-popup path narrows to the
case where nothing applied *and* no panel offered a disabled view. Since that is
the default, this changes nothing until an author opts in.

The same question is asked one level down, and answered the same way: a row that
opens a submenu greys when its body drew nothing. That is the resting state of an
extension surface nobody has extended, so it is a normal condition rather than an
edge case. The row is greyed rather than removed — it keeps its place, and the
primitive cannot tell "nothing ever" from "nothing right now".

Discarding a rendered tree means running `draw()` for a menu nobody sees. That is
affordable because the surface gate runs first, keeping the cost off every path
where the menu does not apply at all, and because deleting the popup deletes its
subtree along with anything those draws created.

**A surface may be named from outside the process.** A skin marks a DOM element
with a surface id and the canvas opens that surface on right-click. It is the one
place a surface id arrives as an untyped string from another library, and so the
one place it may not resolve.

Entities the canvas already knows — pin, node, edge, empty canvas — do not use
it. Each is detected from the attributes it carries for dragging, selection and
routing, and which surface each opens is the framework's decision rather than the
skin's. The attribute exists only so a library can add a menu the framework knows
nothing about.

Nothing constrains which surface it may name. An id resolving to an inspector
renders inspector panels into a popup: wrong-looking, but inert — inspector
panels never call `self.actions` — and visible to its author on the first
right-click. An id resolving to nothing opens nothing and logs. Neither earns a
marker field, because no default can misfire on its own: every id in that
attribute was typed by someone.

What such a surface may *demand* is constrained, and not by us. Its `provides` is
checked against the host the canvas supplies, which is the graph editor's own
provider. A third-party surface can reuse a Protocol that provider already
satisfies, or declare none and let its panels act through `ctx` directly. It
cannot invent verbs and expect them to arrive.

## Considered alternatives

- **A `zone` field on the panel** to place it in a menu region. Rejected — every
  host must agree on the vocabulary, and the registry cannot verify a zone name
  refers to anything. `hosts=` is the verifiable form of the same intent: it
  names a Surface class, so a typo is an ImportError and a cycle is a
  registration error.
- **Surfaces declare a parent surface.** Rejected in favour of panels hosting
  surfaces: a static surface-to-surface tree cannot express a region owned by one
  panel among several on the same surface, and a panel that opens a flyout is
  already the natural owner of what the flyout contains. `hosts=` keeps that
  ownership — the edge runs panel → surface, so the same surface hosted by two
  panels is two edges rather than a contested parent.
- **Nesting known only at render time, with no `hosts=` declaration.** Rejected —
  three things need the tree before anything renders: the redraw union a
  long-lived host subscribes to on mount, the root/nested split the properties
  strip lists from, and cycle detection. All three fail silently or not at all
  without a static edge. A render-time-only tree also leaves a cycle undetectable
  until someone happens to render it.
- **Infer the nested host structurally** — the hosting panel serves as host when
  it satisfies the Protocol, else pipes. Rejected — `isinstance` against a
  `runtime_checkable` Protocol tests member presence, not intent, and a marker
  Protocol with no members matches every object. The failure is silent and
  one-directional: a layout panel quietly becomes the host and the real provider
  never reaches the panels that need it.
- **Panels declare `presentation`; the host draws their rows and greys them.**
  Rejected — it is the properties editor's expansion-header pattern generalised,
  and it does not survive the generalisation. A host-drawn row owns the label, so
  it loses the dynamic half ("Copy 3 nodes"), and the panel then needs a
  command-shaped API — a declared action for the host to wire, plus an enrichment
  slot to put the count back. Three new contracts to avoid one method. It also
  breaks the strip's discriminator, since a submenu row would be a second host
  drawing chrome.
- **One `draw()` with an `enabled` flag.** Rejected — the inapplicable path would
  run inside a body written on the guarantee that `poll()` already passed. Every
  `active_node.settings` in the tree becomes one empty selection away from an
  exception rendered where a greyed row belongs. Two methods keep the guarantee
  and cost nothing when unused.
- **Dropping `poll()` from panels and letting `draw()` return early.** Rejected —
  applicability is a value the *host* consumes, not a panel-internal branch: it
  chooses the container before the body runs, and it must be askable without an
  instance, a slot, or a layout. `poll()` is also the only word `Surface` and
  `Panel` share, and surfaces have no `draw()` to fold it into.
- **A dedicated `is_tab` marker for properties surfaces.** Not adopted — it would
  restate what `presentation` already says. A surface declares presentation
  exactly when some host draws chrome around it, and the properties editor is the
  only host that does. Revisit if a second one appears.
- **Merge the surface and its Protocol into one class.** Rejected on mechanics: a
  Protocol may only inherit from other protocols, so the base could carry no id,
  `poll()`, or registry behaviour. The two also hold different kinds of member —
  class-level data the framework reads, versus instance methods a host
  implements — so the structural check would demand the host supply both. Naming
  the Protocol keeps it reusable by more than one surface.
- **Partial redraw of a subtree.** Rejected — panels hold no state across draws,
  so there is nothing to preserve and the accounting buys nothing.
- **Deciding emptiness by probing the tree instead of rendering it.** Rejected —
  the `hosts=` graph is static enough to walk, but a probe polls every surface and
  panel a second time, breaking the once-per-render guarantee below, and it still
  cannot separate a visible panel that draws something from one that draws
  nothing. Rendering and discarding answers the question actually being asked.
- **Letting the root layout panel's `poll()` stand in for its regions.** Rejected
  — it cannot know. Asking authors to keep a root panel's predicate in sync with
  whatever its regions contain reintroduces exactly the coupling this model
  removes, and it fails silently when they drift.
- **Requiring a surface to opt in to being named from the DOM** — an
  `addressable` flag, or deriving it from `provides`. Not adopted. Deriving it
  from `provides` is free but wrong: it would block precisely the third-party menu
  that needs no verbs from the provider, which is the common shape. A flag would
  work, but once the canvas detects its own entities structurally there is no
  default left to misfire, and a wrong id is visible on the first right-click.
  Revisit if a surface ever becomes reachable by a path nobody authored.
- **One attribute per kind of trigger** — the `port` and `custom` menu attributes
  the model inherits. Rejected — they are the same mechanism twice, with two
  fallbacks, two events and two handlers, and the divergence is where the
  inspector-reachable default came from. One attribute also makes the innermost
  annotation win, which is what an author expects and what the priority-ordered
  pair did not do.

## Consequences

- Nesting depth is unbounded. A cycle is **reported** at registration, where the
  `hosts=` edges form a graph the registry can walk, and **enforced** at render by
  a re-entry guard. It is not rejected: the graph closes only through
  surface → panels, so a cycle becomes visible when the *second* panel registers,
  and refusing that one would drop a panel from the catalog based on which library
  loaded first. Two libraries that are each sound alone would then fail
  differently depending on install order. Reporting early and refusing to render
  gives the author both signals — a log naming both edges, and an inline error
  where the nesting would have gone — without making load order load-bearing.
- A host that cannot satisfy a nested surface's Protocol is an authoring error,
  not a state condition, and reports as one: an inline error where the panels
  would have gone. This is the loud path, unlike a false `poll()`, which is quiet
  by design. It cannot move to registration time — the host is a runtime object —
  so it is the one contract `hosts=` does not make static.
- `poll()` runs for surfaces as well as panels on every rebuild, at every level,
  and exactly once per surface per render — the host gates the surface, the
  shared panel filter does not re-check it.
- Routing by surface id alone means a surface can no longer be reused for two
  unrelated purposes. Two surfaces that were one id distinguished by "does this
  panel declare a host contract" become two ids.
- A long-lived host's subscription set is the union across its whole tree, so a
  panel deep in a flyout can trigger a redraw of the surface that contains it.
  This is intended: the tree renders as a unit.
- Every kind of nesting is authored the same way, so a new command surface gets
  regions and flyouts without new machinery.
- A context menu's close cleanup runs whether or not a popup appears, by
  construction rather than by convention. Intent handlers reset gesture state in
  that callback — `active_port`, `active_edge`, a paused edge-drag — so the price
  of getting it wrong is a stuck drag surfacing far from its cause.
- A menu nobody sees still ran its panels' `draw()`. The surface gate ahead of it
  keeps that off the paths where the menu does not apply, and deleting the popup
  deletes whatever those draws created.
- The canvas decides which surface each of its own entities opens. A skin gains a
  menu by declaring a surface and naming it on an element; it no longer decides
  whether a pin has a menu at all, and cannot suppress a built-in one.
- Menus can follow the platform convention — an inapplicable command greys rather
  than disappearing — without any host learning to draw a panel. Every panel that
  wants it implements one method; every panel that does not keeps vanishing.
- A panel that implements `draw_disabled()` states its label twice, once per
  method. That is the price of the panel owning both renderings, and a class
  constant covers it.
- Panel `label` and `icon` stay what they have always been: component identity for
  listings, generated docs, and the properties editor's expansion header. They are
  not chrome a host reads to place the panel.
- Panels are mutually blind, so anything requiring sibling awareness belongs to
  whatever opened the box they are drawn into — not to them, and not to the
  surface they sit on. A menu level is a popup or a flyout: one panel may render
  two surfaces into a single popup, and rows from both are siblings there. The
  hover-flyout invariant (exactly one open path from the root) is the live case;
  roving focus and radio-group behaviour would resolve the same way.
