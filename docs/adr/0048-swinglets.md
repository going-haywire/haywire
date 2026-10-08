---
name: swinglets
description: A third port type, the swinglet, may be either end of an edge; each port holds an incoming and an outgoing link set, and the formal check is positive
status: accepted
see-also: ADR-0036, ADR-0042, ADR-0043, ADR-0044, ADR-0047
level: architectural
---

# Swinglets: a port that may be either end of an edge

**Context.**

- The annotation node (a box of text, linked to other boxes by drawn connectors) needs one pin per card side. Which end of a connector carries an arrow head is a property of the connector's style, not of the pins it joins.
- A port was an inlet or an outlet, and an edge had an outlet end and an inlet end. Direction was the blocker: the first annotation build gave each side two pins, an inlet and an outlet, and a drop had to find the pin of the opposite direction.
- Every reader of direction (the formal check, the canvas, assembly, pin placement) compared a port type for equality, so a third type was cheaper than it looked. What needed care was where an edge is stored.

**Decision.**

- **`PortType.SWINGLET`** is a port that may be either end of an edge, on any wire type. `is_inlet()` means "can be an edge's inlet end" and `is_outlet()` "can be its outlet end"; both are true for a swinglet. `is_swinglet()` serves the places that need exactly one direction. `get_ports(is_port_type=INLET | OUTLET)` also returns swinglets. `IType.as_swinglet(id, **kwargs)` declares one.
- **The formal check is positive.** An edge's outlet end must be `is_outlet()` and its inlet end `is_inlet()`. There is no table of allowed pairings; between two swinglets the direction is the drag order.
- **One edge between two pins, on every wire.** `add_edge_wrapper` refuses an edge whose reverse id exists, and the canvas checks both orders on every drop. The stored order stays the drag order.
- **`LinkSet`.** A port holds two, `port.incoming` and `port.outgoing`; each keeps its linked edges and every edge targeting that end, displaced ones included. `port_type` decides which an edge may link to, so a port that changes direction never strands an edge. Each set has its own link ceiling (ADR 0044):
    - outgoing allows many unless the wire role is `SEQUENCE`;
    - incoming allows many for `SEQUENCE` and `VISUAL`, otherwise the field decides;
    - `single_link` narrows both.
    - `takes_many_links` reads the outgoing set for an outlet and the incoming set for any other port.
- **Readers take the matching set.** Pipes and control transitions read the outgoing set. Re-enablement, revealing the own value and `should_show_widget` read the incoming set (an outlet is judged on its outgoing set). `_get_edge_wrappers_for_port(node_id, port_id, *, incoming)` names the end for assembly, on the graph and on `FlatGraphView`. `adopt_state_from` adopts both sets and re-points the edges of both.
- **Values.**
    - What an edge writes is stored as the linked value and stops there, as at an inlet.
    - The node's own write, `out()`, goes to the port's own value and passes on to the outgoing edges, as at an outlet.
    - A pipe reads its source's own value, which is the same thing for an outlet.
    - A swinglet nothing feeds reads its own last write when its node next runs. A data node runs only when one of its ports is dirty, and its own `out()` dirties nothing; a control node runs every time control reaches it.
    - `as_swinglet` defaults to `store_strategy = HAS_WIDGET | NODE_SET` and `show_widget = NOT_LINKED`; a type's own declaration wins.
- **`on_change` reports what a node receives:** edge, widget and setting writes, on inlets, swinglets and configs. The outlet half of a write (`out()` and its internal `_emit`) never fires it, `as_outlet(..., on_change=...)` raises `ValueError` at declaration, and no port built with `as_outlet` carries one. A fold wrapping outlets may carry `on_change`, and its own toggle write reaches it through `set_value`.
- **Pins.**
    - A swinglet's glyph role is `swing` (`data_swing`, `control_swing`, and so on); a declared glyph uses `icon_in`.
    - Skins draw a swinglet once, on the inlet side.
    - Listings give it its own group: Properties, Farmhand (`swinglets`, with `outgoing_takes_many` on its row) and the docs generator.
- **A reconnect keeps both ends' roles.** `SyncEdgeReconnectEvent.anchorEnd` (`"outlet"` or `"inlet"`) is the anchor's role in the old edge. Between two swinglets the canvas keeps that role; a swinglet anchor dropped on a pure inlet or outlet takes its orientation from that pure pin.
- **The annotation node** keeps one growing swinglet set per side, ids `{side}_{index}` with indices never reused. The skin draws a side's pins centred as a group, each with the `LayoutDirection` that puts it on that side (`_LAYOUT[side]`). The open slot sits in a zero-width wrapper after the last pin; ghost pins sit in a wrapper of their own.

**Alternatives.**

- *Paired inlet and outlet ports drawn as one pin.* The doubling stays in the model and in saved files.
- *A pin attribute for the wire role, so the canvas accepts any pair on a visual wire only.* A swinglet works on every wire; the formal check alone decides.
- *Reading the own value in a data node on every frame.* Data nodes stay dirty-gated; a node that must react only to input uses `on_change`.

**Consequences.**

- The hot path gains no branch: `out()` calls the outlet half of `set_value` directly, an arriving value keeps the inlet path, and `Pipe.pull` reads the own value. A `LinkSet` is read at patch time only.
- An older build cannot initialise a node holding a swinglet (`'swinglet' is not a valid PortType`); the graph loads, the node fails and its edges show as invalid. A release note covers it.
- A data node re-reads its own write only when it runs again.
- A reverse edge is refused on every wire, not only on `VISUAL`.
- `on_change` does not see a node's own write, and an outlet refuses one.
- A note link crossing a Group collapse is re-wired through the card's pins like any `VISUAL` wire and loses its style on the way.
- The ordering walks of the data-flow builder (`_check_cycles`, `_topological_sort`) use inlet-side lookups, because `FlatGraphView` splices the Output-to-consumer crossing of a data-only Subgraph only into incoming lookups. An outgoing lookup returns the owning graph's edges unchanged, so an outlet-side walk misses the Output-to-consumer edge. The Group-ordering defect surfaced while the lookups were split by end.
