# DataField System - Implementation Summary

## Overview

The DataField system provides a flexible, type-safe storage layer for node ports in the Haywire system. It replaces the previous monolithic approach with a polymorphic hierarchy where each field type handles a specific storage pattern with uniform API.

---

## Core Architectural Principles

### 1. **Storage in Natural Form**

DataFields store data in its most natural, efficient form—NOT wrapped in multiple layers:

- **PrimitiveField**: Stores `PrimitiveType[T]` instance (e.g., `FLOAT(42.0)`)
- **ComplexField**: Stores `BaseType` instance (e.g., `MeshData(...)`)
- **PooledField**: Stores `Dict[str, T]` with unwrapped values (e.g., `{"node1": 42.0}`)
- **ArrayField**: Stores `List[T]` with unwrapped values (e.g., `[1.0, 2.0, 3.0]`)

**Key Insight**: IType wrappers are metadata holders and interface contracts, not storage containers.

### 2. **Wrapping Only at Boundaries**

Wrapping/unwrapping happens only at system boundaries:

- **Type Decorator (`@type`)**: Defines metadata (color, icon, widget, etc.)
- **Connection Transfer**: Wrap on send, unwrap on receive
- **Default Creation**: `FLOAT.create_default()` creates instance, gets unwrapped for storage

### 3. **Polymorphic Access Patterns**

All DataField subclasses implement the same core API but with type-appropriate semantics:

- `get_value()`: Returns data in worker-friendly form
- `set_value()`: Handles wrapped or unwrapped incoming data
- `get_for_transfer()`: Returns data wrapped for connections
- `is_compatible_with()`: Checks type compatibility with adapters

**Note**: Property-level updates for widget bindings are handled by `PropertyBinding`, not `DataField`.

### 4. **Separation of Concerns: Data vs Bindings**

**DataField** focuses purely on data storage and transfer:
- ✅ Store data efficiently
- ✅ Provide worker-friendly access
- ✅ Handle connection transfers
- ✅ Type compatibility checking
- ❌ Widget-specific operations (handled by PropertyBinding)

**PropertyBinding** handles all widget-specific logic:
- ✅ Property-level updates
- ✅ Nested property navigation
- ✅ Binding validation
- ✅ Field type compatibility for bindings

This creates cleaner boundaries and makes both classes simpler and more focused.

### 5. **Type Safety Through element_type_cls**

Pooled and Array fields track their element type separately from container type:

- **type_cls**: Container type (synthetic marker for pooled/array)
- **element_type_cls**: Actual element type (FLOAT, MeshData, etc.)

This enables:
- Compile-time type hints
- Runtime compatibility checking
- Adapter chain resolution
- Proper serialization

---

## Updated Access Matrix

### Use Case 1: Node-to-Node Data Transfer

| Field Type | Outlet Sends | Inlet Receives | What Gets Stored |
|------------|--------------|----------------|------------------|
| **PrimitiveField** | `FLOAT(42.0)` instance | `FLOAT(42.0)` instance | `FLOAT(42.0)` instance |
| **ComplexField** | `MeshData(...)` instance | `MeshData(...)` instance | `MeshData(...)` instance |
| **PooledField** | ❌ **INVALID** | `FLOAT(42.0)` from "node1" | `{"node1": 42.0}` (unwrapped) |
| **ArrayField** | `[FLOAT(1), FLOAT(2)]` (re-wrapped) | `[FLOAT(1), FLOAT(2)]` | `[1.0, 2.0]` (unwrapped) |

**Pattern:**
- Outlets send wrapped instances via `get_for_transfer()`
- Inlets receive and store appropriately via `set_value()`
- Pooled fields unwrap and track by source_id
- Array fields unwrap elements for storage efficiency

---

### Use Case 2: Worker Method Access (`node.inlet(id)`)

| Field Type | What Worker Gets | Example |
|------------|------------------|---------|
| **PrimitiveField** | Unwrapped primitive `T` | `42.0`, `"hello"`, `True` |
| **ComplexField** | Container instance `BaseType` | `MeshData(vertices=[], faces=[])` |
| **PooledField** | `Dict[str, T]` (unwrapped values) | `{"node1": 42.0, "node2": 15.0}` |
| **ArrayField** | `List[T]` (unwrapped primitives or BaseType) | `[42.0, 3.14]` or `[MeshData(...), MeshData(...)]` |

