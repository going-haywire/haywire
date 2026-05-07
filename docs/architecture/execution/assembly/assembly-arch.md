---
status: draft
doc_template: impl-spec
scope: Graph→Flow assembly pipeline — FlowAssemblyManager, validation, event-node identification, control-flow + localized data-flow construction, JIT reassembly
see-also:
  - ../flow/flow-arch.md
  - ../edges/edges-arch.md
  - ../callbacks/callbacks-arch.md
  - ../virtual-machine/virtual-machine-arch.md
  - ../../../reference/glossary.md
---

# Assembly — Architecture

## 1. Mental model

**Assembly** is the process of compiling a Graph (a passive data structure) into one or more executable Flows. The assembled Flow is what the VM runs; the Graph itself is never executed directly.

The pipeline is rooted at **event nodes**. Every Flow has exactly one entry event node. The assembler identifies all event nodes, builds one Flow per event node, and links them via callback edges (assembly-time wiring; see [architecture/execution/callbacks](../callbacks/callbacks-arch.md)).

Within each Flow, two structures are built side by side:

- The **control-flow DAG** — the sequence of CONTROL nodes the VM walks during execution.
- One **localized data-flow** per CONTROL node — the dependency DAG of DATA nodes whose outputs feed *that* control node's inlets. Data nodes are not in a global topology; they're scoped per control node.

Assembly is owned by `FlowAssemblyManager`. It runs once at graph load, then **just-in-time** on relevant graph mutations.

## 2. Contract

### 2.1 `FlowAssemblyManager`

Single class, single entry point: `assemble_graph(graph) → list[Flow]`. Responsibilities:

- Identify event nodes and separate Flows.
- Coordinate control-flow and data-flow builders.
- Cache assembled flows (`assembled_flows: dict[flow_id, Flow]`).
- Handle JIT reassembly when the graph mutates (`dirty_flows: set[flow_id]`).
- Process callback edges for observability (cross-flow wiring; see [callbacks](../callbacks/callbacks-arch.md)).

`AssemblyMetadata` captures per-flow info — `flow_id`, `timestamp`, `node_count`, `event_node_id`.

### 2.2 Pipeline stages

```text
assemble_graph(graph)
  ├─ _validate_graph(graph)         pre-flight: structure, duplicate event-types
  ├─ _identify_event_nodes(graph)   one Flow per event node
  └─ for each event node:
        ├─ _assemble_flow(event_node, graph)
        │     ├─ build control-flow DAG (walk EXEC edges from the event node)
        │     ├─ for each CONTROL node in the DAG:
        │     │     └─ build its localized data-flow
        │     │         (backpropagate from inlets through DATA edges,
        │     │          topologically sort)
        │     └─ store assembled Flow + metadata
        └─ cache → assembled_flows[flow_id]
  └─ _process_callback_edges(graph, flows)   wire cross-flow callbacks
```

### 2.3 Validation rules

`_validate_graph()` runs structural checks before assembly. Failures raise `RuntimeError` and abort.

| Check | Why |
|---|---|
| **Duplicate event types** | Multiple event nodes listening for the same event (e.g. two `BeginPlay` nodes) is undefined — which Flow runs first? |
| (Future) Graph-node Source/Sink presence | Graph-nodes without a Source or Sink can't enter or exit |
| (Future) Cycle detection in data-flow | Pure data cycles are illegal; cycles passing through a CONTROL node are allowed |

The validation is structural; per-edge validation happens in `EdgeWrapper.build()` ([edges](../edges/edges-arch.md) §2.2).

### 2.4 Assembly metadata

Every assembled Flow carries metadata exposed via `interpreter.get_statistics()`:

```python
stats['assembly']['flow_count']       # number of Flows
stats['assembly']['callback_edges']   # count of FlowType.CALLBACK edges
stats['assembly']['callback_topology'] # {emitter_id: [listener_flow_id, ...]}
```

Useful for debugging — confirm a graph assembled the expected Flow count and callback topology.

## 3. Lifecycle

### 3.1 Initial assembly (graph load)

```text
graph.load_from_json(...)
  ↓ (graph fully populated, but no Flows yet)
FlowAssemblyManager.assemble_graph(graph)
  ├─ clear previous assembly (assembled_flows, assembly_cache, dirty_flows)
  ├─ _validate_graph → raise on failure
  ├─ _identify_event_nodes → list of event nodes
  └─ for each event_node:
        Flow = _assemble_flow(event_node, graph)
        cache flow
        cache metadata
  └─ _process_callback_edges → wire callback topology
```

After this completes, `assembled_flows[flow_id] = Flow` for every Flow, and the Interpreter can register them.

### 3.2 Just-in-time reassembly

