---
status: draft
doc_template: guide
scope: Authoring ports — as_inlet / as_outlet / as_config, primitive vs array vs pooled, worker access, port flags
see-also:
  - ../components/nodes/node-canon.md
  - ../components/datatypes/datatype-canon.md
  - ../components/widgets/widget-canon.md
  - ../architecture/execution/edges/edges-arch.md
  - ../reference/glossary.md
---

# Ports — Authoring Guide

## 1. What it solves

A **port** is a typed, directional connection point on a node. As a node author, you create ports inside `init()` by calling type factory methods — `FLOAT.as_inlet('value')`, `MeshData.as_outlet('mesh')`, `EXEC.as_inlet('trigger')` — and pass each spec to `self.add(...)`. The framework constructs the right `DataPort` and attaches it to the node.

Ports are how nodes declare what they consume and produce. Once declared, they show up as pins on the canvas, accept connections, deliver values to your `worker()` function, and propagate outputs to downstream nodes. The same surface covers four distinct roles:

- **Inlets** receive data or control into the node.
- **Outlets** emit data or control out of the node.
- **Config ports** are inlets with no pin on the canvas; they configure the node from the property panel.
- **Group / Section ports** organise other ports without affecting the worker contract.

## 2. How it fits

```text
Type system              Port factory          Runtime
────────────            ─────────────          ────────
FLOAT (IType cls)   →   FLOAT.as_inlet(    →   DataPort instance
                          id='value',           on node.ports[id]
                          default=0.0,          + DataField that holds the value
                          label='Value',        + flow_type, socket_type, mate_type
                          widget=...)           + edge wrappers (when connected)
                          → spec dict
                                            self.add(spec) attaches it
```

`as_inlet` / `as_outlet` / `as_config` return **port specs** (dicts). `self.add(spec)` consumes the spec, builds the `DataPort`, attaches its matching `DataField`, and registers it under `self.ports[id]`. From the worker, you access values via `self.value(id)` and `self.out(id, value)`.

**Boundaries.** What types exist and how to define them lives in [components/datatypes](../components/datatypes/datatype-canon.md). What widgets are bound to ports lives in [components/widgets](../components/widgets/widget-canon.md). The node lifecycle that calls your worker lives in [components/nodes](../components/nodes/node-canon.md). The runtime mechanics of edge build / adapter chain construction live in [architecture/execution/edges](../architecture/execution/edges/edges-arch.md).

## 3. Important concepts

**Three creation methods.** Every type has the same three factories:

| Method | Returns a port that... | Has a pin on the canvas? |
|---|---|---|
| `T.as_inlet(id, **kwargs)` | Receives data or control | Yes |
| `T.as_outlet(id, **kwargs)` | Emits data or control | Yes |
| `T.as_config(id, **kwargs)` | Internal parameter, only visible in the property panel | No |

`as_config` is implemented as an inlet with `flow_type=FlowType.NONE`. Use it for "knobs" that the user adjusts via the property panel rather than connecting to other nodes (a mode selector, a quality preset).

**Common kwargs (all optional, pass to any of the three factories).**

