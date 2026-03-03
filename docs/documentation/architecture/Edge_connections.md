# Haywire Edge Connection System — Architecture Notes

Reference document for the edge creation and validation system.
Written alongside `test_edge_connections.py` to capture the rules being tested.

---

## Core Flow: How Edges Are Created and Validated

An edge connects an **outlet port** on a source node to an **inlet port** on a sink node. Creation happens via `graph.create_edge_wrapper(source_node_id, outlet_port_id, sink_node_id, inlet_port_id, lazy=False)` which:

1. Looks up the outlet's `FlowType` to classify the edge
2. Instantiates `EdgeWrapper` (which also creates the internal `Edge` data object)
3. Calls `edge_wrapper.build()` — the 4-stage validation pipeline
4. Calls `graph.add_edge_wrapper()` — registers + calls `edge_wrapper.link()`

## The Build Pipeline (4 stages, sequential, short-circuits on failure)

```
build()
  → _formal_validation()    — do nodes/ports exist? same direction? same FlowType?
  → _structural_validation() — domain rules (e.g. callback source must be event node)
  → _build_adapter_chain()   — find/create adapter chain (DATA edges only)
  → _test()                  — run test value through the adapter chain
```

Each stage sets flags and error fields on `EdgeWrapperState`. An edge is **functional** if registered + formally validated + built + test passed. An edge is **valid** if functional + structural + linked on both ports.

## Port Linking: Two-Tier Storage

Ports maintain two separate edge dictionaries:

- **`_linked_edges`**: Active edges used for data pipes. Only functional edges that "won" their slot.
- **`_all_edges`**: ALL edges ever registered, including displaced and non-functional ones. Used for re-enablement.

### Link Lifecycle (managed by EdgeWrapper)

Edge linking is owned by `EdgeWrapper`, not the graph. Three methods control the lifecycle:

- **`edge.link()`** — Functional edge registers at both ports. May displace existing edges on single-connection ports. Displaced edges stay in `_all_edges` but leave `_linked_edges`.
- **`edge.unlink()`** — Edge lost functionality (e.g. adapter broke during hot reload). Removed from `_linked_edges` but stays in `_all_edges`. Triggers re-enablement scan.
- **`edge.detach()`** — Edge explicitly deleted. Full removal from both `_linked_edges` and `_all_edges`. Triggers re-enablement scan.

### Displacement and Re-enablement

When a new edge displaces an existing one on a single-connection port:

- The displaced edge is removed from `_linked_edges` but remains in `_all_edges`
- **Asymmetric notification**: inlet displacement informs the source outlet (needs pipe update); outlet displacement does NOT inform the sink inlet

When an active edge is removed (`detach`) or loses functionality (`unlink`), the port scans `_all_edges` FIFO for a functional candidate to re-enable. If found, `candidate.link()` + `candidate.redraw()` is called.

### Graph Integration

- `graph.add_edge_wrapper()` → `edge_wrapper.link()`
- `graph.remove_edge_wrapper()` → `edge_wrapper.detach()`
- The graph no longer owns port-linking logic (decentralized in Phase 4 refactoring)

## Connection Rules by FlowType

| | Outlet `allow_multiple` | Inlet `allow_multiple` |
|---|---|---|
| **DATA** | `True` (set in `DataPort.__post_init__`) | `False` (default) |
| **CONTROL (EXEC)** | `False` (hardcoded in `__post_init__`) | `True` (hardcoded in `__post_init__`) |
| **CALLBACK** | `False` (default) | `False` (default) |
| **Pooled inlets** | N/A (inlet only) | `True` (set by `PooledType._configure_port`) |

Cross-flow connections (e.g. EXEC→DATA) are rejected in `_formal_validation()` via `flow_type` mismatch check. Same-direction connections (outlet→outlet, inlet→inlet) are also rejected there.

## Adapter Chain Creation (DATA edges only)

`AdapterFactory.create_chain(source_type, sink_type)` handles three cases:

1. **Both scalar** → `_create_scalar_chain()`:
   - Same type or child→parent (`issubclass`): `ReturnAdapter()` (no-op)
   - Different types: BFS through `AdapterRegistry` to find shortest chain, walks source's MRO for derived types
   - Chain is built right-to-left: `AdapterA(child=AdapterB(child=ReturnAdapter()))`

2. **Same compound structure** (e.g. `ArrayType[X] → ArrayType[Y]`): `_create_element_chain()`:
   - Finds container adapter (e.g. `ArrayArrayAdapter`) via registry
   - Creates element chain for inner types
   - Same element type → `ReturnAdapter()`
   - Different → wraps: `ArrayArrayAdapter(child=element_chain)`

