# Callback Edge Processing - Implementation Summary

## Overview

Successfully implemented **callback edge observability** for the Haywire assembly and execution system. This enhancement provides visibility into inter-flow callback connections for debugging, monitoring, and understanding graph communication topology.

## What Was Implemented

### 1. FlowAssemblyManager Enhancements

**File**: `/haywire/core/assembly/flow_assembly_manager.py`

**New Method: `_process_callback_edges()`**
- Discovers all callback edges in the graph after flow assembly
- Builds bidirectional connection maps:
  - **Forward map** (emitter → listeners): Shows which nodes emit to which listeners
  - **Reverse map** (listener → emitters): Shows which listeners receive from which emitters
- Logs inter-flow dependencies for debugging
- Stores topology data for statistics

**New Methods for External Access**:
- `get_callback_connections()` - Returns forward connection map
- `get_callback_triggers()` - Returns reverse connection map

**Enhanced `get_statistics()`**:
- Added `callback_edges` count
- Added `callback_topology` with:
  - Total emitters count
  - Total listeners count
  - Complete connection maps (both directions)
- Added per-flow flags:
  - `emits_callbacks` - Whether flow emits callbacks
  - `receives_callbacks` - Whether flow receives callbacks

### 2. Interpreter Enhancements

**File**: `/haywire/core/execution/interpreter.py`

**Enhanced `get_statistics()`**:
- Exposes `callback_topology` from assembly manager
- Provides complete view of inter-flow callback connections
- Integrated with existing callback manager statistics

### 3. Updated Examples

**File**: `/haywire/examples/execution_examples.py`

**Example 3: String-Based Callbacks (Dynamic)**
- Demonstrates manual configuration with matching callback names
- No visual edge connection needed
- Both nodes configured with `callback_name='my_callback'`
- Shows traditional string-matching approach
- Displays callback statistics

**Example 4: Edge-Based Callbacks (Visual)**
- Demonstrates visual callback edge connection
- Event name propagates automatically through pipe
- Creates callback edge: `CustomCallback.listen_callback → EmitCallback.edge_callback`
- Shows detailed topology statistics and connection maps
- Displays both connection directions

## How It Works

### The Edge-Based Callback Mechanism

Your implementation already had all the pieces in place! Here's how it works:

```
1. CustomCallbackNode (Listener)
   ├─ listen_callback outlet (default=self.node_id)
   └─ event_subscription = CallbackEvent(event_name=self.node_id)

2. Callback Edge Created
   CustomCallback.listen_callback → EmitCallback.edge_callback

3. Pipe Propagation (Automatic!)
   listen_callback.value (node_id) ──→ edge_callback.value
   
4. EmitCallback.worker()
   edge_callback_value = self.value('edge_callback')  # Gets node_id
   context.emit_callback(edge_callback_value, payload)

5. CallbackManager Routes
   subscription_key = f"callback:{node_id}"
   → Matches CustomCallback's event_subscription!
```

### What _process_callback_edges() Does

```python
# Assembly Process
FlowAssemblyManager.assemble_graph():
    1. Build flows (control + data)
    2. _process_callback_edges():  # NEW!
       - Find all callback edges
       - Build connection maps
       - Log topology
       - Store for statistics

# Result: Observability without changing runtime behavior!
```

## Verification of Node Implementation

Your `CustomCallbackNode` and `EmitCallbackNode` correctly support **both modes**:

### Mode Switch: False (Edge-Based, Default)
```python
CustomCallbackNode:
  - listen_callback outlet → sends node_id via pipe
  
EmitCallbackNode:
  - edge_callback inlet → receives node_id from pipe
  - Uses edge_callback value for emission
```

### Mode Switch: True (String-Based)
```python
CustomCallbackNode:
  - custom_callback_name config → manual string
  
EmitCallbackNode:
  - custom_callback_name config → manual string
  - Uses custom name for emission
```

✅ **Verified**: Your implementation is correct and supports both approaches seamlessly!

## Statistics Output

### Assembly Statistics
```python
stats = interpreter.get_statistics()

{
    'assembly': {
        'total_flows': 2,
        'callback_edges': 1,
        'callback_topology': {
            'emitters': 1,  # Number of nodes emitting callbacks
            'listeners': 1,  # Number of nodes listening for callbacks
            'connections': {
                'custom_callback_abc123': ['emit_callback_xyz789']
            },
            'triggers': {
                'emit_callback_xyz789': ['custom_callback_abc123']
            }
        },
        'flows': [
            {
                'flow_id': 'flow_begin_play',
                'event_type': 'system:begin_play',
                'node_count': 2,
                'emits_callbacks': False,
                'receives_callbacks': False
            },
            {
                'flow_id': 'flow_custom_callback',
                'event_type': 'callback:custom_callback_abc123',
                'node_count': 1,
                'emits_callbacks': True,   # ← NEW!
                'receives_callbacks': False
            }
        ]
    }
}
```

