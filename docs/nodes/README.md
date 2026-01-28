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
