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

An **edge** connects an outlet port on a source node to an inlet port on a sink node. The data structure is `Edge` (a dataclass — connection identifiers, type, adapter chain keys, lazy flag). The lifecycle is owned by `EdgeWrapper` — a wrapper that runs the 4-stage build pipeline (formal validation → structural validation → adapter chain → test), manages the `link → unlink → detach` lifecycle, and handles displacement and re-enablement when ports are over-subscribed.

Two-tier port storage is the core mental model. Each port keeps two dictionaries:

- **`_linked_edges`** — active edges currently used for data pipes.
- **`_all_edges`** — every edge ever registered, including displaced and non-functional ones. This is what makes re-enablement possible.

When a new edge displaces an existing one on a single-connection inlet, the displaced edge stays in `_all_edges` but leaves `_linked_edges`. If the new edge later loses functionality (adapter broken by hot-reload), the port scans `_all_edges` for a candidate to re-enable. Edges aren't deleted — they're just not currently the active one.

## 2. Contract

### 2.1 Creation flow

```python
graph.create_edge_wrapper(source_node_id, outlet_port_id,
                          sink_node_id, inlet_port_id,
                          lazy=False)
```

Internal sequence:

1. Look up the outlet's `FlowType` to classify the edge (DATA / CONTROL / CALLBACK).
2. Instantiate `EdgeWrapper` (which constructs the internal `Edge` dataclass).
3. Call `edge_wrapper.build()` — runs the 4-stage pipeline (§3.1).
4. Call `graph.add_edge_wrapper()` → `edge_wrapper.link()` — registers at both ports.

### 2.2 The 4-stage build pipeline

```text
build()
  ├─ _formal_validation()    do nodes/ports exist? same direction? same FlowType?
  ├─ _structural_validation() domain rules (e.g. callback source must be event node)
  ├─ _build_adapter_chain()   find/create adapter chain (DATA edges only)
  └─ _test()                  run a sample value through the adapter chain
```

Sequential and short-circuiting on failure. Each stage sets flags and error fields on `EdgeWrapperState`.

| State | Meaning |
|---|---|
| **functional** | registered + formally validated + built + test passed |
| **valid** | functional + structural + linked on both ports |

### 2.3 Connection rules by FlowType

| | Outlet `allow_multiple` | Inlet `allow_multiple` |
|---|---|---|
| **DATA** | `True` (set by `DataPort.__post_init__`) | `False` (default) |
| **CONTROL (EXEC)** | `False` (hardcoded in `__post_init__`) | `True` (hardcoded in `__post_init__`) |
| **CALLBACK** | `False` (default) | `False` (default) |
| **Pooled inlet** | N/A (inlet only) | `True` (set by `PooledType._configure_port`) |

Cross-flow connections (e.g. EXEC→DATA) are rejected in `_formal_validation()`. Same-direction connections (outlet→outlet, inlet→inlet) are also rejected there.

### 2.4 EdgeWrapper lifecycle methods

Three methods own the lifecycle (all on `EdgeWrapper`, not on the graph):

- **`link()`** — Functional edge registers at both ports. May displace existing edges on single-connection ports. Displaced edges stay in `_all_edges` but leave `_linked_edges`.
- **`unlink()`** — Edge lost functionality (e.g. adapter broke during hot-reload). Removed from `_linked_edges` but stays in `_all_edges`. Triggers re-enablement scan on the affected port.
- **`detach()`** — Edge explicitly deleted. Full removal from both `_linked_edges` and `_all_edges`. Triggers re-enablement scan.

Graph integration:

- `graph.add_edge_wrapper()` → `edge_wrapper.link()`
- `graph.remove_edge_wrapper()` → `edge_wrapper.detach()`

The graph no longer owns port-linking logic — it's decentralised in `EdgeWrapper`.

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

- The displaced edge is removed from `_linked_edges` but remains in `_all_edges`.
- **Asymmetric notification**: inlet displacement informs the source outlet (it needs a pipe update); outlet displacement does NOT inform the sink inlet.

When an active edge is removed (`detach`) or loses functionality (`unlink`), the port scans `_all_edges` FIFO for a functional candidate to re-enable. If found, `candidate.link() + candidate.redraw()` is called.

### 3.3 Lazy propagation and the unified dirty model

Edges support two propagation modes via `Edge.is_lazy` (per-edge, not per-port):

