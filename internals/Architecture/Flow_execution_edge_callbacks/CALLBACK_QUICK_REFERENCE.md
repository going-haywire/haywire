# Callback Edge System - Quick Reference

## Files Modified

1. **flow_assembly_manager.py** - Added callback edge processing and observability
2. **interpreter.py** - Enhanced statistics with callback topology
3. **execution_examples.py** - Added two callback examples (string-based + edge-based)

## New Features

### 1. Callback Edge Discovery
Assembly manager now processes callback edges and builds connection maps.

### 2. Enhanced Statistics
```python
stats = interpreter.get_statistics()

stats['assembly']['callback_edges']  # Count of callback edges
stats['assembly']['callback_topology']  # Complete topology
stats['callback_topology']  # Quick access from interpreter
```

### 3. Two Callback Modes

**Edge-Based (Visual)**:
- Default mode (mode_switch=False)
- Create callback edge in graph
- Event name propagates automatically
- Clean visual representation

**String-Based (Dynamic)**:
- Opt-in mode (mode_switch=True)
- Configure matching callback names
- No edge needed
- Good for dynamic/configurable scenarios

## Usage Examples

### Edge-Based Callback

```python
# Create nodes
listener = graph.create_node_wrapper('custom_callback')
emitter = graph.create_node_wrapper('emit_callback')

# Leave mode_switch=False (default)

# Create callback edge
graph.create_edge_wrapper(
    listener.node_id, 'listen_callback',  # Source: listener outlet
    emitter.node_id, 'edge_callback'      # Target: emitter inlet
)

# Event name propagates automatically!
# No configuration needed!
```

### String-Based Callback

```python
# Create nodes
listener = graph.create_node_wrapper('custom_callback')
emitter = graph.create_node_wrapper('emit_callback')

# Enable string-based mode
listener.node.ports['mode_switch'].set_value(True)
emitter.node.ports['mode_switch'].set_value(True)

# Set matching names
listener.node.ports['custom_callback_name'].set_value('data_ready')
emitter.node.ports['custom_callback_name'].set_value('data_ready')

# No edge needed!
```

## Accessing Statistics

### Callback Topology

```python
stats = interpreter.get_statistics()

# Number of callback edges
edge_count = stats['assembly']['callback_edges']

# Topology details
topology = stats['callback_topology']

# Who emits to whom
connections = topology['connections']  # {source_id: [target_ids]}

# Who receives from whom
triggers = topology['triggers']  # {target_id: [source_ids]}

# Per-flow info
for flow_info in stats['assembly']['flows']:
    print(f"Flow {flow_info['flow_id']}:")
    print(f"  Emits callbacks: {flow_info['emits_callbacks']}")
    print(f"  Receives callbacks: {flow_info['receives_callbacks']}")
```

### Callback Manager

```python
callback_stats = stats['callbacks']

# All registered callbacks
for cb in callback_stats['callbacks']:
    print(f"Event: {cb['event_name']}")
    print(f"  Listeners: {cb['listener_count']}")
    print(f"  Emissions: {cb['emit_count']}")
```

## Debugging

### Assembly Logs

```
INFO: Found 1 callback edges connecting flows
DEBUG:   Callback edge: custom_callback.listen_callback → emit_callback.edge_callback
DEBUG:     Event propagation: 'custom_callback_abc123' → emit_callback
INFO: Callback topology: 1 emitters, 1 listeners
```

### Runtime Logs

```
DEBUG: Dispatching event 'callback:custom_callback_abc123' to 1 flows
DEBUG: Emitting callback 'custom_callback_abc123' to 1 flows
```

## Node Configuration Reference

### CustomCallbackNode Ports

| Port | Type | Purpose |
|------|------|---------|
| `mode_switch` | Config (bool) | False=edge-based, True=string-based |
| `custom_callback_name` | Config (string) | Name for string-based mode |
| `listen_callback` | Outlet (callback) | For edge-based connections |
| `triggered` | Outlet (exec) | Control flow when triggered |
| `payload` | Outlet (float) | Data from callback |

### EmitCallbackNode Ports

