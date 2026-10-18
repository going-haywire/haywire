---
status: draft
doc_template: impl-spec
scope: EdgeWrapper lifecycle, the 4-stage build pipeline, two-tier port storage, adapter chains, lazy propagation, dirty model
see-also:
  - ../../../components/adapters/adapter-canon.md
  - ../../../guides/ports.md
  - ../../hot-reload/hot-reload-arch.md
  - ../assembly/assembly-arch.md
  - ../../../reference/glossary.md
---

# Edges — Architecture

## 1. Mental model

An **edge** connects an outlet port on a source node to an inlet port on a sink node. The data structure is `Edge` (a dataclass — connection identifiers, type, adapter chain keys, propagation mode). The lifecycle is owned by `EdgeWrapper` — a wrapper that runs the 4-stage build pipeline (formal validation → structural validation → adapter chain → test), manages the `link → unlink → detach` lifecycle, and handles displacement and re-enablement when ports are over-subscribed.

Two-tier port storage is the core mental model. Each port holds two `LinkSet`s, `port.incoming` (edges ending at it) and `port.outgoing` (edges leaving it); an inlet fills only the first, an outlet only the second, a swinglet ([ADR 0048](../../../adr/0048-swinglets.md)) may fill both. Each set keeps two dictionaries:

- **`linked`** — active edges currently used for data pipes.
- **`all`** — every edge ever registered at this end, including displaced and non-functional ones. This is what makes re-enablement possible.

When a new edge displaces an existing one on a single-connection end, the displaced edge stays in `all` but leaves `linked`. If the new edge later loses functionality (adapter broken by hot-reload), the set scans `all` for a candidate to re-enable. Edges aren't deleted — they're just not currently the active one.

## 2. Contract

### 2.1 Creation flow

```python
graph.create_edge_wrapper(source_node_id, outlet_port_id,
                          sink_node_id, inlet_port_id,
                          propagation=Propagation.EAGER)
```

Internal sequence:

1. Take the edge's wire type from its ports (`EdgeWrapper.wire_type`): a data, control or callback wire, with the role that tells the framework what to do with the edge. It is derived, never passed or saved.
2. Instantiate `EdgeWrapper` (which constructs the internal `Edge` dataclass).
3. Call `edge_wrapper.build()` — runs the 4-stage pipeline (§3.1).
4. Call `graph.add_edge_wrapper()` → `edge_wrapper.link()` — registers at both ports.

### 2.2 The 4-stage build pipeline

```text
build()
  ├─ _formal_validation()    do nodes/ports exist? same direction? wire keys match (`wires_match`)?
  ├─ _structural_validation() domain rules (none per edge today)
  ├─ _build_adapter_chain()   find/create adapter chain (DATA edges only)
  └─ _test()                  run a sample value through the adapter chain
```

Sequential and short-circuiting on failure. Each stage sets flags and error fields on `EdgeWrapperState`.

| State          | Meaning                                               |
| -------------- | ----------------------------------------------------- |
| **functional** | registered + formally validated + built + test passed |
| **valid**      | functional + structural + linked on both ports        |

Only a **valid** edge carries values. An outlet builds its pipes from its valid linked edges (`DataPort.get_valid_edges()`), so an edge that fails structural validation stays in the graph and is drawn as invalid, but delivers nothing to its inlet.

### 2.3 Connection rules by wire type

Each port has a **link ceiling**: how many edges it holds at once, read as `DataPort.takes_many_links`. The framework derives it from the port's wire role and its field's storage; nothing else writes it (`_configure_port` sets colour and refusals only). A port can only narrow it with `single_link=True`. See [ADR 0044](../../../adr/0044-link-ceiling.md).

| Port                                                         | Outlet                                       | Inlet                                          |
| ------------------------------------------------------------ | -------------------------------------------- | ---------------------------------------------- |
| `DataWire` (`DEPENDENT`)                                     | many                                         | one                                            |
| `ControlWire` (`SEQUENCE`)                                   | one (the VM keeps one transition per outlet) | many                                           |
| `CallbackWire` (`IMMEDIATE`)                                 | many                                         | one                                            |
| a `VISUAL` wire                                              | many                                         | many                                           |
| bare `ADD` slot                                              | many                                         | one                                            |
| pooled inlet (field `keeps_value_per_source()`)              | n/a (a pool has no outlet)                   | many                                           |

A container's role is its element's. `PooledType` refuses a control element and an outlet; `ArrayType` of control and callback elements is allowed.

