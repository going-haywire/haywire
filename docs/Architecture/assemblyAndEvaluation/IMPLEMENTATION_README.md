# Haywire Assembly and Execution System

This document provides a complete overview of the Haywire assembly and execution system implementation.

## Architecture Overview

The system consists of two main subsystems:

1. **Assembly System** - Converts graphs into executable flows
2. **Execution System** - Runs flows in response to events

```
Graph (BaseGraph)
  ↓
Assembly (FlowAssemblyManager)
  ↓
Flows (Control + Data flows)
  ↓
Execution (Interpreter + VM)
  ↓
Results
```

## Core Concepts

### Event Sources

Event sources define what triggers a flow:

- **SystemEvent**: Lifecycle events (BEGIN_PLAY, TICK, SHUTDOWN)
- **ExternalEvent**: External system events (input, network, etc.)
- **CallbackEvent**: Inter-flow communication

```python
from haywire.core.execution.event_source import SystemEvent, SystemEventType

# Event node declares what it listens for
class BeginPlayNode(EventNode):
    EVENT_SOURCE = SystemEvent(SystemEventType.BEGIN_PLAY)
```

### Control Flow vs Data Flow

**Control Flow**: Determines execution order
- Follows Control-pin connections
- Navigation graph (not a sequence!)
- Runtime decisions determine path

**Data Flow**: Passes values between nodes
- Localized per control node
- Backpropagated from inlets
- Topologically sorted

### Flow Structure

A **Flow** contains:
- Entry event node
- Control flow graph (navigation structure)
- Localized data flows (one per control node)
- Scheduler (for execution management)

```python
Flow
├── entry_event_node: NodeWrapper
├── event_subscription: EventSource
├── control_graph: ControlFlowGraph
│   └── control_nodes: Dict[str, ControlNodeInfo]
│       ├── outlet_map: Dict[str, str]  # outlet_id → next_node_id
│       └── localized_data_flow: LocalizedDataFlow
└── scheduler: FlowScheduler
```

## Assembly Process

### 1. Flow Identification

```python
# FlowAssemblyManager.assemble_graph()
flows = []
for event_node in graph.find_event_nodes():
    flow = Flow(
        entry_event_node=event_node,
        event_subscription=event_node.event_subscription
    )
    flows.append(flow)
```

### 2. Control Flow Building

```python
# ControlFlowBuilder.build()
control_graph = ControlFlowGraph(entry_node=event_node)

# BFS traversal from event node
queue = [event_node]
while queue:
    current = queue.pop(0)
    
    # Map outlets to next nodes
    info = ControlNodeInfo(node_wrapper=current)
    for outlet in current.control_outlets:
        next_node = get_connected_node(outlet)
        info.outlet_map[outlet.id] = next_node.node_id
        queue.append(next_node)
    
    control_graph.control_nodes[current.node_id] = info
```

**Key Insight**: The control flow is a **navigation graph**, not an execution sequence. The VM consults it at runtime to decide where to go next.

### 3. Data Flow Building

```python
# DataFlowBuilder.build_localized()
data_flow = LocalizedDataFlow(control_node_id=control_node.node_id)

# Backpropagate from each data inlet
for inlet in control_node.data_inlets:
    dependencies = backpropagate_from(inlet)
    required_nodes.update(dependencies)

# Topological sort for execution order
data_flow.execution_sequence = topological_sort(required_nodes)
```

**Key Features**:
- Backpropagation stops at control nodes
- Cycles checked (illegal in data flow)
- Lazy evaluation masks computed

## Execution Process

### 1. Interpreter Setup

```python
# Create interpreter
interpreter = Interpreter(global_context={'user_id': 123})

# Load graph (triggers assembly)
interpreter.load_graph(my_graph)

# Flows are now ready to execute
```

### 2. Event Dispatch

```python
# System events
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
interpreter.dispatch_system_event(SystemEventType.TICK)

# External events
interpreter.dispatch_external_event(
    category='input',
    name='key_pressed',
    payload={'key': 'Space'}
)
```

### 3. Flow Execution

```python
# VM.execute_control_flow()
done_stack = []
loopback_stack = []
current_node_id = flow.entry_node_id

while current_node_id:
    # Get node info from control graph
    info = flow.control_graph.get_node_info(current_node_id)
    
    # Evaluate localized data flow
    evaluate_data_flow(info.localized_data_flow)
    
    # Execute control node worker
    next_outlet_id = node.worker(context)
    
    # Navigate to next node (runtime decision!)
    if next_outlet_id:
        current_node_id = info.outlet_map[next_outlet_id]
    else:
        # Handle loopback or end flow
        current_node_id = handle_loopback(loopback_stack, done_stack)
```

### 4. Stack Management

**Done Stack**: Tracks executed nodes (for loop detection)

**Loopback Stack**: Tracks nodes that expect branches to return

```python
# When executing loopback node (ForLoop, WhileLoop, Sequence)
if info.is_loopback:
    loopback_stack.append(LoopbackFrame(
        node_id=current_node_id,
        done_index=len(done_stack)
    ))

# When branch ends without Output node
if not next_outlet_id and not is_output_node:
    # Pop loopback frame
    frame = loopback_stack.pop()
    
    # Roll back done stack
    done_stack = done_stack[:frame.done_index + 1]
    
    # Return to loopback node
    current_node_id = frame.node_id
```

## Callback System

Callbacks enable inter-flow communication:

```python
# Flow 1: Emitter
class ProcessDataNode(BaseNode):
    def worker(self, context):
        result = process_data()
        
        # Emit callback
        context['emit_callback']('data_ready', {'result': result})
        
        return {'next_outlet': 'success'}

# Flow 2: Listener
class DataReadyEventNode(EventNode):
    EVENT_SOURCE = CallbackEvent(event_name='data_ready')
    
    def worker(self, context):
        payload = context['trigger'].payload
        print(f"Received: {payload['result']}")
        return {'next_outlet': 'triggered'}
```

