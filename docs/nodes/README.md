# Nodes Documentation

```python
"""
ForLoop Node - Standard loop construct for iteration.

Executes loop body a specified number of times with index tracking.
"""
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
    def on_init(self):
        pass

    # Method that is called once when the node is started up in the VM.
    def on_startup(self, context: ExecutionContext):
        pass

    # Handle validation of inputs before execution. Called before worker execution.
    def on_validate(self, context: ExecutionContext) -> None:

    # Main workhorese method. This is called by the VM when this node is executed.
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
2. **Setup**: `on_init()` method is called for additional setup.

when the flow starts executing:
3. **Startup**: `on_startup(context)` is called once when the node starts executing.
inside the execution loop:
4. **On Validate**: `on_validate(context)` is called to validate inputs.
5. **Worker Execution**: `worker(context, ...)` is called to perform the node's main function.

when the flow stops executing:
6. **Shutdown**: `on_shutdown(context)` is called once when the node stops executing.
when the node is being unloaded:
7. **Saved**: `on_saved()` is called just before the node is being saved.
8. **Teardown**: `on_teardown()` is called to clean up resources.

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

## Custom instance attributes

You can define your own instance attributes within your node class to encapsulate reusable logic. To make sure your custom methods work even when the haywire framework is adding new functionality in the future, use the following guidelines:

start the method name with **hb_**, **my_**, **custom_** or **ext_**. 