**Key Points:**
- Workers get the most convenient form for computation
- Primitives are unwrapped automatically
- Complex types are instances (already unwrapped since `.value == self`)
- Collections are native Python dicts/lists

**Worker Code Examples:**
```python
def worker(self, context):
    # Primitive - unwrapped
    temp = self.inlet('temperature')  # 42.0
    
    # Complex - instance
    mesh = self.inlet('mesh')  # MeshData(...)
    vertices = mesh.vertices
    
    # Pooled - dict
    temps = self.inlet('temp_pool')  # {"node1": 20.0, "node2": 25.0}
    avg = sum(temps.values()) / len(temps)
    
    # Array - list
    numbers = self.inlet('numbers')  # [1.0, 2.0, 3.0]
    sorted_nums = sorted(numbers)
    
    # Set outputs
    self.set_outlet('result', avg)
```

---

### Use Case 3: Widget Property Binding

#### Simple Widgets (SimpleWidget)

| Field Type | Supports Binding? | Binding Target | Widget Reads/Writes |
|------------|-------------------|----------------|---------------------|
| **PrimitiveField** | ✅ Yes | `container.value` | Unwrapped `T` (42.0) |
| **ComplexField** | ✅ Yes | Individual attributes | e.g., `container.radius` |
| **PooledField** | ⚠️ Read-only | - | One-way binding for display only |
| **ArrayField** | ⚠️ Read-only | - | One-way binding or wholesale replacement |

#### Complex Widgets (BaseWidget)

| Field Type | Binding Capabilities | Example Use Cases |
|------------|---------------------|-------------------|
| **PrimitiveField** | Single property: `value` | Number input, slider, text field |
| **ComplexField** | Multiple properties | Multi-field form, vector editor, mesh properties |
| **PooledField** | Advanced: Dynamic display | List/table showing all sources (read-only) |
| **ArrayField** | Advanced: List replacement | Dynamic list display, batch operations |

**Widget Update Pattern:**
```python
# PropertyBinding handles property updates internally
binding._update_nested_property('value', 75.0)
# For PrimitiveField: container.value = 75.0 (uses PrimitiveType setter)

# PropertyBinding navigates nested paths
binding._update_nested_property('radius', 5.0)
# For ComplexField: container.radius = 5.0

# Pooled/Array - raises clear error
binding._update_nested_property(...)  # ValueError: Cannot update properties of PooledField
```

**Note**: Property-level updates are now handled by `PropertyBinding` rather than `DataField.update_property()`. This creates better separation between data storage and binding logic.

---

### Use Case 4: Property Updates

Property-level updates are handled by `PropertyBinding`, not directly by `DataField`. This keeps the DataField API focused on data storage and transfer.

**PropertyBinding Update Behavior:**

| Field Type | Supports Property Updates? | Behavior |
|------------|---------------------------|----------|
| **PrimitiveField** | ✅ Yes | PropertyBinding updates `container.value` |
| **ComplexField** | ✅ Yes | PropertyBinding updates via setattr |
| **PooledField** | ❌ No | PropertyBinding raises ValueError (read-only) |
| **ArrayField** | ❌ No | PropertyBinding raises ValueError (use set_value()) |

**Implementation:**
```python
# In PropertyBinding class (not DataField)
def _update_nested_property(self, path: str, value: Any) -> None:
    """Update property and notify observers"""
    container = self._get_container()  # Gets PrimitiveType or BaseType
    
    # Navigate to parent of final property
    parts = path.split('.')
    current = container
    for part in parts[:-1]:
        current = getattr(current, part)
    
    # Update final property
    setattr(current, parts[-1], value)
    
    # Notify observers via field
    field.is_dirty = True
    field.fire(container)
```

---

## Type Compatibility System

### Compatibility Checking

Each DataField implements `is_compatible_with()` to check if it can receive data from another field:

```python
is_compatible, reason = inlet_field.is_compatible_with(outlet_field, adapter_registry)
```

**Return Values:**
- `(True, "direct")` - Same type, direct connection
- `(True, "Temperature->FLOAT")` - Single adapter available
- `(True, "Temperature->FLOAT->STRING")` - Adapter chain available
- `(False, "No adapter found")` - Incompatible types

### Compatibility Rules

