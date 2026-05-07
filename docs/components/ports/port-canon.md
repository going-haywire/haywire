---
status: draft
template: canonical-example
scope: Authoring ports — as_inlet / as_outlet / as_config, primitive vs array vs pooled, worker access, port flags
see-also:
  - ../nodes/node-canon.md
  - ../datatypes/datatype-canon.md
  - ../widgets/widget-canon.md
  - ../../architecture/execution/edges/edges-arch.md
  - ../../reference/glossary.md
---

# Port — Canonical Example

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

**Boundaries.** What types exist and how to define them lives in [components/datatypes](../datatypes/datatype-canon.md). What widgets are bound to ports lives in [components/widgets](../widgets/widget-canon.md). The node lifecycle that calls your worker lives in [components/nodes](../nodes/node-canon.md). The runtime mechanics of edge build / adapter chain construction live in [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

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

The `on_change` callback is what you wire to a `hb_*` reconfigure method when a config port should rebuild dynamic ports. See [components/nodes](../nodes/node-canon.md) §3 for the rejig pattern.

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

Both are explained in [components/nodes](../nodes/node-canon.md) §3.

## 4. One comprehensive example

A worked example exercising every port shape, callback, and worker access pattern: a `MultiSourceAggregator` node that accepts a single threshold (primitive inlet), an array of weights (array inlet), a pool of incoming values (pooled inlet), a label (config), and emits a result + a log array. It uses `on_change` to recompute on threshold changes and `is_linked()` to detect optional connections.

```python
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.node.behavior import NodeType
from haywire.core.execution.execution_context import ExecutionContext


@node(
    label='Multi-Source Aggregator',
    description='Aggregates a pool of values weighted by an array',
    menu='math/aggregate',
    search_tags=['aggregate', 'pool', 'weight'],
    node_type=NodeType.DATA,
)
class MultiSourceAggregator(BaseNode):

    def init(self):
        from ..types.specs import FLOAT, INT, STRING, BOOL
        from haywire.core.types.array_type import ArrayType
        from haywire.core.types.pooled_type import PooledType
        from haybale_core.widgets.basic_widgets import NumberWidget

        # ── Primitive inlet with default and on_change callback ───────
        self.add(FLOAT.as_inlet(
            'threshold',
            label='Threshold',
            default=0.5,
            widget=NumberWidget.config(),
            on_change='hb_threshold_changed',
        ))

        # ── Array inlet (one connection, list of typed values) ────────
        self.add(ArrayType[FLOAT].as_inlet(
            'weights',
            label='Weights',
            default=[1.0, 1.0, 1.0],
        ))

        # ── Pooled inlet (multiple connections, dict to worker) ───────
        # PooledType is inlet-only — as_outlet would raise.
        self.add(PooledType[FLOAT].as_inlet(
            'values',
            label='Values to Aggregate',
        ))

        # ── Config port (no pin on canvas, only in property panel) ────
        self.add(STRING.as_config(
            'label',
            label='Label',
            default='aggregator',
        ))

        # ── Optional inlet — used only when connected ─────────────────
        self.add(FLOAT.as_inlet(
            'gain',
            label='Gain (optional)',
            default=1.0,
        ))

        # ── Outlets: a primitive, an array, a flag ────────────────────
        self.add(FLOAT.as_outlet('result', label='Aggregated result'))
        self.add(ArrayType[FLOAT].as_outlet('per_source', label='Per-source values'))
        self.add(BOOL.as_outlet('above_threshold', label='Above threshold?'))
        self.add(INT.as_outlet('source_count', label='Source count'))

    # hb_* prefix → safe across framework updates
    def hb_threshold_changed(self, *args, **kwargs):
        # Could trigger UI refresh, log, etc. Called whenever 'threshold'
        # is edited from the property panel.
        pass

    def worker(
        self,
        context: ExecutionContext,
        threshold: float = 0.5,
        weights: list = None,
        values: dict = None,    # pooled — dict[source_id, value]
        gain: float = 1.0,
    ) -> str | None:
        """
        Demonstrates all worker access patterns.

        - threshold, weights, values, gain → arrive by named parameter
        - 'label' (config) → read with self.value('label')
        - 'gain' optionality → checked with self.ports['gain'].is_linked()
        """
        # Read a config port that wasn't bound by parameter:
        label = self.value('label')

        # Detect whether an optional inlet is actually connected.
        # is_linked() is the canonical API — older docs may show
        # is_connected, which doesn't exist.
        gain_active = self.ports['gain'].is_linked()
        effective_gain = gain if gain_active else 1.0

        # Pooled value comes in as a dict; default for safety.
        values = values or {}
        weights = weights or []

        # Aggregate: weighted sum, falling back to equal weights.
        per_source = []
        for i, (src_id, v) in enumerate(values.items()):
            w = weights[i] if i < len(weights) else 1.0
            per_source.append(v * w * effective_gain)

        result = sum(per_source) if per_source else 0.0

        # Pooled access also exposes helpers via the underlying field.
        # Equivalent to len(values), shown for completeness.
        source_count = len(self.ports['values'].data.get_source_ids())

        # Write all outlets — never wrap; just pass the raw value.
        self.out('result', result)
        self.out('per_source', per_source)
        self.out('above_threshold', result > threshold)
        self.out('source_count', source_count)

        # Optional debug — uses the config port we read above.
        # context.log_debug(f'{label}: aggregated {source_count} sources -> {result:.3f}')
```

What this example exercises:

| Concept | Where it shows up |
|---|---|
| Primitive inlet with `default` and `on_change` | `threshold` |
| Array inlet (`ArrayType[FLOAT]`) with default list | `weights` |
| Pooled inlet (`PooledType[FLOAT]`, inlet-only) | `values` |
| Config port (no canvas pin) | `label` |
| Multiple outlets in different shapes | `result`, `per_source`, `above_threshold`, `source_count` |
| Worker parameter binding by name | `threshold`, `weights`, `values`, `gain` |
| `self.value(id)` for non-bound ports | `self.value('label')` |
| `self.ports[id].is_linked()` for optional inlets | `self.ports['gain'].is_linked()` |
| Pooled field helpers | `self.ports['values'].data.get_source_ids()` |
| `self.out(id, value)` (no wrapping) | result, per_source, above_threshold, source_count |
| `on_change` callback hooks (`hb_*` convention) | `hb_threshold_changed` |

For declarative settings instead of config ports, see [components/settings](../settings/setting-canon.md). For the lifecycle hooks that surround `worker()` (`init`, `post_init`, `on_validate`, etc.), see [components/nodes](../nodes/node-canon.md). For the dynamic `rejig()` pattern that adds and removes ports based on a config value, see [components/nodes §3](../nodes/node-canon.md#3-important-concepts).

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
