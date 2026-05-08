---
status: draft
doc_template: canonical-example
scope: Authoring node classes — BaseNode, @node decorator, lifecycle hooks, worker function, dynamic reconfiguration
see-also:
  - ../ports/port-canon.md
  - ../datatypes/datatype-canon.md
  - ../settings/setting-canon.md
  - ../../guides/node-roles.md
  - ../../architecture/execution/virtual-machine/virtual-machine-arch.md
  - ../../reference/glossary.md
---

# Node — Canonical Example

## 1. What it solves

A **node** is a unit of work in a haywire graph. As a node author, you define a Python class that inherits from `BaseNode`, decorate it with `@node(...)`, declare its ports in `init()`, and implement a `worker()` method that does the actual computation. Once registered (your library's `register_components()` picks it up automatically), it appears in the canvas menu, is connectable to other nodes, hot-reloads on file save, and runs inside the VM.

Three node roles exist; you pick one at decoration time:

- **CONTROL** — has at least one EXEC inlet *and* outlet; participates in execution flow.
- **DATA** — no EXEC ports; runs only when its outputs are demanded by downstream control nodes.
- **EVENT / OUTPUT / LOOPBACK** — special CONTROL-flavoured roles (entry, exit, loops).

See [reference/glossary](../../reference/glossary.md) for the full **NodeType** taxonomy.

## 2. How it fits

```text
@node decoration         Class registry          Runtime
─────────────────        ──────────────          ────────
BaseNode subclass   →    NodeRegistry      →    NodeWrapper
+ @node metadata          (registry_key)         (live instance + lifecycle state)
+ init() declares ports                          + ports[] (DataPort objects)
+ worker() does work                             + behavior (NodeType, flags)
                                                 + executed by VM
```

The class you write is the *blueprint*. At runtime, a `NodeWrapper` owns the live instance, manages its lifecycle, and proxies it into the VM. You never instantiate `NodeWrapper` directly — the framework does, when a node is added to a graph or hot-reloaded.

**Boundaries.** Port creation primitives (`as_inlet`, `as_outlet`, `as_config`, primitive vs array vs pooled access) live in [components/ports](../ports/port-canon.md). Datatypes (`@type`, IType subclasses) live in [components/datatypes](../datatypes/datatype-canon.md). Settings declared on a node go in [components/settings](../settings/setting-canon.md). The VM that runs your worker lives in [architecture/execution/virtual-machine](../../architecture/execution/virtual-machine/virtual-machine-arch.md).

## 3. Important concepts

**The `@node` decorator.** Attaches identity metadata: `label`, `description`, `menu` (canvas menu path), `search_tags`, `node_type` (`NodeType.CONTROL` / `NodeType.DATA` / etc.). The decorator's `node_type` argument sets the default execution role; the actual role is inferred from the EXEC ports declared in `init()`.

**`init()` declares ports.** Called once when the node is first instantiated. Use `self.add(...)` with port specs from the type system: `EXEC.as_inlet('trigger')`, `FLOAT.as_inlet('value', default=0.0)`, `MyComplexType.as_outlet('result')`. Port creation surface lives in [components/ports](../ports/port-canon.md). 

**IMPORTANT**: When a node is deserialized (loaded for a graph) its ports are instantiated from disc and the **`init()`** method is **NOT** called. What is called though is the **`post_init()`** method. Thus the **`init()`** should only define those ports that are needed when the node is instantiated awnew or reset.

**`post_init()`** should be used to perform any additional setup that cannot be done through deserialization, such as instantiating classes. Do not use it for performative operations or as a preparation for the worker execution - the on_startup() method should be used for that purpose.


**Lifecycle hooks (called by the VM in this order).**

| Hook | When | Purpose |
|---|---|---|
| `init(self)` | Once at node creation | Declare ports |
| `post_init(self)` | Once after init | Set up state that cannot be serialized |
| `on_startup(self, context)` | Once when the flow starts | Acquire resources |
| `on_frame_start(self, context)` | Each frame, before workers run | Per-frame setup |
| `on_validate(self, context)` | Each frame, before this node's worker | Pre-flight input validation |
| `worker(self, context, ...)` | Each frame this node executes | The main computation |
| `on_frame_end(self, context)` | Each frame, after workers run | Per-frame teardown |
| `on_shutdown(self, context)` | Once when the flow stops | Release resources |
| `on_saved(self)` | Just before the graph is saved | Capture last-moment state |
| `on_teardown(self)` | When the node is destroyed/unloaded | Clean up |

Override only what you need. Most nodes override `init()` and `worker()` and nothing else.

**The worker function.** The heart of every node. Signature: `def worker(self, context: ExecutionContext, *args, **kwargs) -> str | None`. Return value:

- `None` — for DATA nodes, or when no further control flow continues.
- `'outlet_id'` — trigger control flow through that EXEC outlet (CONTROL nodes only).

Inlet values arrive as named parameters: parameter names must match inlet IDs declared in `init()`. The framework reads the inlets, unwraps the values, and binds them by name. Use type hints for clarity; defaults make the parameter optional.

```python
def worker(self, context: ExecutionContext, value: float, multiplier: float = 1.0) -> str | None:
    self.out('result', value * multiplier)
    return 'next'   # CONTROL nodes only — DATA nodes return None
```

**Reading and writing values inside `worker`.** `self.value('inlet_id')` returns the unwrapped value of an inlet. `self.out('outlet_id', value)` writes the unwrapped value to an outlet. These are the canonical accessors. (Some older docs reference `self.inlet(...)` / `self.set_outlet(...)` — those names are out of date.)

**Dynamic reconfiguration via `rejig()`.** When a config port changes (e.g. a "data type" selector), call `self.rejig()` from a `hb_*` callback. Inside the `with self.rejig(...)` block, every port not re-added is destroyed; ports re-added by ID keep their connections.

```python
with self.rejig(exclude=['exec', 'true', 'false', 'DataType']):
    if self.value('DataType') == 'int':
        self.add(INT.as_inlet('compare'))
        self.add(INT.as_inlet('with'))
    else:
        self.add(FLOAT.as_inlet('compare'))
        self.add(FLOAT.as_inlet('with'))
```

`rejig()` accepts `include=` and `exclude=` (list of IDs or regex string). Static ports — those declared once in `init()` and never changing — should be excluded so the system doesn't tear them down.

**Groups and sections.** Two ways to organise ports without changing the worker contract:

- `with self.group(GROUP.as_inlet('advanced', label='Advanced'))` — collapsible UI container; child ports are hidden when collapsed but connections are preserved via ghost pins. Groups can nest.
- `with self.section('validation')` — moves ports off the node body and into a property-panel section. Worker contract unchanged.

**Custom instance attributes — the `hb_*` convention.** Methods or attributes you add to a node class should start with `hb_`, `my_`, `custom_`, or `ext_` so they don't collide with future framework additions. The `hb_*` prefix is the project convention for "this is a node-author hook."

**Settings inner classes.** A node can declare one or more `NodeSettings` inner classes for declarative settings (with `setting()`, `shadow()`, `watch()`). Full coverage in [components/settings](../settings/setting-canon.md).

## 4. One comprehensive example

A worked example that exercises every concept above: a control-flow `RangeFilter` node that switches between INT and FLOAT mode based on a config port, exercises rejig and groups, demonstrates the full lifecycle, and uses a `hb_*` helper.

```python
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.node.behavior import NodeType
from haywire.core.execution.execution_context import ExecutionContext

@node(
    label='Range Filter',
    description='Filters a value by range; mode is configurable',
    menu='math/filters',
    search_tags=['filter', 'range', 'clamp'],
    node_type=NodeType.CONTROL,
)
class RangeFilter(BaseNode):
    """
    Single comprehensive example: control-flow node that:
      - declares static and dynamic ports
      - reconfigures itself when a config port changes (rejig)
      - groups optional ports under a collapsible header
      - branches control flow based on its computation
      - uses an hb_* helper that survives hot-reload
    """

    def init(self):
        from ..types.specs import EXEC, INT, FLOAT, STRING, GROUP
        from haybale_core.widgets.basic_widgets import SelectWidget, NumberWidget

        # Static ports — these are excluded from rejig
        self.add(EXEC.as_inlet('exec', label='Execute'))
        self.add(EXEC.as_outlet('in_range', label='In range'))
        self.add(EXEC.as_outlet('out_of_range', label='Out of range'))

        # Config port — change triggers hb_reconfigure
        self.add(STRING.as_config(
            'mode', label='Mode',
            widget=SelectWidget.config(properties={'options': ['int', 'float']}),
            default='int',
            on_change='hb_reconfigure',
        ))

        # Group: optional bounds. Collapsed by default in UI; ghost pins
        # preserve connections when collapsed.
        with self.group(GROUP.as_inlet('bounds', label='Bounds')):
            self.add(FLOAT.as_inlet('min', label='Min', default=0.0,
                                    widget=NumberWidget.config()))
            self.add(FLOAT.as_inlet('max', label='Max', default=100.0,
                                    widget=NumberWidget.config()))

    def post_init(self):
        # Wire up the dynamic ports for the initial mode value. After
        # deserialization the dynamic 'value' port is already present, so we
        # only rebuild it when it's missing (i.e. on a fresh instantiation).
        try:
            self.value("value")
        except KeyError:
            self.hb_reconfigure()

    # hb_* prefix → guaranteed safe across haywire framework updates
    def hb_reconfigure(self, *args, **kwargs):
        # This method is called when the 'mode' changes. It shows the prefered
        # way how to manage dynamic
        from ..types.specs import INT, FLOAT
        from haybale_core.widgets.basic_widgets import NumberWidget

        # Rejig only the dynamic value port. Static ports (exec, in_range,
        # out_of_range, mode, min, max, bounds) are preserved.
        with self.rejig(exclude=['exec', 'in_range', 'out_of_range',
                                 'mode', 'min', 'max', 'bounds']):
            if self.value('mode') == 'int':
                self.add(INT.as_inlet('value', label='Value',
                                      widget=NumberWidget.config()))
            else:
                self.add(FLOAT.as_inlet('value', label='Value',
                                        widget=NumberWidget.config()))

    def on_startup(self, context: ExecutionContext):
        # Place to acquire resources. Called once when the flow starts.
        pass

    def on_validate(self, context: ExecutionContext):
        # Optional pre-flight check before worker runs.
        if self.value('min') > self.value('max'):
            pass
            # Set error state — this surfaces in the UI.
            # TODO: Nice idea: create a mechanism to allow the user to post a 
            # runtime error - currently not supported though
            # from haywire.ui.error_info import NodeErrorInfo
            # self.error_info = NodeErrorInfo(message='min must be <= max')

    def worker(
        self,
        context: ExecutionContext,
        value: float = 0.0,
        min: float = 0.0,
        max: float = 100.0,
    ) -> str | None:
        """Parameter names match inlet IDs. Inlet values arrive unwrapped.
        Returns the EXEC outlet ID to follow next."""
        if min <= value <= max:
            return 'in_range'
        return 'out_of_range'

    def on_shutdown(self, context: ExecutionContext):
        # Release any resources acquired in on_startup.
        pass

    def on_teardown(self):
        # Final cleanup when the node is unloaded (e.g. on hot-reload).
        pass
```

What this example exercises:

| Concept | Where it shows up |
|---|---|
| `@node(node_type=NodeType.CONTROL)` | decoration |
| `init()` declares static and grouped ports | `EXEC`, `STRING.as_config`, `GROUP` |
| `post_init()` for non-serializable setup | calls `hb_reconfigure()` |
| `on_change='hb_reconfigure'` triggers dynamic ports | `mode` config port |
| `with self.rejig(exclude=...)` preserves static ports | inside `hb_reconfigure` |
| `with self.group(...)` for collapsible UI | `bounds` group |
| `hb_*` prefix for custom methods | `hb_reconfigure` |
| `worker()` with named inlet params | `value`, `min`, `max` |
| Worker returns EXEC outlet ID | `'in_range'` / `'out_of_range'` |
| `self.value('id')` to read | `self.value('mode')`, `self.value('min')` |
| `on_validate()` for input checks | the min/max validation |
| `on_startup` / `on_shutdown` / `on_teardown` lifecycle | hook signatures shown |

For the port creation surface (everything `as_inlet` / `as_outlet` / `as_config` accepts, primitive vs array vs pooled, worker access patterns), see [components/ports](../ports/port-canon.md). For declarative settings on the node (instead of config ports), see [components/settings](../settings/setting-canon.md).

For worked examples of each role — CONTROL multi-pin dispatch, DATA pure compute, EVENT with the matching emitter, LOOPBACK round-trip with break — see [guides/node-roles](../../guides/node-roles.md).

---

## Worker function reference

| Return value | Meaning |
|---|---|
| `None` | DATA node, or no further control flow |
| `'outlet_id'` | Trigger control flow through that EXEC outlet |

Parameter binding rule: `worker` parameter names must match inlet IDs declared in `init()`. The framework extracts and unwraps inlet values automatically. Type hints document expected types; defaults make the parameter optional. A required parameter (no default) without a matching port raises `ValueError`.

## Lifecycle hook reference

| Hook | Signature | Purpose |
|---|---|---|
| `init` | `(self)` | Declare ports via `self.add(...)` |
| `post_init` | `(self)` | Non-serializable setup |
| `on_startup` | `(self, context)` | Once when flow starts |
| `on_frame_start` | `(self, context)` | Each frame, before workers |
| `on_validate` | `(self, context)` | Each frame, before this worker |
| `worker` | `(self, context, *args, **kwargs)` | Main computation; returns `None` or `'outlet_id'` |
| `on_frame_end` | `(self, context)` | Each frame, after workers |
| `on_shutdown` | `(self, context)` | Once when flow stops |
| `on_saved` | `(self)` | Just before graph is saved |
| `on_teardown` | `(self)` | When node is destroyed |
