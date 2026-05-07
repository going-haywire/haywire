## Assembly System Architecture

### 1. Flow Assembly Manager

```
FlowAssemblyManager
├── Responsibilities:
│   ├── Coordinate entire assembly pipeline
│   ├── Manage flow lifecycle from graph to executable
│   └── Cache and invalidate assembled flows
│
├── Core Components:
│   ├── GraphValidator - Pre-assembly validation
│   ├── FlowIdentifier - Separate disconnected flows
│   ├── ControlFlowBuilder - Build control execution paths
│   └── DataFlowBuilder - Build localized data flows
│
└── State:
    ├── assembled_flows: Dict[str, Flow]
    ├── assembly_cache: Dict[str, AssemblyMetadata]
    └── dirty_nodes: Set[str]
```

### 2. Flow Structure

```
Flow
├── Metadata:
│   ├── flow_id: str
│   ├── entry_event_node: NodeWrapper
│   ├── graph_ref: BaseGraph
│   └── assembly_timestamp: datetime
│
├── Control Flow:
│   ├── control_sequence: List[ControlStep]
│   ├── loopback_points: Dict[str, LoopbackMetadata]
│   └── branch_map: Dict[str, List[BranchTarget]]
│
├── Data Flow:
│   ├── localized_flows: Dict[str, LocalizedDataFlow]
│   └── lazy_eval_masks: Dict[str, LazyEvaluationMask]
│
└── Execution State:
    ├── scheduler: FlowScheduler
    └── is_locked: bool
```

### 3. Assembly Pipeline Steps

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

### 4. Just-In-Time Assembly

```
JITAssemblyManager (listens to ValidationManager)
├── On NODE_ADDED/REMOVED:
│   ├── Identify affected flows
│   └── Mark for reassembly
│
├── On EDGE_ADDED/REMOVED:
│   ├── If Control-edge: rebuild entire flow
│   └── If Data-edge: rebuild affected localized flows
│
├── On PORT_RECONFIGURED:
│   └── Rebuild localized flows for that node
│
└── Incremental Rebuild:
    ├── Reuse unaffected ControlSteps
    ├── Reuse unaffected LocalizedDataFlows
    └── Update only dirty portions
```

## Execution System Architecture

### 1. Haywire Virtual Machine

```
HaywireVM
├── Execution Context:
│   ├── global_context: Dict[str, Any]  # From external system
│   ├── local_context: Dict[str, Any]   # Graph variables
│   └── execution_trace: List[ExecutionEvent]
│
├── Control Flow State:
│   ├── done_stack: List[ControlStep]
│   ├── loopback_stack: List[LoopbackFrame]
│   ├── current_step: ControlStep
│   └── max_stack_depth: int = 10000
│
├── Execution Methods:
│   ├── execute_control_flow()
│   ├── execute_control_node()
│   ├── evaluate_data_flow()
│   └── evaluate_data_node()
│
└── State Management:
    ├── pause_execution()
    ├── resume_execution()
    └── abort_execution()
```

### 2. Flow Scheduler

```
FlowScheduler (per Flow)
├── Trigger Management:
│   ├── trigger_queue: Queue[Trigger]
│   ├── queue_mode: QueueMode  # BLOCK or DROP
│   └── is_executing: bool
│
├── Thread Management:
│   ├── execution_thread: Thread
│   └── lock: threading.Lock
│
└── Methods:
    ├── enqueue_trigger(trigger: Trigger)
    ├── execute_flow()
    └── wait_for_completion()
```

### 3. Control Flow Execution

```
VM.execute_control_flow(flow: Flow, trigger: Trigger):
    
    # Initialize stacks
    done_stack = []
    loopback_stack = []
    
    # Start from Event-node
    current = flow.entry_event_node
    
    while current is not None:
        
        # Stack overflow protection
        if len(done_stack) > max_stack_depth:
            raise StackOverflowError()
        
        # Execute current node
        next_pin = execute_control_node(current, flow)
        
        # Update stacks
        done_stack.append(current)
        if current.node.behavior.is_loopback:
            loopback_stack.append(LoopbackFrame(
                node=current,
                done_index=len(done_stack) - 1
            ))
        
        # Determine next step
        if next_pin is None:
            # No outlet specified
            if current.node.is_output_node:
                break  # End flow
            else:
                # Branch ended without Output-node
                current = handle_loopback()
        else:
            # Follow specified outlet
            current = current.next_steps.get(next_pin)
            if current is None:
                # Dead end
                current = handle_loopback()

def handle_loopback():
    if loopback_stack:
        frame = loopback_stack.pop()
        # Rollback done_stack to loopback point
        done_stack = done_stack[:frame.done_index + 1]
        return frame.node
    else:
        return None  # Flow complete
```

### 4. Control Node Execution

```
VM.execute_control_node(node_wrapper: NodeWrapper, flow: Flow):
    
    node = node_wrapper.node
    
    # 1. ON_VALIDATION_LAZY (optional)
    lazy_mask = None
    if has_lazy_inlets(node):
        lazy_mask = node.ON_VALIDATION_LAZY(context)
    
    # 2. Evaluate localized data flow
    localized_flow = flow.localized_flows[node_wrapper.node_id]
    evaluate_data_flow(localized_flow, lazy_mask)
    
    # 3. ON_CHANGED_ASYNC (optional)
    if hasattr(node, 'ON_CHANGED_ASYNC'):
        changes = node.ON_CHANGED_ASYNC(context)
        if changes:
            # Handle external changes
            update_inlets(node, changes)
    
    # 4. ON_VALIDATION_INPUT (optional)
    if hasattr(node, 'ON_VALIDATION_INPUT'):
        if not node.ON_VALIDATION_INPUT(context):
            raise ValidationError()
    
    # 5. Execute worker function
    result = node.worker(context={
        'global': global_context,
        'local': local_context,
        'control_pin': current_control_inlet,
        'node': node_wrapper
    })
    
    # 6. Parse result for next outlet
    next_outlet = parse_worker_result(result)
    
    return next_outlet
```

