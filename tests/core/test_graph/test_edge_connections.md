# Haywire Edge Connection System — Architecture Notes

Reference document for the edge creation and validation system.
Written alongside `test_edge_connections.py` to capture the rules being tested.

---

## Core Flow: How Edges Are Created and Validated

An edge connects an **outlet port** on a source node to an **inlet port** on a sink node. Creation happens via `graph.create_edge_wrapper(source_node_id, outlet_port_id, sink_node_id, inlet_port_id)` which:

1. Looks up the outlet's `FlowType` to classify the edge
2. Instantiates `EdgeWrapper` (which also creates the internal `Edge` data object)
3. Calls `edge_wrapper.build()` — the 4-stage validation pipeline
4. Calls `graph.add_edge_wrapper()` — registers + links to ports

## The Build Pipeline (4 stages, sequential, short-circuits on failure)

```
build()
  → _formal_validation()    — do nodes/ports exist? same direction? same FlowType?
  → _structural_validation() — domain rules (e.g. callback source must be event node)
  → _build_adapter_chain()   — find/create adapter chain (DATA edges only)
  → _test()                  — run test value through the adapter chain
```

Each stage sets flags and error fields on `EdgeWrapperState`. An edge is **functional** if registered + formally validated + built + test passed. An edge is **valid** if functional + structural + linked on both ports.

## Port Linking (separate from build)

After build, `graph.add_edge_wrapper()` calls `update_port_link()`. This is where connection limits are enforced:

- If the edge is **functional**, it calls `port._add_link(edge)` on both ports
- `_add_link` checks `allow_multiple_connections`:
  - If `False`: replaces existing edge (calls `_clear_link` on old one first)
  - If `True`: adds alongside existing edges
- Then `edge.validate_link(port)` checks if the port actually accepted the link
- Other edges on the same port get re-validated (they may become unlinked)
- Finally `_housekeeping()` refreshes the Pipes (outlet → inlet data propagation)

## Connection Rules by FlowType

| | Outlet `allow_multiple` | Inlet `allow_multiple` |
|---|---|---|
| **DATA** | `True` (set in `DataPort.__post_init__`) | `False` (default) |
| **CONTROL (EXEC)** | `False` (default) | `False` (default) |
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

## Registered Test Adapters (haybale-testing)

```
BoolToIntAdapter:     TEST_BOOL  → TEST_INT
IntToFloatAdapter:    TEST_INT   → TEST_FLOAT
FloatToStringAdapter: TEST_FLOAT → TEST_STRING
```

So the chains are: BOOL→INT (1), BOOL→FLOAT (2), BOOL→STRING (3), INT→FLOAT (1), INT→STRING (2), FLOAT→STRING (1).

`TEST_TEMPERATURE` extends `TEST_FLOAT` — so TEMPERATURE→FLOAT is a no-op (child→parent), and FLOAT→TEMPERATURE also works (the system treats it as compatible via the sink type's ancestry). TEMPERATURE→STRING resolves via MRO: finds FLOAT→STRING chain.

## Key State Locations

- **`EdgeWrapper._state`** (`EdgeWrapperState` dataclass): all flags, errors, timing
- **`DataPort._edge_wrappers`**: `dict[connection_uuid, EdgeWrapper]` — the linked edges
- **`DataPort.allow_multiple_connections`**: the connection limit flag
- **`Edge.chain_adapter_keys`**: list of adapter registry keys (empty = ReturnAdapter)
- **`EdgeWrapper._first_adapter`**: the head of the adapter chain (executable)
- **`EdgeWrapper._outlet_port` / `_inlet_port`**: resolved DataPort references (set during formal validation)

## Key Files

- `src/haywire/core/edge/edge_wrapper.py` — EdgeWrapper + EdgeWrapperState
- `src/haywire/core/edge/edge.py` — Edge data object
- `src/haywire/core/types/port.py` — DataPort (link management, connection rules)
- `src/haywire/core/graph/base.py` — BaseGraph (create/add/remove edge, port linking)
- `src/haywire/core/adapter/factory.py` — AdapterFactory (chain creation)
- `src/haywire/core/adapter/registry.py` — AdapterRegistry (BFS chain discovery)
- `src/haywire/core/adapter/base.py` — IAdapter, ReturnAdapter, BaseAdapter
- `src/haywire/core/validation/structural_validator.py` — domain rules
- `src/haywire/core/types/enums.py` — FlowType, PortType
- `libraries/haybale-core/haybale_core/types/pooled_type.py` — PooledType + PooledField
- `libraries/haybale-core/haybale_core/types/array_type.py` — ArrayType + ArrayField
- `libraries/haybale-core/haybale_core/adapters/compound_adapters.py` — ArrayArrayAdapter


## Notes on Test Cases

Data Inlet: Many-to-One (4 tests)
	Single connection accepted on standard inlets
	Second valid connection replaces the first (unlinks old edge)
	Invalid cross-flow connection does NOT replace existing valid connection
	Adapter-requiring connections (bool→int) still trigger replacement

Data Inlet: Many-to-Many / Pooled (3 tests)
	Pooled inlets accept multiple simultaneous connections
	Pooled inlets work with adapter chains from different source types
	Data outlets allow multiple outgoing connections

Adapter Chain Creation (9 tests)
	Same type → no adapter (empty chain)
	TEST_BOOL → TEST_INT = 1 adapter
	TEST_BOOL → TEST_FLOAT = 2 adapters
	TEST_BOOL → TEST_STRING = 3 adapters
	TEST_INT → TEST_FLOAT = 1, TEST_INT → TEST_STRING = 2, TEST_FLOAT → TEST_STRING = 1
	ARRAY[TEST_STRING] → ARRAY[TEST_STRING] = no adapter (same element)
	ARRAY[TEST_BOOL] → ARRAY[TEST_STRING] = has adapter(s)

Derived Type Connections (3 tests)
	TEST_TEMPERATURE → TEST_FLOAT (child→parent) = no adapter needed
	TEST_TEMPERATURE → TEST_STRING = resolves via MRO ancestor chain
	TEST_FLOAT → TEST_TEMPERATURE (parent→child) = succeeds (bidirectional compatibility)

Execute Flow Connections (3 tests)
	EXEC connections work
	EXEC outlets allow only one outgoing connection (second replaces first)
	EXEC inlets allow only one incoming connection
	Cross Flow-Type Rejection (6 tests)
	EXEC ↔ DATA rejected both directions
	EXEC ↔ CALLBACK rejected both directions
	CALLBACK ↔ DATA rejected both directions

Additional Tests (11 tests)
	Outlet→outlet and inlet→inlet rejected (direction validation)
	Self-connection (node to itself) passes formal validation
	Edge removal unlinks both ports
	Removing one edge from pooled inlet preserves others
	Valid edge state flags inspection
	Invalid edge has error set
	Scalar→array compound type mismatch rejected
	Pooled port allow_multiple_connections flag verification
	Standard data inlet allow_multiple_connections = False verification


