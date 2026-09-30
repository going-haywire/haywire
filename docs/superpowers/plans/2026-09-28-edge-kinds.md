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
| 0 | Groundwork: split-reroute tests used a stale key; callback and pipe architecture docs corrected, ErrorNode test trap recorded | **Landed** on `master` | none | push |
| 1 | Callbacks through reroutes; `Propagation` (lazy / eager / immediate) replaces `is_lazy` | **Landed** on `master` | [landed/2026-09-27-callbacks-through-reroutes.md](landed/2026-09-27-callbacks-through-reroutes.md) | push |
| 2 | Unlinking reveals a port's own value — one rule for every port, edge kind and propagation mode, promoted settings included | **Built** on `unlink-own-value`, not merged | [2026-09-28-unlink-reveals-own-value.md](2026-09-28-unlink-reveals-own-value.md), 10 tasks; supersedes [2026-09-28-immediate-reset-to-default.md](2026-09-28-immediate-reset-to-default.md) | merge |
| 3 | Lock-order cycle between `NodeWrapper.redraw()` and validation | **Built** on `unlink-own-value`, not merged | none (small; recorded in `.insights/project_subgraph_scheduler_deadlock.md`) | merge with step 2 |
| 4 | Callbacks across Subgraph boundaries (Groups and macros) | **Built** on `unlink-own-value`, not merged | [2026-09-29-callbacks-across-subgraph-boundaries.md](2026-09-29-callbacks-across-subgraph-boundaries.md), 10 tasks | merge |
| 5 | EdgeKind | Analysis done, not designed | needed, probably several (5.1, 5.2, …) | inquisition |

Local `master` is ahead of `origin/master` (steps 0 and 1, and this
overview), not pushed. Acceptance tests for steps 1 and 2 live in
`tests/core/test_edge/test_disconnect_semantics.py`; since step 2 they report
`9 passed`, no xfails.

### The sequence

**1. Callbacks through reroutes** — **landed**. Reroutes
forward callback subscriptions at once, removing an edge upstream
unsubscribes, and edges carry a `Propagation` mode with `immediate` locked on
callback edges and `lazy` locked on edges out of promoted outlets (ADR 0039).
An unlinked callback inlet resets to `None` for now; step 2 replaces that rule.
Merging before step 2 because step 2 reaches into settings, promotion and
widgets, too much to hold on one branch.

**2. Unlinking reveals a port's own value.** **Built**:
[2026-09-28-unlink-reveals-own-value.md](2026-09-28-unlink-reveals-own-value.md),
branch `unlink-own-value`, ADR 0040 lands with it.

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

*Settled in the inquisition of 2026-09-28:*

- vocabulary: **own value** and **linked value**;
- only the own value is saved; `StoreStrategy.WHEN_LINKED` is removed;
- a widget on a linked inlet shows the linked value and refuses edits, the
  view snapping back — one widget kind, the rule in the widget base layer;
- a pending lazy pull is dropped with its edge;
- a multi-link inlet reveals only when its last edge goes; a DATA inlet takes
  one edge unless pooled;
- promotion marks nothing locally set, so a promoted shadow inlet keeps
  tracking its global;
- the field event fires on every stored change; the node's `on_change` only
  when the value it sees changes;
- `CALLBACK`'s default becomes `""`, callbacks need no absence storage, and an
  immediate pool drops an entry equal to its element's default (a library may
  still give its callback type another default);
- `@type` rejects a primitive type whose default holds no value;
- the linked value lives in the `DataField` base, as a second instance of the
  field class;
- `get_value()`'s extra branch is benchmarked before and after;
- ADR 0040 "unlinking reveals the own value" supersedes ADR 0014 §C3.

**3. The redraw/validation lock cycle.** **Built**.
`NodeWrapper.redraw()` held `NodeWrapper._lock` and then took the validation
lock through `mark_node_dirty`, while `ValidationManager._validate_batch` holds
the validation lock and takes node locks in `build()`/`_housekeeping`. So did a
hot reload (`_on_node_lifecycle_event`, on the watcher thread) and `build()`
itself (node code adding a port). Seen once as a 120 s timeout in
`test_node_skin_graph_tier.py` under `-n 4`. Rule now: the graph's validation
lock comes before a node's lock (`NodeWrapper._locked()`); the notify-only
methods take no node lock. Pinned by `tests/core/test_node/test_node_lock_order.py`.
Across graphs the order is Subgraph before host (a Subgraph batch reaches the
host through the card); step 4 must keep to it.

**4. Callbacks across Subgraph boundaries.** **Built**:
[2026-09-29-callbacks-across-subgraph-boundaries.md](2026-09-29-callbacks-across-subgraph-boundaries.md);
ADR 0041 lands with it. Settled 2026-09-29: an immediate relay on both sides of
the card (keyed on `is_immediate`), a resync in `reconcile_interface`, deferred
pairs only in the execution copy, a bare `ADD` accepting any flow, one
subscription per interface port, one validation lock per graph tree. A listener
is an EVENT node, which a Subgraph may not contain, so outward a subscription
crosses only on its way through (Q11A). The questions below were the input.
Reuses steps 1 and 2: the inlet-`on_change` relay pattern, locked `immediate`
propagation, the unlink rule. Open questions carried from the 2026-09-27
inquisition:

- how a boundary finds its pairs at wiring time — pairs are cached in
  `on_assembly`, but `subgraph_crossing.card_port_id()` maps ids without
  assembly;
- where the entering handler lives: the card's inlet, in the host graph;
- lock order across the card: Subgraph before host, never the reverse
  (step 3; `.insights/project_subgraph_scheduler_deadlock.md`);
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
- *A wildcard kind.* A bare `ADD` accepts an edge of any flow (step 4); today
  that is `type_cls._is_any`, checked in `_formal_validation`, `edge_flow_type`
  and `pin_render` + `canvas.vue`. Rather than a `FlowType.ANY`, make it a rule
  of the compatibility key each kind computes, so "matches any kind" is stated
  once. `_is_any` stays for the adapter factory's type compatibility.
- *Split `FlowType.NONE`.* It does three jobs today: a config port's flow, which
  nothing reads (`PortType.CONFIG` decides); a container type's "take my
  element's flow" (`ArrayType`/`PooledType._configure_port`); and the default of
  every type that declares none — a value type then gets pins that connect only
  to each other and that assembly ignores, silently (`haybale-TEST_A`'s
  `TestData` did, fixed 2026-09-30). With kinds: a config port carries no kind,
  a container derives its element's kind explicitly, and `@type` rejects a value
  type that declares no kind, as it rejects a primitive with no default value.
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
- Check the OAK-D camera once in the studio: step 1 fixed a stale cache, so
  `OakDCameraNode.hb_on_callbacks_changed` now fires on edge-driven writes, as
  `callbacks-arch.md` always described. visiongraph's tests do not cover that
  path.

