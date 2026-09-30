---
status: draft
doc_template: impl-spec
scope: Callback edge system — cross-flow triggers, FlowType.CALLBACK semantics, CallbackManager, listener registration
see-also:
  - ../edges/edges-arch.md
  - ../assembly/assembly-arch.md
  - ../flow/flow-arch.md
  - ../../../reference/glossary.md
---

# Callbacks — Architecture

## 1. Mental model

A **callback** is a cross-flow trigger: a running node calls `context.emit_callback(event_name, payload)`, and every Flow whose entry EVENT node subscribed to that name runs in response. Callbacks let an event-node-rooted Flow be triggered *programmatically* by another running flow, instead of only by an external system event (BEGIN_PLAY, Tick, user input).

Routing is by **event name** alone and never goes through the graph. What a CALLBACK edge adds is the *subscription*: it carries the listener event node's subscription value to the emitting node, so the emitter knows which names to emit. The value is whatever the callback type defines — for core `CALLBACK` (a `STRING`) it is the event name; for a library type such as haybale-visiongraph's `MULTIFRAME_CALLBACK` it is a dataclass holding the name plus the stream requirements the camera node reads.

This is the third leg of haywire's connection types — see [reference/glossary §Flow Types & Port Kinds](../../../reference/glossary.md#flow-types-port-kinds):

| Connection | Purpose | Lifetime |
|---|---|---|
| **DATA edge** | Carries typed values from outlet to inlet | Run-time data transport |
| **EXEC edge** | Carries control flow within a Flow | Run-time control transport |
| **CALLBACK edge** | Carries a listener's subscription value from its EVENT node's CALLBACK outlet to an emitter's pooled `PooledType[...]` callback inlet | Run-time value transport |

## 2. Contract

### 2.1 The `FlowType.CALLBACK` port type

CALLBACK ports use the same `DataPort` infrastructure as DATA ports but carry the `FlowType.CALLBACK` flag. They have no hardcoded connection rules:

| Direction | `allow_multiple` |
|---|---|
| Outlet | `False` by default; listener event nodes declare `True`, so one listener can subscribe to several emitters |
| Inlet | `False` by default; emitters use a `PooledType[...]` inlet, which accepts many sources and keys each value by its edge id |

A CALLBACK edge is created through the same `graph.create_edge_wrapper(...)` as DATA and EXEC edges, and its value travels over an ordinary pipe into the emitter's pool. Removing a direct edge removes that edge's entry from the pool (`PooledField.remove_source`); longer paths are covered in §2.4. Assembly does not read callback edges to route anything — see §3.1.

#### `on_change` timing on CALLBACK inlets

`DataPort.set_value()` normally defers an edge-driven inlet's `on_change` callback to `resolve_dirty_data()`, which only runs when the owning node's `worker()` is next dispatched (see [edges-arch.md](../edges/edges-arch.md)). Immediate inlets — every CALLBACK flow (`FlowType.is_immediate`) — are the one exception: `set_value()` fires `on_change` **immediately**, even when the write came from an edge (`edge_id` set), instead of deferring it.

This matters because emitter nodes with a pooled `PooledType[CALLBACK]` inlet are often `NodeType.CONTROL` nodes (e.g. `OakDCameraNode`) that only execute their `worker()` in response to a control pulse (`start`/`stop`), not on every dirty-port change. If a callback inlet's `on_change` were deferred like a normal DATA inlet, a subscriber changing its requirements (e.g. a `NumpyFrameEventNode` toggling `enable_depth`) would update the pooled dict but the emitter's `on_change` handler — and anything it derives, like a requirement-union setting — would silently stay stale until the node happened to execute again for an unrelated reason.

### 2.2 Two ways to subscribe