| Port | Type | Purpose |
|------|------|---------|
| `execute` | Inlet (exec) | Control flow in |
| `mode_switch` | Config (bool) | False=edge-based, True=string-based |
| `custom_callback_name` | Config (string) | Name for string-based mode |
| `payload` | Inlet (float) | Data to send |
| `edge_callback` | Inlet (callback) | Receives event name from pipe |
| `exec` | Outlet (exec) | Control flow out |

## How It Works

### Edge-Based Flow

```
1. CustomCallback.listen_callback (outlet)
   default = self.node_id
   
2. Callback edge created
   → Pipe established
   
3. Pipe propagates value
   listen_callback.value → edge_callback.value
   
4. EmitCallback.worker()
   event_name = edge_callback.value  # Contains listener's node_id
   emit_callback(event_name, payload)
   
5. CallbackManager routes
   subscription_key = f"callback:{event_name}"
   → Matches CustomCallback's subscription
```

### String-Based Flow

```
1. Both nodes configured
   listener: custom_callback_name = 'my_event'
   emitter: custom_callback_name = 'my_event'
   
2. CustomCallback subscribes
   event_subscription = CallbackEvent('my_event')
   subscription_key = 'callback:my_event'
   
3. EmitCallback emits
   emit_callback('my_event', payload)
   
4. CallbackManager routes
   subscription_key = 'callback:my_event'
   → Matches CustomCallback's subscription
```

## Common Patterns

### Single Emitter, Multiple Listeners

```python
# Create emitter
emitter = graph.create_node_wrapper('emit_callback')

# Create multiple listeners
listener1 = graph.create_node_wrapper('custom_callback')
listener2 = graph.create_node_wrapper('custom_callback')
listener3 = graph.create_node_wrapper('custom_callback')

# Connect all to emitter (edge-based)
for listener in [listener1, listener2, listener3]:
    graph.create_edge_wrapper(
        listener.node_id, 'listen_callback',
        emitter.node_id, 'edge_callback'
    )

# All three listeners will receive the callback!
```

### Multiple Emitters, Single Listener

```python
# Create listener
listener = graph.create_node_wrapper('custom_callback')

# Create multiple emitters
emitter1 = graph.create_node_wrapper('emit_callback')
emitter2 = graph.create_node_wrapper('emit_callback')
emitter3 = graph.create_node_wrapper('emit_callback')

# Connect all to listener (edge-based)
for emitter in [emitter1, emitter2, emitter3]:
    graph.create_edge_wrapper(
        listener.node_id, 'listen_callback',
        emitter.node_id, 'edge_callback'
    )

# Listener will receive callbacks from all three emitters!
```

### Callback Chain

```python
# Flow 1: BeginPlay → EmitCallback1
# Flow 2: CustomCallback1 → EmitCallback2  
# Flow 3: CustomCallback2 → PrintMessage

# Callbacks propagate through the chain!
```

## Best Practices

1. **Use edge-based for static connections** - Better visual representation
2. **Use string-based for dynamic scenarios** - Configurable at runtime
3. **Check topology statistics** - Helps debug callback routing
4. **Monitor emit counts** - Detect missing or duplicate callbacks
5. **Use descriptive callback names** - Makes debugging easier (string-based mode)

## Troubleshooting

### Callback Not Triggering

1. Check topology: `stats['callback_topology']['connections']`
2. Verify listener is registered: `stats['callbacks']['callbacks']`
3. Check mode switch matches on both nodes
4. Verify callback edge is valid (if edge-based)
5. Confirm event names match (if string-based)

### Multiple Callbacks Firing

1. Check if multiple emitters connected to same listener
2. Verify emit counts: `stats['callbacks']['callbacks'][i]['emit_count']`
3. Review connection map: `stats['callback_topology']`

### Wrong Listener Triggered

1. Verify event names match
2. Check for duplicate callback names (string-based)
3. Review pipe propagation (edge-based)
4. Examine assembly logs for event propagation


## Summary

✅ **Validation**: StructuralValidator
✅ **Runtime**: Pipe propagation
✅ **Observability**: FlowAssemblyManager
✅ **Dual Mode**: Edge-based + String-based

The system is complete and production-ready!
