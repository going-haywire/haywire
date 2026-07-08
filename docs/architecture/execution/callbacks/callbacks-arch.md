---
status: draft
doc_template: impl-spec
scope: Callback edge system — cross-flow triggers, FlowType.CALLBACK semantics, CallbackManager, assembly-time wiring
see-also:
  - ../edges/edges-arch.md
  - ../assembly/assembly-arch.md
  - ../flow/flow-arch.md
  - ../../../reference/glossary.md
---

# Callbacks — Architecture

## 1. Mental model

A **callback** is a cross-flow trigger: one Flow emits an event, and a sibling Flow whose entry EVENT-node is configured to listen for that event runs in response. Callbacks let an event-node-rooted Flow be triggered *programmatically* by another running flow, instead of only by an external system event (BEGIN_PLAY, Tick, user input).

CALLBACK edges serve two roles: **assembly-time wiring** and **run-time value transport**. At assembly time, a CALLBACK edge between an emitter outlet and a listener-event-node's inlet tells the assembler "hook this listener up to fire when the emitter writes." At run-time, the pipe mechanism transports the string listener-id from the EVENT node outlet to the emitter's inlet — the emitter reads it to know which callbacks to fire.

This is the third leg of haywire's connection types — see [reference/glossary §Flow Types & Port Kinds](../../../reference/glossary.md#flow-types-port-kinds):

| Connection | Purpose | Lifetime |
|---|---|---|
| **DATA edge** | Carries typed values from outlet to inlet | Run-time data transport |
| **EXEC edge** | Carries control flow within a Flow | Run-time control transport |
| **CALLBACK edge** | Carries a string listener-id from an EVENT node outlet to an emitter's `PooledType[CALLBACK]` inlet; wires listener Flows to emitter ports | **Run-time** value transport (string) + assembly-time topology registration |

## 2. Contract

### 2.1 The `FlowType.CALLBACK` port type

CALLBACK ports use the same `DataPort` infrastructure as DATA ports but carry the `FlowType.CALLBACK` flag. Connection rules:

| Direction | `allow_multiple` |
|---|---|
| Outlet | `False` (default — one emitter per source) |
| Inlet | `False` (default — one listener per target) |

A CALLBACK edge is registered through the same `graph.create_edge_wrapper(...)` flow as DATA/EXEC edges. At run-time, the pipe mechanism transports the string listener-id from the EVENT node outlet to the emitter's `PooledType[CALLBACK]` inlet — the emitter reads this value to know which callback names to emit. Additionally, at assembly time, the assembler reads the edge topology to register listener Flows with the CallbackManager.

#### `on_change` timing on CALLBACK inlets

`DataPort.set_value()` normally defers an edge-driven inlet's `on_change` callback to `resolve_dirty_data()`, which only runs when the owning node's `worker()` is next dispatched (see [edges-arch.md](../edges/edges-arch.md)). CALLBACK-flow inlets are the one exception: `set_value()` fires `on_change` **immediately**, even when the write came from an edge (`edge_id` set), instead of deferring it.

This matters because emitter nodes with a pooled `PooledType[CALLBACK]` inlet are often `NodeType.CONTROL` nodes (e.g. `OakDCameraNode`) that only execute their `worker()` in response to a control pulse (`start`/`stop`), not on every dirty-port change. If a callback inlet's `on_change` were deferred like a normal DATA inlet, a subscriber changing its requirements (e.g. a `NumpyFrameEventNode` toggling `enable_depth`) would update the pooled dict but the emitter's `on_change` handler — and anything it derives, like a requirement-union setting — would silently stay stale until the node happened to execute again for an unrelated reason.

### 2.2 Two callback modes

The framework supports two ways to wire a listener to an emitter:

**Edge-based (visual, default).** A `FlowType.CALLBACK` edge connects an emitter outlet to a listener `CallbackEvent`-node inlet. The event name propagates automatically — the emitter doesn't need a string identifier; the edge is the wiring.

**String-based (`mode_switch=True`).** No edge is drawn. Instead, the emitter and listener nodes both have a `event_name` config port set to the same string. The framework matches them at assembly time. Useful for graphs where the visual clutter of callback edges is undesirable.

Both modes coexist. A graph can have some callbacks edge-wired and others string-matched.

### 2.3 The two endpoints

- **Emitter** — a node whose outlet emits a callback signal. Configured with optional `event_name` (string-mode only) and a `mode_switch` config port.
- **Listener** — a node with a `FlowType.CALLBACK` inlet that listens for a named event. The Flow rooted at this node runs when the event fires.

By design, every callback-listener Flow has its own EVENT-node entry — typically `CallbackEvent(event_name=...)`.

## 3. Lifecycle

### 3.1 Assembly-time wiring

