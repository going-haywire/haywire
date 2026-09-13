---
name: fold-replaces-group-and-section
description: One container concept for ports — a pin-less, widget-less boolean port opened by a disclosure triangle, replacing both the GROUP-port group() and the never-adopted section()
status: accepted
see-also: ADR-0029, ADR-0030
level: architectural
---

# One way to contain ports: the fold

**Context.** A node had two ways to group its ports, and they did not compose.

`group()` took a `GROUP` port — a `PrimitiveType[bool]` declared in
haybale-core whose only distinguishing feature is `widget_key="SwitchWidget"` —
and made every port added inside it a child. The group renders on the node card
and in the Properties panel, collapses, and keeps ghost pins for linked children
it hides. It is a real port: its value is the expanded state, it serializes, and
a node can read it or hook `on_change` to reconfigure itself.

`section()` took a bare name and wrote it onto each port inside. It creates no
port, has no value, does not collapse, and is excluded from the node card
entirely — `iter_visible_ports` skips a sectioned port unless a caller asks for
it. It was panel-only grouping.

Two facts decided this. **No node anywhere declares a section** — not one in the
repository, including the testbed node named `TestGroupAndSectionNode`, which
uses only `group()`. And `DataPort.is_section` was declared once and read
nowhere: dead code from an earlier design in which sections were marker ports.

So one mechanism had zero adoption and a dead flag, while the other carried a
widget the author had to choose and a type the author had to import.

**Decision.** One concept, `fold()`, replaces both. The author writes:

```python
with self.fold("Solver"):
    self.add(INT.as_config("substeps", default=10))
```

and chooses nothing else. The framework mints a `FOLD` port — a `BOOL` subtype
declaring the rules a fold needs rather than restating them at each call: no
widget, and `StoreStrategy.ALWAYS` so a widget-less port still remembers whether
it was open. `has_pin()` is false, so it draws no edge handle. The disclosure
triangle is the affordance. Ports added inside become its children, exactly as
under `group()`.

`section()` and everything reachable only from it are removed: `DataPort.section`,
`DataPort.is_section`, `iter_section_ports`, `get_sections_map`, and the
`include_sections` parameter threaded through `iter_visible_ports` and
`get_visible_ports`.

## The value is a disclosure state, not a decision

A fold's boolean answers "is this open", not "is this option enabled". The
distinction matters because `group()` was routinely used for the latter: the
existing call sites label their groups imperatively (`"Use Custom Name"`) and
drive a `rejig()` from the toggle.

Those nodes keep working — a fold accepts `on_change=` and `default=`, and a node
may read its value like any port. What changes is which gesture produces it: the
user folds, rather than flipping a switch. The two coincide often enough that
this is the same affordance Blender gives its modifier panels.

Authors should therefore label a fold as a section (`"Custom Name"`), not as an
imperative.

The header still states the value as a boolean: a checkbox to the right of the
label, checked while the fold is open. A fold's value is readable by the node
and drives `on_change=`, so a header showing only a triangle understates what
folding does — the checkbox says the state is a value, while the triangle says
there is content underneath. They never disagree: both render the same boolean.

## A fold is scoped to one direction

Skins render inlets, outlets and config ports in separate lanes — opposite card
edges under `l2r`, separate strips under `t2b`. A fold containing both an inlet
and an outlet would have to draw its header in two lanes or force its children
into one.

So a fold takes the direction of the ports inside it, and mixing directions
raises at declaration time. A config fold renders in the config band, an inlet
fold in the inlet lane.

## A fold holds ports, not other folds

Folds are one level deep. A fold declared inside another raises at declaration
time, alongside the mixed-direction and empty-fold errors.

Arbitrary depth is expressible but costs more than it returns. A fold is spec'd
`as_config` and only learns its direction when its block closes, so a nested one
cannot vote in its parent's lane on the way in — it has no direction yet. Making
that work needs the parent's direction vote deferred for containers and replayed
afterwards, plus a recursive renderer. No node in the repository needs more than
one level, so the depth buys nothing that pays for that machinery.

Indentation still belongs on a port row's **content column**, never its pin
column, and that rule is independent of depth.

A port row is a two-column grid, `{PIN_GUTTER}px 1fr` — the pin in the first
column, label and widget in the second. A pin is placed by a negative offset,
`card_padding + pin_gutter // 2 + pin_protrusion`, which assumes the row begins
at the card edge. Indenting the whole row — as the superseded `_render_group`
did with `pl-2 ml-1` — falsifies that assumption and insets the pin from the
border, silently.

Indenting the content column instead leaves the pin column's geometry untouched,
so the offset stays correct and label and widget indent together. The edge layer
is unaffected either way: `_getPinPosition` measures pins with
`getBoundingClientRect()` and follows the pin wherever it lands.

A fold's own header is pinless, so it indents like a config row rather than a
port row — measured against `CONTENT_GAP`, which is negative to overlap the pin
gutter, a header is pulled left of the card padding.

## Consequences

A widget-less fold must declare `StoreStrategy.ALWAYS`. A `GROUP` port persists
its open state today only because `HAS_WIDGET` satisfies `should_store`; removing
the widget removes the reason it was stored, and a fold would forget whether it
was open with nothing reporting it.

The five in-repo `self.group(...)` call sites migrate to `fold()`, keeping their
`default=` and `on_change=` arguments. The `GROUP` type has no author-facing role
left.

`parent_group` remains the one hierarchy a port belongs to, which is what makes
port ordering expressible: a port's siblings are the ports sharing its direction
lane and its fold.