#### PrimitiveField and ComplexField
- ✅ Direct match: Same type_cls
- ✅ Adapter: Single adapter exists
- ✅ Chain: Multi-hop adapter path exists
- ❌ No path: No adapter chain found

#### PooledField
- ✅ Single → Pooled: If element types compatible
- ✅ Adapter support: Can use adapters on element types
- ❌ Pooled → Pooled: Cannot connect pooled to pooled
- ❌ Array → Pooled: Cannot pool array outputs

#### ArrayField
- ✅ Array → Array: If element types compatible
- ✅ Adapter support: Can use adapters on element types
- ❌ Single → Array: Cannot connect single to array
- ❌ Array size mismatch: Accepted (runtime, not connection time)

### Adapter Chain Resolution

**NOTE**: Full implementation deferred, but architecture supports:

1. **Direct Lookup**: `adapter_registry.has_adapter(source, target)`
2. **Chain Search**: `adapter_registry.find_adapter_chain(source, target)`
3. **Cost Optimization**: Prefer shorter chains
4. **Cycle Detection**: Prevent infinite loops
5. **Caching**: Cache resolved chains for performance

**Future Implementation Example:**
```python
class AdapterRegistry:
    def find_adapter_chain(
        self, 
        source_type: type[IType], 
        target_type: type[IType],
        max_depth: int = 3
    ) -> List[type[IType]] | None:
        """
        Find shortest adapter chain from source to target.
        
        Uses breadth-first search to find shortest path.
        Returns list of intermediate types or None if no path exists.
        """
        # Implementation using graph search
        pass
```

---

## Field Type Responsibilities Summary

| Field Type | Primary Purpose | Container Storage | Worker Access | Transfer Format | Binding Support |
|------------|----------------|-------------------|---------------|-----------------|-----------------|
| **PrimitiveField** | Simple values | `PrimitiveType[T]` | Unwrapped `T` | `PrimitiveType[T]` | ✅ Via PropertyBinding |
| **ComplexField** | Structured data | `BaseType` | `BaseType` | `BaseType` | ✅ Via PropertyBinding |
| **PooledField** | Multi-source aggregation | `Dict[str, T]` | `Dict[str, T]` | ❌ Inlet-only | ⚠️ Read-only |
| **ArrayField** | Homogeneous collections | `List[T]` | `List[T]` | `List[IType]` | ⚠️ Wholesale only |

---

## Key Design Decisions

### 1. Why Store PrimitiveType Instances?

**Decision**: Store `FLOAT(42.0)` instead of just `42.0`

**Rationale**:
- Avoids repeated instantiation on transfer
- `get_for_transfer()` just returns the instance (efficient!)
- Still provides unwrapped access via `get_value()`
- Uses efficient setter: `container.value = new_value`

**Alternative Considered**: Store unwrapped, re-wrap on transfer
- ❌ More instantiations (slower)
- ❌ More complex transfer logic
- ✅ Slightly simpler storage

**Verdict**: Current approach is more efficient for connection-heavy workflows

### 2. Why Unwrap in Pooled/Array Fields?

**Decision**: Store `[1.0, 2.0]` not `[FLOAT(1), FLOAT(2)]`

**Rationale**:
- Workers iterate over collections frequently
- Unwrapped values are more Pythonic: `sum(values)` vs `sum(v.value for v in values)`
- Memory efficient for large arrays
- Re-wrapping on transfer is acceptable overhead (happens less frequently)

**Alternative Considered**: Store wrapped instances
- ❌ More memory for large arrays
- ❌ Less convenient worker API
- ✅ Consistent with PrimitiveField

**Verdict**: Worker convenience and efficiency win for collections

### 3. Why element_type_cls for Pooled/Array?

**Decision**: Track element type separately from container type

**Rationale**:
- Enables type checking: `Array[FLOAT]` vs `Array[STRING]`
- Adapter resolution needs element type
- Serialization needs to recreate correct types
- Generic-like behavior without complex typing gymnastics

**Alternative Considered**: Use generic typing (`ArrayField[FLOAT]`)
- ❌ Python's typing system doesn't support this well at runtime
- ❌ Complex metaclass magic required
- ❌ Serialization becomes very difficult

**Verdict**: Explicit `element_type_cls` is cleaner and more practical