Two pins connect when their wire keys match: equal wire-type ids, or a bare `ADD` slot's wildcard `*` (`wires_match`, mirrored on the canvas). Connections across wire types (e.g. EXEC→DATA) are rejected in `_formal_validation()`. A failing edge is never rewritten; while it fails, its wire type comes from whichever end resolves, for drawing only. See [ADR 0042](../../../adr/0042-wire-types-replace-flowtype.md). Same-direction connections (outlet→outlet, inlet→inlet) are also rejected there.

### 2.4 EdgeWrapper lifecycle methods

Three methods own the lifecycle (all on `EdgeWrapper`, not on the graph):

- **`link()`** — Functional edge registers at both ports. May displace existing edges on single-connection ports. Displaced edges stay in the set's `all` but leave `linked`.
- **`unlink()`** — Edge lost functionality (e.g. adapter broke during hot-reload). Removed from `linked` but stays in `all`. Triggers re-enablement scan on the affected port.
- **`detach()`** — Edge explicitly deleted. Full removal from both `linked` and `all`. Triggers re-enablement scan.

Graph integration:

- `graph.add_edge_wrapper()` → `edge_wrapper.link()`
- `graph.remove_edge_wrapper()` → `edge_wrapper.detach()`

Port-linking logic lives in `EdgeWrapper`, not `Graph` — each edge owns its own link/detach lifecycle.

## 3. Lifecycle

### 3.1 Adapter chain creation (DATA edges only)

`AdapterFactory.create_chain(source_type, sink_type)` handles four cases:

1. **Both scalar** → `_create_scalar_chain()`:
   
   - Same type or child→parent (`issubclass`): `ReturnAdapter()` — no-op.
   - Different types: BFS through `AdapterRegistry` to find shortest chain; walks source's MRO for derived types.
   - Chain is built right-to-left: `AdapterA(child=AdapterB(child=ReturnAdapter()))`.

2. **Same compound structure** (e.g. `ArrayType[X] → ArrayType[Y]`): `_create_element_chain()`:
   
   - Finds container adapter (e.g. `ArrayArrayAdapter`) via registry.
   - Creates element chain for inner types.
   - Same element type → `ReturnAdapter()`.
   - Different → wraps: `ArrayArrayAdapter(child=element_chain)`.

3. **Different compound structure** → `_create_structural_chain()` (structural transformation).

4. **Scalar ↔ compound** → rejected (no conversion possible).

The chain is stored as a list of registry keys in `edge.chain_adapter_keys`. `ReturnAdapter` has no keys, so `len(chain_adapter_keys) == 0` means direct/identity pass-through.

Authoring adapters lives in [components/adapters](../../../components/adapters/adapter-canon.md).

### 3.2 Displacement and re-enablement

When a new edge displaces an existing one on a single-connection port:

- The displaced edge is removed from `linked` but remains in `all`.
- **Asymmetric notification**: inlet displacement informs the source outlet (it needs a pipe update); outlet displacement does NOT inform the sink inlet.

When an active edge is removed (`detach`) or loses functionality (`unlink`), the port's set scans `all` FIFO for a functional candidate to re-enable. If found, `candidate.link() + candidate.redraw()` is called.

**Unlinking reveals the own value.** When an inlet loses its last linked edge and no displaced edge takes over, its field drops the linked value (`DataField.clear_linked`) and the own value shows again (ADR 0040). The node learns of it through the port's propagation: an immediate inlet fires `on_change` at once, so a reroute passes it on (see [callbacks-arch §2.4](../callbacks/callbacks-arch.md)); a deferred inlet is marked dirty for its node's next execution. A lazy pull still queued for the removed edge is dropped. A pooled inlet needs nothing extra: `LinkSet.clear_link` already removed that source's entry.

### 3.3 Propagation and the unified dirty model

Each edge has a **propagation** mode (`Propagation`, per edge, not per port):

- **Eager** (default): outlet value is transformed through the adapter chain and pushed to the inlet immediately. The inlet is marked dirty; `on_change` is deferred to execution time.
- **Lazy**: no transform or push at propagation time. The inlet is marked dirty with a reference to the pipe. At execution time, `resolve_dirty_data()` pulls the outlet's *current* value (always-latest semantics) through the adapter chain.
- **No propagation** (callback edges): a wire type whose `propagation` is empty gives its edges none. The value takes effect on write by the `IMMEDIATE` role (see the exception below).

