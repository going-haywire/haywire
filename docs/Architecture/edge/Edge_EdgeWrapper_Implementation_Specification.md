# Edge/EdgeWrapper Implementation Specification

**Version:** 1.0  
**Date:** December 20, 2025  
**Status:** Draft Specification

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Lifecycle Management](#lifecycle-management)
4. [Adapter Chain System](#adapter-chain-system)
5. [Hot Reload Support](#hot-reload-support)
6. [API Specification](#api-specification)
7. [Migration Strategy](#migration-strategy)
8. [Implementation Phases](#implementation-phases)

---

## Overview

This specification defines the implementation of EdgeWrapper and related components, following the same architectural patterns as NodeWrapper. The EdgeWrapper manages the complete lifecycle of an Edge, including adapter chain management, hot reload support, validation, and data transformation.

### Design Principles

- **Parallel to NodeWrapper**: EdgeWrapper follows the same lifecycle patterns as NodeWrapper
- **Separation of Concerns**: Edge (data), EdgeWrapper (lifecycle), AdapterFactory (adapter chain creation)
- **Type Safety**: Full type checking through adapter chains
- **Hot Reload**: Automatic adapter chain updates when adapters are reloaded
- **Validation**: Edge validity determined by inlet DataField with adapter chain support

---

## Architecture

### Component Hierarchy

```
BaseGraph
    ├── NodeWrapper (manages nodes)
    │   └── BaseNode
    │
    └── EdgeWrapper (manages edges)
        ├── Edge (data structure)
        └── AdapterChain (transformation pipeline)

AdapterFactory
    ├── AdapterRegistry
    └── Manages EdgeWrapper dependencies
```

### Data Flow

```
1. Edge Creation:
   User Action → AddEdgeAction → Graph.create_edge_wrapper() 
   → EdgeWrapper.__init__() → EdgeWrapper.initialize(graph)
   → EdgeWrapper returns self → Graph.add_edge_wrapper()

2. Hot Reload:
   AdapterRegistry → AdapterFactory → EdgeWrapper 
   → EdgeWrapper.rebuild_chain() → Notify UIEdge

3. Data Execution:
   Source Outlet → EdgeWrapper.transform(value) 
   → AdapterChain.execute(value) → Target Inlet
```

---

## 

## Lifecycle Management

### Edge Creation Flow

```
1. User creates connection in UI
   ↓
2. AddEdgeAction created with node/pin IDs
   ↓
3. Action._execute_impl() - first execution
   ↓
4. Graph.create_edge_wrapper() called
   ↓
5. EdgeWrapper.__init__()
   - Stores node/pin IDs
   - Generates edge_id
   - State = not initialized
   ↓
6. EdgeWrapper.initialize(graph)
   - Gets node wrapper references
   - Gets DataPort references
   - Determines edge type
   - Validates with inlet DataField
   - Creates adapter chain via factory
   - Creates Edge instance
   - Subscribes to adapter factory
   - Returns self if successful, None if failed
   ↓
7. Graph.add_edge_wrapper(wrapper)
   - Adds to edge_wrappers dict
   - Adds to legacy edges dict (for compatibility)
   ↓
8. Action stores wrapper reference for undo
   ↓
9. UIEdge subscribes to EdgeWrapper
   - Receives lifecycle events
   - Displays metrics/warnings

Redo Flow:
   AddEdgeAction._execute_impl() checks if self.wrapper is None:
   - If None (first execution): create_edge_wrapper()
   - Else (redo): add_edge_wrapper(self.wrapper)
```

### Hot Reload Flow

```
1. Adapter class file modified
   ↓
2. AdapterRegistry detects change
   - Reloads adapter class
   - Creates LifeCycleEvent
   ↓
3. AdapterFactory receives event
   - Looks up dependent edges
   - Calls EdgeWrapper callbacks
   ↓
4. EdgeWrapper rebuilds chain
   - Calls factory.rebuild_chain()
   - Compares old/new adapter keys
   - Updates state
   ↓
5. EdgeWrapper notifies UIEdge
   - Lifecycle event with status
   - Warnings if chain changed
   ↓
6. UIEdge updates display
   - Shows new chain description
   - Displays warning if needed
```

---

## Adapter Chain System

### Chain Creation Strategy

1. **Direct Match** (chain length = 0)
   
   - Source type == Target type
   - No adapters needed
   - Example: FLOAT → FLOAT

2. **Single Adapter** (chain length = 1)
   
   - Direct adapter exists
   - Example: Temperature → FLOAT (via TempToFloatAdapter)

3. **Multi-hop Chain** (chain length = 2-3)
   
   - Registry finds adapter path
   - Example: Temperature → FLOAT → INT
   - Maximum depth configurable (default 3)

4. **No Chain** (invalid edge)
   
   - No adapter path found
   - Edge marked invalid
   - Error stored in state

### Inlet Validation Strategy

**Simplified Validation - Single Method for Compatibility**

Validation uses `DataField.get_compatible_type()` which combines structural validation with type compatibility declaration. This approach correctly handles compound types where element-level compatibility matters (e.g., `Array[FLOAT] → Array[FLOAT]` checks FLOAT compatibility, not ArrayType compatibility).

**Flow:**

1. EdgeWrapper validates port-level rules (via DataPort)
2. EdgeWrapper calls `inlet_field.get_compatible_type(outlet_field)`
3. Fields declare what type they need and perform structural validation:
   - **Scalar fields** (PrimitiveField/BaseField): Return `type_cls`
   - **Compound fields** (ArrayField): Raise ValueError if outlet not compound, return `element_type_cls`
   - **Pooled fields** (PooledField): Accept both scalar and compound, return `element_type_cls`
4. EdgeWrapper creates adapter chain with resolved types (single source of truth)

**DataField.get_compatible_type() Method:**

```python
# In DataField base class (fields.py)
def get_compatible_type(self, outlet_field: 'DataField') -> type:
    """
    Return the type needed for adapter compatibility checking.

    For structural validation, raise ValueError with clear message.
    Default: return own type_cls (scalar behavior).

    Examples:
        # Scalar fields check type_cls
        FLOAT inlet returns FLOAT type_cls

        # Compound fields check element_type_cls
        Array[FLOAT] inlet checks outlet is also compound,
        returns FLOAT element_type_cls

        # Pooled accepts both, checks element_type_cls
        Pooled[FLOAT] returns FLOAT element_type_cls
        (works with FLOAT outlet or Array[FLOAT] outlet)
    """
    return self.type_cls  # Default for scalars
```

**Field Implementations:**

```python
# PrimitiveField/BaseField - use default (returns type_cls)

# CompoundField base - element-level checking for arrays
def get_compatible_type(self, outlet_field):
    if not isinstance(outlet_field, CompoundField):
        raise ValueError(
            f"Cannot connect scalar to compound. "
            f"{outlet_field.type_cls.__name__} → {self.type_cls.__name__}"
        )
    return self.element_type_cls  # Check FLOAT, not Array

# PooledField - flexible, accepts both scalar and compound
def get_compatible_type(self, outlet_field):
    # No structural restrictions
    # Pooled[FLOAT] accepts FLOAT or Array[FLOAT]
    return self.element_type_cls
```

**EdgeWrapper Validation Flow:**

```python
# In EdgeWrapper._create_adapter_chain()

# Step 1: Port-level rules
is_valid, error_msg = self._inlet_port.validate_connection_rules(
    self._outlet_port
)
if not is_valid:
    return (False, HaywireException(message=error_msg))

# Step 2: Get compatible types (includes structural validation)
try:
    # Inlet determines what type it needs
    target_type = self._inlet_port.data.get_compatible_type(
        self._outlet_port.data
    )

    # Outlet provides its type
    outlet_field = self._outlet_port.data
    if hasattr(outlet_field, 'element_type_cls'):
        source_type = outlet_field.element_type_cls
    else:
        source_type = outlet_field.type_cls

except ValueError as e:
    return (False, HaywireException(message=str(e)))

# Step 3: Create adapter chain (SINGLE registry access)
chain, error_msg = self._adapter_factory.create_chain(
    source_type, target_type, self.edge_id
)
```

**Example Connections:**

```python
# Scalar → Scalar
FLOAT → FLOAT:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → FLOAT
    adapter_factory.create_chain(FLOAT, FLOAT) → no adapter needed ✓

Temperature → FLOAT:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → Temperature
    adapter_factory.create_chain(Temperature, FLOAT) → TempToFloat adapter ✓

# Compound → Compound  
Array[FLOAT] → Array[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT (element check)
    outlet provides → FLOAT (element)
    adapter_factory.create_chain(FLOAT, FLOAT) → no adapter needed ✓

Array[Temperature] → Array[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → Temperature
    adapter_factory.create_chain(Temperature, FLOAT) → TempToFloat adapter ✓

# Scalar → Compound (INVALID)
FLOAT → Array[FLOAT]:
    inlet.get_compatible_type(outlet) raises ValueError ✗
    "Cannot connect scalar FLOAT to compound ArrayType"

# Pooled (flexible)
FLOAT → Pooled[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → FLOAT
    adapter_factory.create_chain(FLOAT, FLOAT) ✓

Array[FLOAT] → Pooled[Array[FLOAT]]:
    inlet.get_compatible_type(outlet) → FLOAT (element)
    outlet provides → FLOAT (element)
    adapter_factory.create_chain(FLOAT, FLOAT) ✓
```

**Key Benefits:**

1. **Single Method** - `get_compatible_type()` handles structural and type declaration
2. **Element-Level Checking** - Correctly handles compound types (Array[X] checks X compatibility)
3. **No Registry Bypass** - DataField never calls AdapterRegistry
4. **Clear Separation**: DataPort (connection rules) → DataField (type declaration) → AdapterFactory (compatibility)
5. **Flexible Pooling** - Supports both scalar and compound aggregation
6. **Single Responsibility** - Type checking once in AdapterFactory

---

## Hot Reload Support

### Adapter Change Scenarios

1. **Adapter Modified** (code changed)
   
   - Registry reloads adapter class
   - Factory rebuilds chains
   - EdgeWrapper validates new chain
   - If same adapters: silent update
   - If different adapters: warning

2. **Adapter Removed**
   
   - Registry removes adapter
   - Factory attempts rebuild
   - If alternative found: warning
   - If no alternative: edge invalid

3. **Adapter Added**
   
   - Registry adds new adapter
   - Existing edges unaffected
   - New edges can use it

4. **Adapter Failed to Load**
   
   - Registry reports error
   - EdgeWrappers keep old chain
   - Warning issued

### Warning System

EdgeWrapper tracks chain changes:

```python
state.chain_changed_warning = True  # Flag set during hot reload
```

UIEdge displays warnings:

- Visual indicator on edge
- Tooltip with chain comparison
- Option to view details/dismiss

User should be informed:

- Which edges affected
- Old vs new adapter chain
- Potential behavior changes



---

## Appendix

### Example Usage

**Creating an Edge:**

```python
# Via Editor
editor.create_connection(
    output_node_id="node_1",
    outlet_pin="temperature_out",
    input_node_id="node_2",
    inlet_pin="value_in"
)

# Via Action (undo/redo)
action = AddEdgeAction(
    graph=graph,
    output_node_id="node_1",
    outlet_pin_id="temperature_out",
    input_node_id="node_2",
    inlet_pin_id="value_in"
)
history_manager.add_action(action)
```

**Using Transform:**

```python
# Get edge wrapper
wrapper = graph.get_edge_wrapper(edge_id)

# Transform value
temp_value = Temperature(25.0)  # Celsius
int_value = wrapper.transform(temp_value)  # Returns: 25 (int)

# Or reference in outlet port
outlet_port.edge_transform = wrapper.transform
```

**Checking Edge Status:**

```python
wrapper = graph.get_edge_wrapper(edge_id)

# Validation
errors = wrapper.validate()
if errors:
    print(f"Edge issues: {errors}")

# Metrics
metrics = wrapper.get_metrics()
print(f"Chain: {metrics['adapter_chain']}")
print(f"Executions: {metrics['execution_count']}")
print(f"Avg time: {metrics['chain_metrics']['avg_time_ms']}ms")

# Warnings
if wrapper.state.chain_changed_warning:
    print("WARNING: Adapter chain changed!")
```

---

## Future Enhancements

1. **UIEdge Component**
   
   - Visual edge representation
   - Real-time metrics display
   - Interactive debugging

2. **Edge Execution Integration**
   
   - Integrate with pipeline execution
   - Lazy evaluation support
   - Parallel execution

3. **Advanced Validation**
   
   - Edge dependency cycles
   - Type constraint checking
   - Performance optimization

4. **Adapter Chain Optimization**
   
   - Cache compiled chains
   - JIT compilation
   - Vectorized operations

5. **User Warnings UI**
   
   - Edge health dashboard
   - Chain change notifications
   - Automatic issue detection

---

**End of Specification**
