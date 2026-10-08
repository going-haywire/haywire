# Diagram annotations: notes linked by direction-free connectors

Status: **landed 2026-10-08.** Design settled 2026-10-07 (Q95 to Q117) and verified; built by
the detail plan [2026-10-06-swinglets.md](2026-10-06-swinglets.md); live-checked by the user
2026-10-08. Branch `diagram-annotations`, squashed on `master` 727d336b into
`fix(assembly): order a Group's data consumers after its interior` (a master bug found on the
way), `feat: swinglets, and diagram annotations built on them` (ADR 0048) and this plan move.
Replaces the goal of
[2026-10-04-wire-types-5-5-annotation.md](2026-10-04-wire-types-5-5-annotation.md), which named
the work by its parts rather than by what the user gets.

## Goal

The user draws diagrams on any graph: boxes of text linked by connectors. A connector is drawn
and saved but never executed. **The user connects any side of one note to any side of another,
with one gesture and one pin per side; which end carries an arrow head is a property of the
connector, set in its style, not of the pins it was dragged between.**

## Why the 5.5 build is not shippable

A pin is a port, and a port is either an inlet or an outlet (`PortType`). Everything built in
5.5 follows from that:

- each card side carries two slots, an inlet and an outlet: eight per card, visually doubled;
- the direction of a link is decided by which slot the user grabs, although nothing flows;
- a drop must find the slot of the opposite direction (`_isValidEdge` requires an outlet and an
  inlet), so dragging from an inlet slot to another inlet slot fails for no reason the user can
  see.

