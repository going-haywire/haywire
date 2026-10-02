# Wire types (edge-kinds step 5): design and sub-plans

Settled in the inquisition of 2026-09-30 to 2026-10-02, questions Q1 to Q17. The
sequence overview is [2026-09-28-edge-kinds.md](2026-09-28-edge-kinds.md), step 5.
This document is the design. The detail plans for P and 5.1 to 5.5 are written one
at a time from it, each with its own tasks.

## Goal

A library author can define a new kind of edge, including one that is only drawn
and never executed, with rendering the user can edit per edge. Data types say
which kind they use. `FlowType` is removed. Breaking changes are acceptable,
saved graphs included.

The working name was EdgeKind. The settled name is **wire type** (Q7a): every
port has a data type, and the data type declares its wire type. The data type
says what the value is. The wire type says how it travels and how it is drawn.

## The model

### Roles

A wire type picks one of four roles. The set is closed and owned by the
framework, and framework code branches on the role, never on which wire type it
is (Q3). A new role is a framework change.

| `WireRole` | Meaning | Today |
|---|---|---|
| `DEPENDENT` | assembly walks it backward from a consumer | DATA |
| `SEQUENCE` | the VM walks it forward | CONTROL |
| `IMMEDIATE` | takes effect on write, no engine involved | CALLBACK |
| `VISUAL` | drawn and saved, never executed | none |

`IMMEDIATE` was a `Propagation` value. It moves to the role (Q2), because it was
never a user choice: the code already kept the two apart (`Pipe.is_lazy` versus
`DataPort._is_immediate`). A config port has no wire type at all, which is why the
visual role is not called `NONE` (Q7b).

### Wire types

