# A rejig inside a validation callback orphans its edges' port references

`rejig` replaces port **objects**. `DataPort.adopt_state_from` transplants
`_linked_edges` to the replacement, and an `EdgeWrapper` holds its endpoints by
object reference (`_inlet_port` / `_outlet_port`), resolved when the edge was
last validated.

So a replaced port leaves every attached edge pointing at an object that is no
longer on the node. `detach()` then unlinks the **orphan**, the live port keeps
its `_linked_edges` entry, and `is_linked()` stays True for good. Nothing
raises. The only symptom is a pin frozen in its linked rendering — most
visibly, an inlet whose widget never comes back after the edge is removed.

## Why it almost never bites

`NodeData.add()` ends with `mark_as_structuraly_dirty()`. For a node that
rejigs itself from a `hb_*` callback, the next validation batch revalidates its
edges, and `EdgeWrapper._validate_port_types` re-resolves both endpoints **by
id** — quietly repairing the reference before anyone reads it.

That rescue does not arrive when the rejig runs **inside a validation
callback**: its marks go into the *next* batch, which is after the current
batch has already rendered from the stale reference. `GraphNode.reconcile_interface`
is exactly this case — it is driven by the Subgraph's own validation.

Hence a bug that appeared only on Graph-node cards, and only sometimes:
whether a reconcile happened between wiring the edge and removing it.

## The rule

`adopt_state_from` re-points the edges it inherits. If you write another path
that swaps a live port object, re-point them there too — do not rely on a later
revalidation, which is a different code path with different timing.

## Why the obvious diagnoses are wrong

Three plausible readings that each cost real time here:

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