For a `VISUAL` wire, direction carries no meaning in the engine (no pipe, no assembly, ADR
0043's "refuse only what breaks"). The arrow heads already live in the edge's style bag
(`arrow_start`, `arrow_end`, Q58), so the visible direction does not need the port direction.

## What exists on the branch

Kept as the starting point; any of it may change in the design round.

- `AnnotationWire` (`VISUAL`, style bag `AnnotationStyle` with all five style fields) and the
  `ANNOTATION` type, in `builtin/types/annotation.py` (Q81).
- `AnnotationNode`: a builtin `CONTROL` node with `exec`/`done` pass-through, `text` and
  `show_control_pins` props (Q82), and growing `ADD[ANNOTATION]` slots per side and direction,
  the side recorded in the port id (`left_in_0`), indices never reused.
- `AnnotationSkin`: one absolutely positioned strip per card side, each pin rendered with the
  one `LayoutDirection` that puts it on that side; ghost pins (Q86); double-click opens the
  text modal (Q83).
- Canvas: `edge-dragging` on the container during an edge drag and `hw-pin-reveal` for
  hover-only pins (Q84).
- Tests for all of the above (core, skin, browser harness route `/graph-annotation`).

Live-checked on 2026-10-05: everything works as built; the blocker is the model, not a bug.

## The question for the design round

How does a pin take part in a link without being an inlet or an outlet, given that
`EdgeWrapper` has an outlet end and an inlet end, `generate_edge_uuid` encodes that order, and
the canvas, the validator, auto-wire, reroute split and Group collapse all read it?

Candidate directions, to be grilled (not decided):

- (a) **Direction stays internal.** A `VISUAL` pin is one port that accepts a link at either
  end: the edge still stores outlet and inlet (the drag's start and end), but the framework
  lets a pin serve as either for a wire whose role is `VISUAL`. One pin per side; the canvas
  accepts any two such pins on different nodes.
- (b) **A third port type for visual pins** (neither inlet nor outlet), with an edge kind whose
  two ends are symmetric. Cleaner model, wider change (every `is_inlet()`/`is_outlet()`
  reader).
- (c) **Paired ports, one rendered pin.** Keep an inlet and an outlet per side but render them
  as one pin, and let the canvas pick the direction from the drag order. Smallest change, but
  the doubling stays in the model and in saved files.

Each must answer: what the edge id is, what a save looks like, how growing slots work with one
pin per side, how removing a pin treats its edges (Q28), and whether reroutes and Groups need to
handle these edges at all (Q91: styled edges rarely meet them).

**Resolved 2026-10-06: (b), refined.** A third port type, the swinglet, which may be either end
of any edge on any wire. The audit showed (b) is not the wide change it looked like: every
`is_inlet()`/`is_outlet()` reader is an equality test, and the engine readers that need a
swinglet's edges get them from a per-end edge set (Q102), not from the port type.

## Decisions of 2026-10-06, design round (Q95 to Q103)

The round's working numbers Q1 to Q6 are given in brackets.

| Q | Decision | Lands in |
|---|---|---|
| 95 | A third `PortType`, `SWINGLET`: a port that may be either end of an edge. Every port type works on every wire type; the framework refuses only what breaks. `is_inlet()` means "can be an edge's inlet end" and `is_outlet()` "can be its outlet end", so both are True for a swinglet. `is_swinglet()` serves the places that need exactly one direction (pin placement, labels, `data-pin-dir`). `get_ports(is_port_type=INLET\|OUTLET)` also returns swinglets, so the method and enum views agree | `types/enums.py`, `types/port.py`, `types/interface.py` (`as_swinglet`), UI |
| 96 | The formal check is positive and symmetric: an edge's outlet end must be `is_outlet()`, its inlet end `is_inlet()`. No table of allowed pairings; a swinglet-to-swinglet edge takes its direction from the drag order | `EdgeWrapper._formal_validation` |
| 97 | (Q1) A `VISUAL` edge whose reverse id is already in the graph is refused in `add_edge_wrapper`; the canvas's `_edgeExists` checks both orders. **Corrected by Q112:** for every wire, one edge between two pins. The stored order stays the drag order, so the arrow heads keep their meaning | `graph/base.py`, `canvas.vue` |
| 98 | (Q2) A `VISUAL` edge crossing a Group/Subgraph collapse is removed by the collapse action, and undo restores it: `derive_interface` skips edges that carry no values. **Dropped by Q106** | — |
| 99 | (Q4) How many swinglets a side has, and whether they grow, is the node's and the skin's choice: a swinglet is an ordinary port, and `ADD[X]` slots with `on_connect` still work. The builtin annotation node's default is for the detail plan. Supersedes Q89's per-direction slots | node, skin |
| 100 | (Q5, Q6) Values. An edge's write is stored as the linked value and stops there (inlet behaviour); only the node's own write, `out()`, passes on (outlet behaviour). The node's write goes to the own value, and a swinglet's pipe reads the own value. Consequences, to document: a swinglet nothing feeds reads its own last write (`out("x", value("x") + 1)` counts up on every run); after its feeding edge goes, the node continues from its last output; the node's write replaces the widget value; whether it is saved is the type's `StoreStrategy` (`NODE_SET`). **Refined by Q107 and Q108** | `types/port.py`, `types/pipe.py`, docs |
| 101 | Hot path: no new branch, two fewer. `out()` accepts any `is_outlet()` port and calls the outlet half of `set_value` directly (`_emit`). Edge and widget writes keep the inlet path (`_is_inlet` is True for a swinglet). `Pipe.pull` reads `get_own_value()`, which is the same for an outlet: its field never holds a linked value, because only `Pipe.pull` writes one, into its sink. The "set by node" mark is cleared only by own-value writes, inside the existing `edge_id is None` branch, so an arriving value does not drop a `NODE_SET` save | `types/port.py`, `types/pipe.py`, `node/data.py` |
| 102 | `LinkSet`: the edge storage of `DataPort` (`_linked_edges`, `_all_edges` and the methods on them) moves unchanged into a class with one instance per end, `port.incoming` and `port.outgoing`, shaped like `Pipes`. Every port has both; `port_type` decides which an edge may link to, so a port changing direction (a fold, `refresh_from`) never strands its edges. Each set takes its half of `takes_many_links`: outgoing allows many unless `SEQUENCE`; incoming allows many for `SEQUENCE`/`VISUAL`, else the field decides; `single_link` narrows both. Clearing an incoming link also drops the edge's linked value and queued lazy pull. The edge addresses the set by its own end (`_inlet_port.incoming`, `_outlet_port.outgoing`). The hot path never reads the sets | `types/port.py`, `edge/edge_wrapper.py`, `node/data.py` |
| 103 | Readers take the matching set. `_refresh_pipes` and `control_transitions` read the outgoing set. `_try_reenable`, `_reveal_own_value_if_unlinked` (fixes a stale linked value while an outgoing edge stays) and `should_show_widget` read the incoming set. `NodeData._pop` handles each set separately: an incoming edge informs its source, an outgoing edge does not. `adopt_state_from` copies both, and its edge re-pointing loop walks both (trap: `project_rejig_orphans_edge_port_refs`). `graph._get_edge_wrappers_for_port` splits into one method per direction for assembly (`data_flow_builder`, `flat_view`) (**replaced by Q109**; `should_show_widget` **refined by Q110**). `is_linked()` and `_get_linked_edges_uuid()` count both sets | as listed |

## Decisions of 2026-10-06, the two open items (Q104, Q105)

| Q | Decision | Lands in |
|---|---|---|
| 104 | The first build includes value-carrying swinglets: every port type on every wire type. Q3's "refuse for now" is dropped | detail plan |
| 105 | The annotation node keeps a growing set of swinglets per side (Q99), and a side's pins are drawn centred along it; today they start at one end | annotation node and skin |

## Verification of 2026-10-06

A throwaway spike in a separate worktree (reference diff, not for merging:
`.scratch/swinglet-spike/spike.diff`) added `SWINGLET`, both predicates, `_emit`, the own-value
pipe read, the positive formal check and the end filter in `DataFlowBuilder`, plus two testbed
nodes (one writes its swinglet in its worker, one does not).

- **A→S→B, eager and lazy: confirmed.** All four eager/lazy combinations pass. An arriving value
  stops at S, the worker reads it, `out()` passes the node's write on, and B gets it in run order
  A, S's node, B.
- **Q100 corrected.** A data node runs only when one of its ports is dirty
  (`BaseNode._execute`), and its own `out()` dirties nothing. So a data node does not count up on
  every frame: it reads its own last write when it next runs for another reason (a widget edit,
  another port changing). A control node runs every time control reaches it, so there
  `out("x", value("x") + 1)` counts once per pass.
- **The stale linked value is real.** Remove A→S while S→B stays, and S keeps A's last value and
  its node does not run again. Checking only incoming edges in `_reveal_own_value_if_unlinked`
  fixes it: S shows the node's last write, the node runs, and B gets the result (Q103's incoming
  set).
- **Q101's premise holds.** The non-browser suite on the spike (6244 tests) ran with a probe in
  `Pipe.pull` that logs any outlet holding a linked value; it never fired. By reading: only
  `Pipe.pull` writes a linked value, into its sink; a promoted port borrows its own node's cell,
  in one direction only.
- **The spike broke nothing else.** The one failure was a test that stubs `_linked_edges` with
  bare `object()`s; under `LinkSet` it moves to `port.incoming.linked`.
- **Reroute on a `VISUAL` edge: works.** The split types the reroute to the outlet's stored type
  (`ANNOTATION`); both halves validate on the annotation wire. Both halves carry the original's
  style, heads included (Q91).
- **An older build and a saved swinglet.** The graph loads; the node holding the swinglet fails
  to initialise ("'swinglet' is not a valid PortType") and its edges show as invalid. Nothing
  crashes. A release note is enough.
- **Q98 conflicts with Q41.** Q41 (wire types) made a `VISUAL` wire cross a Group boundary like
  any other wire, tested in `tests/core/test_graph/test_visual_wire_group.py`. Q98 assumed
  crossing swinglet edges would fail validation; under Q96 they re-wire validly. The detail plan
  proposes dropping Q98.
- **Canvas and readers.** Two sweeps listed every direction reader and every canvas site; their
  findings are the detail plan's tasks. Two need a decision, proposed in the detail plan:
  re-dragging one end of a swinglet-to-swinglet edge flips it (the drag starts at the kept end),
  and the canvas cannot tell a `VISUAL` wire from another without a new pin attribute.

## Decisions of 2026-10-07, detail plan corrections (Q106 to Q117)

The detail plan's corrections C1 to C11 (plus C2b), decided one by one.

| Q | Decision | Lands in |
|---|---|---|
| 106 | (C1) Drop Q98; keep Q41. A note link crossing a collapse is re-wired through the card's pins like any `VISUAL` wire, and loses its style on the way (Q91) | Task 9 test |
| 107 | (C2) Data nodes stay dirty-gated. Docs: a data node reads its own last write when it next runs for another reason; a control node runs every time control reaches it. `out("x", value("x") + 1)` is one pattern among others, explained from the inlet and outlet rules; to react only to input changes, use `on_change` | docs, `as_swinglet` docstring |
| 108 | (C2b) `on_change` reports what a node receives: edge, widget and setting writes, on inlets, swinglets and configs. The outlet half of a write (`out()`, `_emit`, and `set_value` on an outlet) never fires it, and `as_outlet(..., on_change=...)` raises `ValueError` at declaration. No port uses an outlet `on_change` today | `types/port.py`, `types/interface.py` |
| 109 | (C3) `_get_edge_wrappers_for_port(node_id, port_id, *, incoming: bool)` on `BaseGraph` and `FlatGraphView`: every caller names the end; the view applies `_reroute_source` to incoming and `_interior_sinks` to outgoing edges | `graph/base.py`, `assembly/` |
| 110 | (C4) `should_show_widget` judges an inlet or swinglet on its incoming set and an outlet on its outgoing set | `types/port.py` |
| 111 | (C5) A reconnect keeps both ends' roles: `SyncEdgeReconnectEvent.anchorEnd` (`"outlet"`/`"inlet"`); between two swinglets the canvas keeps the anchor's role | canvas, context menu |
| 112 | (C6, and corrects Q97) One edge between two pins, for every wire: `add_edge_wrapper` refuses an edge whose reverse id exists, unconditionally, and the canvas's `_edgeExists` checks both orders on every drop. No pin attribute for the wire role | `graph/base.py`, `canvas.vue` |
| 113 | (C7) `as_swinglet` defaults: `store_strategy = HAS_WIDGET \| NODE_SET`, `show_widget = NOT_LINKED`; a type's own declaration wins | `types/interface.py` |
| 114 | (C8) `DataPort.takes_many_links` stays: the outgoing set's ceiling for an outlet, the incoming set's otherwise. Farmhand adds `outgoing_takes_many` to a swinglet's row | `types/port.py`, Farmhand |
| 115 | (C9) A swinglet's glyph role is `swing`: `<kind>_swing[_multi]`, then `<kind>`, then the fallback. Defaults: `data_swing`/`compound_swing` `radio_button_checked`, `control_swing` `join_inner`, `callback_swing` `swap_horiz`. A declared glyph uses `icon_in`/`icon_in_multi` | `ui/skin/pin_icons.py`, `ui/themes/icons.py` |
| 116 | (C10) Skins draw a swinglet once, on the inlet side (`LayoutDirection.side_for`). Text listings give it its own group: a "Swinglets" lane in Properties, `direction: "swinglet"` and a `"swinglets"` bucket in Farmhand, docs order inlet, swinglet, config, outlet | skins, Properties, Farmhand, docs generator |
| 117 | (C11) A side's grown pins are centred as a group; the slot sits in a zero-width wrapper after the last pin (centred when the side has none) and stays revealed by `visibility`. Ghost pins get their own wrapper, rendered before the strip | `annotation_skin.py` |

**Glossary terms, to land with the code:** swinglet; link set (`LinkSet`, the incoming and
outgoing set of a port).

**ADR, to land with the code:** swinglets, a third port direction: per-end link sets, the value
semantics of Q100, and the symmetric formal check.

## Decisions from 5.5 to re-examine

Q81 to Q90 (design doc [2026-10-02-wire-types.md](2026-10-02-wire-types.md)), in particular Q85 (drops commit to the
nearest compatible pin) and Q89 (slots never removable), which assume per-direction slots. Q89's
per-direction slots are superseded by Q99.

## Not in scope

- Linking a note to an ordinary node ("pins anywhere", a later follow-up).
- Markdown in the text.
- Undoable text and style edits (Q92: settings changes stay off the undo history).

## Next

1. ~~Design round (inquisition) on the question above; record decisions as Q95 onward.~~ Held
   2026-10-06.
2. ~~Detail plan with tasks, written from Q95 to Q105 and the verification.~~
   [2026-10-06-swinglets.md](2026-10-06-swinglets.md).
3. ~~Rework the branch; live checks; squash; merge.~~ Reworked 2026-10-07, live-checked and
   squashed 2026-10-08.
