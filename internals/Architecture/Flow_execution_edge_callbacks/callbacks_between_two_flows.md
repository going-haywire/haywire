# Callbacks Between Two Flows

In Haywire, callbacks provide a powerful mechanism for communication between **disconnected flows**. This guide will walk you through how callbacks work under the hood, using a concrete example of two flows. The code for both nodes is attached at the end for reference.

## Callback Flow - Step by Step

### The Graph Structure

```
Flow 1 (Emitter):
  BeginPlay → EmitCallback
  (no connection to Flow 2)

Flow 2 (Listener):
  CustomCallback → PrintMessage
  (no connection to Flow 1)
```

These are **completely disconnected** in the graph - no edges between them!

### Assembly Time: Registration

Let me trace through what happens during assembly:

```python
# 1. FlowAssemblyManager.assemble_graph()
flows = []

# 2. For each event node, create a flow
for event_node in [BeginPlayNode, CustomCallbackNode]:
    flow = Flow(
        entry_event_node=event_node,
        event_subscription=event_node.event_subscription  # <-- Key!
    )
    flows.append(flow)

# Flow 1: event_subscription = SystemEvent(BEGIN_PLAY)
# Flow 2: event_subscription = CallbackEvent(event_name='my_callback')
```

**Key insight**: The `CustomCallbackNode` declares it listens for callback `'my_callback'` via its `event_subscription`. This is like saying "wake me up when someone emits 'my_callback'".

```python
# 3. Interpreter._register_flow() for Flow 2 (listener)
def _register_flow(self, flow: Flow):
    # Regular event subscription
    subscription_key = flow.get_subscription_key()
    # For CustomCallbackNode: "callback:my_callback"
    self.event_subscriptions[subscription_key].append(flow)
    
    # Special handling for CallbackEvent!
    if isinstance(flow.event_subscription, CallbackEvent):
        self.callback_manager.register_callback_listener(
            event_name='my_callback',  # <-- From event_subscription
            flow=flow
        )

# Now CallbackManager knows:
# callbacks['my_callback'] = [Flow2]
```

**At this point**, the connection is established **through the interpreter's callback manager**, not through graph edges!

### Runtime: Callback Emission

Now let's trace execution:

```python
# 1. User dispatches BEGIN_PLAY
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)

# 2. This triggers Flow 1
Flow1.scheduler.enqueue_trigger(trigger)

# 3. VM executes Flow 1
# ... executes BeginPlayNode ...
# ... navigates to EmitCallbackNode ...

# 4. EmitCallbackNode.worker() executes
def worker(self, context):
    callback_name = 'my_callback'
    message = 'Hello from callback!'
    
    # This is the key line!
    context.emit_callback( event_name=callback_name, payload=payload)
    #       ^^^^^^^^^^^^^^
    # This function is provided by ExecutionContext
    
    return {'next_outlet': 'done'}
```

Let's zoom into what `context['emit_callback']()` does:

```python
# ExecutionContext.emit_callback()
def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
    if self.vm:
        self.vm.emit_callback(event_name, payload)
    #     ^^^^^^
    #     VM has reference to CallbackManager!
```

```python
# HaywireVM.emit_callback()
def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
    if self.callback_manager:
        self.callback_manager.emit_callback(event_name, payload)
    #                       ^^^^^^^^^^^^^^
    #                       This reaches across flows!
```

```python
# CallbackManager.emit_callback()
def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
    # 1. Look up who's listening
    flows = self.callbacks.get('my_callback', [])
    # Returns: [Flow2]
    
    # 2. Create a trigger (like an event from outside)
    trigger = Trigger(
        source_key='callback:my_callback',
        payload={'message': 'Hello from callback!'},
        timestamp=time.time()
    )
    
    # 3. Enqueue trigger in Flow2's scheduler
    for flow in flows:  # Flow2
        flow.scheduler.enqueue_trigger(trigger)
        # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # This wakes up Flow 2!
```

```python
# 4. Flow2's scheduler picks up trigger
# Flow2.scheduler._execution_loop() gets trigger from queue

# 5. VM executes Flow2
# CustomCallbackNode.worker() receives trigger
def worker(self, context: ExecutionContext):
    # Extract payload from trigger
    payload = context.trigger.payload
    # {'message': 'Hello from callback!'}
    
    return ('triggered', (('payload', payload),))
    
# 6. Flow continues: CustomCallback → PrintMessage
# PrintMessage gets payload through data connection
```

