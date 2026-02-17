# Nodes Documentation

```python
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.node.behavior import NodeType
from haywire.core.execution.execution_context import ExecutionContext


@node(
    label='Simple Node',
    description='Doing something simple',
    menu='simple/nodes',
    search_tags=['simple', 'task'],
    node_type=NodeType.CONTROL, # indicates that this node controls execution flow
)
class SimpleNode(BaseNode):

    def init(self):
        from ..types.specs import EXEC, INT
        from haybale_core.widgets.basic_widgets import NumberWidget

        # Control input - starts the loop
        self.add(EXEC.as_inlet(
            'trigger',
            label='Execute'
        ))

        # value inputs
        self.add(INT.as_inlet(
            'value',
            label='Value',
            default=0,
            widget=NumberNumberWidget.config()
        ))

        # OUTLETS

        # Loop body outlet - executes on each iteration
        self.add(EXEC.as_outlet(
            'execute',
            label='Execute next node',
        ))

        # simple outlet
        self.add(INT.as_outlet(
            'result',
            label='result'
        ))

    # Method that is called right after initialize() to set up any additional state
    # that cannot be serialized.
    def post_init(self):
        pass

    # Method that is called once when the node is started up in the VM.
    def on_startup(self, context: ExecutionContext):
        pass

    # Method that is called at the start of each execution of the flow.
    def on_frame_start(self, context: ExecutionContext) -> None:
        pass

    # Handle validation of inputs before execution. Called before worker execution.
    def on_validate(self, context: ExecutionContext) -> None:

    # Main workhorse method. This is called by the VM when this node is executed.
    # It receives the execution context. All method inputs after context are optional and
    # correspond to the node's inlets. 'value' inlet is passed as an argument here.
    def worker(
        self,
        context: ExecutionContext,
        value: int = 0
    ) -> str | None:

        # simply passes the value to the output
        self.out('result', value)
        # and triggers the next node through 'execute' outlet.       
        return 'execute',

    # Method that is called when the flow has finished executing the frame.
    def on_frame_end(self, context: ExecutionContext):
        pass

    # Method that is called once when the node is being shut down in the VM.
    def on_shutdown(self, context: ExecutionContext):
        pass

    # Method that is called when the node is being saved.
    # last moment to save any valuable data that should persist.
    def on_saved(self):
        pass

    # Method that is called when the node is being destroyed/unloaded.
    # place to clean up any resources or references.
    def on_teardown(self):
        pass
```

## Lifecyle of a Node

1. **Initialization**: `init()` method is called to set up inlets and outlets.
2. **Setup**: `post_init()` method is called for additional setup.

when the flow starts executing:
3. **Startup**: `on_startup(context)` is called once when the node starts executing.

before the flow is beeing executed
4. **Frame Start**: `on_frame_start(context)` is called at the start of each execution of the flow.
   
inside the execution loop:
5. **On Validate**: `on_validate(context)` is called to validate inputs.
6. **Worker Execution**: `worker(context, ...)` is called to perform the node's main function.

when the flow finishes an execution cycle:
7. **Frame End**: `on_frame_end(context)` is called at the end of each execution of the flow.

when the flow stops executing:
8. **Shutdown**: `on_shutdown(context)` is called once when the node stops executing.

when the node is being unloaded:
9. **Saved**: `on_saved()` is called just before the node is being saved.
10. **Teardown**: `on_teardown()` is called to clean up resources.
---

## The Worker Method

The `worker()` method is the main execution logic of your node. It's called by the VM when the node is executed.

### Method Signature

```python
def worker(self, context: ExecutionContext, *args, **kwargs) -> str | None:
```

**Key Design Principle:** Parameter names must match inlet port IDs. The system automatically extracts and passes inlet values as unwrapped arguments.

### Parameter Mapping

```python
def initialize(self):
    self.add(FLOAT.as_inlet(id='value', default=0.0))
    self.add(FLOAT.as_inlet(id='multiplier', default=1.0))
    self.add(FLOAT.as_outlet(id='result'))

# Parameters 'value' and 'multiplier' match the inlet IDs above
def worker(self, 
    context: ExecutionContext, 
    value: float, 
    multiplier: float
    ) -> str | None:

    self.out('result', value * multiplier)
```

**Rules:**

