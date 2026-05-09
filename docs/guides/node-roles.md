---
status: draft
doc_template: guide
scope: Worked examples of each node role — CONTROL (multi-pin dispatch), DATA (pure compute), EVENT (with matching emitter), LOOPBACK (round-trip with break)
see-also:
  - ../components/nodes/node-canon.md
  - ./ports.md
  - ../architecture/execution/callbacks/callbacks-arch.md
  - ../reference/glossary.md
---

# Node roles — worked examples

The node authoring API — the `@node` decorator, lifecycle hooks, the worker contract, port access, `rejig()`, groups — is documented in [components/nodes/node-canon](../components/nodes/node-canon.md). This guide shows what's distinctive about each **role**: CONTROL, DATA, EVENT, and LOOPBACK. Each example is minimal — only the role-specific bits are explained inline; everything else is in the canon.

## CONTROL — multi-pin dispatch

A CONTROL node has at least one EXEC inlet *and* outlet. When it has **multiple** EXEC inlets, the worker uses `context.control_pin` to discover which one fired and dispatch accordingly.

Source: [`barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py`](../../barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py)

`TestEmitCallbackNode` is a CONTROL node with one EXEC inlet (`execute`) and one EXEC outlet (`exec`). It also demonstrates `PooledType[CALLBACK]` as an inlet, `post_init()` for non-serializable state, and dispatching via `context.emit_callback`:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py:test_emit_callback_node"
```

**Role-specific:** EXEC inlet (`execute`) + EXEC outlet (`exec`) makes this CONTROL. The worker returns the outlet ID `"exec"` to continue control flow. `context.emit_callback(event_name=..., payload=...)` dispatches to listener nodes by name. `PooledType[CALLBACK].as_inlet(...)` collects all connected listener IDs into a dict.

## DATA — pure compute

A DATA node has **no EXEC ports**. It runs only when a downstream CONTROL node demands one of its outputs. Its worker returns `None` and writes results via `self.out(...)`.

Source: [`barn/haybale-testing/haybale_testing/nodes/testbed/math_op_node.py`](../../barn/haybale-testing/haybale_testing/nodes/testbed/math_op_node.py)

`TestAddFloatNode` is the minimal DATA node: two FLOAT inlets, one FLOAT outlet, worker adds them and returns `None`:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/math_op_node.py:test_add_float_node"
```

**Role-specific:** no EXEC ports, returns `None`, runs lazily on demand from downstream.

## EVENT — `event_subscription`

An EVENT node has no EXEC inlet either, but unlike DATA it is an **entry point** of a control flow: it runs when an event source fires. The role-defining hook is `self.event_subscription`, set in `post_init()`.

### System event

Source: [`barn/haybale-testing/haybale_testing/nodes/testbed/begin_play_node.py`](../../barn/haybale-testing/haybale_testing/nodes/testbed/begin_play_node.py)

`TestBeginPlayNode` fires once when execution starts, emitting the current timestamp:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/begin_play_node.py:test_begin_play_node"
```

**Role-specific:** `event_subscription = SystemEvent(SystemEventType.BEGIN_PLAY)` in `post_init()`. No EXEC inlet — the framework dispatches the event source instead. Worker returns the outlet ID `"exec"` to trigger control flow.

### Callback event pair (listener + emitter)

`event_subscription` also accepts `CallbackEvent(event_name=...)`, which lets one node trigger another by name. A callback listener needs a matching emitter, so we show the pair together.

**Listener** — source: [`barn/haybale-example/haybale_example/nodes/emits/custom_callback.py`](../../barn/haybale-example/haybale_example/nodes/emits/custom_callback.py)

`CustomCallbackNode` listens for named callbacks from other flows. It broadcasts its own ID via a `CALLBACK` outlet so emitters can wire to it, and updates its `event_subscription` dynamically when the config changes:

```python
--8<-- "barn/haybale-example/haybale_example/nodes/emits/custom_callback.py:custom_callback_node"
```

**Emitter** — source: [`barn/haybale-example/haybale_example/nodes/emits/emit_callback.py`](../../barn/haybale-example/haybale_example/nodes/emits/emit_callback.py)

`EmitCallbackNode` is the CONTROL counterpart: it has an EXEC inlet, reads connected listener IDs via `PooledType[CALLBACK]`, and emits to them via `context.emit_callback`:

```python
--8<-- "barn/haybale-example/haybale_example/nodes/emits/emit_callback.py:emit_callback_node"
```

**What the pair shows:**

- **`allow_multiple_links=True`** on the listener's `CALLBACK` outlet lets many emitters target the same listener (port detail in [guides/ports](./ports.md)).
- **`PooledType[CALLBACK].as_inlet(...)`** on the emitter collects all connected listener IDs into a dict (port detail in [guides/ports](./ports.md)).
- **`context.emit_callback(event_name=..., payload=...)`** dispatches to subscribers.
- **`context.trigger.payload`** delivers the emitter's payload to the listener's worker.
- **`wrapper.request_graph_reassembly()`** is called when the subscription changes so the flow graph is rebuilt with the new wiring.

For the framework's dispatch model — assembly-time wiring, FlowType.CALLBACK, CallbackManager — see [architecture/execution/callbacks](../architecture/execution/callbacks/callbacks-arch.md).

## LOOPBACK — round-trip with break

A LOOPBACK node fires an EXEC outlet, control flows through downstream nodes, and **returns to the same node** to run its worker again. The role-defining marker is `needs_loopback=True` on the body outlet.

Source: [`barn/haybale-core/haybale_core/nodes/for_loop.py`](../../barn/haybale-core/haybale_core/nodes/for_loop.py)

`ForLoopNode` iterates from `start` to `end` with a configurable `step`. A second EXEC inlet (`break_loop`) provides early exit:

```python
--8<-- "barn/haybale-core/haybale_core/nodes/for_loop.py:for_loop_node"
```

**Role-specific:**

- **`needs_loopback=True`** on `loop_body` declares the round-trip: the VM remembers this node and returns control to it after the body completes.
- **`context.control_pin` dispatch** distinguishes three cases: `'execute'` (first entry), `'break_loop'` (early exit), and anything else (re-entry from the body). This is the same `control_pin` mechanism shown in the CONTROL example, used here for iteration state.
- **`post_init()`** initialises instance variables for loop state (index, end, step) — these survive across the multiple worker calls that make up one loop run.