Users choose lazy or eager per edge, and different edges to the same inlet can differ. `create_edge_wrapper(propagation=...)` stores the choice on the `Edge`, and `to_dict()` saves it under `propagation`. A wire type lists the modes its edges may take (`WireType.propagation`); a single entry locks the edge to it, and an empty list gives the edge no propagation (`EdgeWrapper.propagation` is `None`). A mode is also locked to `lazy` on an edge out of an `is_linked_lazy` outlet (every promoted outlet). Neither lock is read from a saved graph. `EdgeWrapper.locked_propagation` names the lock; `EdgeWrapper.propagation` is the mode in effect. See [ADR 0039](../../../adr/0039-propagation-mode-replaces-is-lazy.md).

**Unified dirty model.** Both eager and lazy edges use the same deferred callback model. `on_change` callbacks for edge-driven inlet changes are *never* fired at push time — they are always deferred to `resolve_dirty_data()` at execution time. This debounces mixed pooled+lazy scenarios.

**Exception: immediate inlets fire at once.** An inlet on a wire with the `IMMEDIATE` role (`DataPort.is_immediate`, i.e. `CallbackWire`) is exempt from the deferral above — `set_value()` fires its `on_change` synchronously at push time even when `edge_id` is set, same as the widget/programmatic path.

```text
EAGER EDGE:
  outlet.set_value(value) → pipes.propagate() → pipe.propagate()
    └─ pipe.pull()
       ├─ reads the outlet's current value
       ├─ adapter chain transforms it
       └─ inlet.set_value(converted, edge_id=uuid)
          ├─ stores value (NO on_change)
          └─ inlet._mark_as_data_dirty()

LAZY EDGE:
  outlet.set_value(value) → pipes.propagate() → pipe.propagate()
    └─ inlet._mark_as_data_dirty(pipe=self)   pipe queued, nothing pulled yet

AT EXECUTION TIME (both):
  node._execute()
    ├─ for each dirty port: resolve_dirty_data()
    │     ├─ pull lazy pipe data (transform + store via pull())
    │     └─ fire on_change ONCE (debounced across all edge types)
    ├─ on_validate()
    └─ worker()
```

### 3.3a Style bag and saving

A wire type that names a style bag (`WireType.style`, an `EdgeSettings` subclass) gives each of its edges one, bound in `build()` once formal validation passes and dropped, values kept, when it fails (ADR 0047). `EdgeWrapper.serialize()` is the one save path: `Edge.to_dict()` plus `"style"` when a value is set; graph save, the clipboard and collapse all call it. A style change marks `ChangeReason.EDGE_STYLE_CHANGED`, which redraws the edge and, unlike `EDGE_REDRAW_REQUESTED`, records an unsaved change. Paste, Subgraph instantiation, collapse and expand pass `propagation` and `style` on to the edges they create.

### 3.4 `set_value()` callback rules

The `set_value()` method on DataPort distinguishes between edge-driven, widget/programmatic changes and the wire role:

| Path                                  | `Edge-driven` | `on_change` | Behaviour                                                                                       |
| ------------------------------------- | --------- | ----------- | ----------------------------------------------------------------------------------------------- |
| (any)               | no    | absent      | `on_change` does not fire      |
| Widget / programmatic input           | no   | exists      | `on_change` fires **immediately**         |
| Own write while linked (no `edge_id`, field holds a linked value) | no | exists | no `on_change`, no dirty mark: the own value changed behind the linked one |
| Immediate role (CALLBACK) | yes       | exists       | `on_change` fires **immediately**                                                 |
| DEPENDENT, SEQUENCE role   | yes       | exists       | `on_change` fires just before the worker |
| Outlet (any)                          | (any)     | exists      | `on_change` fires **immediately**; pipes propagate downstream                                       |

`Pipe.pull()` stores through the same `set_value(converted, edge_id=...)` call, so a lazily pulled value follows the edge-driven rows above.

### 3.5 Pipe-based data transport

A linked outlet owns one `Pipes`, which holds a `Pipe` per valid edge, keyed by edge id (`Pipes._pipes`). A `Pipe` owns one connection — both eager push (`propagate()`) and the pull itself (`pull()`):

| Field                 | Purpose                                                                          |
| --------------------- | -------------------------------------------------------------------------------- |
| `sink`                | Target inlet `DataPort`                                                          |
| `chain`               | Head of the edge's adapter chain                                                 |
| `is_lazy`             | Whether the edge's propagation is lazy, copied from the edge when the pipe is built |
| `_outlet_port`        | Source `DataPort`, read on every pull (always-latest)                            |
| `_sink_holds_absence` | Whether the sink accepts absence, read once from `sink.data.accepts_absence()`   |