### 5. Data Flow Evaluation

```
VM.evaluate_data_flow(
    localized_flow: LocalizedDataFlow,
    lazy_mask: Optional[int]
):
    
    for data_node_wrapper in localized_flow.execution_sequence:
        
        node = data_node_wrapper.node
        
        # Check if lazy evaluation applies
        if lazy_mask and localized_flow.requires_lazy:
            eval_mask = localized_flow.eval_masks[node_wrapper.node_id]
            if (lazy_mask & eval_mask) == 0:
                continue  # Skip this node
        
        # Re-validate lazy conditions if changed
        if hasattr(node, 'ON_VALIDATION_LAZY'):
            current_lazy = node.ON_VALIDATION_LAZY(context)
            if current_lazy != node._last_lazy_state:
                # Reassemble required!
                reassemble_localized_flow(control_node)
                return  # Restart evaluation
        
        # Check if any inlets are dirty
        if not any_inlet_dirty(node):
            continue  # Skip evaluation
        
        # ON_CHANGED_ASYNC (optional)
        if hasattr(node, 'ON_CHANGED_ASYNC'):
            node.ON_CHANGED_ASYNC(context)
        
        # ON_VALIDATION_INPUT (optional)
        if hasattr(node, 'ON_VALIDATION_INPUT'):
            if not node.ON_VALIDATION_INPUT(context):
                raise ValidationError()
        
        # Execute worker
        result = node.worker(context={
            'global': global_context,
            'local': local_context
        })
        
        # Mark inlets as clean
        mark_inlets_clean(node)
```

### 6. Lazy Evaluation System

```
LazyEvaluationMask
├── Structure: 32-bit or 64-bit integer
├── One bit per Data-inlet on Control-node
└── 1 = evaluate, 0 = skip

Assembly-time:
    For each Data-inlet on Control-node:
        Create EVAL_MASK with single bit set
        
    During backpropagation:
        At each Data-node merge point:
            EVAL_MASK = OR(all incoming EVAL_MASKs)
        
    Store in LocalizedDataFlow:
        node_eval_masks[node_id] = EVAL_MASK

Runtime:
    LAZY_MASK = node.ON_VALIDATION_LAZY()  # Returns mask
    
    For each Data-node:
        if (LAZY_MASK & EVAL_MASK) > 0:
            evaluate_node()
        else:
            skip_node()
```

### 7. Callback System

```
CallbackManager (part of Interpreter)
├── Callback Registration (during Assembly):
│   ├── Scan for Callback-pin-outlets on Event-nodes
│   ├── Follow Callback-edges to find listeners
│   └── Register: callbacks[event_type] = [Flow, ...]
│
└── Callback Dispatch (during Execution):
    ├── Control-node emits callback
    ├── Lookup registered listeners
    ├── Create Trigger for each listening Flow
    └── Enqueue in respective FlowSchedulers

Implementation:
    # During Assembly
    for event_node in graph.get_event_nodes():
        for callback_outlet in event_node.callback_outlets:
            for callback_edge in callback_outlet.edges:
                listener_event = callback_edge.target_node
                callback_manager.register(
                    event_type=callback_outlet.event_type,
                    listener_flow=flows[listener_event.flow_id]
                )
    
    # During Execution (in worker function)
    def control_node.worker(context):
        # ... do work ...
        
        # Emit callback
        context.emit_callback(
            event_type='data_ready',
            payload={'data': result}
        )
        
        return {'next_outlet': 'success'}
    
    # In VM
    def emit_callback(event_type, payload):
        flows = callback_manager.get_listeners(event_type)
        for flow in flows:
            trigger = Trigger(
                type=event_type,
                payload=payload
            )
            flow.scheduler.enqueue_trigger(trigger)
```

## Integration Points

### 1. Graph → Assembly

```
GraphValidationManager subscribes to:
    - NODE_ADDED → mark flows dirty
    - EDGE_ADDED → mark flows dirty
    - PORT_RECONFIGURED → mark localized flows dirty

On validation complete:
    JITAssemblyManager.reassemble_dirty_flows()
```

### 2. Assembly → Execution

```
FlowAssemblyManager.on_flow_assembled(flow):
    Interpreter.register_flow(flow)
    
Interpreter.on_external_event(event):
    matching_flows = find_flows_with_event_node(event.type)
    for flow in matching_flows:
        flow.scheduler.enqueue_trigger(event)
```

### 3. Execution → Graph State

```
During execution:
    - Read from: Graph.variables
    - Read from: NodeWrapper.node.ports
    - Write to: NodeWrapper.node.ports (outlets)
    - Write to: Graph.variables (if allowed)

After execution:
    - Reset dirty flags
    - Maintain state in variables
```

## Key Design Decisions

1. **Separation of Concerns**: Assembly builds static structure, VM executes it
2. **Incremental JIT**: Only reassemble affected portions
3. **Lazy Evaluation**: Bitfield masks for O(1) skip decisions
4. **Thread Safety**: Each Flow gets own thread via Scheduler
5. **Stack-based Control**: Done/Loopback stacks mirror execution
6. **Localized Data**: Each Control-node owns its data flow
7. **Callback Decoupling**: Flows communicate via event bus, not direct calls

This architecture provides clean separation between graph structure (BaseGraph), compiled flows (Flow), and execution runtime (HaywireVM), enabling hot reload, JIT compilation, and parallel execution while maintaining the dual-flow model specified in your document.