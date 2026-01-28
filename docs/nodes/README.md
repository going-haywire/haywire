# Nodes Documentation

```python:
"""
ForLoop Node - Standard loop construct for iteration.

Executes loop body a specified number of times with index tracking.
"""
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.execution.execution_context import ExecutionContext


@node(
    label='Simple Node',
    description='Doing something simple',
    menu='simple/nodes',
    search_tags=['simple', 'task'],
)
class SimpleNode(BaseNode):
    
    def initialize(self):
        from ..types.specs import EXEC, INT
        from haybale_core.widgets.basic_widgets import NumberWidget

        
        # Mark as control node (not data node)
        self.behavior.is_control_node = True
        self.behavior.is_data_node = False
                
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
    def setup(self):
        pass

    # Method that is called once when the node is started up in the VM.
    def startup(self, context: ExecutionContext):
        pass

    # Handle asynchronous changes to the node. Called before worker execution.
    def on_changed_async(self, context: ExecutionContext) -> None:

    # Handle validation of inputs before execution. Called before worker execution.
    def on_validation_input(self, context: ExecutionContext) -> None:
 
    # Main workhorese method. This is called by the VM when this node is executed.
    # It receives the execution context. All method inputs after context are optional and
    # correspond to the node's inlets. 'value' inlet is passed as an argument here.
    def worker(
        self,
        context: ExecutionContext,
        value: int = 0
    ) -> dict | tuple:

        # simply passes the value to the output
        # and triggers the next node through 'execute' outlet.       
        return 'execute', (('result', value),)

    # Method that is called once when the node is being shut down in the VM.
    def shutdown(self, context: ExecutionContext):
        pass

    # Method that is called when the node is being destroyed/unloaded.
    # place to clean up any resources or references.
    def teardown(self):
        pass

```

## Lifecyle of a Node

1. **Initialization**: `initialize()` method is called to set up inlets and outlets.
2. **Setup**: `setup()` method is called for additional setup.

when the flow starts executing:
3. **Startup**: `startup(context)` is called once when the node starts executing.
   
inside the execution loop:
4. **On Changed Async**: `on_changed_async(context)` is called to handle async changes.
5. **On Validation Input**: `on_validation_input(context)` is called to validate inputs.
6. **Worker Execution**: `worker(context, ...)` is called to perform the node's main function.

when the flow stops executing:
7. **Shutdown**: `shutdown(context)` is called once when the node stops executing.

when the node is being unloaded:
8. **Teardown**: `teardown()` is called to clean up resources.

---

## The Worker Method

The `worker()` method is the main execution logic of your node. It's called by the VM when the node is executed.

### Method Signature

```python
def worker(self, context: ExecutionContext, *args, **kwargs) -> WorkerResult:
```

**Key Design Principle:** Parameter names must match inlet port IDs. The system automatically extracts and passes inlet values as unwrapped arguments.

### Parameter Mapping

```python
def initialize(self):
    self.add(FLOAT.as_inlet(id='value', default=0.0))
    self.add(FLOAT.as_inlet(id='multiplier', default=1.0))
    self.add(FLOAT.as_outlet(id='result'))

# Parameters 'value' and 'multiplier' match the inlet IDs above
def worker(self, context: ExecutionContext, value: float, multiplier: float):
    return (None, (('result', value * multiplier),))
```

**Rules:**
- Use type hints to document expected types
- Use default values for optional ports (if port doesn't exist, default is used)
- Required parameters (no default) must have matching ports or `ValueError` is raised

### Return Types (WorkerResult)

The worker method returns a `WorkerResult` which can take several forms:

| Return Value | Meaning |
|--------------|---------|
| `None` | No control flow, no outputs |
| `'outlet_id'` | Trigger control flow through outlet, no data outputs |
| `('outlet_id', ())` | Trigger control flow, no outputs (explicit) |
| `(None, (('out1', 10), ('out2', 20)))` | Set data outputs, no control flow |
| `('outlet_id', (('out1', 10), ('out2', 20)))` | Trigger control flow AND set outputs |

### Examples

**Simple data node:**
```python
def worker(self, context: ExecutionContext, value: float, multiplier: float):
    result = value * multiplier
    return (None, (('result', result),))
```

**Node with optional inputs:**
```python
def worker(self, context: ExecutionContext, value: float, offset: float = 0.0):
    result = value + offset
    return (None, (('result', result),))
```

**Control flow node (branching):**
```python
def worker(self, context: ExecutionContext, condition: bool):
    return 'true_branch' if condition else 'false_branch'
```

**Multi-output with control flow:**
```python
def worker(self, context: ExecutionContext, x: float, y: float):
    return ('next', (
        ('sum', x + y),
        ('product', x * y),
        ('difference', x - y),
    ))
```

---

## Alternative Access Methods

If you prefer not to use parameter mapping, or need dynamic access to ports, you can use the `self.value()` and `self.out()` methods directly.

### Reading Inlet Values: `self.value()`

```python
def worker(self, context: ExecutionContext):
    # Access inlet values by ID
    value = self.value('input')
    threshold = self.value('threshold')
    
    result = value if value > threshold else 0.0
    return (None, (('result', result),))
```

### Setting Outlet Values: `self.out()`

```python
def worker(self, context: ExecutionContext):
    value = self.value('input')
    
    # Set outlet values by ID
    self.out('doubled', value * 2)
    self.out('halved', value / 2)
    self.out('squared', value ** 2)
    
    return 'next'  # Only return control flow, outputs already set
```

### Comparison

| Approach | Pros | Cons |
|----------|------|------|
| **Parameter mapping** | Faster, cleaner, type-hinted | Less flexible |
| **`self.value()` / `self.out()`** | Dynamic, flexible | Slower, no type hints |

### Mixed Approach

You can combine both methods:

```python
def worker(self, context: ExecutionContext, value: float, multiplier: float):
    # Use parameters for main inputs
    result = value * multiplier
    
    # Use self.out() for setting outputs
    self.out('result', result)
    self.out('debug_info', f"Computed {value} * {multiplier}")
    
    return 'next'
```

### Checking Port Connection Status

```python
def worker(self, context: ExecutionContext):
    # Check if an inlet is connected before accessing
    if self.ports['optional_input'].is_connected:
        value = self.value('optional_input')
        result = process_with(value)
    else:
        result = process_default()
    
    return (None, (('result', result),))
```