3. **Different compound structure** → `_create_structural_chain()` (structural transformation)

4. **Scalar ↔ compound** → rejected (no conversion possible)

The chain is stored as a list of registry keys in `edge.chain_adapter_keys`. `ReturnAdapter` has no keys, so `len(chain_adapter_keys) == 0` means direct/identity pass-through.

## Validation Pipeline (ValidationManager)

The `ValidationManager` processes dirty nodes and edges in debounced batches (50ms default). Tests use `force_immediate_validation()` for synchronous execution.

### Priority System (ChangeReason)

Reasons are prioritized — higher priority reasons override lower ones in the dirty queue:

| Priority | Reasons |
|----------|---------|
| 100 | `NODE_REMOVED`, `EDGE_REMOVED` |
| 90 | `NODE_ADDED`, `EDGE_ADDED` |
| 80 | `NODE_HOT_RELOADED`, `NODE_RESET_REQUESTED`, `EDGE_ADAPTERS_RELOADED`, `EDGE_RESET_REQUESTED` |
| 70 | `NODE_VALIDATION_REQUESTED`, `EDGE_VALIDATION_REQUESTED` |
| 60 | Redraw reasons |
| 50 | `GRAPH_REQUIRE_REASSEMBLY` |

**Important for testing**: `create_node_wrapper()` leaves a pending `NODE_ADDED` (priority 90) in the dirty queue. Subsequent `mark_node_dirty()` calls with lower-priority reasons (like `NODE_HOT_RELOADED` at 80) will be silently dropped. Tests must call `force_immediate_validation()` after setup to flush pending validations before testing specific scenarios.

### Batch Processing

1. **Nodes first**: `requires_rebuild()` → `node_wrapper.build()` + mark attached edges dirty. `requires_validation()` → just mark attached edges dirty (no node rebuild).
2. **Edges second**: `requires_rebuild()` or `requires_validation()` → `edge.build()`, then `edge.link()` if functional, `edge.unlink()` if lost functionality.

### Node Hot Reload

`NODE_HOT_RELOADED` triggers full `node_wrapper.build()`:

1. `_instantiate()` — creates a brand new node instance (old instance cleaned up)
2. `_initialize()` — calls `init()` on new instance, creating new port objects
3. All attached edges are marked dirty and rebuilt in the edge phase
4. Edge `_formal_validation()` refreshes port references from the new node instance
5. Edge `link()` registers at the new port objects

## Lazy Propagation and Unified Dirty Model

### Overview

Edges support two propagation modes controlled by `Edge.is_lazy` (per-edge, not per-port):

- **Eager** (`is_lazy=False`, default): Outlet value is transformed through the adapter chain and pushed to the inlet immediately. The inlet is marked dirty; `on_change` is deferred to execution time.
- **Lazy** (`is_lazy=True`): No transform or push at propagation time. The inlet is marked dirty with a reference to the pipe. At execution time, `resolve_dirty_data()` pulls the outlet's **current** value (always-latest semantics) through the adapter chain.

Different edges to the same inlet can have different modes. The `lazy` parameter is passed to `create_edge_wrapper()` and stored on the `Edge` dataclass. It serializes via `to_dict()` and deserializes via `load_from_dict()` (with `False` default for backward compatibility).

### Unified Dirty Model

Both eager and lazy edges use the same deferred callback model. `on_change` callbacks for edge-driven inlet changes are **never** fired at push time — they are always deferred to `resolve_dirty_data()` at execution time. This debounces mixed pooled+lazy scenarios.

```
EAGER EDGE:
  outlet.set_value(value) → pipes.propagate(value)
    → adapter chain transforms value
    → inlet.set_value(converted, edge_id=uuid)
      → stores value (NO on_change)
      → inlet._mark_as_data_dirty()
    → node marks port dirty

LAZY EDGE:
  outlet.set_value(value) → pipes.propagate(value)
    → pipe sees lazy flag → skips transform
    → inlet._mark_as_data_dirty(pipe=self, edge_id=uuid)
    → node marks port dirty

AT EXECUTION TIME (both):
  node._execute()
    → for each dirty port: resolve_dirty_data()
      → pull lazy pipe data (transform + store via pull_lazy())
      → fire on_change ONCE (debounced across all edge types)
    → on_validate()
    → worker()
```

### `set_value()` Callback Rules

