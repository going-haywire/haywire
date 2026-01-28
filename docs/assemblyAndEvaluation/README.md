# Haywire Assembly and Execution System

This document provides a overview of the Haywire assembly and execution system implementation.

## Architecture Overview

The system consists of two main subsystems:

1. **Graph Creation** - Users create graphs using nodes and edges.
2. **Assembly System** - Converts graphs into executable flows
3. **Execution System** - Runs flows in response to events

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

## Usage Example

### Simple Flow

```python
from haywire.core.graph import BaseGraph
from haywire.core.execution import Interpreter
from haywire.core.execution.event_source import SystemEventType

# Create graph
graph = BaseGraph('my_graph', 'My Graph')

# Graph creation (nodes and edges)
graph.load_from_file('path/to/graph_file.haywire')

# Create interpreter
interpreter = Interpreter()

# Assembly Process
interpreter.load_graph(graph)

# Execution Process
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)

# Wait for all flows to complete
interpreter.wait_all()

# Shutdown interpreter
interpreter.shutdown()
```


### Event Sources

Event sources define what triggers a flow:

- **SystemEvent**: Lifecycle events (BEGIN_PLAY, TICK, SHUTDOWN)
- **ExternalEvent**: External system events (input, network, etc.)
- **CallbackEvent**: Inter-flow communication

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


## How It Works

### Assembly Process

```
1. Identify event nodes
   ↓
2. For each event node:
   - Build control flow graph (navigation)
   - For each control node:
     - Build localized data flow (backpropagation)
   ↓
3. Create Flow with scheduler
   ↓
4. Register with Interpreter
```

#### Detailed Assembly Pipeline Steps

```
Assembly Pipeline:

1. GraphValidator.validate()
   ├── Check node type constraints
   ├── Validate Event/Output node placement
   ├── Check for required Source/Sink in Graph-nodes
   └── Return validation_errors: List[str]

2. FlowIdentifier.identify_flows()
   ├── Find all Event-nodes
   ├── Traverse from each Event-node
   ├── Group connected node-trees
   ├── Handle callback-connections specially
   └── Return flows: List[FlowDescriptor]

3. For each FlowDescriptor:
   
   a. ControlFlowBuilder.build()
      ├── Start from Event-node
      ├── Follow Control-pin-outlets
      ├── Build ControlStep chain:
      │   ├── node_wrapper: NodeWrapper
      │   ├── next_steps: Dict[str, ControlStep]
      │   └── is_loopback: bool
      ├── Identify branch points
      └── Detect cycles (allowed for control)
   
   b. For each Control-node in sequence:
      
      DataFlowBuilder.build_localized(control_node)
      ├── Backpropagate from Data-inlets
      ├── Build dependency DAG
      ├── Check for cycles (error unless through Control-node)
      ├── Topological sort for execution order
      ├── Handle lazy evaluation flags:
      │   ├── Call node.ON_VALIDATION_LAZY()
      │   ├── Generate EVAL_MASK per inlet
      │   └── Optimize prunable branches
      └── Return LocalizedDataFlow:
          ├── execution_sequence: List[NodeWrapper]
          ├── eval_masks: Dict[str, int]  # bitfield
          └── requires_lazy: bool

4. Flow.assemble()
   ├── Package ControlFlow + LocalizedDataFlows
   ├── Register with scheduler
   └── Return assembled Flow
```


### Execution Process

```
1. External event occurs
   ↓
2. Interpreter dispatches to flows
   ↓
3. Interpreter creates triggers for flows
   ↓
4. Interpreter identifes flows that are triggered
   ↓
5. Flow scheduler enqueues trigger
   ↓
6. Flow scheduler enshures thread is running
   ↓
7. Scheduler's execution loop picks up trigger from queue
   ↓
8. Scheduler's virtual machine (VM) gets the trigger and the flow context
   ↓
9. VM assembles execution context
   ↓
10. VM executes flow:
   - Start from event node
   - For each control node:
     a. Evaluate localized data flow
     b. Execute worker function
     c. Navigate to next node (runtime decision)
   - Handle loopbacks and branches
   ↓
11. Flow completes or loops back
```

### Callback Flow

```
1. Control node emits callback
   ↓
2. VM forwards to CallbackManager
   ↓
3. CallbackManager finds listening flows
   ↓
4. Creates trigger for each listener
   ↓
5. Enqueues in flow schedulers
   ↓
6. Flows execute independently
```