### 4. Why Property Updates in PropertyBinding, Not DataField?

**Decision**: Move property-level update logic to PropertyBinding

**Rationale**:
- DataField is for data storage, not widget operations
- Only bindings need property-level granularity
- Simpler DataField API (no binding-specific methods)
- Clearer error messages from binding context
- No stub methods in PooledField/ArrayField that just raise errors

**Alternative Considered**: Keep `update_property()` in DataField
- ❌ Mixes concerns (data storage + widget operations)
- ❌ Forces PooledField/ArrayField to implement stubs
- ❌ Less clear what DataField is responsible for

**Verdict**: PropertyBinding owns all binding logic, DataField owns all data logic

---

## Performance Considerations

### Storage Efficiency

| Field Type | Memory Overhead | Access Speed | Transfer Speed |
|------------|----------------|--------------|----------------|
| **PrimitiveField** | One wrapper instance | O(1) unwrap | O(1) direct return |
| **ComplexField** | Instance only | O(1) direct return | O(1) direct return |
| **PooledField** | Dict overhead | O(1) dict lookup | ❌ N/A |
| **ArrayField** | List overhead | O(1) list access | O(n) re-wrap primitives |

### Optimization Strategies

1. **PrimitiveField**: Keep wrapper instance, update via setter
2. **ArrayField**: Consider lazy re-wrapping (wrap on-demand during transfer)
3. **PooledField**: Use OrderedDict if insertion order matters
4. **All Fields**: Event batching to reduce notification overhead

---

## Extension Points

### Custom Field Types

The system can be extended with custom field types:

```python
@dataclass
class CustomField(DataField[CustomType]):
    """Example custom field for special use cases"""
    
    def get_value(self) -> CustomType:
        # Custom access logic
        pass
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        # Custom storage logic
        pass
    
    # ... implement other abstract methods
```

**Use Cases**:
- **SparseField**: For sparse matrices or graphs
- **StreamField**: For continuous data streams
- **CachedField**: For expensive computations with memoization
- **HistoryField**: For time-series or undo/redo

---

## Migration Path

### From Old System

**Old Code:**
```python
# Access was inconsistent
value = self.inlets['input'].data.get_container().value  # For primitives
value = self.inlets['input'].data.get_container()  # For complex
```

**New Code:**
```python
# Uniform access
value = self.inlet('input')  # Works for all types!
```

### Compatibility Notes

- All existing `Type.as_inlet()` and `Type.as_outlet()` calls work unchanged
- Worker code needs update to use `self.inlet()` instead of manual unwrapping
- Widget bindings need review but API is compatible
- Serialization format changes (but migration is automatic via from_dict)

---

## Testing Recommendations

### Unit Tests

1. **Field Storage**: Test each field type stores data correctly
2. **Unwrapping**: Test get_value() returns correct format
3. **Transfer**: Test get_for_transfer() wraps correctly
4. **Property Updates**: Test update_property() for supported fields
5. **Compatibility**: Test is_compatible_with() with various type combinations

### Integration Tests

1. **Connection Transfer**: Test data flows correctly between nodes
2. **Pooled Aggregation**: Test multiple sources update correctly
3. **Array Operations**: Test array transfer and worker access
4. **Adapter Chains**: Test multi-hop type conversions
5. **Widget Binding**: Test property binding with different field types

### Performance Tests

1. **Large Arrays**: Test with 1000+ element arrays
2. **Many Sources**: Test pooled fields with 100+ sources
3. **Connection Churn**: Test repeated connect/disconnect cycles
4. **Event Overhead**: Test observer notification performance

---

## Future Enhancements

### Short Term
- [ ] Implement adapter chain resolution
- [ ] Add validation to set_value() (type checking)
- [ ] Optimize array re-wrapping (lazy or cached)
- [ ] Add field statistics (last updated, change count)

### Medium Term
- [ ] Support for nested arrays (Array[Array[FLOAT]])
- [ ] Union types (inlet accepts FLOAT or INT)
- [ ] Optional type coercion (auto-convert compatible types)
- [ ] Field metadata (units, ranges, constraints)

### Long Term
- [ ] Reactive computation graphs (auto-propagate changes)
- [ ] Incremental updates (delta-based change notification)
- [ ] Distributed fields (share data across network)
- [ ] Persistent fields (save to disk automatically)