| Kwarg | Type | Effect |
|---|---|---|
| `label` | `str` | Display label (defaults to type's label) |
| `default` | varies | Override the type's default value |
| `widget_key` | `str` | Override the type's widget |
| `widget_config` | `dict` | Override the widget's config |
| `flow_type` | `FlowType` | Override the type's flow type |
| `on_change` | `str` | Name of a node method to call when the port's value changes |
| `on_connect` | `str` | Name of a node method to call when an edge connects |
| `on_disconnect` | `str` | Name of a node method to call when an edge disconnects |
| `store_data` | `bool` | Override whether values persist on graph save |

The `on_change` callback is what you wire to a `hb_*` reconfigure method when a config port should rebuild dynamic ports. See [components/nodes](../components/nodes/node-canon.md) §3 for the rejig pattern.

**Three port shapes per type.** Every datatype gives you three connection shapes:

```python
# Single value
FLOAT.as_inlet('threshold', default=0.5)

# Array of typed values (one connection, multiple values)
ArrayType[FLOAT].as_inlet('numbers', default=[1.0, 2.0, 3.0])

# Pooled — accepts MULTIPLE connections; values arrive as a dict
PooledType[FLOAT].as_inlet('values')
```

**Pooled is inlet-only.** `PooledType[T].as_outlet(...)` is invalid and raises an error.

**Worker access — three patterns.**

```python
def worker(self, context: ExecutionContext, value: float, name: str = 'default'):
    # Pattern A — named parameter binding (preferred when ports are static)
    # Parameter name MUST match the inlet ID
    print(value, name)

    # Pattern B — explicit accessor (use when you need dynamic access)
    threshold = self.value('threshold')

    # Pattern C — port object access (for connection-state checks)
    if self.ports['optional_input'].is_linked():
        v = self.value('optional_input')

    # Writing outlets
    self.out('result', value * 2.0)
```

`self.value(id)` returns the unwrapped value. `self.out(id, value)` writes the unwrapped value. Both work for primitives, complex types, arrays, and pooled (where the pooled inlet returns a `dict[source_id, value]`).

**Connection-state checking.** Use `self.ports['id'].is_linked()` — returns `True` when at least one edge is linked to the port. Some older docs reference `is_connected` or `inlets[id].is_connected`; those names do not exist on the current API.

**Pooled access helpers.** A pooled inlet's value is a `dict[node_id, value]`. The underlying field also exposes:

```python
inlet = self.ports['values']
inlet.data.get_values_list()   # [v1, v2, v3]
inlet.data.get_source_ids()    # ['node_a', 'node_b', 'node_c']
```

**Port groups and sections.** Two ways to organise ports without touching the worker contract:

- `with self.group(GROUP.as_inlet('advanced', label='Advanced'))` — a collapsible UI container; child ports are hidden when collapsed but connections survive via ghost pins. Groups can nest.
- `with self.section('validation')` — moves child ports off the node body and into a property-panel section.

Both are explained in [components/nodes](../components/nodes/node-canon.md) §3.

## 4. Live examples from the codebase

### Port shapes — declaration

Source: [`barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py`](../../barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py)

`EdgeLinkTestNode` exercises every port shape in `init()`: primitive inlets and outlets, `ArrayType[T]` outlets, `PooledType[T]` inlets, and `EXEC` for control flow. It is purpose-built as a connection testbed, so its `worker` is intentionally empty:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py:edge_link_test_node"
```

What this example covers for port shapes:

| Concept | Where it shows up |
|---|---|
| Primitive inlet / outlet | `TEST_BOOL`, `TEST_INT`, `TEST_FLOAT`, `TEST_STRING` |
| Derived type inlet (hierarchy) | `TEST_TEMPERATURE` — subtype of `FLOAT` |
| `PooledType[T].as_inlet(...)` (inlet-only) | `pooled_bool_inlet`, `pooled_int_inlet`, etc. |
| `ArrayType[T].as_outlet(...)` | `array_bool_outlet`, `array_int_outlet`, etc. |
| `PooledType[ArrayType[T]].as_inlet(...)` | `pooled_array_string_inlet` — nested shapes |
| `EXEC` inlet + outlet | `execute_inlet`, `execute_out` |
| `CALLBACK` inlet + outlet | `callback_inlet`, `callback_outlet` |

### Pooled worker access

Source: [`barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py`](../../barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py)

`TestEmitCallbackNode` shows how a pooled inlet is consumed in a worker: the value arrives as a `dict`, iterated to dispatch to multiple listeners. It also demonstrates `on_change` on a pooled inlet, `post_init()` for non-serializable state, and `GROUP.as_config` for a collapsible config section:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py:test_emit_callback_node"
```

What this example covers for worker access:

| Concept | Where it shows up |
|---|---|
| `PooledType[CALLBACK].as_inlet(...)` | `edge_callback` — collects multiple listener IDs |
| Pooled value arrives as `dict` in worker | `edge_callbacks` parameter, iterated with `.values()` |
| `on_change='printout'` on a pooled inlet | called when connections change |
| `GROUP.as_config(...)` collapsible config section | `mode_switch` group with `custom_callback_name` |
| `STRING.as_config(...)` inside a group | `custom_callback_name` — panel-only, no canvas pin |
| `post_init()` for non-serializable state | `self.callback_index = 0` |
| Worker named parameter binding | `mode_switch`, `sequential_mode`, `edge_callbacks`, etc. |
| `context.emit_callback(event_name=..., payload=...)` | dispatches to all or one listener |

For declarative settings instead of config ports, see [components/settings](../components/settings/setting-canon.md). For the lifecycle hooks that surround `worker()` (`init`, `post_init`, `on_validate`, etc.), see [components/nodes](../components/nodes/node-canon.md). For the dynamic `rejig()` pattern that adds and removes ports based on a config value, see [components/nodes §3](../components/nodes/node-canon.md#3-important-concepts).

---

## Quick reference

### Port creation

```python
# Single primitive
FLOAT.as_inlet('threshold', default=0.5)
FLOAT.as_outlet('result')

# Complex type
MeshData.as_inlet('mesh', default={'vertices': [], 'faces': []})
MeshData.as_outlet('combined')

# Array (one connection, list of typed values)
ArrayType[FLOAT].as_inlet('weights', default=[1.0, 1.0])
ArrayType[FLOAT].as_outlet('filtered')

# Pooled (inlet only, multiple connections)
PooledType[FLOAT].as_inlet('values')

# Config (no pin on canvas, panel-only)
STRING.as_config('mode', default='int')
```

### Worker access

```python
# Read (always unwrapped)
v = self.value('inlet_id')

# Write (always unwrapped)
self.out('outlet_id', v)

# Connection check
if self.ports['inlet_id'].is_linked():
    ...

# Pooled helpers
inlet = self.ports['pooled_id']
inlet.data.get_values_list()   # [v1, v2, v3]
inlet.data.get_source_ids()    # ['n1', 'n2', 'n3']

# Array helpers
inlet = self.ports['array_id']
item = inlet.data.get_item(0)
length = len(inlet.data)
```

### Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'my_port'` from `self.value()` | Port ID typo or mismatch with `init()` | Match the IDs exactly; they are case-sensitive |
| `PooledType[T].as_outlet(...)` raises | Pooled is inlet-only by design | Use `ArrayType[T].as_outlet` for fan-out |
| Array outlet won't connect to single-value inlet | Type-mismatch on container shape | Use matching shape (both array, or both single) |
| Worker parameter is `None` when expected to be bound | Parameter name doesn't match inlet ID | Check spelling; or use `self.value(id)` for dynamic access |