**Callback Flow**:
1. Control node calls `emit_callback()`
2. VM forwards to CallbackManager
3. CallbackManager looks up listening flows
4. Creates Trigger for each listener
5. Enqueues triggers in flow schedulers
6. Flows execute in their own threads

## Threading Model

Each **Flow** has its own **Scheduler** with dedicated thread:

```python
FlowScheduler
├── trigger_queue: Queue[Trigger]
├── execution_thread: Thread
└── is_executing: bool (lock for mutual exclusion)
```

**Benefits**:
- Flows execute independently
- No blocking between flows
- Callbacks trigger async

**Thread Safety**:
- Each flow locked during execution
- Queue handles concurrent triggers
- Graph state read-only during execution

## Lazy Evaluation

(Partially implemented - full implementation pending)

**Concept**: Skip data node evaluation when inlets not needed

```python
# Assembly time
for inlet in control_node.data_inlets:
    inlet_mask = 1 << i  # Bit for this inlet
    
    # Backpropagate with mask
    for data_node in dependencies:
        eval_masks[data_node] |= inlet_mask

# Runtime
lazy_mask = control_node.ON_VALIDATION_LAZY()  # Which inlets needed?

for data_node in data_flow:
    if (lazy_mask & eval_masks[data_node]) == 0:
        continue  # Skip evaluation
    
    evaluate_node(data_node)
```

## File Structure

```
haywire/core/
├── execution/
│   ├── __init__.py
│   ├── interpreter.py          # Main coordinator
│   ├── vm.py                   # Virtual machine
│   ├── flow.py                 # Flow data structures
│   ├── scheduler.py            # Per-flow scheduler
│   ├── event_source.py         # Event source types
│   └── callback_manager.py     # Inter-flow callbacks
│
├── assembly/
│   ├── __init__.py
│   ├── flow_assembly_manager.py    # Assembly coordinator
│   ├── control_flow_builder.py     # Control flow assembly
│   └── data_flow_builder.py        # Data flow assembly
│
└── nodes/
    └── events/
        ├── event_node.py           # EventNode base class
        ├── begin_play.py           # BeginPlayNode
        ├── tick.py                 # TickNode
        └── custom_callback.py      # CustomCallbackNode
```

## Usage Examples

### Example 1: Simple Flow

```python
from haywire.core.execution import Interpreter
from haywire.core.execution.event_source import SystemEventType

# Create graph
graph = BaseGraph('my_graph', 'My Graph')

# Add BeginPlay → PrintMessage
begin_play = graph.create_node_wrapper('begin_play', (100, 100))
print_msg = graph.create_node_wrapper('print_message', (300, 100))
graph.create_edge_wrapper(
    begin_play.node_id, 'exec',
    print_msg.node_id, 'exec'
)

# Execute
interpreter = Interpreter()
interpreter.load_graph(graph)
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
interpreter.wait_all()
interpreter.shutdown()
```

### Example 2: Data Flow

```python
# BeginPlay → PrintNumber
# AddNumbers → PrintNumber.value

# ... create nodes ...

# Control flow
graph.create_edge_wrapper(begin_play.node_id, 'exec', print_num.node_id, 'exec')

# Data flow
graph.create_edge_wrapper(add.node_id, 'result', print_num.node_id, 'value')

# Execute - data flow evaluated automatically before PrintNumber
interpreter.load_graph(graph)
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
```

### Example 3: Callbacks

```python
# Flow 1: BeginPlay → EmitCallback
# Flow 2: CustomCallback → PrintMessage

# ... create flows ...

# Execute
interpreter.load_graph(graph)

# Trigger Flow 1 (which emits callback)
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)

# Flow 2 executes automatically when callback received
interpreter.wait_all()
```

## Key Design Decisions

1. **Navigation Graph vs Execution Sequence**
   - Control flow is a **map**, not a path
   - VM makes runtime decisions
   - Enables branching, loops, dynamic control

2. **Localized Data Flows**
   - Each control node owns its data flow
   - Evaluated on-demand before execution
   - Isolated from other control nodes

3. **Event-Driven Model**
   - Multiple independent flows per graph
   - Flows triggered by events
   - Callbacks enable communication

4. **Thread-Per-Flow**
   - Each flow has dedicated scheduler
   - Independent execution
   - Queue-based trigger management

5. **Immutable Flow Structure**
   - Flows assembled once
   - Runtime only navigates
   - Changes require reassembly (JIT)

## Future Enhancements

### Just-In-Time Assembly
- Incremental reassembly on graph changes
- Reuse unaffected flow portions
- Connected to validation pipeline

### Lazy Evaluation
- Full implementation of ON_VALIDATION_LAZY
- Runtime mask computation
- Dynamic data flow pruning

### Parallel Flow Execution
- Multiple flows execute concurrently
- Shared graph state management
- Thread-safe variable access

### Debugging & Profiling
- Execution tracing
- Breakpoint support
- Performance metrics
- Step-through debugging

## Testing

The system can be tested with:

```bash
# Run examples
python haywire/examples/execution_examples.py

# Run unit tests (when available)
pytest tests/execution/
pytest tests/assembly/
```

## Conclusion

This implementation provides a complete, working assembly and execution system for Haywire that:

✅ Separates control flow and data flow
✅ Supports runtime control flow decisions
✅ Handles event-driven execution
✅ Enables inter-flow callbacks
✅ Uses thread-per-flow model
✅ Provides clean API for external systems

The architecture is extensible and ready for the planned enhancements like JIT assembly, full lazy evaluation, and advanced debugging features.