- Use type hints to document expected types
- Use default values for optional ports (if port doesn't exist, default is used)
- Required parameters (no default) must have matching ports or `ValueError` is raised

### Return Types

The worker method return can take two forms:

| Return Value           | Meaning                                        |
| ---------------------- | ---------------------------------------------- |
| `None`                 | No control flow continuation                   |
| `'outlet_id'`          | Trigger control flow through specified outlet  |


### Examples

**Simple data node:**

```python
def worker(self, context: ExecutionContext, value: float, multiplier: float):
    self.out('result', value * multiplier)
```

**Node with optional inputs:**

```python
def worker(self, context: ExecutionContext, value: float, offset: float = 0.0):
    self.out('result', value + offset)
```

**Control flow node (branching):**

```python
def worker(self, context: ExecutionContext, condition: bool):
    return 'true_branch' if condition else 'false_branch'
```

**Multi-output with control flow:**

```python
def worker(self, context: ExecutionContext, x: float, y: float) -> str| None:
    self.out('sum', x + y)
    self.out('product', x * y)
    self.out('difference', x - y)
    return 'next'
```

---

## Alternative Access Methods

If you prefer not to use parameter mapping, or need dynamic access to ports, you can use the `self.value()` methods directly.

### Reading Inlet (and Outlet) Values: `self.value()`

```python
def worker(self, context: ExecutionContext):
    # Access inlet values by ID
    value = self.value('input')
    threshold = self.value('threshold')

    self.out('result', value if value > threshold else 0.0)
```

## Dynamic Port Reconfiguration (`rejig`)

Nodes can dynamically add and remove ports at runtime using the `rejig()` context manager. This is useful for nodes whose port layout depends on a configuration value (e.g. a data type selector or a count input).

### Basic Pattern

```python
def hb_reconfigure(self, port=None, *args):
    """Called when config port changes."""
    with self.rejig(exclude=['my_config_port']):
        # All ports except 'my_config_port' are flagged for removal.
        # Ports re-added here are preserved with their connections intact.
        # Ports NOT re-added are destroyed when the block exits.
        self.add(FLOAT.as_inlet('value', label='Value'))
        self.add(FLOAT.as_outlet('result', label='Result'))
```

### Filtering Which Ports to Rejig

`rejig()` accepts `include` and `exclude` parameters (list of IDs or regex string):

```python
# Rejig all ports
with self.rejig():
    ...

# Rejig only dynamic ports (by regex)
with self.rejig(include=r'^dynamic_'):
    ...

# Rejig all except specific static ports
with self.rejig(exclude=['exec', 'config']):
    ...
```

### Complete Example: Type-Switching Node

```python
@node(label='Control Switch', node_type=NodeType.CONTROL)
class ControlSwitch(BaseNode):

    def init(self):
        from ..types.specs import EXEC, STRING
        from haybale_core.widgets.basic_widgets import SelectWidget

        self.add(EXEC.as_inlet('exec', label='Execute'))
        self.add(STRING.as_config(
            'DataType', label='Data Type',
            widget=SelectWidget.config(properties={'options': ['int', 'float']}),
            default='int',
            on_change='hb_change'
        ))
        self.add(EXEC.as_outlet('true', label='True'))
        self.add(EXEC.as_outlet('false', label='False'))

    def post_init(self):
        self.hb_change()

    def hb_change(self, *args, **kwargs):
        from ..types.specs import INT, FLOAT, STRING
        from haybale_core.widgets.basic_widgets import SelectWidget, NumberWidget

        with self.rejig(exclude=['exec', 'true', 'false', 'DataType']):
            if self.value('DataType') == 'int':
                self.add(INT.as_inlet('compare', label='Compare',
                         widget=NumberWidget.config()))
                self.add(INT.as_inlet('with', label='With',
                         widget=NumberWidget.config()))
            else:
                self.add(FLOAT.as_inlet('compare', label='Compare',
                         widget=NumberWidget.config()))
                self.add(FLOAT.as_inlet('with', label='With',
                         widget=NumberWidget.config()))
```

### What Happens to Connections

- **Re-added port (same ID)**: connections are preserved — the edge survives the rejig
- **Removed port (not re-added)**: all edges are detached and cleaned up automatically
- **Static ports (excluded from rejig)**: completely unaffected

---

## Port Groups and Sections

### Groups (Collapsible Port Containers)

Groups create a collapsible header in the node UI. Ports added inside a `group()` block become children of the group — when the group is collapsed, child ports are hidden but connections are preserved via ghost pins.

```python
def init(self):
    from ..types.specs import FLOAT, GROUP

    self.add(FLOAT.as_inlet('value', label='Value'))

    with self.group(GROUP.as_inlet('advanced', label='Advanced Options')):
        self.add(FLOAT.as_inlet('epsilon', label='Epsilon', default=0.001))
        self.add(FLOAT.as_inlet('tolerance', label='Tolerance', default=0.1))

        # Groups can be nested
        with self.group(GROUP.as_inlet('expert', label='Expert')):
            self.add(FLOAT.as_inlet('damping', label='Damping', default=0.5))
```

### Sections (Property Panel Organization)

Sections organize ports in the property panel/inspector without affecting the node's visual layout. Ports in a section are hidden from the node body but accessible in the inspector.

```python
def init(self):
    from ..types.specs import FLOAT, BOOL

    self.add(FLOAT.as_inlet('value', label='Value'))

    with self.section('validation'):
        self.add(FLOAT.as_inlet('min_value', label='Min', default=0.0))
        self.add(FLOAT.as_inlet('max_value', label='Max', default=100.0))
        self.add(BOOL.as_inlet('clamp', label='Clamp', default=False))
```

---

## Custom Instance Attributes

You can define your own instance attributes within your node class to encapsulate reusable logic. To make sure your custom methods work even when the haywire framework is adding new functionality in the future, use the following guidelines:

start the method name with **hb_**, **my_**, **custom_** or **ext_**. 