- **Eager** (`is_lazy=False`, default): outlet value is transformed through the adapter chain and pushed to the inlet immediately. The inlet is marked dirty; `on_change` is deferred to execution time.
- **Lazy** (`is_lazy=True`): no transform or push at propagation time. The inlet is marked dirty with a reference to the pipe. At execution time, `resolve_dirty_data()` pulls the outlet's *current* value (always-latest semantics) through the adapter chain.

Different edges to the same inlet can have different modes. The `lazy` parameter is passed to `create_edge_wrapper()` and stored on the `Edge` dataclass. It serialises via `to_dict()` and deserialises with `False` default for backward compatibility.

**Unified dirty model.** Both eager and lazy edges use the same deferred callback model. `on_change` callbacks for edge-driven inlet changes are *never* fired at push time — they are always deferred to `resolve_dirty_data()` at execution time. This debounces mixed pooled+lazy scenarios.

```text
EAGER EDGE:
  outlet.set_value(value) → pipes.propagate(value)
    ├─ adapter chain transforms value
    └─ inlet.set_value(converted, edge_id=uuid)
       ├─ stores value (NO on_change)
       └─ inlet._mark_as_data_dirty()

LAZY EDGE:
  outlet.set_value(value) → pipes.propagate(value)
    ├─ pipe sees lazy flag → skips transform
    └─ inlet._mark_as_data_dirty(pipe=self, edge_id=uuid)

AT EXECUTION TIME (both):
  node._execute()
    ├─ for each dirty port: resolve_dirty_data()
    │     ├─ pull lazy pipe data (transform + store via pull_lazy())
    │     └─ fire on_change ONCE (debounced across all edge types)
    ├─ on_validate()
    └─ worker()
```

### 3.4 `set_value()` callback rules

The `set_value()` method on DataPort distinguishes between edge-driven and widget/programmatic changes:

| Path | `edge_id` | `on_change` | Behaviour |
|---|---|---|---|
| Edge-driven inlet | set | (any) | Value stored; `_mark_as_data_dirty()` called; `on_change` fires later in `resolve_dirty_data()` |
| Widget / programmatic inlet | `None` | exists | Value stored; `on_change` fires **immediately**; no dirty mark (prevents double-fire) |
| Widget / programmatic inlet | `None` | absent | Value stored; `_mark_as_data_dirty()` called; `resolve_dirty_data()` skips callback (none) |
| Outlet (any) | (any) | exists | `on_change` fires immediately; pipes propagate downstream |

`set_value_by_lazy_link()` is a low-level method that stores the value without firing any callbacks. Used by `pull_lazy()` during lazy resolution. `set_value()` delegates to it for the actual storage step.

### 3.5 Pipe-based data transport

The `Pipes` class owns all data transport — both eager push (`propagate()`) and lazy pull (`pull_lazy()`). It stores:

| Field | Purpose |
|---|---|
| `_outlet_port` | Reference to the source DataPort (for lazy reads) |
| `sinks` | `dict[edge_id, DataPort]` — target inlets |
| `chains` | `dict[edge_id, IAdapter]` — adapter chains per connection |
| `lazy_flags` | `dict[edge_id, bool]` — propagation mode per connection |

`pull_lazy(edge_id)` reads the outlet's current value (always-latest), transforms it through the adapter chain, and calls `set_value_by_lazy_link()` on the inlet.

### 3.6 ValidationManager — debounced batch processing

`ValidationManager` processes dirty nodes and edges in debounced batches (50ms default). Tests use `force_immediate_validation()` for synchronous execution.

**Priority system (`ChangeReason`).** Reasons are prioritised — higher priority overrides lower in the dirty queue:

| Priority | Reasons |
|---|---|
| 100 | `NODE_REMOVED`, `EDGE_REMOVED` |
| 90 | `NODE_ADDED`, `EDGE_ADDED` |
| 80 | `NODE_HOT_RELOADED`, `NODE_RESET_REQUESTED`, `EDGE_ADAPTERS_RELOADED`, `EDGE_RESET_REQUESTED` |
| 70 | `NODE_VALIDATION_REQUESTED`, `EDGE_VALIDATION_REQUESTED` |
| 60 | Redraw reasons |
| 50 | `GRAPH_REQUIRE_REASSEMBLY` |

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

The full hot-reload pipeline (file watcher → import → registry events → wrapper rebuild → graph revalidation) lives in [architecture/hot-reload](../../hot-reload/hot-reload-arch.md). The original visual diagram (`diagrams.md`) for the EdgeWrapper → UIEdge → GraphCanvasVue cascade is recoverable via git history.