`FlowAssemblyManager._process_callback_edges()` runs after individual Flows are built:

```text
FlowAssemblyManager.assemble_graph(graph)
  ├─ identify event nodes → one Flow per event node
  │     Flow 1: event_subscription = SystemEvent(BEGIN_PLAY)
  │     Flow 2: event_subscription = CallbackEvent(event_name='my_callback')
  │
  ├─ build each Flow normally (control + data assembly)
  │
  └─ _process_callback_edges(graph, flows)
       ├─ scan graph.edge_wrappers for FlowType.CALLBACK edges
       ├─ build a topology map: emitter_node → [listener_flow, …]
       ├─ register the topology with CallbackManager
       └─ store statistics on the assembly result
```

### 3.2 Runtime dispatch

When a node worker writes to a callback outlet during execution:

```text
Flow 1 worker emits → outlet.set_value(...)
  ↓
CallbackManager dispatches by event name
  ↓
Each listener Flow registered for that event runs
  (independently, not as part of Flow 1's control chain)
```

The listener Flow runs through the standard VM dispatch — it's a Flow like any other; the only thing special is how it was *triggered*.

### 3.3 Statistics

The assembly result and the Interpreter both expose callback topology for debugging:

```python
stats = interpreter.get_statistics()

stats['assembly']['callback_edges']     # count of CALLBACK edges in the graph
stats['assembly']['callback_topology']  # {emitter_id: [listener_flow_id, ...]}
stats['callback_topology']              # same, on interpreter for quick access
```

### 3.4 Hot-reload behaviour

CALLBACK edges follow the same hot-reload path as DATA/EXEC edges (see [architecture/execution/edges](../edges/edges-arch.md)). If an emitter or listener node reloads:

1. `NODE_HOT_RELOADED` triggers full `node_wrapper.build()` for the affected node.
2. Attached CALLBACK edges are marked dirty, rebuilt, and re-linked.
3. The next assembly pass (triggered by the dirty-edge state change) re-runs `_process_callback_edges()` and rebuilds the callback topology.

## 4. Boundary

The callback subsystem is **not**:

- A **synchronous function call** mechanism — listeners run as standalone Flows; emitters do not wait.
- A **data-passing channel for arbitrary types** — CALLBACK ports carry string listener-ids only. Data flow between sibling Flows requires AppState (see [architecture/session-and-state](../../session-and-state/session-and-state-arch.md)) or a shared `LibrarySettings`.
- A **subscription protocol** for UI events — that's the studio's `notify_context_changed` system; see [architecture/studio](../../studio/studio-arch.md).
- An **inter-process communication** mechanism — callbacks are intra-Interpreter only.

## 5. Examples

### 5.1 Edge-based callback

```text
Flow 1 (BeginPlay):                Flow 2 (Listener):
  ┌──────────┐                       ┌─────────────────┐
  │BeginPlay │─exec→ ... ─emit→     │ CallbackEvent   │
  └──────────┘                       │ event_name=     │
                                     │ 'my_callback'   │
                                     └─────────────────┘

A CALLBACK edge connects the emitter outlet (in Flow 1) to the listener
event-node's CALLBACK inlet (root of Flow 2). At assembly time, the
edge is read once to register Flow 2 as a listener; at runtime, when
Flow 1's emit fires, Flow 2 runs.
```

### 5.2 String-based callback (no edge)

```python
# Emitter node config:
emitter.set_value('mode_switch', True)
emitter.set_value('event_name', 'my_callback')

# Listener event node config:
listener.set_value('event_name', 'my_callback')

# No edge between them. Assembly matches them by event_name string.
```

### 5.3 Inspecting the topology

```python
stats = interpreter.get_statistics()
for emitter_id, listener_flows in stats['callback_topology'].items():
    print(f"{emitter_id} → {listener_flows}")
```

## 6. Open questions

- **Cyclic callback chains.** A → B → A is currently undetected at assembly time. The Done-stack in the VM bounds runaway loops at execution but a static check would surface them earlier.
- **Per-callback configuration** (priority, debouncing) is not exposed today — every listener runs on every emit.
- **Cross-Interpreter callbacks.** Each `GraphEntry` has its own Interpreter; callbacks are scoped to one Interpreter. Inter-graph callbacks would require an SessionManager-level dispatch that does not currently exist.

## Key files

- `src/haywire/core/assembly/flow_assembly_manager.py` — `_process_callback_edges()`
- `src/haywire/core/execution/callback_manager.py` — `CallbackManager` (runtime dispatch)
- `src/haywire/core/execution/interpreter.py` — `Interpreter` (per-graph; owns the CallbackManager)
- `src/haywire/core/execution/event_source.py` — `CallbackEvent` listener event-node (framework class; library nodes import it)