### Callback Manager Statistics
```python
{
    'callbacks': {
        'total_callbacks': 1,
        'callbacks': [
            {
                'event_name': 'custom_callback_abc123',
                'listener_count': 1,
                'emit_count': 1
            }
        ]
    }
}
```

## Key Insights

### ✅ Everything Was Already Working!

Your pipe propagation mechanism already solved the visual connection problem:

1. **Validation**: StructuralValidator ensures callback edges connect event nodes
2. **Runtime Propagation**: Pipe mechanism automatically propagates event names
3. **Flow Separation**: One flow per event node (callback edges don't affect this)
4. **Callback Routing**: CallbackManager routes based on event names

### What Was Actually Missing

**Only observability!** The system needed:
- Visibility into callback topology
- Debugging support for callback routing
- Statistics for monitoring inter-flow communication
- Documentation of flow dependencies

## Benefits

### 1. Visual Feedback
Developers can see callback connections in statistics:
```
Connections (listener → emitter):
  custom_callback_node → emit_callback_node
```

### 2. Debugging Support
Assembly logs show:
```
INFO: Found 1 callback edges connecting flows
DEBUG:   Callback edge: custom_callback.listen_callback → emit_callback.edge_callback
DEBUG:     Event propagation: 'custom_callback_abc123' → emit_callback
INFO: Callback topology: 1 emitters, 1 listeners
```

### 3. Monitoring
Statistics track:
- Number of callback edges
- Which flows emit/receive callbacks
- Callback emission counts
- Complete topology

### 4. Graph Understanding
Connection maps show flow dependencies clearly, helping with:
- Architecture visualization
- Performance analysis
- Debugging callback issues

## Example Usage

### String-Based (Example 3)
```python
# Configure both nodes with matching names
emit_callback.node.ports['mode_switch'].set_value(True)
emit_callback.node.ports['custom_callback_name'].set_value('my_callback')

callback_listener.node.ports['mode_switch'].set_value(True)
callback_listener.node.ports['custom_callback_name'].set_value('my_callback')

# No edge needed - connection via string matching
```

### Edge-Based (Example 4)
```python
# Leave mode_switch=False (default)

# Create callback edge
callback_edge = graph.create_edge_wrapper(
    callback_listener.node_id, 'listen_callback',  # Source
    emit_callback.node_id, 'edge_callback'         # Target
)

# Event name propagates automatically!
print(f"Event: {callback_listener.node_id}")
# Shows in topology statistics
```

## About event_filter

The `event_filter` attribute in your callback ports is currently **not used** by the implementation. It can be:

**Option A**: Removed (not needed for current functionality)
**Option B**: Kept as placeholder for future filtering features
**Option C**: Used for documentation purposes

### Potential Future Use
Could enable wildcard matching:
```python
# Listener accepts any event starting with 'data_'
CALLBACK.as_outlet('listen', event_filter='data_*')

# Would match: 'data_ready', 'data_update', 'data_complete'
```

## No Functional Changes

**Important**: This implementation is **purely observability**. The callback mechanism was already working correctly through your pipe propagation system. These changes just make it:
- Visible
- Debuggable  
- Monitorable
- Documentable

## System Status

The callback edge system is now **complete and production-ready**:

✅ **Validation** (StructuralValidator)
✅ **Runtime Propagation** (Pipe mechanism)
✅ **Flow Separation** (Event node-based)
✅ **Observability** (NEW - this implementation)
✅ **Dual Mode Support** (String-based + Edge-based)

Both callback approaches work correctly with your node implementations!

## Next Steps (Optional)

### Enhanced Filtering
Implement wildcard event filtering:
```python
if event_filter and not matches_filter(event_name, event_filter):
    continue  # Skip this callback
```

### Topology Visualization
Use connection maps to generate visual graph:
```python
def visualize_callback_topology(stats):
    topology = stats['callback_topology']
    # Generate graph visualization
```

### Performance Monitoring
Track callback execution times and frequencies:
```python
callback_stats['event_name']['execution_times'] = [0.002, 0.003, ...]
callback_stats['event_name']['avg_time'] = 0.0025
```

### Real-time Updates
Subscribe to callback topology changes:
```python
interpreter.on_topology_changed(callback=my_handler)
```

## Conclusion

Your callback system design was already excellent - the pipe propagation mechanism elegantly solves the visual connection problem without any special handling. This implementation simply adds the observability layer that makes the system debuggable and monitorable in production.

The dual-mode support (string-based for dynamic scenarios, edge-based for visual clarity) provides maximum flexibility while maintaining a clean, simple implementation.

Great work on the design! 🎉
