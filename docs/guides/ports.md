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
- **Folds** organise other ports into a collapsible container without affecting the worker contract.

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
| `show_widget` | `ShowWidgetStrategy` | When the port's inline widget renders, relative to link state (see below) |
| `store_strategy` | `StoreStrategy` | When values persist on graph save (older docs called this `store_data: bool` — out of date) |

The `on_change` callback is what you wire to a `hb_*` reconfigure method when a config port should rebuild dynamic ports. See [components/nodes](../components/nodes/node-canon.md) §3 for the rejig pattern.

**Widget visibility (`show_widget`).** A `ShowWidgetStrategy` controlling whether a port's inline widget is rendered on the node card, relative to whether the pin is linked:

| Value | Not linked | Linked |
|---|---|---|
| `NEVER` | hidden | hidden |
| `NOT_LINKED` | shown | hidden |
| `WHEN_LINKED` | hidden | shown |
| `ALWAYS` | shown | shown |

Defaults are per-direction and usually correct without setting anything: **inlet → `NOT_LINKED`** (a connected inlet's widget is misleading, since the upstream edge overrides it), **outlet → `NEVER`** (an outlet's value is produced by the node, not entered), **config → `ALWAYS`** (a config port has no pin, so it is never linked). Because a widget can be assigned once at the type level, these defaults let the same type render an editable widget on inlets and suppress it on outlets automatically. Override per-port when needed, e.g. `FLOAT.as_inlet('gain', widget=..., show_widget=ShowWidgetStrategy.ALWAYS)`. Widgets toggle live when you connect/disconnect a pin. The full rationale is in [ADR 0003](../adr/0003-show-widget-strategy.md).

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

**Underlying field access.** `port.data` returns the port's `DataField` — the typed storage behind the port. Compound shapes expose shape-specific helpers on it (`get_values_list()`, `get_source_ids()` for pooled; `get_item()`, `len()` for array). `port.stored_type` is a shortcut for the `IType` the field actually stores.

**Pooled access helpers.** A pooled inlet's value is a `dict[node_id, value]`. The underlying field also exposes:

```python
inlet = self.ports['values']
inlet.data.get_values_list()   # [v1, v2, v3]
inlet.data.get_source_ids()    # ['node_a', 'node_b', 'node_c']
```

**Folds.** `with self.fold(label, ...)` organises ports into a collapsible UI container without touching the worker contract — the author supplies only a name; the framework mints the container port itself. Explained further below and in [components/nodes](../components/nodes/node-canon.md) §3.

### Folds

A fold is a real port, as any inlet or outlet is: it holds the open/closed
state, serializes with the graph, and parents its children through
`parent_fold`. Unlike a hand-declared port, the author supplies only a
label — the framework mints a pin-less, widget-less `FOLD` port, whose header
carries a disclosure triangle, the label, and a checkbox showing the same
open/closed boolean:

```python
with self.fold('Solver'):
    self.add(INT.as_config('substeps', default=10))
    self.add(INT.as_config('iterations', default=1))
```

While closed, child ports are hidden but their edges survive, drawn to a
ghost pin near the node title (see `iter_hidden_connected_ports`). `default=`
sets the starting open/closed state, and `on_change=` names a method to call
when the user folds or unfolds — the same reconfigure hook a config port
uses:

```python
with self.fold('Advanced', default=False):
    self.add(FLOAT.as_config('epsilon', default=1e-6))

with self.fold('Custom Name', on_change='hb_change'):
    self.add(STRING.as_config('name', default='my_callback'))
```

`description=` replaces the default line under the label in the header's hover
tooltip, which appears when the pointer crosses the disclosure triangle:

```python
with self.fold('Solver', description='How the solver steps through time.'):
    self.add(INT.as_config('substeps', default=10))
```

**One direction per fold.** Every port added inside one fold must share the
same `PortType` (inlet, outlet, or config) — a skin renders each direction in
its own lane, so a fold spanning two would need its header drawn twice.
Mixing raises `ValueError` at declaration time, from `init()`.

**A fold holds ports, not other folds.** Folds are one level deep; declaring
one inside another raises `ValueError`, like the two errors above. Use sibling
folds instead:

```python
with self.fold('Solver'):
    self.add(FLOAT.as_config('substeps', default=10.0))

with self.fold('Interpolation Range'):
    self.add(FLOAT.as_config('begin', default=0.0))
    self.add(FLOAT.as_config('end', default=1.0))
```

Label a fold as a section name ("Custom Name"), not as an imperative ("Use
Custom Name") — it names what is inside, and the user opens it rather than
deciding something.

`fold()` replaces the older `group()` (which required importing `GROUP` and
choosing a widget) and `section()` (which had no adopters in this repo).
See [ADR 0035](../adr/0035-fold-replaces-group-and-section.md).

### Ordering

`DataPort.order` is the sort key every card and panel renders by. It defaults
to the order `init()` adds the ports in, so a node's declaration is its
starting arrangement.

The graph user may override it by dragging a port in the **Properties → Ports**
panel. Each direction lane, and each fold within it, is its own drag group: a
port cannot be dragged into another lane or out of its fold. The new order is
persisted with the graph, and a promoted port's order is stored on its
promotion record rather than in the node's ports block.

The user's order wins over the author's. A node that reconfigures itself
through `rejig()` keeps whatever arrangement the user set, and a port added in
a new version of a library appends rather than landing at its declared
position — so reordering a node's `init()` calls does not move ports on graphs
already saved.

Reordering is not undoable. A bad drop is repaired by dragging back.

## 4. Live examples from the codebase

### Port shapes — declaration

Source: `barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py`

`EdgeLinkTestNode` exercises every port shape in `init()`: primitive inlets and outlets, `ArrayType[T]` outlets, `PooledType[T]` inlets, and `EXEC` for control flow. It is purpose-built as a connection testbed, so its `worker` is intentionally empty:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py:10:122"
```

from: `EdgeLinkTestNode` — registry_key: `haybale-testing:node:EdgeLinkTestNode`

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

Source: `barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py`

`TestEmitCallbackNode` shows how a pooled inlet is consumed in a worker: the value arrives as a `dict`, iterated to dispatch to multiple listeners. It also demonstrates `on_change` on a pooled inlet, `post_init()` for non-serializable state, and `fold()` for a collapsible config section:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py:1:79"
```

from: `TestEmitCallbackNode` — registry_key: `haybale-testing:node:TestEmitCallbackNode`

What this example covers for worker access:

| Concept | Where it shows up |
|---|---|
| `PooledType[CALLBACK].as_inlet(...)` | `edge_callback` — collects multiple listener IDs |
| Pooled value arrives as `dict` in worker | `edge_callbacks` parameter, iterated with `.values()` |
| `on_change='printout'` on a pooled inlet | called when connections change |
| `fold(...)` collapsible config section | `Custom Name` fold with `custom_callback_name` |
| `STRING.as_config(...)` inside a fold | `custom_callback_name` — panel-only, no canvas pin |
| `post_init()` for non-serializable state | `self.callback_index = 0` |
| Worker named parameter binding | `custom_name`, `sequential_mode`, `edge_callbacks`, etc. |
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
