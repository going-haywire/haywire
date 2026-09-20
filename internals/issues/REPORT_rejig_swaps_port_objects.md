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

### Resolved: the same-type refresh no longer swaps

`add()` now resolves the spec, compares `type_cls` against the live port, and
splits:

- **Same type** — the common case, and every case above. `DataPort.refresh_from`
  applies the spec's declarative fields to the **live object**, which stays on
  the node. Nothing is transplanted because nothing moved: edges, pipes, value
  and dirty flags are already correct, and every reference to the port is still
  a reference to the port.
- **Type changed** — the one case a refresh cannot express in place, since the
  field and whatever `_configure_port` derives from the type genuinely differ.
  This still builds a replacement, and `adopt_state_from` still transplants.

Declarative is defined as "what the port serializes" — the same `serialize`
field metadata `to_dict` reads, so the two cannot drift. Three exceptions are
excluded by name:

- `order` — user-owned; a user's arrangement outlives a node reconfiguring
  itself.
- `_is_dirty_structural` — live state that only looks declarative; the fresh
  port's value would clear a pending rebuild.
- `port_type` — applied through `adopt_port_type` so the `_is_inlet` cache
  follows. `_is_callback` is refreshed for the same reason, since a compound
  type derives `flow_type` from its element type.

The three unverified leftovers (`_pending_lazy_pipes`, `_is_set_by_node`,
`_is_dirty_structural`) stop mattering on the refresh path — they are never
copied because the object holding them is never replaced. They remain
enumerated on the retype path, which is rare and revalidates anyway.

A third stale reference was found and is now covered by construction: a `Pipe`
holds its sink inlet by reference and lives on the **upstream** outlet, which a
rejig on the sink node never touches. It happened to survive before, but only
because `adopt_state_from` re-pointed `edge._inlet_port` before `_housekeeping`
rebuilt the pipe from that edge — an ordering coincidence between two lines,
not independent correctness.

The invariant still holds for the retype path: **anything that replaces a live
port object must leave the graph indistinguishable from before the swap.** Do
not rely on a later validation batch; it is a different code path with
different timing.

### Evidence

- Regression tests: `tests/core/test_node/test_port_swap_keeps_edges.py`
  (14 tests), covering object identity across a refresh, the upstream pipe's
  sink, that a refresh still applies the new spec and keeps the value, and the
  type-change swap. The `TestTheGraphNodeCard` and
  `test_the_card_outlet_still_delivers_after_a_reconcile` cases remain the ones
  with no validation batch to fall back on.
- The re-stamping loop in `adopt_state_from` is pinned by exactly one test,
  `test_a_retyped_interface_port_re_points_the_edge`: a retype driven through
  `_mirror` from inside the Subgraph's validation. Deleting the loop fails that
  test and **nothing else** — every plain-node retype is masked by the next
  batch re-resolving endpoints by id. A retype test written on a plain node
  asserts nothing about the loop, which is the same asymmetry the report opens
  with, met once more while writing the tests for the fix.
- Trap write-up: `.insights/project_rejig_orphans_edge_port_refs.md`, including
  the three plausible-but-wrong diagnoses this cost (a threading race, the
  NodeDetail CSS, and "the redraw never ran" — the redraw does run, on stale
  state).