`Pipe.pull()` reads the outlet's current value, transforms it through the chain and stores it with `sink.set_value(converted, edge_id=...)`. When the outlet holds `None`, the pull forwards absence only to a sink that accepts it; any other sink keeps its last value.

Pipes are rebuilt whenever the outlet is structurally dirty (`_refresh_pipes()` during housekeeping). After a rebuild the outlet pushes its current value through every pipe at once (`DataPort._housekeeping`), so a newly linked edge, or one rebuilt on load or hot reload, delivers the source's value without any node running. That is why setting `EdgeWrapper.propagation` on a live edge marks its outlet dirty: the existing `Pipe` keeps the mode it was built with.

### 3.6 ValidationManager — debounced batch processing

`ValidationManager` processes dirty nodes and edges in debounced batches (50ms default). Tests use `force_immediate_validation()` for synchronous execution.

**Priority system (`ChangeReason`).** Reasons are prioritised — higher priority overrides lower in the dirty queue:

| Priority | Reasons                                                                                       |
| -------- | --------------------------------------------------------------------------------------------- |
| 100      | `NODE_REMOVED`, `EDGE_REMOVED`                                                                |
| 90       | `NODE_ADDED`, `EDGE_ADDED`                                                                    |
| 80       | `NODE_HOT_RELOADED`, `NODE_RESET_REQUESTED`, `EDGE_ADAPTERS_RELOADED`, `EDGE_RESET_REQUESTED` |
| 70       | `NODE_VALIDATION_REQUESTED`, `EDGE_VALIDATION_REQUESTED`                                      |
| 60       | Redraw reasons                                                                                |
| 50       | `GRAPH_REQUIRE_REASSEMBLY`                                                                    |

**Important for testing**: `create_node_wrapper()` leaves a pending `NODE_ADDED` (priority 90) in the dirty queue. Subsequent `mark_node_dirty()` calls with lower-priority reasons (like `NODE_HOT_RELOADED` at 80) are silently dropped. Tests must call `force_immediate_validation()` after setup to flush pending validations before testing specific scenarios.

**Batch order:**

1. **Nodes first**: `requires_rebuild()` → `node_wrapper.build()` + mark attached edges dirty. `requires_validation()` → just mark attached edges dirty (no node rebuild).
2. **Edges second**: `requires_rebuild()` or `requires_validation()` → `edge.build()`, then `edge.link()` if functional, `edge.unlink()` if lost functionality.

### 3.7 Hot-reload coordination — node rebuild

`NODE_HOT_RELOADED` triggers full `node_wrapper.build()`:

1. `_instantiate()` — creates a brand new node instance (old instance cleaned up).
2. `_initialize()` — calls `init()` on new instance, creating new port objects.
3. All attached edges are marked dirty and rebuilt in the edge phase.
4. Edge `_formal_validation()` refreshes port references from the new node instance.
5. Edge `link()` registers at the new port objects.

The full hot-reload pipeline (file watcher → import → registry events → wrapper rebuild → graph revalidation) lives in [architecture/hot-reload](../../hot-reload/hot-reload-arch.md). The original visual diagram (`diagrams.md`) for the EdgeWrapper → visual-layer → GraphCanvasVue cascade is recoverable via git history.

## 4. Boundary

The edge subsystem is **not**:

- The **adapter authoring surface** — see [components/adapters](../../../components/adapters/adapter-canon.md).
- The **graph→flow assembly** — assembly consumes edges to build the executable Flow; that pipeline lives in [architecture/execution/assembly](../assembly/assembly-arch.md).
- The **VM** — execution context creation, pause/resume, and the two-stack model live in [architecture/execution/virtual-machine](../virtual-machine/virtual-machine-arch.md).
- The **on-canvas rendering** — an edge owns no UI object; `edge_visual_state()` turns wrapper state into stroke values that `VisualLayerHandlers` batches into one `SyncAllEdgesEvent` per validation pass for `GraphCanvasVue` to draw. That's in [architecture/studio/canvas](../../studio/canvas/canvas-arch.md).

## 5. Examples

### 5.1 Adapter chain examples (with the test types in `haybale-testing`)

```text
BoolToIntAdapter:     TEST_BOOL  → TEST_INT
IntToFloatAdapter:    TEST_INT   → TEST_FLOAT
FloatToStringAdapter: TEST_FLOAT → TEST_STRING
```

Chains BFS-resolves to:

| Source → Target | Chain                            |
| --------------- | -------------------------------- |
| BOOL → INT      | 1 adapter                        |
| BOOL → FLOAT    | 2 adapters (BOOL→INT, INT→FLOAT) |
| BOOL → STRING   | 3 adapters                       |
| INT → FLOAT     | 1 adapter                        |
| INT → STRING    | 2 adapters                       |
| FLOAT → STRING  | 1 adapter                        |

`TEST_TEMPERATURE` extends `TEST_FLOAT`, so:

| Source → Target      | Chain                                                   |
| -------------------- | ------------------------------------------------------- |
| TEMPERATURE → FLOAT  | empty (child→parent passthrough)                        |
| TEMPERATURE → STRING | 1 adapter (FLOAT→STRING resolved via MRO)               |
| FLOAT → TEMPERATURE  | rejected (parent→child narrowing, no implicit downcast) |

### 5.2 Pooled inlet receiving multiple sources

A pooled inlet accepts multiple simultaneous edges. Each edge's adapter chain is independent — different source types can all converge on one pooled inlet, each transformed through its own chain.

```text
node_a outlet[BOOL]   ──┐
                        ├── pooled inlet[INT]   ─→ {node_a: 1, node_b: 42, node_c: 0}
node_b outlet[INT]    ──┤
node_c outlet[BOOL]   ──┘
```

Each edge gets its own entry in the pooled `dict[source_id, value]`.

## 6. Open questions

- **Re-enablement priority.** Currently FIFO. If multiple displaced edges are functional at re-enablement time, the first registered wins. A user-controllable priority mechanism may be useful.
- **Adapter chain caching.** Chains are recomputed on every edge build. For libraries with many adapter pairs, caching the BFS result keyed by `(source_type, sink_type)` could help.
- **Lazy propagation hot-reload.** When an adapter inside a lazy chain reloads, the edge marks dirty but the next `pull()` re-resolves through the new chain. This works today; whether the edge should *eagerly* re-pull on adapter change is undecided.

## Appendix — key state locations

| Field                                      | Purpose                                                                             |
| ------------------------------------------ | ----------------------------------------------------------------------------------- |
| `EdgeWrapper._state` (`EdgeWrapperState`)  | All flags, errors, timing                                                           |
| `DataPort.incoming` / `.outgoing` (`LinkSet`) | Per-end edge storage; `.linked` is `dict[edge_id, EdgeWrapper]` of active edges (used for pipes) |
| `LinkSet.all`                              | `dict[edge_id, EdgeWrapper]` — all tracked edges at that end including displaced/non-functional |
| `DataPort._pending_lazy_pipes`             | `set[Pipe]` — lazy pipes to pull at execution time                                  |
| `DataPort.takes_many_links` / `single_link` | The port's link ceiling, and the setting that narrows it (ADR 0044) |
| `Edge.propagation`                         | Chosen propagation mode (default `EAGER`); `EdgeWrapper.propagation` applies the locks |
| `Edge.chain_adapter_keys`                  | List of adapter registry keys (empty = ReturnAdapter)                               |
| `EdgeWrapper._first_adapter`               | Head of the executable adapter chain                                                |
| `EdgeWrapper._outlet_port` / `_inlet_port` | Resolved DataPort references (set during formal validation)                         |
| `Pipes._outlet_port`                       | Source DataPort reference (for lazy reads)                                          |
| `Pipes._pipes`                             | `dict[edge_id, Pipe]` — one pipe per valid edge; each `Pipe` carries its `is_lazy`  |

### Key files

- `src/haywire/core/edge/edge_wrapper.py` — `EdgeWrapper` + `EdgeWrapperState` (owns link/unlink/detach lifecycle)
- `src/haywire/core/edge/edge.py` — `Edge` data object (includes the chosen propagation)
- `src/haywire/core/types/port.py` — `DataPort` (two-tier storage, displacement, re-enablement, deferred on_change, lazy resolution)
- `src/haywire/core/types/pipe.py` — `Pipes` (eager push via `propagate()`, lazy pull via `pull()`, always-latest semantics)
- `src/haywire/core/graph/base.py` — `BaseGraph` (create/add/remove edge, delegates to edge methods)
- `src/haywire/core/graph/validation.py` — `ValidationManager` (debounced batch validation, priority system)
- `src/haywire/core/graph/types.py` — `ChangeReason` enum, `ValidationResult`
- `src/haywire/core/adapter/factory.py` — `AdapterFactory` (chain creation)
- `src/haywire/core/adapter/registry.py` — `AdapterRegistry` (BFS chain discovery)
- `src/haywire/core/adapter/base.py` — `IAdapter`, `ReturnAdapter`, `BaseAdapter`