### Visual Flow Diagram

```
═══════════════════════════════════════════════════════════
                    ASSEMBLY TIME
═══════════════════════════════════════════════════════════

Graph:
  Flow1: BeginPlay → EmitCallback
  Flow2: CustomCallback → PrintMessage
         (NO GRAPH EDGES BETWEEN FLOWS)

        ↓ Assembly ↓

Interpreter:
  event_subscriptions = {
    'system:begin_play': [Flow1],
    'callback:my_callback': [Flow2]  ←── Flow2 registered here
  }

CallbackManager:
  callbacks = {
    'my_callback': [Flow2]  ←── Flow2 registered here too
  }

═══════════════════════════════════════════════════════════
                    RUNTIME
═══════════════════════════════════════════════════════════

Step 1: External event
  → dispatch_system_event(BEGIN_PLAY)
  → Flow1.scheduler.enqueue_trigger()

Step 2: Flow1 executes (in Thread1)
  → BeginPlay.worker()
  → EmitCallback.worker()
      ↓
      context['emit_callback']('my_callback', payload)
      ↓
      VM.emit_callback()
      ↓
      CallbackManager.emit_callback()  ←── BRIDGE POINT!
      ↓
      callbacks['my_callback']  →  [Flow2]
      ↓
      Flow2.scheduler.enqueue_trigger()  ←── Cross-flow trigger!

Step 3: Flow2 executes (in Thread2)
  → CustomCallback.worker()
      ↓ gets payload from trigger
      ↓
  → PrintMessage.worker()
      ↓ gets payload from data connection
      ↓
      prints message

═══════════════════════════════════════════════════════════
```

### The Shared Context

You asked about "shared context" - here's the hierarchy:

```
Interpreter
├── callback_manager  ←── SHARED across all flows
├── vm
│   └── callback_manager  ←── Reference to same instance
└── flows
    ├── Flow1
    │   └── scheduler (Thread1)
    └── Flow2
        └── scheduler (Thread2)
```

**The bridge**: `CallbackManager` is the shared component that connects flows!

### Key Points

1. **No Graph Edges**: Flows are truly disconnected in the graph
2. **Assembly Registration**: Flows register interest during assembly
3. **Runtime Bridge**: CallbackManager connects them at runtime
4. **Thread Safety**: Each flow runs in its own thread
5. **Async Communication**: Callback emission is non-blocking

### Why This Design?

This design is powerful because:

1. **Decoupling**: Emitter doesn't know about listeners
2. **Dynamic**: Multiple listeners can register for same callback
3. **Parallel**: Flows execute independently
4. **Clean**: No special graph connections needed

### Code Trace Summary

```python
# Assembly
CustomCallbackNode.event_subscription = CallbackEvent('my_callback')
  → Interpreter registers Flow2 for 'callback:my_callback'
  → CallbackManager.callbacks['my_callback'] = [Flow2]

# Runtime
EmitCallback.worker():
  context['emit_callback']('my_callback', payload)
    → ExecutionContext.emit_callback()
      → VM.emit_callback()
        → CallbackManager.emit_callback()  ←── BRIDGE!
          → lookup callbacks['my_callback'] → [Flow2]
          → Flow2.scheduler.enqueue_trigger()
            → Flow2 wakes up and executes
```

Does this clarify how callbacks work as the bridge between disconnected flows? The key is that **CallbackManager** is the shared state that connects them at runtime, even though there are no graph edges between them!

## Code Definitions:

### EmitCallbackNode

```python:
class EmitCallbackNode(BaseNode):
    """
    Emits a callback to trigger event nodes in other flows.
    
    Inputs:
        execute: Control flow in
        callback_name: Name of callback to emit
        payload: Data to send with callback
    
    Outputs:
        exec: Control flow out
    """
    
    def initialize(self):
        from ..types.specs import EXEC, STRING, FLOAT, CALLBACK
        
        # Control input
        self.add(EXEC.as_inlet('execute', label='Execute'))

        self.add(CALLBACK.as_inlet(
            'callback',
            label='Trigger',
        ))
    
        # Data inputs
        self.add(STRING.as_inlet(
            'callback_name',
            default='my_callback',
            label='Callback Name'
        ))

        self.add(FLOAT.as_inlet(
            'payload',
            use_mode='optional',
            label='Payload'
        ))
        
        # Control output
        self.add(EXEC.as_outlet('exec', label='Then'))
    
    def worker(self, context: ExecutionContext, callback_name: str, payload: float) -> dict | None:
        # Emit callback (VM provides this in context)
        context.emit_callback( 
            event_name=callback_name,
            payload=payload
        )
        
        return 'exec'
```