When the graph mutates, only affected Flows reassemble. The dirty-tracking is owned by `ValidationManager` (see [edges §3.6](../edges/edges-arch.md#36-validationmanager-debounced-batch-processing)) which marks `dirty_flows` based on `ChangeReason`.

Reasons that trigger reassembly:

| Change | Effect |
|---|---|
| **Node added / removed** in a Flow's reachable set | Flow reassembles |
| **Edge added / removed** in a Flow's control or data graph | Flow reassembles |
| **Edge displaced** (single-connection inlet over-subscribed) | Reassembly only if the *active* edge changed |
| **Adapter chain rebuilt** | No reassembly — chain is per-edge, not per-flow |
| **Hot-reloaded node** | Flow reassembles after the node-wrapper finishes rebuilding |

Reassembly uses the same `_assemble_flow()` path as initial assembly — just for the affected event-node-rooted Flow, not the whole graph.

### 3.3 Lazy evaluation handoff

The assembler is responsible for computing the **EVAL_MASK / LAZY_MASK** bitmasks used by the lazy evaluation algorithm (see [architecture/execution/lazy-evaluation](../lazy-evaluation/lazy-evaluation-arch.md)). For each control node:

1. Each data inlet gets a unique bit position.
2. The localized data-flow is walked backward from the inlets; bits OR-merge as the same data node feeds multiple inlets.
3. The result is a `dict[data_node, EVAL_MASK]` stored on the Flow, telling the VM "for this control node, you need these data nodes if these inlet bits are set."

This pre-computation is what makes lazy evaluation cheap at run-time — the VM just AND-masks at execution.

### 3.4 Hot-reload coordination

The assembler does not do hot-reload itself — it reassembles in response to dirty events. The pipeline is:

```text
File change
  ↓
FileWatcher → BaseRegistry hot-reload
  ↓
NodeWrapper / EdgeWrapper rebuild (see edges §3.7)
  ↓
ValidationManager marks affected Flows dirty
  ↓
FlowAssemblyManager reassembles only the dirty Flows
```

Full pipeline in [architecture/hot-reload](../../hot-reload/hot-reload-arch.md).

## 4. Boundary

The assembly subsystem is **not**:

- The **runtime**. Once Flows are built, they are run by the VM ([virtual-machine](../virtual-machine/virtual-machine-arch.md)) — assembly hands off the executable structure and stops participating.
- The **edge-build pipeline**. Edges have their own 4-stage build ([edges §2.2](../edges/edges-arch.md#22-the-4-stage-build-pipeline)); the assembler reads already-built edges and topologically sorts them into Flows.
- The **callback dispatcher**. Assembly *registers* the topology with `CallbackManager`; runtime dispatch is owned by the manager.
- The **graph data structure**. The Graph predates assembly and survives it. The assembler only reads from the graph.

## 5. Examples

### 5.1 Inspect assembly output

```python
from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager

manager = FlowAssemblyManager()
flows = manager.assemble_graph(graph)

print(f"Assembled {len(flows)} flows")
for flow in flows:
    print(f"  {flow.flow_id}: {len(flow.get_control_node_ids())} control nodes")

print(f"Cached metadata: {manager.assembly_cache}")
```

### 5.2 Forced reassembly

For tests and forced rebuilds:

```python
graph.validation_manager.force_immediate_validation()
# After this, manager.dirty_flows is empty and all reassembly has run
```

### 5.3 Multiple event nodes → multiple Flows

A graph with `BeginPlay`, `Tick`, and a `CallbackEvent('frame_ready')` node yields three Flows. They share the underlying graph but each runs independently:

| Flow | Entry event node | Triggered by |
|---|---|---|
| Flow 1 | `BeginPlay` | once at start |
| Flow 2 | `Tick` | every frame |
| Flow 3 | `CallbackEvent('frame_ready')` | when another Flow emits `'frame_ready'` |

`_process_callback_edges()` registers Flow 3 as a listener of whichever node emits `'frame_ready'`.

## 6. Open questions

- **Partial reassembly inside a Flow.** Today, any change inside a Flow's reachable set rebuilds the whole Flow. Could be smarter — rebuild only the affected localized data-flow.
- **Cross-Flow optimization.** Two Flows sharing a large data-flow subtree compute it twice. The architecture allows shared subtrees but the current implementation doesn't deduplicate.
- **Parallel Flow execution.** The assembler builds independent Flows; whether they run in parallel is the VM's call. Today they run serially. See [virtual-machine](../virtual-machine/virtual-machine-arch.md).

## Key files

- `src/haywire/core/assembly/flow_assembly_manager.py` — `FlowAssemblyManager`, `AssemblyMetadata`
- `src/haywire/core/assembly/control_flow_builder.py` — control-flow DAG construction
- `src/haywire/core/assembly/data_flow_builder.py` — localized data-flow construction
- `src/haywire/core/execution/flow.py` — `Flow` dataclass (the assembly output)
- `src/haywire/core/graph/validation.py` — `ValidationManager` (dirty-flow tracking)