A wire type is a class that is never instantiated, following the Surface pattern
(Q5, ADR 0009). Its metadata is `ClassVar`s, `__init_subclass__` fills an id map,
and data types reference it by class while everything compares it by id. There is
no registry, no DI provider and no folder scan. Hot reload works through the
registry's unmanaged-module dependency reload: a changed wire-type module reloads,
then the type modules that import it, and `TypeRegistry`'s cascade rebuilds ports
and edges ([base.py:559-600](../../../packages/haywire-core/src/haywire/core/registry/base.py#L559-L600)).

| `ClassVar` | Meaning |
|---|---|
| `role` | one `WireRole` |
| `propagation` | the allowed modes. The first is the default, a single entry means locked, an empty tuple means none |
| `outlet_links`, `inlet_links` | link defaults per direction (Q9a) |
| `glyph` | the pin glyph family the skin's `PinIconResolver` maps to an icon (Q10c) |
| `style` | an `EdgeSettings` subclass holding what the user may edit per edge, or `None` (Q10a) |
| `holds_absence` | fields of types on this wire can hold `None`, and pools drop absent entries (Q14) |
| `id` | optional override of the id's last segment |

The id is derived as `f"{library}:wire:{ClassName}"` with `derive_library_identity`,
the same call `@type` makes for its key (Q7d). Collisions across libraries cannot
happen.

```python
class CallbackWire(WireType):
    role = WireRole.IMMEDIATE
    propagation = (Propagation.EAGER,)
    outlet_links = ONE    # a listener's outlet passes allow_multiple_links=True
    inlet_links = ONE     # a pooled inlet takes many through its container
    glyph = "callback"
    holds_absence = True

@type(wire_type=CallbackWire, label="Callback Signal", color="#ff3c00",
      default=None, widget_key=None, store_strategy=StoreStrategy.NODE_SET)
class CALLBACK(STRING): ...
```

Builtin ships four wire types (Q6, Q16): `DataWire` (`DEPENDENT`), `ControlWire`
(`SEQUENCE`), `CallbackWire` (`IMMEDIATE`, `holds_absence`) and `AnnotationWire`
(`VISUAL`, with a style bag). The first three need `EXEC` and `CALLBACK` in
builtin, which plan P delivers.

### Ports and types

- `@type(wire_type=…)` replaces `flow_type=`. A derived type inherits its parent's.
  `@type` rejects a value type that is not a container and has no wire type,
  declared or inherited, with an error that names the fix (Q8b).
- `DataPort.wire_type` is derived and read-only (Q8a). An ordinary type answers
  from its identity. `ArrayType[T]`, `PooledType[T]` and `ADD[T]` answer with
  T's. Bare `ADD` answers `None` and is the wildcard (Q9c). Config and fold ports
  answer `None`: no pin, no wire. There is no per-port override, mirrors stop
  passing one, and `_configure_port` stops rewriting the flow. Colour derives the
  same way.
- Ports and edges store no wire type in files (Q12).

### Connecting

Only ports with the **same wire type** connect, compared by id, plus the bare-ADD
wildcard (Q9b, the user's call). One function, `wires_match(a, b)`, is true for
equal ids or when either side is `"*"`. The server's `_formal_validation`,
`canvas.vue`'s `_isValidEdge` and auto-wire all use it, through one DOM attribute
`data-pin-wire`. An edge with wildcards at both ends is refused, because it has no
wire type to take (today it links and does nothing).

The consequence accepted with it: a non-standard wire type is an island. Adapters
cannot bridge two wire types. A library that wants its types convertible keeps
them on `DataWire`. Every existing DATA type lands on `DataWire`, so nothing that
connects today stops connecting.

### Link limits

The wire type declares per-direction defaults. A port's own `allow_multiple_links=`
is honoured instead of being silently overwritten, as `DataPort.__post_init__`
does today for DATA and CONTROL ports. Containers keep setting their own (a pooled
inlet takes many). Two mechanism limits hold whatever the port says (Q9a):

- a `SEQUENCE` outlet takes one link, because the VM keeps one transition per
  outlet ([base.py:722-727](../../../packages/haywire-core/src/haywire/core/graph/base.py#L722-L727));
- a `DEPENDENT` inlet takes one link unless its field pools, because two writes
  into one linked slot would make the value depend on order.

### Propagation

`Propagation` keeps its name, its saved key and its menu, with two values, `LAZY`
and `EAGER` (Q7c). An edge's mode must be in its wire type's `propagation`. A
single allowed mode locks it, an empty tuple means the edge has no propagation and
no menu entry. The promoted-outlet lazy lock stays a port fact (ADR 0014).

### Visual wires

A `VISUAL` edge goes through the whole edge lifecycle: link, unlink, detach, save,
draw, select, undo. It builds no adapter chain and no pipe, and has no
propagation, so the data types at its two ends need not match (Q9d). Assembly
already ignores it. Structural validation ignores `VISUAL` pins, so they never
make a node invalid. Its inlet never holds a linked value, so a widget there stays
editable.

### The principle behind the rules (Q8c)

The framework refuses only what breaks, and states each rule by the mechanism that
breaks, not by role. Anything else is up to the implementor. ADR 0003 already took
the same stance for widget visibility. Applied here:

- The `@type` rule refusing a widget on CONTROL and CALLBACK types goes. It only
  guarded the inheritance case, and `as_inlet(widget_key=…)` bypassed it anyway.
- The widget layer's read-only guard extends from "the field holds a linked value"
  to "the field cannot hold an own value". That covers pooled fields, whose
  `_set_own` raises, so the first edit of a widget on a pooled port no longer
  crashes ([pooled_type.py:194-228](../../../barn/haybale-core/haybale_core/types/pooled_type.py#L194-L228)).
- haybale-core drops its container refusals (`ArrayType` of CONTROL or CALLBACK,
  `PooledType` of CONTROL) once a test shows each combination runs.

### Edge style

`EdgeSettings` is a fifth settings flavour, built on the ADR 0022 template:
per-instance cells, an `_edge` back-reference, `_node` always `None` so promotion
is off. A wire type's `style` names the bag class, and that class decides what the
user may edit (Q10a). Field defaults are the wire type's default look. A field the
bag does not declare stays computed: colour from the pin gradient, dash from
validity and the adapter chain, width 2. `DataWire`, `ControlWire` and
`CallbackWire` declare no bag and look as they do today. A field declared with
`graph(src=…)` resolves framework < graph < edge, so a graph can set a default for
all its annotation wires. The existing bag renderer draws the fields in the edge
menu and the properties panel. The bag saves under the edge's `"style"` key,
locally set values only.

Recognised style fields: `color`, `width`, `dash`, `arrow` (none, end, start,
both). Arrows are SVG `marker-end` and `marker-start` with `orient="auto"`, one
marker definition per colour. They sit at the ends only, because an edge is a
single cubic bezier and `marker-mid` has no vertex to draw at (Q10b).

Rendering rules (Q10c):

1. Style values travel in the existing edge sync payload: `EdgeVisualState` gains
   `color`, `width`, `dash` and `arrow`. Wire types get no theme tokens.
2. Precedence: invalid or warning overlay, then the edge's style, then computed. A
   declared `dash` replaces the adapter-chain dash. The chain stays visible in the
   edge menu and the connection-info popup.
3. Selection becomes a class. `_updateEdgeVisualSelection` stops writing an inline
   `strokeWidth`, which today overrides any width
   ([canvas.vue:3352-3355](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L3352-L3355)).
4. The pin glyph family comes from the wire type's `glyph`, replacing
   `PinIconResolver._kind_of`'s flow mapping. An unknown family gets the fallback
   glyph instead of no pin.
5. The drag preview and suggestions keep the anchor pin's colour.

Two theme tokens that are documented but unread get read (Q13): `--hw-edge-selected`
by the selection class, `--hw-edge-default` as the colour fallback when a pin has
none, replacing the hard-coded `#bbbbbb` and `#333333`.

### The immediate path

Two guards, both in one helper `DataPort._fire_immediate` that the immediate branch
of `set_value` ([port.py:389](../../../packages/haywire-core/src/haywire/core/types/port.py#L389))
and the reveal path on unlink ([port.py:738](../../../packages/haywire-core/src/haywire/core/types/port.py#L738))
both call (Q13b):

- **Echo guard.** An edge-driven write to an immediate inlet that equals the value
  the node already sees is stored and fires no `on_change`. This is step 2's
  settled rule ("the node's `on_change` only when the value it sees changes"),
  which the immediate path never implemented.
- **Re-entrancy guard.** A thread-local set holds the immediate inlets on the
  current call stack. A fire that reaches an inlet already in the set is dropped
  and logged as a warning naming the port. The value is still stored. This ends
  every loop after one pass, value-changing loops included, without forbidding the
  two-edge cycle the swinglet route needs (Q4). `hb_relay` crosses a Subgraph
  boundary on the same stack, so one set covers both graphs.

Without them, two callback reroutes wired into each other recurse without end:
`set_value` has no equality check and `Reroute.forward_immediate` writes
unconditionally. Found by reading, not run.

### Absence on callback wires (Q14)

This replaces the "drop an entry equal to the element's default" sentinel.

- `CallbackWire.holds_absence` makes every type declared on it absence-tolerant by
  construction: its field class comes from `_absence_tolerant_field(...)`. No guard
  is needed because a library cannot forget it.
- Callback types declare `default=None`. `@type`'s rule against a `None` primitive
  default exists because saving `None` into a primitive crashes. It exempts types
  on a `holds_absence` wire, and `normalize_and_validate_default` accepts `None`
  for them, `BaseType` included.
- `PooledField` accepts absence when its element does and drops an entry whose
  value is `None`. `_drops_default` and `_element_default` are deleted.
- **Serialization.** The `DataField` base serializes absence as JSON `null` at the
  field-data level, keyed on `accepts_absence()`: `to_dict()` returns `None` when
  the own value is `None` and the field can hold it, and `from_dict(None)` restores
  absence. Subclasses implement the present case only. A field that cannot hold
  absence but holds `None` still fails loudly at save, as today. `null` rather than
  `{"value": None}`, because a dataclass type may have an attribute called `value`.
  `OPTIONAL`'s current `{"value": None}` stays readable.
- **`BaseField` storage** gains absence on `holds_absence` wires: `__post_init__`,
  `reset` and `_set_own` accept `None`, and `_absence_tolerant_field` accepts
  `BaseField`. Today it raises for anything but `PrimitiveField`
  ([base.py:400-419](../../../packages/haywire-core/src/haywire/core/types/base.py#L400-L419)).
  This lifts ADR 0033's primitive-only restriction for this wire only.
- Port declarations do not change. An unlinked plain callback inlet reads `None`
  instead of `""`. Code that reads `.name` on an unlinked dataclass callback inlet
  needs a `None` check.

Why it works through relays: `Pipe.pull` forwards `None` only into a sink that
`accepts_absence()` and otherwise keeps the sink's last value
([pipe.py:56-75](../../../packages/haywire-core/src/haywire/core/types/pipe.py#L56-L75)).
A reroute's ports take the split edge's type, and `hb_grow` and
`reconcile_interface` copy the incoming type, so every port on a callback path
holds absence. Wrapping ports in `OPTIONAL[CALLBACK]` would not have been enough:
an OPTIONAL outlet reports its element as stored type and connects to a plain
`CALLBACK` inlet, where absence is skipped and the subscription goes stale.

### NodeType (Q11, Q11b)

- `NodeData.get_ports()` takes `is_role` and `is_not_role` in place of
  `is_flow_type` and `is_not_flow_type`.
- `NodeData.has_sequence_pins()` answers "does this node carry a SEQUENCE pin". It
  replaces the data walk's stop
  ([data_flow_builder.py:135-137](../../../packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py#L135-L137)),
  `flat_view._is_control_crossed` (deleted, three callers) and the check in
  `GraphNode._stamp_node_type`. Today the data walk checks any CONTROL port and the
  others check pinned ones. After Q8b a config port has no wire type, so the two
  agree.
- `behavior.is_control_node` stays. It answers a different question, what the
  class declares, and it is public API with nine test assertions. Both docstrings
  name the difference.
- Doc drift fixed with it: `structural_validator.py:79-81` says REROUTE carries the
  DATA bit (it does not), the `is_reroute_node` docstring calls a reroute a DATA
  node, and the NodeType docstring claims a CONTROL in/out check nothing performs.
  The claim is removed, not enforced.
- NodeType itself stays. Its split is a follow-up.

### Serialization (Q12)

Derive, do not store. The legacy `edge_type` and port `kwargs.flow_type` keys are
ignored on load and never written. `RemappedEdge.edge_type` goes. Farmhand reports
`wire_type` (the id) and `role` in place of `flow_type`. There is no migration
script, re-saving rewrites a file. When a type's wire type changed between save and
load, the edge fails `_formal_validation` and stays visible as an invalid edge,
where today an unknown `edge_type` drops it with a log line
([base.py:1026-1044](../../../packages/haywire-core/src/haywire/core/graph/base.py#L1026-L1044)).

### The annotation node (Q16 to Q16e)

Builtin ships a visual wire type that users can use: `AnnotationWire`, an
`ANNOTATION` type, an annotation node and a skin with pins on every side. The node
binds its skin by key string, as the reroute node does, so the headless execution
path never imports nicegui
([reroute.py:60-80](../../../packages/haywire-core/src/haywire/barn/builtin/nodes/reroute.py#L60-L80)).

- **Pins.** Each side carries a growing `ADD[ANNOTATION]` inlet and outlet, eight
  slots in all. `ADD[T]` answers T's wire type, so the slots accept annotation
  wires only. Dragging onto a side, the suggestion picks the slot that fits;
  confirming grows a `RESOLVED` pin on that side plus a fresh slot, following the
  boundary nodes' `hb_grow` and `_add_slot`. The user removes a grown pin from the
  pin menu. Several pins on one side spread along that edge.
- **Side in the port id.** The side is recorded in the port id prefix, side plus
  direction plus index, as haybale-testing's `add_port_test` node does with
  `_SIDES`
  ([add_port_test.py:60-110](../../../barn/haybale-testing/haybale_testing/nodes/testbed/add_port_test.py#L60-L110)).
  Indices are never reused, because a port id is part of every edge id attached to
  it.
- **`render_pin`** accepts an explicit per-pin side and derives both the CSS side
  and `data-pin-dir-x/y` from it. That keeps the one-source rule of
  `.insights/project_layout_direction_pin_contract.md`.
- **Hover.** Slots stay hidden until hover with `opacity` or `visibility`, never
  `display:none`, so the canvas's pin index can still measure them. They are also
  revealed on every candidate node while a drag is in progress. The suggestion
  rule compares data-type registry keys today (`sameType`), and `ADD[ANNOTATION]`'s
  key is not `ANNOTATION`'s, so it must compare stored types or use `wires_match`.
- **Content.** A plain multi-line `text` setting (`STRING`, `TextWidget` with its
  `text_modal` pop-out), edited in the properties panel. Double-clicking the card
  opens the existing `text_modal`. No in-place editing, which would fight the
  canvas's keyboard shortcuts. Colour comes from `node.props.color_override`,
  resizing from node sizing.
- **A CONTROL node** (the user's choice). It has a control inlet and outlet, and its
  worker passes control through, forwarding the payload with `out()` like a control
  reroute. CONTROL nodes have no validator rules, so an unlinked one is valid and
  silent ([structural_validator.py:100-105](../../../packages/haywire-core/src/haywire/core/validation/structural_validator.py#L100-L105)).
- **Hidden control pins.** The control ports always exist. A setting decides whether
  unlinked ones are drawn, and a linked one is always drawn. The setting never
  changes execution, and no edge anchors to an undrawn pin.

In step 5 annotation nodes link only to each other, a diagram layer of boxes and
arrows. Linking a note to an ordinary node comes with the "pins anywhere"
follow-up.

### Deletions (Q15)

1. `FlowType` and `FlowType.is_immediate`
2. `Propagation.IMMEDIATE` and its branch in `toggled()`
3. `_accepts_any_flow` and `edge_flow_type`, replaced by `wires_match`
4. the dead `_edge_type is None` branch in `_formal_validation`
5. `EdgeWrapper.is_callback_edge`, `is_control_edge`, `is_data_edge` (tests only)
6. `DataPort.is_callback_pin`, `is_control_pin`, `is_data_pin` (no callers)
7. `FlowAssemblyManager._process_callback_edges`, `get_callback_edges` and the
   `callback_edges` and `callback_topology` statistics keys. Nothing in production
   reads them, and since step 1 they count reroutes as emitters.
8. `validate_edge`: the no-op, its `IStructuralValidator` method, its call at
   [edge_wrapper.py:796](../../../packages/haywire-core/src/haywire/core/edge/edge_wrapper.py#L796)
   and its test. Q3 rules out code hooks, and a kept seam would read as an
   invitation.
9. `PooledField._drops_default` and `_element_default`
10. `PinIconResolver._kind_of`'s flow mapping
11. the DOM attributes `data-pin-flow-type` and `data-pin-any-flow`, and the event
    field `pendingFlowType`
12. `RemappedEdge.edge_type`, and writing the legacy keys

## Sub-plans and sequence (Q17)

```text
P ──► 5.1 ──► 5.2 ──┬──► 5.3 ──┐
                    └──► 5.4 ──┴──► 5.5
```

Each plan carries its own glossary, ADR and architecture-doc edits, landing with
its code. Each starts with the failing tests listed for it.

### P. EXEC and CALLBACK into builtin

The new node wizard's follow-on 2
([landed/2026-09-24-new-node-wizard.md](landed/2026-09-24-new-node-wizard.md), decision 8),
pulled forward as a precondition (Q6b). Detail plan:
[landed/2026-10-02-signal-types-to-builtin.md](landed/2026-10-02-signal-types-to-builtin.md).
Move both types to builtin and update every importer, visiongraph included, with
no re-export. There is no key alias: a script rewrites the saved graphs (14 files
here, one in visiongraph). It also fixes the Python-type lookup, which would
otherwise resolve `dict` to `EXEC` once it is a `haywire-core:` type. The Control, Event and Output
templates stay with the wizard follow-on. It gives a release `haywire init`
project an `EXEC` type, and lets step 5 edit the declarations once, in their final
home.

### 5.1 Wire types and the FlowType sweep, behaviour-preserving

`WireRole`, `WireType` with its id map, the three standard wire types,
`@type(wire_type=…)`, the derivation on ports, `Propagation` reduced to two values
with allowed sets and locks, `wires_match` on the server and in `canvas.vue` with
`data-pin-wire`, `get_ports(is_role=…)` and `has_sequence_pins()`, serialization as
in Q12, Farmhand fields, the deletions. All of the ~200 `FlowType` references and
the 29 explicit `flow_type=` declarations on types move.

Every existing type lands on a wire type that behaves exactly as its flow did, so
the existing suite must pass unchanged. That is the point of keeping this plan
free of rule changes: a red test here is a sweep bug, never an intended change.
Exceptions are tests of deleted API (deletions 5, 6, 8), which go with it.

Verify first: hot reload of a wire type defined in a library, through the
unmanaged-module path.

### 5.2 Rule changes

8c (widget rule dropped, read-only guard for fields without an own value,
container refusals dropped after a test each), 9a (port link setting honoured,
mechanism limits), ADD↔ADD refused (9c), the `VISUAL` lifecycle and validator
exemption (9d), with a test-only `VISUAL` wire type and type in haybale-testing.
Each behaviour change shows up as a deliberate test edit.

Verify first: a widget on a pooled port refuses edits instead of raising; each
container combination runs before its refusal goes.

### 5.3 The immediate path

The echo and re-entrancy guards (Q13b) and callback absence (Q14), including null
serialization in the `DataField` base, absence storage for `BaseField`, pools
dropping absence, `default=None` on `CALLBACK`, `TEST_RECORD_CALLBACK` and
visiongraph's `MULTIFRAME_CALLBACK` (19 references).

Verify first, failing before the change:

- two callback reroutes looped: linking the closing edge ends without
  `RecursionError` and with one warning;
- an immediate pool fed the same subscription twice fires `on_change` once;
- a relay pair across a Subgraph boundary terminates;
- unlinking upstream of a reroute, and upstream of a boundary, removes the
  emitter's pool entry;
- an absent callback value saves and loads as absent, for a primitive and for a
  dataclass callback type;
- every path that writes field data goes through the field's `to_dict` and
  `from_dict`: the port block, `Settings.to_dict` for node and graph bags, the
  clipboard, undo snapshots.

visiongraph's tests do not cover the OAK-D callback path. Check it once in the
running studio.

### 5.4 Edge rendering and the style bag

`EdgeSettings`, the `style` `ClassVar`, the `"style"` key, the payload fields,
`canvas.vue` (style application, arrows, selection class, the two tokens), the
glyph family and fallback glyph, edge menu and properties rendering of the bag.

Verify first: hot reload of a library wire type with a style bag rebinds every
live edge's bag. ADR 0022 deferred library-declared graph bags over exactly this
question; edges rebuild when their ports rebuild and bags round-trip through
`to_dict`, so it is expected to hold, but it is checked before anything is built
on it. Canvas changes are checked in a browser, not only in unit tests
(`.insights/project_multi_canvas_dom_globals.md`).

### 5.5 The annotation wire, type, node and skin

Everything under "The annotation node" above. Depends on P for `EXEC` in builtin,
5.2 for `VISUAL`, and 5.4 for the style bag and arrows.

Verify first: the canvas pin index finds a slot hidden with `opacity` or
`visibility`, and a drag onto a side resolves to the right slot.

## Earlier decisions this revises

- Step 2 settled "`CALLBACK`'s default becomes `""`, callbacks need no absence
  storage" and "an immediate pool drops an entry equal to its element's default".
  Q14 replaces both with `holds_absence` and `default=None`.
- ADR 0039's `IMMEDIATE` propagation value becomes a role. ADR 0039 is amended.
- ADR 0003's example of a pooled type with a dict-editor widget: showing still
  works, editing is refused (Q8c). The ADR text is corrected.
- ADR 0033 restricts absence to `PrimitiveField` storage. Q14 lifts that for types
  on a `holds_absence` wire.
- The overview listed `NodeBehaviorFlags.is_control_node` as unused cleanup. It
  stays (Q11).

## Not in scope

- New roles or execution engines (Q1).
- Swinglets, bidirectional ports. Their route is recorded below (Q4).
- Animating edges when traversed (Q10b). Dropped, not deferred.
- Line types and waypoints (Q10d). Out of scope, not recorded.
- Markdown in annotation nodes. The `text` field stays a string, so it can come
  later without a data change.
- Theme tokens per wire type.
- Adapters across wire types.

## Follow-ups

- **NodeType split** (Q11b). NodeType becomes execution policy only (DATA,
  CONTROL, EVENT, OUTPUT, LOOPBACK). REROUTE and BOUNDARY retire in favour of the
  identity flags `NodeIdentity` already has (`_is_reroute`, `_is_subgraph_input`,
  `_is_subgraph_output`, 41 readers). Findings: two sources for one structural fact,
  validator order that depends on REROUTE and BOUNDARY being checked first, and the
  Graph-node rewriting its NodeType at runtime.
- **Pins anywhere on the card edge** (Q16). Placement as side plus offset, which
  skins honour it, and migrating the annotation node's id-prefix scheme. This is
  also what lets an ordinary node carry annotation pins.
- **Swinglets** (Q4). The expected route: an inlet and outlet pair drawn as one pin,
  linked by two directed `IMMEDIATE` edges drawn as one. The re-entrancy guard
  (Q13b) already stops the pair after one pass. A state machine needs an
  active-state token that persists across frames, which is closer to `SEQUENCE`
  and would be a new role with its own engine.
- **Small item:** the validity colours are hard-coded (`#EF4444` in `ui_edge.py`,
  `#4CAF50` and `#f44336` in `canvas.vue`). Making them theme tokens is new theme
  vocabulary (Q13).

## Docs, glossary and ADR candidates

Collected during the inquisition, written by the plan that lands the code
(feedback: glossary and ADR edits describe what landed).

Glossary:

- new: **Wire type**, **WireRole** and its four values, **edge style** /
  `EdgeSettings`, **annotation node**;
- changed: **FlowType** entries replaced; **Propagation** reduced to lazy and
  eager; **lazy** gains the dirty mark it pushes on write, which is what lets a
  DATA node skip its worker ([base.py:126](../../../packages/haywire-core/src/haywire/core/node/base.py#L126));
  **CALLBACK port** loses "an empty name, which the emitter treats as no
  subscription"; **Edge** keeps *wire* on its avoid list, and the ten or so prose
  uses of "the wire" for an edge become "the edge".

ADRs:

- wire types replace FlowType: Surface pattern, closed roles, same-wire-type
  connection, derived and not stored (5.1);
- ADR 0039 amended: immediate is a role (5.1);
- refuse only what breaks, stated by mechanism, with the ADR 0003 correction (5.2);
- callback absence, superseding step 2's sentinel and ADR 0033's restriction for
  this wire (5.3); the immediate guards may share it;
- `EdgeSettings` as the fifth settings flavour (5.4).

Doc drift found on the way:

- [hot-reload-arch.md:19, 91, 208](../../architecture/hot-reload/hot-reload-arch.md#L19)
  names an `EdgeRegistry` that does not exist. Edges rebuild through the node
  registry and adapter chains. The new wire-type map must not take that name
  either.
- [datatype-canon.md:50](../../components/datatypes/datatype-canon.md#L50)
  describes `flow_type` and says CONTROL and CALLBACK types get no widget.
- `decorator.py:75` and `identity.py:41` list "DATA, CTRL, or NONE".
- The callbacks architecture doc describes the empty-name unsubscribe.

## Facts found on the way, fixed by these plans

| Found | Fixed by |
|---|---|
| A config port reloads as DATA: `to_dict` skips `NONE`, `from_spec` fills in DATA ([port.py:873](../../../packages/haywire-core/src/haywire/core/types/port.py#L873), [:946](../../../packages/haywire-core/src/haywire/core/types/port.py#L946)) | Q8a, Q12 |
| `ADD[T]` is always DATA; `_wrapped_identity` copies no flow | Q8a |
| The container `_configure_port` walk can loop on an undeclared primitive element (read, not run) | Q8a |
| Auto-wire has no ADD exemption | Q9b, Q9c |
| Selection's inline `strokeWidth` overrides the edge's | Q10c |
| An unknown pin family draws no pin | Q10c |
| A widget on a pooled port raises on first edit | Q8c |
| A closed loop of immediate edges recurses (read, not run) | Q13b |
