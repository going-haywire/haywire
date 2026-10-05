# Wire types (edge-kinds step 5): design and sub-plans

Settled in the inquisition of 2026-09-30 to 2026-10-02, questions Q1 to Q17,
reviewed against the code on 2026-10-03 and settled further in a second
inquisition the same day, Q18 to Q33 (see [Decisions of 2026-10-03](#decisions-of-2026-10-03-q18-to-q33)). This
is step 5 of the edge-kinds sequence, whose overview is closed
([landed/2026-09-28-edge-kinds.md](landed/2026-09-28-edge-kinds.md); steps 0 to 4
landed and are on `origin/master`). This document is the design and, from here on,
the status source. The detail plans for P and 5.1 to 5.5 are written one at a time
from it, each with its own tasks.

## Status — 2026-10-03

| Plan | Work | Status | Detail plan | Next |
|---|---|---|---|---|
| P | `EXEC` and `CALLBACK` into builtin | **Merged** into local `master` 2026-10-03 (both repos, fast-forward; gate 5975 passed, visiongraph 29 passed) | [landed/2026-10-02-signal-types-to-builtin.md](landed/2026-10-02-signal-types-to-builtin.md) | push both repos |
| 5.1 | Wire types and the FlowType sweep, behaviour-preserving | **Landed** on branch `wire-types-5-1` (both repos), not merged | [2026-10-03-wire-types-5-1-sweep.md](2026-10-03-wire-types-5-1-sweep.md) | merge |
| 5.2 | Rule changes | Designed, reviewed, O1 settled (Q21) | to write | after 5.1 |
| 5.3 | The immediate path | Designed, reviewed, O2 to O4 settled (Q22 to Q24) | to write | after 5.2 |
| 5.4 | Edge rendering and the style bag | Designed, reviewed | to write | after 5.2 and D's design round |
| 5.5 | The annotation wire, type, node and skin | Designed, reviewed | to write | after 5.3 and 5.4 |
| D | Edge appearance defaults (graph tier, UX colours) | **Design round owed** | none | design after 5.2, beside 5.3; code after 5.4 (Q32) |

5.1 also made an unknown `pin_kind` draw the fallback glyph (`_from_map` always ends in `fallback`), so 5.4 has no fallback-glyph work left.

Reviewed against the code on 2026-10-03. The corrections are folded into the
sections below and listed in [Review corrections](#review-corrections-2026-10-03).
The decisions of the second inquisition are folded in the same way.

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
| `pin_kind` | the key the skin's `PinIconResolver` looks up in its icon map, such as `"control"` (Q10c, Q30). It is not an icon: a real icon stays on the type (`icon_in`, `icon_out`) |
| `style` | an `EdgeSettings` subclass holding what the user may edit per edge, or `None` (Q10a) |
| `holds_absence` | fields of types on this wire can hold `None`, and pools drop absent entries (Q14) |
| `id` | optional override of the id's last segment |

The id is derived as `f"{library}:wire:{ClassName}"` with `derive_library_identity`,
the same call `@type` makes for its key (Q7d). Collisions across libraries cannot
happen. `derive_library_identity` falls back to `__system__` when no ancestor
module carries a `Library`, so the builtin wire types live under
`haywire.barn.builtin`, not `haywire.core`.

The id map behaves like Surface's `_SURFACE_BY_ID`
([surface.py:40-78](../../../packages/haywire-core/src/haywire/ui/surface/surface.py#L40-L78)):

- a reload of the same module and qualname replaces the entry;
- the same id from a different module raises `ValueError`, so moving a wire class
  to another module of its library needs a restart;
- removing a library leaves its ids in the map. Nothing can reach them, because
  the types that named them are gone too.

A root-level wire module is reloaded by every registry on its own timer. That
gives several class objects for one wire type, and comparing by id is the only
safe comparison. Builtin runs with `file_watcher=False`, so builtin wire types
never hot-reload.

```python
class CallbackWire(WireType):
    role = WireRole.IMMEDIATE
    propagation = ()      # takes effect on write: no mode to choose (Q19)
    outlet_links = ONE    # a listener's outlet passes allow_multiple_links=True
    inlet_links = ONE     # a pooled inlet takes many through its container
    pin_kind = "callback"
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
- `OPTIONAL[T]` answers T's wire type, like the other wrappers (Q21). Today
  `OPTIONAL` is declared DATA, and `_wrapped_identity` copies no flow
  ([base.py:475-479](../../../packages/haywire-core/src/haywire/core/types/base.py#L475-L479)),
  so `OPTIONAL[EXEC]` is a data port. All 41 uses of `OPTIONAL` wrap data types, so
  nothing existing changes, but it is a rule change and lands in 5.2.
  `OPTIONAL[CALLBACK]` is redundant once callback inlets hold absence, and stays
  allowed: it breaks nothing (Q8c).
- Ports and edges store no wire type in files (Q12).

### Connecting

Only ports with the **same wire type** connect, compared by id, plus the bare-ADD
wildcard (Q9b, the user's call). One function, `wires_match(a, b)`, is true for
equal ids or when either side is `"*"`. The server's `_formal_validation`,
`canvas.vue`'s `_isValidEdge` and auto-wire all use it, through one DOM attribute
`data-pin-wire`. An edge with wildcards at both ends is refused, because it has no
wire type to take (today it links and does nothing). The wildcard is bare ADD only.

**Ghost pins are not wire participants.** A node's root ghost pins (`root_in`,
`root_out`) are its fallback anchor for an edge whose port is missing or that found
no matching port (Q31). A ghost never starts, ends or joins a user drag. A port can
be removed and re-created at any time. Its edges stay in the graph, draw to the
ghost through the canvas's `port>>parent>>root` fallback, and resolve to the pin
again when a port with that id comes back. The user never redraws them. A ghost
never enters `wires_match`:

- the canvas never starts a drag on a ghost (canvas.vue:1550), never commits to
  one (:1536), and leaves ghosts out of the pin index (:2735). The `eitherIsGhost`
  branch of `_isValidEdge` (:3647) is therefore unreachable and goes;
- the ghost marker moves from `data-pin-flow-type="ghost"` to an attribute of its
  own, `data-pin-ghost`. Its readers are canvas.vue (1536, 1550, the pin-menu
  selector at 1669, 2735), `pin_render.py:349`, three harness tests
  (`test_node_sizing`, `test_edge_drag_cost`, `test_boundary_skin`), `skin-canon.md`
  and the glossary;
- auto-wire with no matching port still targets `root_in` or `root_out`, as today
  ([visual_layer.py:1088-1095](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py#L1088-L1095)).

**An edge that fails validation is never rewritten (Q20).** While it fails, its
wire type comes from whichever end resolves, and only for drawing (look, pin kind).
With neither end resolving it has no wire type and draws in the default look. Its
saved propagation is not clamped and its style is not rebound or dropped. Both
happen once, when the edge validates again. `_formal_validation` already keeps
such an edge as invalid ("Ports not found"), and Q12's rule for a changed wire type
works the same way. The ghost stands in for the missing pin, and a missing port
never costs the user work. Scenario: an edge saved `LAZY` into the dynamic port
`in_3` keeps `LAZY` while `in_3` is gone, even if the surviving outlet's wire type
would not allow it, and gets it back with `in_3`.

**Removing a pin keeps its edges.** The pin menu's removal (`remove_port`, then
`rejig`) detaches the port's edges and keeps them in the graph, drawn to the
ghost ([data.py:372-386](../../../packages/haywire-core/src/haywire/core/node/data.py#L372-L386)).
It is not undoable. This stays the rule for every node, annotation nodes included
(Q28). An annotation edge whose pin was removed never resolves again, because
annotation pin indices are never reused. It waits on the ghost until the user
deletes it. Undoable pin removal is a follow-up.

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

A callback edge has no propagation (Q19): `CallbackWire.propagation = ()`, like
`VISUAL`. Immediate is the role, not a mode, which is what Q2 already said. Eager
means "applied on execute" (ADR 0039), and a callback inlet applies on write, so a
locked `EAGER` would have been a misleading label. What follows, all in 5.1:

- `EdgeWrapper.propagation` answers `None`. The pipe still pushes, because
  `Pipe.is_lazy` tests `is Propagation.LAZY`
  ([pipe.py:101](../../../packages/haywire-core/src/haywire/core/types/pipe.py#L101)).
- The edge menu's propagation row disappears through its existing
  `if mode is None: return`
  ([edge.py:248-250](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py#L248-L250)),
  and its `IMMEDIATE` label, icon and locked tooltip go (deletion 2). The
  properties inspector's propagation panel (`introspect/edge.py:110-151`) hides
  for such an edge too.
- Farmhand reports `propagation: null` and `role: "immediate"`
  (`editor_tools.py:491`).
- The edge saves no `propagation` key.
- The role stays visible in the connection-info popup's header, which shows the
  edge's wire type where it shows `edge_type` today (connection_info_popup.py:46),
  and in the pin's kind.

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
`CallbackWire` declare no bag and look as they do today. The existing bag renderer
(`render_settings`) draws the fields in the edge menu and the `EdgeInspector`
panels. The bag saves under the edge's `"style"` key, locally set values only.

5.4 implements no graph tier. Defaults above the edge (a graph or framework
default for every edge) are design round D's. D's design runs before the 5.4
detail plan (Q32), because its answer on precedence decides how 5.4 defines a
wire's default look: as plain field defaults, or as a tier of its own. 5.4 computes
the effective style in one server-side function, so D's code adds a tier there
without touching the canvas.

**The bag's lifetime.** `EdgeWrapper.build()` creates the bag from the derived wire
type and re-derives it on every rebuild. Validation re-runs `build()` and `link()`
on the same wrapper ([validation.py:346-358](../../../packages/haywire-core/src/haywire/core/graph/validation.py#L346-L358)),
and nothing re-creates the edge. That one place covers a hot reload of the wire
type and a bare-ADD slot growing into a typed port. A bag is bound only while the
edge validates. An edge that fails validation keeps its saved dict verbatim (Q20,
see [Connecting](#connecting)). A new bag class takes the old bag's saved dict
through `to_dict` and `from_dict`. Keys the new class does not declare are skipped
and gone at the next save, as node settings bags do today
([settings.py:613-617](../../../packages/haywire-core/src/haywire/core/settings/settings.py#L613-L617), Q26). Paste and Subgraph instantiation carry `"style"`
through `RemappedEdge`, together with `propagation`, which both drop today
([graph_actions.py:587-596](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L587-L596),
[subgraph.py:212-219](../../../packages/haywire-core/src/haywire/core/graph/subgraph.py#L212-L219)). Undo keeps the wrapper and needs nothing.

Recognised style fields: `color`, `width`, `dash`, `arrow` (none, end, start,
both). Arrows are SVG markers, one definition per colour: `marker-end` with
`orient="auto"` and `marker-start` with `orient="auto-start-reverse"` (plain `auto`
points the start arrow the wrong way). `refX` insets the tip so it does not sit
under the pin. They sit at the ends only, because an edge is a single cubic bezier
and `marker-mid` has no vertex to draw at (Q10b).

Rendering rules (Q10c):

1. Style values travel in the existing edge sync payload. `EdgeVisualState`
   ([ui_edge.py:28-63](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py#L28-L63))
   already carries `stroke_color`, `stroke_width` and `stroke_dasharray`, so only
   `arrow` is new. Its `__eq__` compares the stroke fields only and must include
   `arrow`, or an arrow-only change is deduplicated away. A style edit calls
   `edge.redraw()`, because the visual state is otherwise refreshed only by
   validation. Wire types get no theme tokens.
2. Precedence: invalid or warning overlay, then the edge's style, then computed. A
   declared `dash` replaces the adapter-chain dash. The chain stays visible in the
   edge menu and the connection-info popup.
3. Selection becomes a class. `_updateEdgeVisualSelection` stops writing an inline
   `strokeWidth`, which today overrides any width
   ([canvas.vue:3352-3355](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L3352-L3355)).
   `.connection-active` (:3994-3997) sets width and colour with `!important` and
   overrides a styled edge the same way. Both keep today's look in 5.4. Their
   colours and how they combine with a styled width (a CSS variable for the width)
   are design round D's.
4. The pin's kind comes from the wire type's `pin_kind`, replacing
   `PinIconResolver._kind_of`'s flow mapping. This lands in 5.1 (Q29): the three
   standard wires declare `"data"`, `"control"` and `"callback"`, so every icon
   stays the same. The lookup order is unchanged: an icon declared on the port or
   type wins, then the skin's map by `<kind>_<direction>[_multi]`, then
   `"fallback"`. Two cases need care:
   - A bare ADD slot has no wire type, and `resolve` returns `None` before it reads
     the declared icon
     ([pin_icons.py:71-73](../../../packages/haywire-core/src/haywire/ui/skin/pin_icons.py#L71-L73)),
     so without a fix every boundary-node slot loses its pin. The resolver's `None`
     gate goes: `DataPort.has_pin()` already decides whether a pin exists, so the
     slot keeps its declared `add_circle`.
   - `compound` is not a property of the wire. It stays a refinement for a
     `CompoundType` on `DataWire`, as today.

   What 5.4 adds is the fallback glyph for a `pin_kind` the skin's map does not
   know. That only matters once a library or the test-only `VISUAL` wire brings
   one.
5. The drag preview and suggestions keep the anchor pin's colour.

### The immediate path

Two guards, both in one helper `DataPort._fire_immediate` that the immediate branch
of `set_value` ([port.py:389](../../../packages/haywire-core/src/haywire/core/types/port.py#L389))
and the reveal path on unlink ([port.py:738](../../../packages/haywire-core/src/haywire/core/types/port.py#L738))
both call (Q13b):

- **Echo guard.** An edge-driven write to an immediate inlet that equals the value
  the node already sees is stored and fires no `on_change`. This is step 2's
  settled rule ("the node's `on_change` only when the value it sees changes"),
  which `set_value`'s immediate branch never implemented. The reveal path already
  does ([port.py:736](../../../packages/haywire-core/src/haywire/core/types/port.py#L736)),
  and the guard reuses its `_same_value`, which treats a comparison that raises
  (numpy arrays) as "changed". That is the safe direction.
- **Re-entrancy guard.** A thread-local set holds the immediate inlets on the
  current call stack. A fire that reaches an inlet already in the set is dropped
  and logged as a warning naming the port. The value is not stored either (Q24):
  what an immediate inlet holds is always what its node was last told, so the echo
  guard's comparison stays honest. This ends every loop after one pass,
  value-changing loops included, without forbidding the two-edge cycle the
  swinglet route needs (Q4). `hb_relay` crosses a Subgraph boundary on the same
  stack, with no thread hop, so one set covers both graphs. The cost: in a loop,
  the upstream outlet and the dropped inlet disagree until the next write. That is
  what cutting a loop after one pass means.

  Scenario: listener → reroute A → node T (rewrites the name) → reroute B → A. The
  listener writes `"x"`. A fires, and the loop returns to A with `"x2"`, which is
  dropped, and A keeps `"x"`. When the listener later writes `"x2"` itself, it
  differs from `"x"` and fires. If the dropped value had been stored, the echo
  guard would suppress that write, and the node would never hear of a value it
  holds.

Without them, two callback reroutes wired into each other recurse until
`RecursionError`: `set_value` has no equality check and `Reroute.forward_immediate`
writes unconditionally. Linking the closing edge starts it through `_housekeeping`.
No link-time check catches it, and the assembly cycle check runs too late.
Confirmed by tracing on 2026-10-03.

### Absence on callback wires (Q14)

This replaces the "drop an entry equal to the element's default" sentinel.

- `CallbackWire.holds_absence` makes every type declared on it absence-tolerant by
  construction. The wrapping happens in `create_field`, not in `@type`: assigning
  `field_class` after the decorator is an established pattern (`specs.py:47,80`,
  haybale-testing's `test_types.py`), and a wrap at decoration time would be
  silently lost. In `create_field` a library cannot forget it.
- The wrap is a variant of `_absence_tolerant_field`, not that function itself.
  The existing one is built for wrappers. Its `get_stored_type` returns
  `element_type_cls`
  ([base.py:436-445](../../../packages/haywire-core/src/haywire/core/types/base.py#L436-L445)),
  which for `CALLBACK` is `str`. That would break the reroute split, `hb_grow`,
  adapters and pin rendering. The variant keeps the type's own stored type and
  does not hard-code `PrimitiveField` storage for `None`.
- Callback types declare `default=None`. `@type`'s rule against a `None` primitive
  default exists because saving `None` into a primitive crashes. It exempts types
  on a `holds_absence` wire, and `normalize_and_validate_default` accepts `None`
  for them, `BaseType` included.
- **A `None` default becomes empty `default_kwargs` (Q22).** On a `holds_absence`
  wire, "no default" means absent, for both storages. `PrimitiveField` already
  starts at `None` when `default_kwargs` has no `"value"`
  ([fields.py:298-303](../../../packages/haywire-core/src/haywire/core/types/fields.py#L298-L303)).
  The `BaseField` side of the variant skips the constructor in `__post_init__` and
  `reset`, which otherwise build `type_cls(**default_kwargs)`, a dataclass with
  `name=""`: the very sentinel Q14 removes. `default_kwargs` keeps its `Dict` type,
  and `_new_linked_slot` works unchanged. A type on a `holds_absence` wire that
  declares a present default is allowed, and its unlinked inlet reads that value.
- **Old saves holding `""` (Q23): an accepted break.** Reroute outlets count as set
  by the node (`port.py:397`) and were saved holding `{"value": ""}`.
  - A relay with something upstream heals itself. It takes its value from
    upstream on load, whatever it saved. Checked 2026-10-03 by reloading a
    listener → reroute → emitter graph whose reroute values were overwritten with
    `"stale"`; the emitter subscribed to the real name.
  - What remains is an orphaned callback relay (nothing upstream) whose outlet
    holds `""`. After 5.3 that `""` is a real name that pools no longer drop, and a
    re-save writes it back. The symptom is an emitter with an empty-name
    subscription; relinking or deleting the relay fixes it.
  - None of the 16 saved graphs in either repo has a callback relay. Relay-side
    persistence, or a legacy read of `""` (an in-band sentinel), was rejected as
    mechanism for files that may not exist.
- `PooledField` accepts absence when its element does and drops an entry whose
  value is `None`. `_drops_default` and `_element_default` are deleted.
- **Serialization.** The `DataField` base serializes absence as JSON `null` at the
  field-data level, keyed on `accepts_absence()`: `to_dict()` returns `None` when
  the own value is `None` and the field can hold it, and `from_dict(None)` restores
  absence. Subclasses implement the present case only. A field that cannot hold
  absence but holds `None` still fails loudly at save, as today. `null` rather than
  `{"value": None}`, because a dataclass type may have an attribute called `value`.
  `OPTIONAL`'s current `{"value": None}` stays readable.
- The base's `to_dict` and `from_dict` are stubs today. `to_dict` returns the
  decorator default ([fields.py:241-256](../../../packages/haywire-core/src/haywire/core/types/fields.py#L241-L256)).
  `ArrayField` and `MapsStringField` inherit it, so their port values are never
  saved (see Small items). `PooledField` inherits it too, but a pool's contents
  come from its edges, so nothing is lost there. 5.3 fixes the array and map case
  as part of the hook (Q25). The base becomes a template method:
  absence handled in the base, the present case in a hook. Every `from_dict`
  override (`PrimitiveField`, `BaseField`, the builtin INT/FLOAT/STRING specs, the
  haybale-testing fields) moves to the hook, because each fails on a `None`
  payload today. The `-> dict` return types of `_serialize_value` and
  `PortDefaultWidgetModel.as_default` widen to allow `None`.
- Only the port block goes through field `to_dict` and `from_dict` (`DataPort.to_dict`,
  `from_spec`; the clipboard and the undo actions that serialize ports reuse it).
  Node and graph settings bags do not. They write the raw own value, and `None`
  already round-trips there as JSON `null` (`settings.py:562-623`).
- **`BaseField` storage** gains absence on `holds_absence` wires: `__post_init__`,
  `reset` and `_set_own` accept `None`, through the variant above. Today
  `_absence_tolerant_field` raises for anything but `PrimitiveField`
  ([base.py:400-420](../../../packages/haywire-core/src/haywire/core/types/base.py#L400-L420)).
  This lifts ADR 0033's primitive-only restriction for this wire only.
- Port declarations do not change. An unlinked plain callback inlet reads `None`
  instead of `""`. No product node code reads a plain callback inlet. Framework
  readers (`forward_immediate`, both `hb_relay`, `_resync_immediate_pairs`) only
  forward or log. The six nodes that read a callback pool are safe, because pools
  drop `None` entries. Five test assertions on `""` change
  (`test_callback_values.py`, `test_callback_boundary_relay.py`,
  `test_disconnect_semantics.py`).

Why it works through relays: `Pipe.pull` forwards `None` only into a sink that
`accepts_absence()` and otherwise keeps the sink's last value
([pipe.py:56-75](../../../packages/haywire-core/src/haywire/core/types/pipe.py#L56-L75)).
A reroute's ports take the split edge's type, and `hb_grow` and
`reconcile_interface` copy the incoming type, so every port on a callback path
holds absence. Wrapping ports in `OPTIONAL[CALLBACK]` would not have been enough.
An OPTIONAL outlet reports its element as stored type. Since `OPTIONAL[T]` answers
T's wire type (Q21), it connects to a plain `CALLBACK` inlet. Without Q14 absence
would be skipped there and the subscription would go stale. With Q14 the plain
inlet holds absence itself, so the edge works. Today the flow check refuses it,
because `OPTIONAL` is declared DATA.

### NodeType (Q11, Q11b)

- `NodeData.get_ports()` takes `is_role` and `is_not_role` in place of
  `is_flow_type` and `is_not_flow_type`.
- `NodeData.has_sequence_pins()` answers "does this node carry a SEQUENCE pin". It
  replaces the data walk's stop
  ([data_flow_builder.py:135-137](../../../packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py#L135-L137)),
  `flat_view._is_control_crossed` (deleted, three callers) and the check in
  `GraphNode._stamp_node_type`. Today the data walk checks any CONTROL port and the
  others check pinned ones. They already agree in practice: config ports are forced
  to NONE, reload as DATA, and containers of CONTROL are refused. After Q8b a config
  port has no wire type, so the agreement is by construction.
- `behavior.is_control_node` stays. It answers a different question, what the
  node's behaviour flags say, and it is public API with nine test assertions and no
  production reader. For a class that is what it declares. A Graph-node's flags are
  restamped from its pins by `set_node_type`, so there it follows the pins. Both
  docstrings name the difference.
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
  confirming grows a `RESOLVED` pin on that side plus a fresh slot. The template is
  `add_port_test`'s decided-slot branch (`ADD[T]` keeps T, several prefixes), not
  the boundary nodes' `hb_grow`, which has one prefix and one direction and adopts
  the other end's type. The user removes a grown pin from the pin menu. Several
  pins on one side spread along that edge.
- **Side in the port id.** The side is recorded in the port id prefix, side plus
  direction plus index. `add_port_test` has the id scheme, prefix plus an index
  from `_next_index` that is never reused
  ([add_port_test.py:41-128](../../../barn/haybale-testing/haybale_testing/nodes/testbed/add_port_test.py#L41-L128)).
  Its `_SIDES` are slot families (in, out, str), not card edges. Indices are never
  reused, because a port id is part of every edge id attached to it.
- **`render_pin` stays as it is.** Each side-and-direction pair maps to exactly
  one `LayoutDirection`, and `render_pin` derives both the CSS side and
  `data-pin-dir-x/y` from the layout it gets
  ([pin_render.py:215-216](../../../packages/haywire-core/src/haywire/ui/skin/pin_render.py#L215-L216)).
  The skin passes a per-pin layout, which keeps the one-source rule of
  `.insights/project_layout_direction_pin_contract.md`. The skin still picks the
  axis-specific `card_padding`. No skin places pins on all four sides today, so the
  skin itself is new work.
- **Hover.** Slots stay hidden until hover with `visibility: hidden`, never
  `display:none`. A `display:none` pin is indexed at the viewport origin. An
  `opacity: 0` slot stays clickable and can start a drag by accident. A hidden
  slot cannot be a click target, so a drop on it goes through the pin index's
  distance hit and `nearestCompatiblePin`, which works. While a drag is in
  progress the slots show on every candidate node, which needs a container class
  on the canvas for the drag (none exists). The suggestion rule needs no change:
  `sameType` compares `data-pin-data-type`, which is the stored type's key, and
  `ADD[ANNOTATION]`'s stored type is `ANNOTATION`
  ([add.py:24-28](../../../packages/haywire-core/src/haywire/barn/builtin/types/add.py#L24-L28)).
- **Content.** A plain multi-line `text` setting (`STRING`, `TextWidget` with its
  `text_modal` pop-out), edited in the properties panel. `TextWidget`'s inline
  field is single-line, and the modal is where multi-line text is edited.
  Double-clicking the card opens the existing `text_modal`. No double-click hook
  exists in the canvas or in Python, so this is new wiring, likely a skin-level
  `.on('dblclick')`. No in-place editing, which would fight the canvas's keyboard
  shortcuts. Colour comes from `node.props.color_override`, resizing from node
  sizing.
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

All in 5.1 unless marked.

1. `FlowType` and `FlowType.is_immediate`
2. `Propagation.IMMEDIATE`: its branch in `toggled()`, the refusal in
   `EdgeWrapper.__init__` and the lock (`edge_wrapper.py:155, 276, 293`), and its
   label, icon and locked tooltip in the edge menu (`edge.py:224-232`). An edge on
   an immediate or visual wire has no propagation (Q19)
3. `_accepts_any_flow` and `edge_flow_type`, replaced by `wires_match`
4. the dead `_edge_type is None` branch in `_formal_validation`
5. `EdgeWrapper.is_callback_edge`, `is_control_edge`, `is_data_edge` (tests only)
6. `DataPort.is_callback_pin`, `is_control_pin`, `is_data_pin` (no callers)
7. `FlowAssemblyManager._process_callback_edges`, `get_callback_edges` and the
   `callback_edges` and `callback_topology` statistics keys. Nothing in production
   reads them, and since step 1 they count reroutes as emitters. With them go
   `get_callback_triggers`, `_callback_triggers`, the per-flow `emits_callbacks`
   and `receives_callbacks` (`flow_assembly_manager.py:434, 498-499`) and the
   `callback_topology` passthrough (`interpreter.py:383`).
8. `validate_edge`: the no-op, its `IStructuralValidator` method, its call at
   [edge_wrapper.py:796](../../../packages/haywire-core/src/haywire/core/edge/edge_wrapper.py#L796)
   and its test. Q3 rules out code hooks, and a kept seam would read as an
   invitation.
9. `PooledField._drops_default` and `_element_default` (5.3, with Q14)
10. `PinIconResolver._kind_of`'s flow mapping and the resolver's `None` gate,
    replaced by the wire type's `pin_kind` and `DataPort.has_pin()` (Q29, Q30)
11. the DOM attributes `data-pin-flow-type` and `data-pin-any-flow`, and the event
    field `pendingFlowType` (also in `event_definitions.py:356`, the generated
    `graph_events.js` and `context_menu.py:876`). The ghost marker moves to
    `data-pin-ghost` (see [Connecting](#connecting)), and `_isValidEdge`'s dead
    `eitherIsGhost` branch goes
12. `RemappedEdge.edge_type`, and writing the legacy keys

## Sub-plans and sequence (Q17)

```text
P ──► 5.1 ──► 5.2 ──┬──► 5.3 ────────────────┐
                    └──► D (design) ──► 5.4 ──┴──► 5.5
                                         └──► D (code)
```

D's design round runs beside 5.3 and before the 5.4 detail plan; D's code is its
own plan after 5.4 (Q32).

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

`WireRole`, `WireType` with its id map, the three standard wire types with their
`pin_kind`, `@type(wire_type=…)`, the derivation on ports, `Propagation` reduced to
two values with allowed sets and locks, callback edges without propagation and the
UI that hides for them (Q19), edges that fail validation left unrewritten (Q20),
`wires_match` on the server and in `canvas.vue` with `data-pin-wire` and
`data-pin-ghost`, `get_ports(is_role=…)` and `has_sequence_pins()`, serialization
as in Q12, Farmhand fields, the deletions marked for it.

Size, counted 2026-10-03:

- `FlowType`: about 225 Python references: 141 in this repo's production code,
  13 in visiongraph, 71 in 21 test files;
- lowercase `flow_type`: 136 production and 53 test references;
- the front end: 14 in `canvas.vue`, 3 in the generated `graph_events.js`;
- docs: 25 references in 12 files under `docs/`, plus the generated `flow_type`
  lines in `barn/*/docs`. The generator emits them (`extract.py:20`,
  `inspector.py:84`), so the library docs are regenerated with
  `haywire docs --all`. No test catches that drift;
- declarations: 42 explicit `flow_type=` on types: 29 here, 9 in visiongraph,
  4 in test types.

Every existing type lands on a wire type that behaves exactly as its flow did. The
promise is **no changed behavioural assertion**: a red behavioural test is a sweep
bug, never an intended change. Mechanical test edits are expected and go with the
sweep:

- tests of deleted API (deletions 5, 6, 8) and the `Propagation.IMMEDIATE`
  assertions (`test_edge_propagation.py`, `test_any_flow_slot.py`,
  `test_session_context_menu_provider.py`), which become "no propagation" (Q19);
- the resolver tests that key on flow (`tests/ui/skin/test_pin_icon_resolver.py`,
  such as `test_a_pinless_flow_type_resolves_to_no_icon`), which move to
  `pin_kind` and `has_pin()`;
- about ten tests that build `DataPort(flow_type=…)` directly (`tests/ui/widget/`,
  `tests/ui/skin/`, `test_data_inlet_arity`, `test_unlink_reveals_own_value`);
- fakes with a `get_ports(is_flow_type=)` signature (`test_boundary_nodes.py:33`,
  `test_split_edge_reroute.py:247`);
- Farmhand `flow_type` keys (`test_graph_editor_tools.py`, `test_inspector.py`);
- `test_load_degradation.py:51-57`, which poisons `edge_type`. Once the key is
  ignored the edge loads, so the test needs another way to make an edge fail;
- `test_primitive_type_default.py:29`, which declares a type without a flow.
  Q8b's refusal is a rule change, so it lands in 5.2, not here;
- the ghost marker's three harness tests and `test_pin_any_flow.py`.

Verify first: hot reload of a wire type defined in a library, through the
unmanaged-module path. Cover a wire module at the library root (every registry
reloads it on its own timer), one inside `types/` (the "demoted component" path
logs a re-promote warning), a root-package import (`from mylib import W` matches
no scope prefix and does not cascade), and a wire type used across libraries (the
cascade only reaches a library that lists the defining one in `linked_libraries`).

### 5.2 Rule changes

8c (widget rule dropped, read-only guard for fields without an own value,
container refusals dropped after a test each), 8b (`@type` refuses a value type
with no wire type), 9a (port link setting honoured, mechanism limits), ADD↔ADD
refused (9c), `OPTIONAL[T]` answering T's wire type (Q21), the `VISUAL` lifecycle and validator
exemption (9d), with a test-only `VISUAL` wire type and type in haybale-testing.
Each behaviour change shows up as a deliberate test edit.

Verify first: a widget on a pooled port refuses edits instead of raising (today
`PooledField.set_value` raises `ValueError` before `_set_own` is reached,
`pooled_type.py:209-210`); each container combination runs before its refusal
goes.

### 5.3 The immediate path

The echo and re-entrancy guards (Q13b) and callback absence (Q14), including null
serialization in the `DataField` base, absence storage for `BaseField`, pools
dropping absence, `default=None` on `CALLBACK`, `TEST_RECORD_CALLBACK` and
visiongraph's `MULTIFRAME_CALLBACK` (19 references), the array and map
serialization fix (Q25), and deletion 9. Its decisions are Q22 (absent defaults),
Q23 (old saves) and Q24 (dropped fires store nothing).

Verify first, failing before the change:

- two callback reroutes looped: linking the closing edge ends without
  `RecursionError` and with one warning, and the dropped inlet keeps the value it
  held before (Q24);
- an immediate pool fed the same subscription twice fires `on_change` once;
- a relay pair across a Subgraph boundary terminates;
- unlinking upstream of a reroute, and upstream of a boundary, removes the
  emitter's pool entry;
- an absent callback value saves and loads as absent, for a primitive and for a
  dataclass callback type;
- every path that writes port field data goes through the field's `to_dict` and
  `from_dict`: the port block, the clipboard, and the undo actions that serialize
  ports (Collapse, Expand, Detach, Promote, `_DropSubgraph`). Settings bags are
  not on this path and already store `None` as `null`;
- an `ArrayField` and a `MapsStringField` port value survive save and load (they
  do not today);
- an unlinked dataclass callback inlet reads absent, not a dataclass with
  `name=""` (Q22);
- a callback relay with something upstream takes its value from upstream on
  load, whatever it saved (holds today; it guards Q23's accepted break).

visiongraph's tests do not cover the OAK-D callback path. Check it once in the
running studio.

### 5.4 Edge rendering and the style bag

`EdgeSettings`, the `style` `ClassVar`, the `"style"` key, the bag's lifetime in
`build()` (bound only while the edge validates, Q20; unknown keys skipped, Q26),
`RemappedEdge` carrying style and propagation (Q27), the `arrow` payload field and
`__eq__`, `canvas.vue` (style application, arrows, selection class with today's
look), the fallback glyph for an unknown `pin_kind`, edge menu and `EdgeInspector`
rendering of the bag. No graph tier and no new colour vocabulary: both are D's.
The detail plan is written after D's design round, whose answer on precedence it
follows (Q32).

`EdgeSettings` needs its own owner resolution. `_owning_graph`
(`settings.py:306-317`) reads only `_graph` or `_node`, so an `_edge`
back-reference alone resolves no graph. That matters as soon as D adds a tier.

Verify first: hot reload of a library wire type with a style bag rebinds every
live edge's bag. Edges are not re-created on a port rebuild. Validation re-runs
`build()` on the same wrapper, which is why the bag is derived there. Also verify
that paste and Subgraph instantiation keep a `LAZY` choice and a style. Canvas
changes are checked in a browser, not only in unit tests
(`.insights/project_multi_canvas_dom_globals.md`).

### 5.5 The annotation wire, type, node and skin

Everything under "The annotation node" above. Depends on P for `EXEC` in builtin,
5.2 for `VISUAL`, and 5.4 for the style bag and arrows.

Not costed before the review: the four-sided skin, the double-click hook, and
the canvas container class that reveals slots during a drag.

Verify first: the canvas pin index finds a slot hidden with `visibility`, a drop
on a hidden slot resolves through `nearestCompatiblePin`, and a drag onto a side
resolves to the right slot.

### D. Edge appearance defaults (design round owed)

Taken out of 5.4 in the review of 2026-10-03, and still to be designed. The design
round runs after 5.2, beside 5.3, and before the 5.4 detail plan. Its code is its
own plan after 5.4 (Q32). The aim
is a mechanism like the node settings tiers, but limited: a graph, and possibly the
framework, sets a few appearance defaults for all edges. The candidates so far are
whether edges draw an arrow to show the flow direction, and the edge width. The
same round defines the UX colours of edges.

Questions for the round:

- **Tiers and fields.** Framework < graph < edge, as for nodes (ADR 0022)? Which
  fields: arrow and width only, or more?
- **Scope.** One default for every edge, or per role or per wire type (arrows on
  control edges only, say)?
- **Precedence against a wire type's own look.** A style bag's field defaults are
  the wire type's look (`AnnotationWire` with an arrow, for one). Does a graph
  default override that, or only fill in what the wire type leaves computed? This
  one decides how 5.4 defines a wire's look, which is why D's design comes first.
- **Where the fields live.** `settings_bag_for` knows only `props` and `meta`
  ([base.py:877-885](../../../packages/haywire-core/src/haywire/core/graph/base.py#L877-L885)),
  so graph-tier fields go on the core `GraphProperties`. A library wire type
  cannot add its own while ADR 0022's library graph bags are deferred.
- **Arrow colour on a gradient edge.** An edge without a style is drawn with a
  gradient between its two pin colours. Which colour does its arrow take?
- **UX colours as theme tokens:**
  - selection: `--hw-edge-selected`, declared and documented, never read;
  - the active highlight: `.connection-active` sets width and `--hw-edge-active`
    with `!important`;
  - validity: `#EF4444` in `ui_edge.py:89`;
  - pin highlights during a drag: `#4CAF50` and `#f44336` in `canvas.vue`;
  - the default colour: `--hw-edge-default`, never read. The hard-coded
    `#bbbbbb` and `#333333` (canvas.vue:2916-2917) it would replace are mostly
    dead, because `_updateEdge` re-reads the pin colour without a fallback;
  - the other hard-coded fallbacks: `#000000` (:2621, :3568), `#ff0000` (:3583),
    `#4CAF50` (:2854).
- **Selection and a styled width.** Is the selected width relative to the edge's
  own (width + 1, through a CSS variable) or fixed?

5.4 computes the effective style in one server-side function, so D's code adds a
tier there.

## Earlier decisions this revises

- Step 2 settled "`CALLBACK`'s default becomes `""`, callbacks need no absence
  storage" and "an immediate pool drops an entry equal to its element's default".
  Q14 replaces both with `holds_absence` and `default=None`.
- ADR 0039's `IMMEDIATE` propagation value becomes a role, and an edge on that
  role has no propagation at all (Q19). ADR 0039 is amended.
- The review's "a callback edge shows a locked `EAGER`" and "an edge with a missing
  end derives fully from the surviving end" are replaced by Q19 and Q20.
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
  `_is_subgraph_output`: about 16 production readers, 24 test references). Findings: two sources for one structural fact,
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
- The hard-coded validity colours (Q13) moved into design round D.
- **Undoable pin removal** (Q28). `remove_port` is not undoable, and the edges it
  leaves on the ghost are kept on purpose. If leftover annotation arrows prove
  annoying, make the removal undoable before revisiting edge deletion.
- **Wire-level icons** (Q30). If library authors ask for them, a wire type can
  gain optional `icon_in`/`icon_out` used between the skin's map and
  `"fallback"`, without breaking `pin_kind`.

## Small items

Not wire-type work; each is a single change. Carried over open from the edge-kinds
overview when it closed.

- `docs/guides/panels.md` links to a file under `.insights/`, outside
  `docs_dir`. `mkdocs build --strict` fails on it; CI builds without
  `--strict`, so CI passes.
- `DataPort.set_value`/`get_value` open with `if not self._data: return`, and
  `ArrayField`/`MapsStringField` define `__len__`, so an empty array inlet is
  falsy: it silently drops an edge's `[1.0, 2.0]` and reads `None`. Should be
  `is None`. Found while verifying the step 2 plan; pre-existing.
- `tests/core/test_graph/test_base.py::test_generated_ids_are_distinct` mints
  200 ids with a 6-hex random suffix without registering them, so the
  collision retry never applies: a birthday collision fails it about once in
  800 runs (seen once while building step 2). Register each id, or assert on
  fewer.
- Collapse does not refuse a selection holding an EVENT node; the invalid Group
  surfaces only at host assembly (`validate_subgraph_contents`). Pre-existing,
  not callback-specific; found in step 4.
- Possibly: collapse seeds a data interface port's default from a *pooled*
  interior inlet, whose default is pool-shaped. Unverified; step 4 fixed only
  the immediate case.
- `ArrayField`, `PooledField` and `MapsStringField` have no `to_dict`, so they
  inherit `DataField`'s stub, which returns the decorator default. An array port
  set to `[5, 6]` saves as `{"value": []}`, so array port edits are lost on save.
  (A pool's contents come from its edges, so for `PooledField` nothing is lost.)
  Found in the 2026-10-03 review and confirmed at runtime. Latent today: array
  ports exist only on haybale-testing testbed nodes, and `MapsStringField` only in
  haybale-example. 5.3's template method fixes it (Q25). If a library adds array
  inlets with their own values before 5.3 lands, fix it standalone instead.
- Paste and Subgraph instantiation drop an edge's `propagation`: `RemappedEdge`
  carries it and nobody reads it. A `LAZY` choice silently becomes `EAGER`. Fixed
  by 5.4 together with style (Q27).
- `ADD`'s docstring (`add.py:111-113`) says a typed `ADD[T]` keeps T's flow. It
  does not today. 5.1 makes it true.

## Docs, glossary and ADR candidates

Collected during the inquisition, written by the plan that lands the code
(feedback: glossary and ADR edits describe what landed).

Glossary:

- new: **Wire type**, **WireRole** and its four values, **edge style** /
  `EdgeSettings`, **annotation node**, **pin kind** (the key a wire type gives its
  pins for the skin's icon map, such as `control`; not an icon, Q30);
- changed: **FlowType** entries replaced; **Propagation** reduced to lazy and
  eager; **lazy** gains the dirty mark it pushes on write, which is what lets a
  DATA node skip its worker ([base.py:126](../../../packages/haywire-core/src/haywire/core/node/base.py#L126));
  **CALLBACK port** loses "an empty name, which the emitter treats as no
  subscription"; **Edge** keeps *wire* on its avoid list, and the ten or so prose
  uses of "the wire" for an edge become "the edge"; **ghost pin** is rewritten
  (Q31): "the node's fallback anchor (`root_in`/`root_out`) for an edge whose port
  is missing or that found no matching port; it never starts, ends or joins a user
  drag, and never takes part in wire matching. Removing a pin leaves its edges
  drawn to the ghost." It drops "drop affordance" and carries `data-pin-ghost`;
  **Propagation** gains "an edge on an immediate or visual wire has none" (Q19).

ADRs:

- wire types replace FlowType: Surface pattern, closed roles, same-wire-type
  connection, derived and not stored, and "an edge that fails validation is never
  rewritten" (Q20) (5.1);
- ADR 0039 amended: immediate is a role, and its edges have no propagation (Q19)
  (5.1);
- refuse only what breaks, stated by mechanism, with the ADR 0003 correction (5.2);
- callback absence, superseding step 2's sentinel and ADR 0033's restriction for
  this wire, with absent defaults as empty `default_kwargs` (Q22) (5.3); the
  immediate guards may share it, including "a dropped fire stores nothing" (Q24);
- `EdgeSettings` as the fifth settings flavour (5.4).

Doc drift found on the way:

- [hot-reload-arch.md:19, 91, 208](../../architecture/hot-reload/hot-reload-arch.md#L19)
  names an `EdgeRegistry` that does not exist. Edges rebuild through the node
  registry and adapter chains. The new wire-type map must not take that name
  either.
- [datatype-canon.md:50](../../components/datatypes/datatype-canon.md#L50)
  describes `flow_type` and says CONTROL and CALLBACK types get no widget. More
  flow drift at :19, :132 and :149.
- `skin-canon.md:330, 335` and `glossary.md:513` name `data-pin-flow-type`.
- A ghost pin is called a "drop affordance" in `glossary.md:513`,
  `skin-canon.md:331` (which adds "the temporary target shown while dragging a
  connection to an empty area of a node"), `render_ghost_pin`'s docstring
  (`pin_render.py:309`) and the comment at `canvas.vue:1664`. The code makes it
  none of that (Q31). Fixed with 5.1, which renames the marker anyway; the
  `_baked_docs` copies are regenerated.

Docs additions (Q33), facts established by reading the code, written by the plan
that touches each area:

- the **Ghost pin** glossary entry: removing a user pin keeps its edges, drawn to
  the ghost (`remove_port` → `rejig`) (5.1);
- the callbacks architecture doc: a relay with something upstream takes its value
  from upstream on load, not from its own saved value (5.3);
- the settings docs: a node settings bag skips an unknown key on load and drops it
  at the next save, so a renamed setting loses its value (5.4, where edge bags
  follow the same rule).
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
| A closed loop of immediate edges recurses until `RecursionError` (traced 2026-10-03) | Q13b |
| `_isValidEdge`'s ghost branch is unreachable; ghosts never start, end or join a drag | deletion 11 |
| Paste and Subgraph instantiation drop `propagation` | 5.4 |
| Array and map port values are never saved (base `to_dict` stub) | 5.3 |

## Review corrections (2026-10-03)

The plan was checked claim by claim against the code. Most citations held,
usually to the line. What changed:

| Was | Now | Section |
|---|---|---|
| 5.1's suite "passes unchanged" | no changed behavioural assertion, with a list of mechanical test edits | 5.1 |
| `data-pin-flow-type` deleted outright | the ghost marker moves to `data-pin-ghost`; ghosts never enter `wires_match` | Connecting, deletion 11 |
| an edge's wire type always derivable | an edge that fails validation is never rewritten (Q20) | Connecting |
| deletions 9 and 10 in 5.1 | 9 in 5.3; 10 stays in 5.1 with `pin_kind` (Q29) | Deletions |
| callback edges unchanged in 5.1 | they have no propagation (Q19) | Propagation |
| `glyph` `ClassVar` | `pin_kind`, a map key, not an icon (Q30) | Wire types |
| absence through `_absence_tolerant_field` at `@type` time | a variant that keeps the stored type, applied in `create_field` | Absence |
| settings bags go through field `to_dict` | only the port block does; bags already store `None` | Absence, 5.3 |
| echo guard is new on both paths | the reveal path has it; reuse `_same_value` | The immediate path |
| `OPTIONAL` relay argument true today | true only once O1 gives `OPTIONAL[T]` T's wire type | Absence |
| suggestions must change for `ADD[ANNOTATION]` | no change: `sameType` already compares stored types | Annotation node |
| bag rebinds because edges rebuild | edges are not re-created; the bag is derived in `build()` | Edge style, 5.4 |
| graph tier via `graph(src=…)` in 5.4 | design round D | Edge style, D |
| `--hw-edge-*` tokens read in 5.4 | design round D, with every edge UX colour | D |
| `render_pin` gains a side argument | unchanged; the skin passes a per-pin layout | Annotation node |
| hover via `opacity` or `visibility` | `visibility` only | Annotation node |

The review's open questions O1 to O4 were settled the same day as Q21 to Q24.

## Decisions of 2026-10-03 (Q18 to Q33)

The second inquisition settled the review's open questions and the choices the
review had made on the user's behalf. Facts confirmed in the code were not
reopened.

| Q | Decision | Lands in |
|---|---|---|
| 18 | Scope: O1 to O4 plus the review's own choices; design round D in a session of its own | none |
| 19 | `CallbackWire.propagation = ()`. A callback edge has no propagation: the menu row and the inspector panel hide, Farmhand reports `propagation: null` and `role: "immediate"`, nothing is saved | 5.1 |
| 20 | An edge that fails validation is never rewritten. Its wire type comes from the end that resolves, for drawing only. Propagation is clamped and style rebound once, when it validates again | 5.1, 5.4 |
| 21 | `OPTIONAL[T]` answers T's wire type, like the other wrappers | 5.2 |
| 22 | On a `holds_absence` wire, `default=None` becomes empty `default_kwargs`, and the field starts and resets absent, for `BaseField` too | 5.3 |
| 23 | An orphaned callback relay holding `""` from an old save is an accepted break; linked relays heal on load | 5.3 |
| 24 | A dropped re-entrant fire stores nothing | 5.3 |
| 25 | The array and map save fix lands with 5.3's template method; standalone if a library needs it sooner | 5.3 |
| 26 | On a bag rebind, keys the new class does not declare are skipped, as in node bags | 5.4 |
| 27 | Paste and Subgraph instantiation carry `propagation` together with style | 5.4 |
| 28 | Removing a grown annotation pin leaves its edges on the ghost, as for every node; undoable removal is a follow-up | 5.5 |
| 29 | Q8b to 5.2; `data-pin-ghost`, `pin_kind` with deletion 10, and hiding the propagation UI in 5.1; deletion 9 in 5.3; the fallback glyph for an unknown kind in 5.4 | 5.1 to 5.4 |
| 30 | The wire type's pin family is `pin_kind`, a key for the skin's map. Real icons stay on types | 5.1 |
| 31 | A ghost pin is a fallback anchor, never a drag target. The docs calling it a drop affordance are corrected | 5.1 |
| 32 | D's design round runs after 5.2, beside 5.3, before the 5.4 detail plan. D's code follows 5.4 | sequence |
| 33 | Shared understanding confirmed. Three facts found by reading the code are marked as docs additions | docs |
