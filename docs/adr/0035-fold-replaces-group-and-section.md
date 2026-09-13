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

and chooses nothing else. The framework mints a boolean port in the config
direction — so `has_pin()` is false and it draws no edge handle — with no
widget. The disclosure triangle is the affordance. Ports added inside become its
children, exactly as under `group()`.

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

## A fold is scoped to one direction

Skins render inlets, outlets and config ports in separate lanes — opposite card
edges under `l2r`, separate strips under `t2b`. A fold containing both an inlet
and an outlet would have to draw its header in two lanes or force its children
into one.

So a fold takes the direction of the ports inside it, and mixing directions
raises at declaration time. A config fold renders in the config band, an inlet
fold in the inlet lane.

## Nesting is safe because indentation never moves a pin

Folds nest to any depth. This is only true because depth indents a port row's
**content column** and never its pin column.

A port row is a two-column grid, `{PIN_GUTTER}px 1fr` — the pin in the first
column, label and widget in the second. A pin is placed by a negative offset,
`card_padding + pin_gutter // 2 + pin_protrusion`, which assumes the row begins
at the card edge. Indenting the whole row — as the superseded `_render_group`
did with `pl-2 ml-1` — falsifies that assumption and insets the pin from the
border, silently, once per level.

Indenting the content column instead leaves the pin column's geometry untouched,
so the offset stays correct at any depth and label and widget indent together.
The edge layer is unaffected either way: `_getPinPosition` measures pins with
`getBoundingClientRect()` and follows the pin wherever it lands.

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
