# Edge kinds: steps and sequence

## Context

The goal is to make edges a first-class component, like nodes. A library
author should be able to define a new **edge kind** — including kinds that are
only drawn and never executed, with their own rendering properties — and data
types say which edge kind they use. Today the three kinds are fixed by
`FlowType` (`DATA`, `CONTROL`, `CALLBACK`), and a new one means changing the
framework. Breaking changes are acceptable, saved graphs included: every barn
library has one author.

Analysis of `FlowType` (2026-09-27) found it far less load-bearing than it
looks — ~200 references, almost all of them filters — but it also found two
behaviour gaps in the existing flow types that had to be closed first, so that
EdgeKind does not inherit them as special cases:

- **Callbacks could not pass through anything.** A callback edge had to run
  straight from its event node: no reroute, no Subgraph boundary. Relays
  forwarded values only in their worker, which never runs on a callback path,
  and removing an edge upstream of a relay left the emitter subscribed.
  → **steps 1, 2 and 4.**
- **A port forgets its own value when linked.** Unlinking keeps the last value
  that arrived over the edge (ADR 0014 §C3, freeze-on-disconnect), and a linked
  promoted setting saves the upstream value over the user's. Blender restores
  the user's value instead. → **step 2.**

**Step 5** is EdgeKind itself. **Step 3** fixes a lock cycle found on the way.
The steps are numbered in the order they are meant to be built.

---

## Status and sequence — 2026-09-28

| Step | Work | Status | Detail plan | Next |
|---|---|---|---|---|
| 0 | Groundwork: split-reroute tests used a stale key; callback and pipe architecture docs corrected, ErrorNode test trap recorded | **Landed** on `edge-kinds` | none | merge with step 1 |
| 1 | Callbacks through reroutes; `Propagation` (lazy / eager / immediate) replaces `is_lazy` | **Built** on `edge-kinds`, not merged | [landed/2026-09-27-callbacks-through-reroutes.md](landed/2026-09-27-callbacks-through-reroutes.md) | merge `edge-kinds` as it stands |
| 2 | Unlinking reveals a port's own value — one rule for every port, edge kind and propagation mode, promoted settings included | **Designing** (inquisition 2026-09-28) | needed; [2026-09-28-immediate-reset-to-default.md](2026-09-28-immediate-reset-to-default.md) is a superseded first version for callback ports only | inquisition, then plan, on its own branch |
| 3 | Lock-order cycle between `NodeWrapper.redraw()` and validation | **Found**, pre-existing, not fixed | needed (small) | your go-ahead |
| 4 | Callbacks across Subgraph boundaries (Groups and macros) | Open questions only | needed | inquisition |
| 5 | EdgeKind | Analysis done, not designed | needed, probably several (5.1, 5.2, …) | inquisition |

Branch `edge-kinds` holds steps 0 and 1.
Acceptance tests for steps 1 and 2 live in
`tests/core/test_edge/test_disconnect_semantics.py`; today they report
`7 passed, 2 xfailed` — the two strict xfails are step 2's.

### The sequence

**1. Callbacks through reroutes** — **built**, merge as it stands. Reroutes
forward callback subscriptions at once, removing an edge upstream
unsubscribes, and edges carry a `Propagation` mode with `immediate` locked on
callback edges and `lazy` locked on edges out of promoted outlets (ADR 0039).
An unlinked callback inlet resets to `None` for now; step 2 replaces that rule.
Merging before step 2 because step 2 reaches into settings, promotion and
widgets, too much to hold on one branch.

**2. Unlinking reveals a port's own value.** Inquisition, then plan, on its
own branch.

*The rule.* An inlet shows the value from its edge while an edge feeds it, and
its own value otherwise. The own value is what the user, the node or a setting
wrote, falling back to the declared default. Edges never overwrite it. The
change on unlink takes effect like any other change of that port, through its
propagation mode: an immediate port at once (a reroute forwards it), a
deferred port when its node next executes. That is one rule, with the existing
propagation axis deciding the timing — no per-kind or per-mode variants.

*Where it lives.* Two slots in the `DataField` — own and linked. Edge writes
already arrive as `set_value(v, source_id=edge_id)`, every other write without
a source. A pooled field already has this shape: one entry per source, and
unlinking removes the entry. A promoted port shares the setting's field, so
the setting sees the linked value while linked and the user's value after —
ADR 0014's "one cell, two views" stays; its §C3 freeze rule is replaced.
Nothing structural and no edge ever changes the own value; only edits and an
explicit reset do.

*Promoted settings.* `setting.__get__` is a plain cell read and every setting
write carries no source, so both work as they are. Three changes:
`Settings._local_value` (read by save and `_reset`) reads the own slot, so a
linked promoted setting saves the user's value; the equality guard in
`setting.__set__` compares against the own value; and `demote_setting` must
clear the cell's linked slot first — today it releases the cell before the
port's edges detach, which would leave a stale linked value behind.

*Callbacks.* A relay whose inlet is unlinked forwards its own value, its
default, so a callback emitter reads the element type's default as "no
subscription" and drops that entry. That is what callback values mean, not an
unlink rule, and EdgeKind will own it as a property of the callback kind. The
superseded plan's pool rule and test node carry over.

