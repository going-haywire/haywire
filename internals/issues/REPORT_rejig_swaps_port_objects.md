# Report: `rejig` swaps port objects, and the transplant list is incomplete

Date: 2026-09-19

`NodeData.add()` builds the new `DataPort` **before** it discovers the id is
already present, so a re-add inside `rejig()` cannot reuse the existing object —
it replaces it and calls `DataPort.adopt_state_from(existing)` to carry state
across. Replacement is therefore a consequence of construction order, not a
decision.

`adopt_state_from` is an **enumerated list** of what to carry. A `DataPort`
holds eleven pieces of live state; the list carried three and a half
(`_linked_edges`, `_all_edges`, `order`, and `_data` when the type is
unchanged). Two more were found missing during the Slice-1 Subgraph work, each
failing silently and differently. Both are now patched, but the list is still
an enumeration and the next gap will be found the same way — from the studio.

### The asymmetry that hides it

`add()` ends with `mark_as_structuraly_dirty()`. For a node that rejigs itself
from a `hb_*` callback, the **next validation batch** repairs the damage:

- `EdgeWrapper._validate_port_types` (`edge_wrapper.py:680`) re-resolves both
  endpoints **by id**, fixing stale object references;
- `NodeWrapper._housekeeping` → `DataPort._housekeeping` (`port.py:675`)
  rebuilds `_pipes` from the links.

That rescue never arrives for a node that rejigs **inside** a validation
callback: its marks land in the *next* batch, after the current one has already
read the broken state. `GraphNode.reconcile_interface` is the only such node in
the codebase — it is driven by its Subgraph's own validation — which is why
every symptom appeared on Graph-node cards and nowhere else.

### The two gaps found (both fixed)

**1. Stale `EdgeWrapper` endpoint references.** An `EdgeWrapper` holds
`_inlet_port` / `_outlet_port` by object reference. A replaced port left every
attached edge pointing at the discarded object, so `detach()` unlinked the
orphan and the live port stayed linked for good. Symptom: a card pin frozen in
its linked rendering — the widget never returns after the edge is removed.

**2. Missing `_pipes`.** The outlet's transport is derived state owned by the
port object, so the replacement starts with none. Symptom: **a card outlet
silently stops delivering values.** Quieter than (1): nothing to see at either
end. Verified — `7.0` written to the card's outlet arrived at the consumer as
`0.0`.

Both are now handled in `adopt_state_from` (`port.py:506`): edges are
re-pointed, and the port is marked dirty and housekept before the method
returns.

### What is still enumerated, and unverified

Not carried, with no known live path that breaks on them — but (2) also had no
known path until it was looked for:

- `_pending_lazy_pipes` — queued lazy pulls; a swap mid-frame would drop them
- `_is_set_by_node` — whether the current value came from the node
- `_is_dirty_structural` — now set explicitly by the fix, but not *carried*

### Follow-up: stop swapping the object

The structural fix is for `add()` to detect the refresh **first** and mutate the
existing port in place — apply the new spec's fields to the live object rather
than building a replacement and transplanting. That removes the whole class of
bug instead of enumerating against it, and deletes `adopt_state_from`'s reason
to exist.

Cost and risk to weigh before starting:

- `add()` is a hot path (every node build, every rejig, every promoted-port
  regeneration), and this changes its core branch.
- A spec can legitimately change a port's **type**, which today produces a
  genuinely different object (`_data` is only preserved when `type_cls` is
  unchanged). In-place mutation has to decide what a type change means for the
  field, its observers, and any attached edges.
- `adopt_port_type` (`port.py:96`) already exists as a narrow in-place re-type
  for folds, and documents that assigning `port_type` directly leaves
  `_is_inlet` stale — evidence that in-place mutation needs its own care, not
  that it is simpler.

Until then, the invariant to hold: **anything that replaces a live port object
must leave the graph indistinguishable from before the swap.** Do not rely on a
later validation batch; it is a different code path with different timing.

### Evidence

- Regression tests: `tests/core/test_node/test_port_swap_keeps_edges.py`
  (9 tests). The plain-node cases pass via either path and say so in their
  docstrings; the `TestTheGraphNodeCard` and
  `test_the_card_outlet_still_delivers_after_a_reconcile` cases are the ones
  that fail without the fix.
- Trap write-up: `.insights/project_rejig_orphans_edge_port_refs.md`, including
  the three plausible-but-wrong diagnoses this cost (a threading race, the
  NodeDetail CSS, and "the redraw never ran" — the redraw does run, on stale
  state).