### CustomCallbackNode

```python:
class CustomCallbackNode(EventNode):
    """
    Listens for custom callbacks from other flows.
    
    Config:
        callback_name: Name of the callback to listen for
    
    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """
    
    EVENT_SOURCE = None  # Dynamic, set in initialize()

    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        super().__init__(node_id, wrapper)

        self.behavior.is_event_node = True
    
    def initialize(self):
        super().initialize()
        
        # Config for callback name
        self.add(STRING.as_config(
            'callback_name',
            default='my_callback',
            label='Callback Name',
            on_change='_update_subscription'
        ))
        
        # Set initial subscription
        callback_name = self.value('callback_name')
        self.event_subscription = CallbackEvent(event_name=callback_name)
        
        # Declare callback interest
        self.add(CALLBACK.as_outlet(
            'listen_callback',
            label='Listen'
        ))
        
        # Control output
        self.add(EXEC.as_outlet('triggered', label='Triggered'))
        
        # Data output
        self.add(FLOAT.as_outlet('payload', label='Payload'))
    
    def _update_subscription(self, port, new_value):
        """Update event subscription when callback name changes"""
        self.event_subscription = CallbackEvent(event_name=new_value)
        
        # Update callback port event filter
        callback_port = self.ports['listen_callback']
        
        # Trigger flow reassembly via wrapper
        if self.wrapper:
            self.wrapper.redraw()
    
    def worker(self, context: ExecutionContext):
        # Extract payload from trigger
        payload = context.trigger.payload
        
        return ('triggered', (('payload', payload),))
```

## Example: Callbacks Between Two Flows

```python:
def example_callback_flow():
    """
    Example with callbacks:
    Flow 1: BeginPlay → EmitCallback
    Flow 2: CustomCallback → PrintMessage
    """
    from haybale_core.nodes.begin_play import BeginPlayNode
    from haybale_core.nodes.custom_callback import CustomCallbackNode
    from haybale_core.nodes.emit_callback import EmitCallbackNode
    from haybale_test_a.nodes.print_node import PrintMessageNode
    
    # Create graph
    graph = BaseGraph(
        graph_id='callback_example',
        name='Callback Example'
    )
    
    # Flow 1: Emitter flow
    begin_play = graph.create_node_wrapper(
        BeginPlayNode.class_identity.registry_key,
        position=(100, 100)
    )
    
    emit_callback = graph.create_node_wrapper(
        EmitCallbackNode.class_identity.registry_key,
        position=(300, 100)
    )
    
    graph.create_edge_wrapper(
        begin_play.node_id, 'exec',
        emit_callback.node_id, 'execute'
    )
    
    # Flow 2: Listener flow
    callback_listener = graph.create_node_wrapper(
        CustomCallbackNode.class_identity.registry_key,
        position=(100, 300)
    )
    
    print_msg = graph.create_node_wrapper(
        PrintMessageNode.class_identity.registry_key,
        position=(300, 300)
    )
    
    graph.create_edge_wrapper(
        callback_listener.node_id, 'triggered',
        print_msg.node_id, 'exec'
    )
    
    # Execute
    interpreter = Interpreter()
    
    print("\n=== Loading Graph ===")
    interpreter.load_graph(graph)
    
    # Show callback registrations
    stats = interpreter.get_statistics()
    print(f"\nCallback Statistics:")
    for cb_info in stats['callbacks']['callbacks']:
        print(f"  '{cb_info['event_name']}': {cb_info['listener_count']} listeners")
    
    print("\n=== Dispatching BEGIN_PLAY Event ===")
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    # Wait a bit for callback to trigger
    import time
    time.sleep(0.5)
    
    interpreter.wait_all()
    interpreter.shutdown()
```