*Tests that flip from freeze to reveal:* `test_promotion_single_cell.py:296`
(demote keeps the cell value), `test_promotion_e2e.py` step 4,
`tests/ui/panel/test_promoted_row_state.py:265`.

*Open questions for the inquisition:*

- what a widget shown while its port is linked displays and edits — own or
  linked value;
- what `StoreStrategy.WHEN_LINKED` means once only the own value is saved;
- a pending lazy pull when its edge is removed;
- a multi-link scalar inlet: reveal only when its last edge goes?
- whether promote-to-inlet still marks the field locally set — with two slots
  a mirror sync only reaches the own slot, so a promoted shadow inlet could
  keep tracking its global (the deviation ADR 0014's amendment calls
  deliberate);
- `CALLBACK`'s default becoming `""`, so callbacks need no absence storage;
- the extra branch in `get_value()` on the hot path — benchmark it;
- the ADR: "unlinking reveals the own value", superseding ADR 0014 §C3.

**3. The redraw/validation lock cycle.**
`NodeWrapper.redraw()` holds `NodeWrapper._lock` and then takes the validation
lock through `mark_node_dirty`; `ValidationManager._validate_batch` holds the
validation lock and then takes `NodeWrapper._lock` in `_housekeeping`. Seen once
as a 120 s timeout in `test_node_skin_graph_tier.py` under `-n 4`; it can hang a
studio the same way (see `.insights/project_subgraph_scheduler_deadlock.md` for
the sibling case). Independent of steps 1 and 2, but it comes before step 4,
which adds immediate writes across the Graph-node card — the object that spans
two graphs and two sets of these locks.

**4. Callbacks across Subgraph boundaries.** Inquisition, then plan.
Reuses steps 1 and 2: the inlet-`on_change` relay pattern, locked `immediate`
propagation, the unlink rule. Open questions carried from the 2026-09-27
inquisition:

- how a boundary finds its pairs at wiring time — pairs are cached in
  `on_assembly`, but `subgraph_crossing.card_port_id()` maps ids without
  assembly;
- where the entering handler lives: the card's inlet, in the host graph;
- lock order across the card (step 3 first);
- lifting `CollapseToGraphNodeAction`'s refusal (`_callback_edge_partners`),
  and whether collapse batches the drop-and-re-add of a subscription;
- the growing slot is `FlowType.DATA`, so a callback cannot grow an interface
  port today (ADR 0036) — should it?
- Promote to Macro with a callback interface, and a macro reload rebuilding the
  interior (ADR 0038). Macros are built (`03-macro.md`), so this is in scope.

**5. EdgeKind.** Inquisition, then plans, numbered 5.1, 5.2, … After step 4,
so every relay is generic before kinds become pluggable. Inputs from the
2026-09-27 analysis:

- *Authority.* The port's `flow_type` decides; `Edge.edge_type` is a copied
  cache. No exhaustive `match` or `FlowType`-keyed dict exists, so nothing
  assumes the set is closed.
- *Must become per-kind:* link arity (`DataPort.__post_init__` sets
  `allow_multiple_links` per flow type), immediacy (`FlowType.is_immediate`),
  allowed and locked propagation (ADR 0039), the value that means "none"
  (callbacks, from step 2), the edge validation hook
  (`StructuralValidator.validate_edge`, empty since step 1), control crossing
  (`flat_view._is_control_crossed`) and the data walk's stop at control nodes
  (`data_flow_builder`).
- *Rendering:* edge strokes are already data-driven (`ui_edge.edge_visual_state`);
  pin glyphs come from `PinIconResolver._kind_of`, which draws no pin at all for
  an unknown kind; drag compatibility is string equality in `canvas.vue` on
  `data-pin-flow-type` while the server checks in `_formal_validation` — ship a
  compatibility key the kind computes.
- *Visual-only kinds:* assembly filters on `DATA`/`CONTROL`, so a kind that is
  neither is ignored by execution already; a visual-only kind may allow no
  propagation at all.
- *Serialization and authoring:* saved graphs store `edge_type` as a string;
  ~40 `flow_type=` declarations in barn libraries become edge-kind declarations.
- *Cleanup to fold in:* `FlowAssemblyManager._process_callback_edges`
  (statistics only, and since step 1 it counts reroutes as emitters);
  `EdgeWrapper.is_callback_edge` / `is_data_edge` and
  `DataPort.is_callback_pin` / `is_control_pin` / `is_data_pin` (no callers;
  `is_control_edge` has one test); three separate "is this a control node?"
  derivations beside `NodeBehaviorFlags.is_control_node`; `NodeType` as a
  second classification axis next to the kind.

### Small items

Not steps; each is a single change.

- `packages/haywire-core/src/haywire/barn/builtin/__init__.py` names
  `builtin:type:*` / `builtin:node:*` keys; the real prefix is `haywire-core:`.
  Probably where the stale test key came from.
- `docs/guides/panels.md` links to a file under `.insights/`, outside
  `docs_dir`. `mkdocs build --strict` fails on it; CI builds without
  `--strict`, so CI passes.
- Check the OAK-D camera once in the studio: step 1 fixed a stale cache, so
  `OakDCameraNode.hb_on_callbacks_changed` now fires on edge-driven writes, as
  `callbacks-arch.md` always described. visiongraph's tests do not cover that
  path.