**Edge-based (default).** Draw a CALLBACK edge from the listener event node's CALLBACK outlet to the emitter's pooled callback inlet. The listener publishes its subscription on the outlet (core's `TickEventNode` publishes its own node id), and the emitter emits to every name in its pool.

**By name (no edge).** Nodes that offer it — haybale-example's Custom Callback and Emit Callback — have a **Custom Name** fold (the `custom_name` switch and a `custom_callback_name` text field). With it switched on, the listener subscribes to that name and the emitter emits it. No edge is drawn; the two meet through the CallbackManager's name routing.

Both coexist. A graph can have some callbacks edge-wired and others matched by name.

### 2.3 The two endpoints

- **Listener** — an EVENT node whose `event_subscription` is a `CallbackEvent(event_name=...)`. It roots its own Flow and, in edge-based mode, publishes its subscription on a CALLBACK outlet.
- **Emitter** — a node that calls `context.emit_callback(...)`, usually a CONTROL node (core's `TickEmitNode`, haybale-visiongraph's `OakDCameraNode`). In edge-based mode it reads the names to emit from its pooled callback inlet; `TickEmitNode` reads them from a background thread, outside any execution frame.

By design, every callback-listener Flow has its own EVENT-node entry — typically `CallbackEvent(event_name=...)`.

### 2.4 Through reroutes

A callback edge may pass through reroutes. Every port on a callback flow is **immediate**: an edge-driven write fires `on_change` at once, and a reroute's inlet forwards to its outlet from that handler (`RerouteNode.forward_immediate`), so the subscription reaches the emitter without any node executing. Callback edges always have `immediate` propagation, locked — see [edges-arch §3.3](../edges/edges-arch.md).

Removing any edge on the path unsubscribes. An immediate inlet left without a linked edge is set to absence (`None`), which the reroute forwards; the emitter's pooled inlet then removes the entry keyed by its own edge. A displaced edge that takes over keeps the subscription in place. Fields of immediate types hold absence whatever their storage, dataclass types included (ADR 0033, amendment).

Subgraph boundaries do not relay callbacks yet: collapsing a selection that a callback edge would cross is still refused.

## 3. Lifecycle

### 3.1 Assembly and listener registration

```text
FlowAssemblyManager.assemble_graph(graph)
  ├─ identify event nodes → one Flow per event node
  │     Flow 1: event_subscription = SystemEvent(BEGIN_PLAY)
  │     Flow 2: event_subscription = CallbackEvent(event_name='my_callback')
  │
  ├─ build each Flow normally (control + data assembly)
  │
  └─ _process_callback_edges(graph, flows)
       └─ statistics and debug logging only (§3.3)

Interpreter, starting each Flow
  └─ CallbackEvent subscription
       → callback_manager.register_callback_listener(event_name, flow)
```

Listener Flows are registered from each event node's `event_subscription`, never from edges.

### 3.2 Runtime dispatch

When an emitter fires a callback:

```text
emitter worker (or a thread it started) → context.emit_callback(event_name, payload)
  ↓
VM.emit_callback → CallbackManager.emit_callback
  ↓
Each Flow registered for event_name runs
  (independently, not as part of the emitter's control chain)
```

The listener Flow runs through the standard VM dispatch — it's a Flow like any other; the only thing special is how it was *triggered*.

### 3.3 Statistics

The assembly result and the Interpreter both expose callback topology for debugging:

```python
stats = interpreter.get_statistics()

stats['assembly']['callback_edges']     # number of CALLBACK edges in the graph
stats['callback_topology']              # same as stats['assembly']['callback_topology']:
#   {'emitters': int, 'listeners': int,
#    'edges':    {source_node_id: [sink_node_id, ...]},
#    'triggers': {sink_node_id: [source_node_id, ...]}}
stats['callbacks']                      # CallbackManager: registered event names and listener counts
```

The topology follows the edge direction: an edge's *source* is the listener event node and its *sink* is the emitter. So the `emitters` count is the number of distinct edge sources, and `listeners` the number of distinct sinks — the reverse of the roles in §2.3.

### 3.4 Hot-reload behaviour

CALLBACK edges follow the same hot-reload path as DATA/EXEC edges (see [architecture/execution/edges](../edges/edges-arch.md)). If an emitter or listener node reloads:

1. `NODE_HOT_RELOADED` triggers full `node_wrapper.build()` for the affected node.
2. Attached CALLBACK edges are marked dirty, rebuilt, and re-linked.
3. The next assembly pass re-reads each event node's `event_subscription`, and the Interpreter registers the listener Flows again when it starts them.

## 4. Boundary

The callback subsystem is **not**:

- A **synchronous function call** mechanism — listeners run as standalone Flows; emitters do not wait.
- A **data channel** — a CALLBACK edge carries a subscription, not run-time data. Data sent with a callback travels as `emit_callback(payload=...)`; data shared between sibling Flows requires AppState (see [architecture/session-and-state](../../session-and-state/session-and-state-arch.md)) or a shared `LibrarySettings`.
- A **subscription protocol** for UI events — that's the studio's `notify_context_changed` system; see [architecture/studio](../../studio/studio-arch.md).
- An **inter-process communication** mechanism — callbacks are intra-Interpreter only.

## 5. Examples

### 5.1 Edge-based callback

```text
Flow 1 (BeginPlay):                              Flow 2 (Listener):
  ┌──────────┐      ┌───────────────┐             ┌─────────────────┐
  │BeginPlay │─exec→│ Emit Callback │             │ Custom Callback │
  └──────────┘      │    Trigger ◄──┼─────────────┤ Listen          │
                    └───────────────┘  CALLBACK   └─────────────────┘

The CALLBACK edge runs from the listener's Listen outlet to the emitter's
pooled Trigger inlet and carries the listener's subscription name. When
Flow 1 reaches Emit Callback, it emits to every name in that pool, and
the CallbackManager runs Flow 2.
```

### 5.2 Callback by name (no edge)

```python
# Custom Callback (listener) and Emit Callback (emitter) both switch on
# the Custom Name fold and use the same name. No edge between them.
listener.ports["custom_name"].set_value(True)
listener.ports["custom_callback_name"].set_value("my_callback")

emitter.ports["custom_name"].set_value(True)
emitter.ports["custom_callback_name"].set_value("my_callback")
```

### 5.3 Inspecting the topology

```python
topology = interpreter.get_statistics()["callback_topology"]
for source_id, sink_ids in topology.get("edges", {}).items():
    print(f"{source_id} → {sink_ids}")
```

## 6. Open questions

- **Cyclic callback chains.** A → B → A is currently undetected at assembly time. The Done-stack in the VM bounds runaway loops at execution but a static check would surface them earlier.
- **Per-callback configuration** (priority, debouncing) is not exposed today — every listener runs on every emit.
- **Cross-Interpreter callbacks.** Each `GraphEntry` has its own Interpreter; callbacks are scoped to one Interpreter. Inter-graph callbacks would require an SessionManager-level dispatch that does not currently exist.

## Key files

- `src/haywire/core/execution/interpreter.py` — `Interpreter` (per-graph; owns the CallbackManager and registers `CallbackEvent` Flows with it)
- `src/haywire/core/execution/callback_manager.py` — `CallbackManager` (dispatch by event name)
- `src/haywire/core/execution/execution_context.py` — `ExecutionContext.emit_callback`
- `src/haywire/core/execution/event_source.py` — `CallbackEvent` listener event-node (framework class; library nodes import it)
- `src/haywire/core/assembly/flow_assembly_manager.py` — `_process_callback_edges()` (statistics only)