The `set_value()` method on DataPort distinguishes between edge-driven and widget/programmatic changes:

- **Edge-driven inlet** (`edge_id` is set): Value stored, `_mark_as_data_dirty()` called. `on_change` fires later during `resolve_dirty_data()`.
- **Widget/programmatic inlet** (`edge_id` is `None`, `on_change` exists): Value stored, `on_change` fires **immediately**. `_mark_as_data_dirty()` is NOT called (prevents double-fire).
- **Widget/programmatic inlet** (`edge_id` is `None`, no `on_change`): Value stored, `_mark_as_data_dirty()` called. Node re-executes, `resolve_dirty_data()` skips callback (it's `None`).
- **Outlet** (any): `on_change` fires immediately. Pipes propagate to downstream inlets.

### `set_value_by_lazy_link()` — Pure Value Storage

`set_value_by_lazy_link()` is a low-level method that stores the value without firing any callbacks. Used by `pull_lazy()` during lazy resolution. `set_value()` delegates to it for the actual storage step.

### Pipe-Based Data Transport

The `Pipes` class owns all data transport — both eager push (`propagate()`) and lazy pull (`pull_lazy()`). It stores:

- `_outlet_port`: Reference to the source DataPort (for lazy reads)
- `sinks`: `dict[edge_id, DataPort]` — target inlets
- `chains`: `dict[edge_id, IAdapter]` — adapter chains per connection
- `lazy_flags`: `dict[edge_id, bool]` — propagation mode per connection

`pull_lazy(edge_id)` reads the outlet's **current** value (always-latest), transforms it through the adapter chain, and calls `set_value_by_lazy_link()` on the inlet.

### `resolve_dirty_data()` on DataPort

```python
def resolve_dirty_data(self):
    # 1. Pull data from lazy pipes (always-latest)
    while self._pending_lazy_pipes:
        pipe, uuid = self._pending_lazy_pipes.pop()
        pipe.pull_lazy(uuid)

    # 2. Fire deferred on_change ONCE (covers both eager pushes and lazy pulls)
    if self.on_change is not None:
        self._trigger_callback('on_change', self.get_value())
```

`_pending_lazy_pipes` stores `(Pipes, edge_id)` tuples for lazy edges needing resolution. Eager edges don't add entries here — they store their value at push time but still defer `on_change` to this method.

### Dirty Port Resolution in `_execute()`

Dirty ports are resolved for **all node types** (not just data nodes), before `on_validate()` and `worker()`:

```python
def _execute(self, context):
    if self.behavior.is_data_node:
        if not self._has_dirty_ports:
            return None  # data nodes skip if nothing changed

    while self._has_dirty_ports:
        port = self._has_dirty_ports.pop()
        port.resolve_dirty_data()

    self.on_validate(context)
    # ... worker ...
```

## Dynamic Port Reconfiguration (`rejig`)

Nodes can dynamically add/remove ports using the `rejig()` context manager:

```python
with self.rejig(include=r'^dynamic_'):    # flag matching ports for removal
    self._build_dynamic_ports(count)      # re-add surviving ports (unflagged by add())
# _pop() runs automatically on exit      # remove any still-flagged ports
```

`rejig()` wraps the internal `_push()`/`_pop()` pair in a context manager, guaranteeing cleanup even if an exception occurs during reconfiguration.

### How It Works

1. **On enter**: flags existing ports as candidates for removal (filtered by `include`/`exclude`)
2. **Inside the block**: ports re-added via `self.add()` are unflagged (preserved with connections intact)
3. **On exit**: any still-flagged ports are destroyed

### Port Destruction on Exit

When a flagged port is destroyed:

- `_detach_all_edges()` removes all edges from both tiers
- **Asymmetric notification**: destroyed inlet → informs source outlet; destroyed outlet → does NOT inform sink inlet
- `mark_as_structuraly_dirty()` queues validation for edge rebuilds

### Filter Options

| Call                                                  | Effect                   |
| ----------------------------------------------------- | ------------------------ |
| `rejig()` | All ports |
| `rejig(include=['a', 'b'])` | Only 'a' and 'b' |
| `rejig(exclude=['ctrl'])` | All except 'ctrl' |
| `rejig(include=r'^input_')` | All starting with 'input_' |
| `rejig(exclude=r'^ctrl_')` | All except control ports |
| `rejig(include=r'^param_', exclude=['param_0'])` | Params except param_0 |

### DynamicPortTestNode (test fixture)

`DynamicPortTestNode` provides configurable dynamic ports for testing:

- **Static ports**: `bool_inlet`, `bool_outlet` (always present)
- **Config port**: `port_count` (TEST_INT inlet with `on_change='hb_reconfigure'`)
- **Dynamic ports**: `dynamic_inlet_0..N`, `dynamic_outlet_0..N` (TEST_INT, controlled by `port_count`)

Setting `port_count` triggers `hb_reconfigure()` synchronously via the `on_change` callback, which uses `rejig(include=r'^dynamic_')` internally.

## Registered Test Adapters (haybale-testing)

```
BoolToIntAdapter:     TEST_BOOL  → TEST_INT
IntToFloatAdapter:    TEST_INT   → TEST_FLOAT
FloatToStringAdapter: TEST_FLOAT → TEST_STRING
```

So the chains are: BOOL→INT (1), BOOL→FLOAT (2), BOOL→STRING (3), INT→FLOAT (1), INT→STRING (2), FLOAT→STRING (1).

`TEST_TEMPERATURE` extends `TEST_FLOAT` — so TEMPERATURE→FLOAT is a no-op (child→parent). FLOAT→TEMPERATURE is rejected (parent→child narrowing, no implicit downcast). TEMPERATURE→STRING resolves via MRO: finds FLOAT→STRING chain.

## Key State Locations

- **`EdgeWrapper._state`** (`EdgeWrapperState` dataclass): all flags, errors, timing
- **`DataPort._linked_edges`**: `dict[edge_id, EdgeWrapper]` — active linked edges (used for pipes)
- **`DataPort._all_edges`**: `dict[edge_id, EdgeWrapper]` — all tracked edges including displaced/non-functional
- **`DataPort._pending_lazy_pipes`**: `set[(Pipes, edge_id)]` — lazy pipes needing resolution at execution time
- **`DataPort.allow_multiple_connections`**: the connection limit flag
- **`Edge.is_lazy`**: `bool` — per-edge lazy propagation flag (default `False`)
- **`Edge.chain_adapter_keys`**: list of adapter registry keys (empty = ReturnAdapter)
- **`EdgeWrapper._first_adapter`**: the head of the adapter chain (executable)
- **`EdgeWrapper._outlet_port` / `_inlet_port`**: resolved DataPort references (set during formal validation)
- **`Pipes._outlet_port`**: source DataPort reference (for lazy reads)
- **`Pipes.lazy_flags`**: `dict[edge_id, bool]` — per-connection propagation mode

## Key Files

- `src/haywire/core/edge/edge_wrapper.py` — EdgeWrapper + EdgeWrapperState (owns link/unlink/detach lifecycle)
- `src/haywire/core/edge/edge.py` — Edge data object (includes `is_lazy` flag)
- `src/haywire/core/types/port.py` — DataPort (two-tier storage, displacement, re-enablement, deferred on_change, lazy resolution)
- `src/haywire/core/types/pipe.py` — Pipes (eager push via `propagate()`, lazy pull via `pull_lazy()`, always-latest semantics)
- `src/haywire/core/graph/base.py` — BaseGraph (create/add/remove edge, delegates to edge methods)
- `src/haywire/core/graph/validation.py` — ValidationManager (debounced batch validation, priority system)
- `src/haywire/core/graph/types.py` — ChangeReason enum, ValidationResult
- `src/haywire/core/node/base.py` — NodeData (`rejig()` port reconfiguration, `_iter_ports()` generator queries)
- `src/haywire/core/node/node_wrapper.py` — NodeWrapper (build/rebuild, mark_as_structuraly_dirty)
- `src/haywire/core/adapter/factory.py` — AdapterFactory (chain creation)
- `src/haywire/core/adapter/registry.py` — AdapterRegistry (BFS chain discovery)
- `src/haywire/core/adapter/base.py` — IAdapter, ReturnAdapter, BaseAdapter
- `src/haywire/core/validation/structural_validator.py` — domain rules
- `src/haywire/core/types/enums.py` — FlowType, PortType
- `libraries/haybale-core/haybale_core/types/pooled_type.py` — PooledType + PooledField
- `libraries/haybale-core/haybale_core/types/array_type.py` — ArrayType + ArrayField
- `libraries/haybale-core/haybale_core/adapters/compound_adapters.py` — ArrayArrayAdapter
- `libraries/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py` — EdgeLinkTestNode (main test node)
- `libraries/haybale-testing/haybale_testing/nodes/testbed/dynamic_port_test.py` — DynamicPortTestNode (dynamic reconfiguration)


## Test Cases (60 tests)

### Data Inlet: Many-to-One (4 tests)

- Single connection accepted on standard inlets
- Second valid connection replaces the first (unlinks old edge)
- Invalid cross-flow connection does NOT replace existing valid connection
- Adapter-requiring connections (bool→int) still trigger replacement

### Data Inlet: Many-to-Many / Pooled (3 tests)

- Pooled inlets accept multiple simultaneous connections
- Pooled inlets work with adapter chains from different source types
- Data outlets allow multiple outgoing connections

### Adapter Chain Creation (9 tests)

- Same type → no adapter (empty chain)
- TEST_BOOL → TEST_INT = 1 adapter
- TEST_BOOL → TEST_FLOAT = 2 adapters
- TEST_BOOL → TEST_STRING = 3 adapters
- TEST_INT → TEST_FLOAT = 1, TEST_INT → TEST_STRING = 2, TEST_FLOAT → TEST_STRING = 1
- ARRAY[TEST_STRING] → ARRAY[TEST_STRING] = no adapter (same element)
- ARRAY[TEST_BOOL] → ARRAY[TEST_STRING] = has adapter(s)

### Derived Type Connections (3 tests)

- TEST_TEMPERATURE → TEST_FLOAT (child→parent) = no adapter needed
- TEST_TEMPERATURE → TEST_STRING = resolves via MRO ancestor chain
- TEST_FLOAT → TEST_TEMPERATURE (parent→child) = fails without adapter (no implicit downcast)

### Execute and Callback Flow Connections (4 tests)

- EXEC connections work (formally validated)
- EXEC outlets allow only one outgoing connection (second replaces first)
- EXEC inlets allow multiple incoming connections (both edges stay valid)
- CALLBACK connections pass formal validation

### Cross Flow-Type Rejection (6 tests)

- EXEC ↔ DATA rejected both directions
- EXEC ↔ CALLBACK rejected both directions
- CALLBACK ↔ DATA rejected both directions

### Direction and Self-Connection (3 tests)

- Outlet→outlet rejected (direction validation)
- Inlet→inlet rejected (direction validation)
- Self-connection (node to itself) rejected in formal validation

### Edge Removal (2 tests)

- Edge removal unlinks both ports
- Removing one edge from pooled inlet preserves others

### Edge State (5 tests)

- Valid edge state flags inspection
- Invalid edge has error set
- Scalar→array compound type mismatch rejected
- Pooled port `allow_multiple_connections` flag verification
- Standard data inlet `allow_multiple_connections = False` verification

### Two-Tier Storage and Re-enablement (6 tests)

- Displaced edge remains in `_all_edges` but leaves `_linked_edges`
- Removing active edge promotes displaced functional candidate via re-enablement
- `detach()` removes from both `_all_edges` and `_linked_edges`
- Inlet displacement informs source outlet (asymmetric rule)
- Outlet displacement does NOT inform sink inlet (asymmetric rule)
- Re-enablement skips non-functional edges

### Validation Pipeline: Node Rebuild (4 tests)

- `NODE_VALIDATION_REQUESTED` → edges stay valid (no node rebuild, just edge revalidation)
- `NODE_HOT_RELOADED` → node re-instantiated with new port objects, edges survive rebuild
- Hot reload preserves adapter chains (bool→int survives with chain intact)
- Hot reload preserves displacement state (displaced edge stays in `_all_edges` on rebuilt ports)

### Dynamic Port Reconfiguration (3 tests)

- Port removed via `rejig()` → connected edge detached
- Port surviving `rejig()` (same ID re-added) → edge survives reconfiguration
- Static port edge unaffected by dynamic port reconfiguration

### Lazy Propagation (8 tests)

- `create_edge_wrapper(..., lazy=True)` sets `is_lazy` on edge and edge wrapper
- `is_lazy` survives `to_dict()` serialization round-trip
- Eager edge pushes value to inlet, port marked dirty, `on_change` deferred to `resolve_dirty_data()`
- Lazy edge does NOT transform/push value — marks inlet dirty with pipe reference
- `resolve_dirty_data()` pulls lazy value through adapter chain (bool→int conversion)
- Always-latest: outlet changes 10→20→30, lazy inlet gets 30 on resolve (skips intermediates)
- Mixed pooled inlet (eager+lazy edges), `on_change` fires once during resolve (debounced)
- Widget/programmatic change (no `edge_id`) fires `on_change` immediately, not deferred