## 4. Boundary

The edge subsystem is **not**:

- The **adapter authoring surface** — see [components/adapters](../../../components/adapters/adapter-canon.md).
- The **graph→flow assembly** — assembly consumes edges to build the executable Flow; that pipeline lives in [architecture/execution/assembly](../assembly/assembly-arch.md).
- The **VM** — execution context creation, pause/resume, and the two-stack model live in [architecture/execution/virtual-machine](../virtual-machine/virtual-machine-arch.md).
- The **on-canvas rendering** — visual state propagates through `UIEdge → GraphCanvasVue`; that's in [architecture/studio/canvas](../../studio/canvas/canvas-arch.md).

## 5. Examples

### 5.1 Adapter chain examples (with the test types in `haybale-testing`)

```text
BoolToIntAdapter:     TEST_BOOL  → TEST_INT
IntToFloatAdapter:    TEST_INT   → TEST_FLOAT
FloatToStringAdapter: TEST_FLOAT → TEST_STRING
```

Chains BFS-resolves to:

| Source → Target | Chain |
|---|---|
| BOOL → INT | 1 adapter |
| BOOL → FLOAT | 2 adapters (BOOL→INT, INT→FLOAT) |
| BOOL → STRING | 3 adapters |
| INT → FLOAT | 1 adapter |
| INT → STRING | 2 adapters |
| FLOAT → STRING | 1 adapter |

`TEST_TEMPERATURE` extends `TEST_FLOAT`, so:

| Source → Target | Chain |
|---|---|
| TEMPERATURE → FLOAT | empty (child→parent passthrough) |
| TEMPERATURE → STRING | 1 adapter (FLOAT→STRING resolved via MRO) |
| FLOAT → TEMPERATURE | rejected (parent→child narrowing, no implicit downcast) |

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
- **Lazy propagation hot-reload.** When an adapter inside a lazy chain reloads, the edge marks dirty but the next `pull_lazy()` re-resolves through the new chain. This works today; whether the edge should *eagerly* re-pull on adapter change is undecided.

## Appendix — key state locations

| Field | Purpose |
|---|---|
| `EdgeWrapper._state` (`EdgeWrapperState`) | All flags, errors, timing |
| `DataPort._linked_edges` | `dict[edge_id, EdgeWrapper]` — active linked edges (used for pipes) |
| `DataPort._all_edges` | `dict[edge_id, EdgeWrapper]` — all tracked edges including displaced/non-functional |
| `DataPort._pending_lazy_pipes` | `set[(Pipes, edge_id)]` — lazy pipes needing resolution at execution time |
| `DataPort.allow_multiple_links` | Connection limit flag |
| `Edge.is_lazy` | Per-edge lazy propagation flag (default `False`) |
| `Edge.chain_adapter_keys` | List of adapter registry keys (empty = ReturnAdapter) |
| `EdgeWrapper._first_adapter` | Head of the executable adapter chain |
| `EdgeWrapper._outlet_port` / `_inlet_port` | Resolved DataPort references (set during formal validation) |
| `Pipes._outlet_port` | Source DataPort reference (for lazy reads) |
| `Pipes.lazy_flags` | `dict[edge_id, bool]` — per-connection propagation mode |

### Key files

- `src/haywire/core/edge/edge_wrapper.py` — `EdgeWrapper` + `EdgeWrapperState` (owns link/unlink/detach lifecycle)
- `src/haywire/core/edge/edge.py` — `Edge` data object (includes `is_lazy` flag)
- `src/haywire/core/types/port.py` — `DataPort` (two-tier storage, displacement, re-enablement, deferred on_change, lazy resolution)
- `src/haywire/core/types/pipe.py` — `Pipes` (eager push via `propagate()`, lazy pull via `pull_lazy()`, always-latest semantics)
- `src/haywire/core/graph/base.py` — `BaseGraph` (create/add/remove edge, delegates to edge methods)
- `src/haywire/core/graph/validation.py` — `ValidationManager` (debounced batch validation, priority system)
- `src/haywire/core/graph/types.py` — `ChangeReason` enum, `ValidationResult`
- `src/haywire/core/adapter/factory.py` — `AdapterFactory` (chain creation)
- `src/haywire/core/adapter/registry.py` — `AdapterRegistry` (BFS chain discovery)
- `src/haywire/core/adapter/base.py` — `IAdapter`, `ReturnAdapter`, `BaseAdapter`
