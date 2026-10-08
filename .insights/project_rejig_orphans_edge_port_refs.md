# A port-type change inside a validation callback can orphan edge references

Scope: this only fires when a `rejig` re-add changes a port's **type**. A
same-type re-add (`NodeData.add` → `DataPort.refresh_from`) keeps the live
port object — there is no swap, so nothing to orphan. The trap below lives
entirely in `DataPort.adopt_state_from`, the retype fallback.

## The mechanism

A retyped re-add still builds a new `DataPort` and discards the old one.
`adopt_state_from` transplants both `LinkSet`s (`incoming`, `outgoing`) to the replacement, but an
`EdgeWrapper` holds its endpoints by object reference (`_inlet_port` /
`_outlet_port`), resolved when the edge was last validated. Left alone, every
attached edge would point at an object no longer on the node: `detach()` would
unlink the **orphan**, the live port would keep its `LinkSet` entry, and
`is_linked()` would stay True for good. Nothing raises — the only symptom is a
pin frozen in its linked rendering, most visibly an inlet whose widget never
comes back after the edge is removed.

`adopt_state_from` re-points both endpoints on every transplanted edge of both
sets before it returns. That loop is the only thing standing between a retype and the bug
above.

## Why it almost never bites

`NodeData.add()` marks the node structurally dirty. For a node that rejigs
itself from a `hb_*` callback, the next validation batch revalidates its
edges, and `EdgeWrapper._validate_port_types` re-resolves both endpoints **by
id** — quietly repairing the reference even if nothing else did.

That rescue does not arrive when the rejig runs **inside a validation
callback**: its marks go into the *next* batch, after the current batch has
already rendered from the stale reference. `GraphNode.reconcile_interface` is
exactly this case — driven by the Subgraph's own validation — and `_mirror`
passes the interface port's `type_cls` straight through, so retyping a
boundary port retypes the card's pin and reaches this exact path.

Hence the original bug appeared only on Graph-node cards, and only
sometimes: whether a reconcile happened between wiring the edge and removing
it.

## The rule

Anything that swaps a live port object must re-point every reference to it
before returning control — do not rely on a later validation batch, which is a
different code path with different timing. Three things hold a port by
reference:

- `EdgeWrapper._inlet_port` / `_outlet_port`
- the outlet's own `_pipes`
- `Pipe.sink`, which lives on the **upstream** outlet — a rejig on the sink
  node never touches it directly. It survives today only because
  `adopt_state_from` re-points the edge before `_housekeeping` rebuilds the
  pipe from it; that's an ordering dependency between two lines, not
  independent correctness.

## Testing this is subject to the same trap it describes

A test of the re-pointing **passes whether or not the re-pointing exists**
whenever the graph's scheduler runs validation: the sync scheduler revalidates
when the rejig exits, and `_validate_port_types` re-resolves both endpoints by
id before the assertion runs. Delete the loop in `adopt_state_from` and such a
test stays green — this happened twice, including
`test_a_retyped_interface_port_re_points_the_edge` in
`tests/core/test_node/test_port_swap_keeps_edges.py`, which passes with the
loop deleted and so does not guard it on its own.

A guarding test builds the graph with a scheduler that holds every scheduled
validation and never runs it (`_ParkedScheduler` in
`tests/core/test_edge/test_swinglet_links.py`), wires the edges, calls
`force_validation()`, rejigs, and asserts `edge._inlet_port is new` /
`edge._outlet_port is new` straight after — before any further validation.
`test_a_retyped_swinglet_keeps_both_edges` does this and fails with the loop
removed for the incoming set, the outgoing set, or both. Check any test
claiming to cover this by deleting the loop and confirming it fails.

## Why the obvious diagnoses are wrong

Three plausible readings that each cost real time diagnosing the original bug:

- **"It's a threading race."** The validation batch does run on a daemon timer
  (`ThreadingTimerScheduler`), so a race is available as an explanation for any
  intermittent redraw bug. It was not this. The tell against it: the failure
  was specific to one node type, and a timing race is not.
- **"The NodeDetail CSS is hiding it."** `[data-node-props-detail="pins"]`
  really does `display: none` both `.hw-detail-widget` and
  `.hw-detail-pins_all`. Check the attribute's live value before believing it
  — a dropdown showing options is not a committed rank.
- **"The redraw never ran."** It ran. `syncNodeRedraw` fires and the card
  re-measures at its new height. The state it rendered *from* was wrong.

Diagnose it by asking whether `edge._inlet_port is node.ports[pin_id]`, not by
reading the render path.
