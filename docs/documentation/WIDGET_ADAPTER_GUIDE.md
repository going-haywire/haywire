# Widget Binding and Adapter Chain - Implementation Guide

## Overview

This document outlines the architecture and considerations for implementing:
1. Widget property bindings with the new DataField system
2. Adapter chain resolution for type compatibility

Both features integrate with the DataField system but are deferred for future implementation.

---

## Part 1: Widget Property Binding

### Current State

The existing widget system uses:
- **SimpleWidget**: Direct DataPort ↔ UI binding with minimal overhead
- **BaseWidget**: Sophisticated binding with converters, validation, debouncing
- **PropertyBinding**: Declarative binding configuration

### Integration Points with DataField

#### 1. Binding to PrimitiveField

**Current Implementation:**
```python
class SimpleWidget:
    def _sync_to_view(self):
        value = self.element.get_value()  # Gets unwrapped primitive
        setattr(self.ui_element, self.UI_PROPERTY, value)
    
    def _sync_to_model(self):
        value = getattr(self.ui_element, self.UI_PROPERTY)
        self.element.set_value(value)  # Wraps and stores
```

**Key Observations:**
- ✅ Already compatible! `get_value()` returns unwrapped primitive
- ✅ `set_value()` handles wrapping automatically
- ✅ No changes needed for simple widgets

**Advanced Binding with PropertyBinding:**
```python
class PropertyBinding:
    def _sync_to_view(self):
        if self.source_property == "value":
            # Use high-level API - works for all field types
            model_value = self._element.get_value()  # Unwrapped
        else:
            # Navigate to nested property
            container = self._get_container()  # Gets PrimitiveType wrapper
            model_value = self._navigate_path(container, self.source_property)
        
        view_value = self.converter.to_view(model_value)
        setattr(self._ui_element, self.target_property, view_value)
    
    def _sync_to_model(self, view_value):
        model_value = self.converter.to_model(view_value)
        
        if self.source_property == "value":
            # Simple replacement
            self._element.set_value(model_value)
        else:
            # Property-level update (now in PropertyBinding!)
            self._update_nested_property(self.source_property, model_value)
```

**Key Change:**
- Property updates now handled by PropertyBinding, not DataField
- PropertyBinding calls `_get_container()` to get the wrapper/instance
- PropertyBinding navigates and updates properties directly
- PropertyBinding fires observers via `field.fire()`

#### 2. Binding to BaseField

**Example: Binding to MeshData.scale**
```python
# Widget configuration
binding = PropertyBinding(
    source_property="scale",  # Bind to mesh.scale attribute
    target_property="value",
    converter=None,  # No conversion needed
    mode=BindingMode.TWO_WAY
)

# Binding implementation (in PropertyBinding)
def _sync_to_model(self, view_value):
    # PropertyBinding handles the update internally
    self._update_nested_property('scale', view_value)
    
def _update_nested_property(self, path, value):
    container = self._get_container()  # Gets MeshData instance
    setattr(container, path, value)  # container.scale = value
    field.is_dirty = True
    field.fire(container)  # Notify observers
```

**Multi-Property Widget:**
```python
class VectorWidget(BaseWidget):
    def configure_bindings(self):
        # Bind X component
        self.add_binding(PropertyBinding(
            source_property="x",
            target_property="value"
        ), target_element="x_input")
        
        # Bind Y component  
        self.add_binding(PropertyBinding(
            source_property="y",
            target_property="value"
        ), target_element="y_input")
        
        # Bind Z component
        self.add_binding(PropertyBinding(
            source_property="z",
            target_property="value"
        ), target_element="z_input")
```

**Key Observation:**
- PropertyBinding navigates to container and updates directly
- No need for DataField to know about widget-specific operations
- Clean separation: DataField stores, PropertyBinding binds

#### 3. Binding to PooledField

**Constraint:** Pooled fields are read-only from widget perspective

**Read-Only Display Widget:**
```python
class PooledDisplayWidget(BaseWidget):
    """Displays pooled values as a table"""
    
    def configure_bindings(self):
        # One-way binding for display only
        binding = PropertyBinding(
            source_property="value",  # Gets entire dict
            target_property="rows",
            converter=PooledToTableConverter(),
            mode=BindingMode.ONE_WAY  # Read-only!
        )
        self.add_binding(binding)
    
    def create_element(self):
        return ui.table(columns=[
            {'name': 'source', 'label': 'Source', 'field': 'source'},
            {'name': 'value', 'label': 'Value', 'field': 'value'}
        ])

class PooledToTableConverter(BindingConverter):
    def to_view(self, model_value: Dict[str, float]) -> List[Dict]:
        """Convert pooled dict to table rows"""
        return [
            {'source': source_id, 'value': value}
            for source_id, value in model_value.items()
        ]
```

**Key Observations:**
- ✅ One-way binding works naturally
- ❌ Two-way binding blocked by `update_property()` raising error
- ✅ Custom converters can format pooled data for display

#### 4. Binding to ArrayField

**Constraint:** Arrays are replaced wholesale, not mutated element-wise

**Read-Only List Display:**
```python
class ArrayDisplayWidget(BaseWidget):
    """Displays array as a list"""
    
    def configure_bindings(self):
        binding = PropertyBinding(
            source_property="value",  # Gets entire list
            target_property="items",
            converter=ArrayToListConverter(),
            mode=BindingMode.ONE_WAY
        )
        self.add_binding(binding)
    
    def create_element(self):
        return ui.list()
```

**Editable Array (Advanced):**
```python
class ArrayEditorWidget(BaseWidget):
    """Allows editing array by replacing it wholesale"""
    
    def configure_bindings(self):
        # No automatic binding - manual control
        pass
    
    def create_element(self):
        with ui.column() as container:
            self.list_display = ui.list()
            ui.button('Add Item', on_click=self._add_item)
            ui.button('Remove Last', on_click=self._remove_last)
        
        # Subscribe to model changes
        self._element.data.on_changed += self._update_display
        
        return container
    
    def _update_display(self, items):
        # Refresh display
        self.list_display.clear()
        for item in items:
            self.list_display.add_item(str(item))
    
    def _add_item(self):
        current = self._element.get_value()  # Get list
        new_list = current + [0.0]  # Add default item
        self._element.set_value(new_list)  # Replace wholesale
    
    def _remove_last(self):
        current = self._element.get_value()
        if current:
            new_list = current[:-1]
            self._element.set_value(new_list)
```

**Key Observations:**
- ✅ Display binding works naturally
- ❌ Element-wise editing not supported by update_property()
- ✅ Wholesale replacement via set_value() is the pattern
- ✅ Manual event subscription for complex interactions

### Recommended Implementation Strategy

1. **SimpleWidget**: No changes needed, already compatible
2. **BaseWidget/PropertyBinding**: 
   - ✅ Already updated! Property update logic moved to PropertyBinding
   - `_get_container()` retrieves PrimitiveType or BaseType for navigation
   - `_navigate_path()` reads nested properties
   - `_update_nested_property()` writes nested properties and fires observers
   - Field type detection ensures clear errors for Pooled/Array
3. **Pooled Widgets**: Implement read-only display widgets with one-way bindings
4. **Array Widgets**: Implement with wholesale replacement pattern, not element-wise editing

### Code Changes Required

**PropertyBinding (COMPLETE - see binding_updated.py):**
```python
class PropertyBinding:
    def _sync_to_model(self, view_value: Any) -> None:
        model_value = self.converter.to_model(view_value)
        
        if self.source_property == "value":
            # High-level API - works for all types
            self._element.set_value(model_value)
        else:
            # Property-level update - now handled here!
            self._update_nested_property(self.source_property, model_value)
    
    def _update_nested_property(self, path: str, value: Any) -> None:
        """Update property and notify observers"""
        field = self._element.data
        
        # Validate field type
        if isinstance(field, (PooledField, ArrayField)):
            raise ValueError(f"Cannot update properties of {type(field).__name__}")
        
        # Get container and navigate path
        container = self._get_container()
        parts = path.split('.')
        current = container
        for part in parts[:-1]:
            current = getattr(current, part)
        
        # Update property
        setattr(current, parts[-1], value)
        
        # Notify via field
        field.is_dirty = True
        field.fire(container)
```

**DataField (COMPLETE - see datafields.py):**
```python
# No update_property() method - simpler API!
class DataField(ABC):
    @abstractmethod
    def get_value(self) -> T: pass
    
    @abstractmethod
    def set_value(self, value, source_id=None): pass
    
    @abstractmethod
    def get_for_transfer(self) -> IType: pass
    
    # No update_property() - that's PropertyBinding's job!
```

**SimpleWidget (NO CHANGES):**
```python
# Already works perfectly!
def _sync_to_model(self) -> None:
    value = getattr(self.ui_element, self.UI_PROPERTY)
    self.element.set_value(value)  # Works for all field types!
```

---

## Part 2: Adapter Chain Resolution

TODO: Adapter Chain Resolution: This description is out of date. Update to reflect current design and implementation plan.

### Architecture Overview

**Goal:** Automatically find adapter chains to enable connections between incompatible types

**Example:**
```
Temperature outlet → FLOAT inlet
  ↓
Check: Temperature → FLOAT adapter exists? ✅
Result: (True, "Temperature->FLOAT")
```

**Complex Example:**
```
Temperature outlet → STRING inlet
  ↓
Check: Temperature → STRING adapter exists? ❌
  ↓
Search for chain: Temperature → ? → STRING
  ↓
Found: Temperature → FLOAT → STRING
Result: (True, "Temperature->FLOAT->STRING")
```

### AdapterRegistry Design

**Current Stub:**
```python
class AdapterRegistry:
    def has_adapter(self, source: type, target: type) -> bool:
        """Check if direct adapter exists"""
        pass
    
    def get_adapter(self, source: type, target: type) -> BaseAdapter:
        """Get direct adapter instance"""
        pass
```

**Extended Interface:**
```python
class AdapterRegistry:
    def __init__(self):
        # Direct adapters: (source, target) -> adapter_class
        self._adapters: Dict[tuple[type, type], type[BaseAdapter]] = {}
        
        # Cache for resolved chains
        self._chain_cache: Dict[tuple[type, type], List[type] | None] = {}
    
    def register_adapter(
        self, 
        source: type[IType], 
        target: type[IType], 
        adapter: type[BaseAdapter]
    ) -> None:
        """Register a direct adapter"""
        self._adapters[(source, target)] = adapter
        self._chain_cache.clear()  # Invalidate cache
    
    def has_adapter(self, source: type, target: type) -> bool:
        """Check if direct adapter exists"""
        return (source, target) in self._adapters
    
    def get_adapter(self, source: type, target: type) -> BaseAdapter:
        """Get direct adapter instance"""
        adapter_cls = self._adapters.get((source, target))
        if not adapter_cls:
            raise ValueError(f"No adapter from {source} to {target}")
        return adapter_cls()
    
    def find_adapter_chain(
        self,
        source: type[IType],
        target: type[IType],
        max_depth: int = 3
    ) -> List[type[IType]] | None:
        """
        Find shortest adapter chain from source to target.
        
        Uses breadth-first search to find shortest path.
        Returns list of intermediate types or None if no path exists.
        
        Args:
            source: Source type
            target: Target type
            max_depth: Maximum chain length (prevent infinite loops)
        
        Returns:
            List of types in chain (including source and target)
            or None if no path found
        
        Example:
            find_adapter_chain(Temperature, STRING, max_depth=3)
            Returns: [Temperature, FLOAT, STRING]
        """
        # Check cache
        cache_key = (source, target)
        if cache_key in self._chain_cache:
            return self._chain_cache[cache_key]
        
        # Direct connection (no adapter needed)
        if source == target:
            return [source]
        
        # BFS to find shortest path
        from collections import deque
        
        queue = deque([(source, [source])])
        visited = {source}
        
        while queue:
            current_type, path = queue.popleft()
            
            # Check if we've exceeded max depth
            if len(path) > max_depth + 1:
                continue
            
            # Try all adapters from current type
            for (src, tgt), adapter_cls in self._adapters.items():
                if src != current_type:
                    continue
                
                # Found target!
                if tgt == target:
                    result = path + [target]
                    self._chain_cache[cache_key] = result
                    return result
                
                # Add to queue if not visited
                if tgt not in visited:
                    visited.add(tgt)
                    queue.append((tgt, path + [tgt]))
        
        # No path found
        self._chain_cache[cache_key] = None
        return None
    
    def get_chain_cost(self, chain: List[type[IType]]) -> int:
        """
        Calculate cost of an adapter chain.
        
        Can be extended to prefer certain adapters over others.
        """
        # Base cost: number of adapters (chain length - 1)
        return len(chain) - 1
    
    def build_chain(self, chain: List[type[IType]]) -> List[BaseAdapter]:
        """
        Build adapter instances for a chain.
        
        Args:
            chain: List of types from find_adapter_chain()
        
        Returns:
            List of adapter instances to apply in sequence
        """
        adapters = []
        for i in range(len(chain) - 1):
            source = chain[i]
            target = chain[i + 1]
            adapter = self.get_adapter(source, target)
            adapters.append(adapter)
        return adapters
    
    def apply_chain(
        self, 
        value: IType, 
        chain: List[type[IType]]
    ) -> IType:
        """
        Apply adapter chain to convert value.
        
        Args:
            value: Value to convert
            chain: Type chain from find_adapter_chain()
        
        Returns:
            Converted value
        """
        adapters = self.build_chain(chain)
        current = value
        for adapter in adapters:
            current = adapter.convert(current)
        return current
```

### Integration with DataField.is_compatible_with()

**Current Implementation:**
```python
def is_compatible_with(self, other_field, adapter_registry):
    # Direct match
    if other_field.type_cls == self.type_cls:
        return (True, "direct")
    
    # Single adapter
    if adapter_registry.has_adapter(other_field.type_cls, self.type_cls):
        return (True, f"{other_field.type_cls.__name__}->{self.type_cls.__name__}")
    
    # Adapter chain
    chain = adapter_registry.find_adapter_chain(other_field.type_cls, self.type_cls)
    if chain:
        return (True, "->".join([c.__name__ for c in chain]))
    
    return (False, f"No adapter from {other_field.type_cls.__name__} to {self.type_cls.__name__}")
```

**This already works!** Just need to implement `find_adapter_chain()`.

### Connection System Integration

**Connection Validation:**
```python
class ConnectionManager:
    def can_connect(
        self,
        source_port: PortOutlet,
        target_port: PortInlet,
        adapter_registry: AdapterRegistry
    ) -> tuple[bool, str, List[type] | None]:
        """
        Check if ports can be connected.
        
        Returns:
            (can_connect, reason, adapter_chain)
        """
        # Check compatibility
        compatible, reason = target_port.data.is_compatible_with(
            source_port.data,
            adapter_registry
        )
        
        if not compatible:
            return (False, reason, None)
        
        # Extract chain if exists
        if reason == "direct":
            chain = None
        else:
            # Parse reason to extract chain
            # Or better: return chain from is_compatible_with()
            chain = adapter_registry.find_adapter_chain(
                source_port.data.type_cls,
                target_port.data.type_cls
            )
        
        return (True, reason, chain)
    
    def create_connection(
        self,
        source_port: PortOutlet,
        target_port: PortInlet,
        adapter_registry: AdapterRegistry
    ) -> Connection:
        """Create connection with automatic adapter chain"""
        can_connect, reason, chain = self.can_connect(
            source_port, target_port, adapter_registry
        )
        
        if not can_connect:
            raise ValueError(f"Cannot connect: {reason}")
        
        # Create connection
        connection = Connection(
            source=source_port,
            target=target_port,
            adapter_chain=chain
        )
        
        return connection

class Connection:
    def __init__(
        self,
        source: PortOutlet,
        target: PortInlet,
        adapter_chain: List[type[IType]] | None = None
    ):
        self.source = source
        self.target = target
        self.adapter_chain = adapter_chain
    
    def transfer_data(self, adapter_registry: AdapterRegistry) -> None:
        """Transfer data from source to target with conversion"""
        # Get value from source
        value = self.source.data.get_for_transfer()
        
        # Apply adapter chain if exists
        if self.adapter_chain:
            value = adapter_registry.apply_chain(value, self.adapter_chain)
        
        # Set on target
        source_id = self.source.node.node_id
        self.target.data.set_value(value, source_id=source_id)
```

### Performance Considerations

**Caching Strategy:**
- Cache resolved chains in AdapterRegistry
- Invalidate cache when adapters are registered/unregistered
- Consider per-connection caching of chain instances

**Optimization:**
- Limit max_depth to prevent expensive searches (3 is reasonable)
- Use BFS for shortest path (fewer adapter calls)
- Consider A* with heuristic for very large adapter graphs

**Memory:**
- Cache size grows O(n²) with number of types
- Consider LRU cache with bounded size
- Clear cache on hot-reload

### Example Adapter Definitions

```python
@adapter(description="Convert Temperature to FLOAT", converts_from=Temperature, converts_to=FLOAT)
class TemperatureToFloat(BaseAdapter):
    """Convert Temperature to FLOAT"""

    @override
    def convert(self, value: Temperature) -> float:
        # Temperature extends FLOAT, just return as FLOAT
        return value.value

@adapter(description="Convert FLOAT to STRING", converts_from=FLOAT, converts_to=STRING)
class FloatToString(BaseAdapter):
    """Convert FLOAT to STRING"""

    @override
    def convert(self, value: float) -> str:
        return str(value)

# With these registered:
# Temperature → STRING chain: [Temperature, FLOAT, STRING]
```

### UI Feedback for Adapter Chains

**Visual Indicators:**
- Different connection colors for direct vs adapted connections
- Tooltip showing adapter chain: "Temperature → FLOAT → STRING"
- Badge on connection showing number of adapters
- Warning icon if chain is long (>2 adapters)

**Example:**
```
[Temperature Outlet] ═══[🔄]═══[🔄]═══> [STRING Inlet]
                        ^T→F  ^F→S
Tooltip: "2 adapters: Temperature→FLOAT→STRING"
```

---

## Implementation Priorities

### Phase 1: Widget Bindings (Immediate)
1. ✅ SimpleWidget already works—no changes needed
2. Update PropertyBinding to use get_value()/update_property() appropriately
3. Add field type detection in binding sync methods
4. Test with all four field types

### Phase 2: Adapter Chain (Short Term)
1. Implement AdapterRegistry.find_adapter_chain() with BFS
2. Add caching for resolved chains
3. Update is_compatible_with() to use chain finding (already done!)
4. Test with 2-3 adapter chains

### Phase 3: Connection System (Medium Term)
1. Update ConnectionManager to use compatibility checking
2. Store adapter chain in Connection objects
3. Apply chain during data transfer
4. Add UI feedback for adapted connections

### Phase 4: Optimization (Long Term)
1. Profile chain resolution performance
2. Add bounded LRU cache for chains
3. Consider pre-computing common chains
4. Add metrics/logging for adapter usage

---

## Testing Strategy

### Widget Bindings
- Unit tests for each field type with SimpleWidget
- Integration tests for PropertyBinding with all field types
- Manual UI tests for complex widgets (pooled display, array editor)
- Performance tests with rapid value updates

### Adapter Chains
- Unit tests for BFS algorithm
- Tests for cycle detection
- Tests for max_depth limiting
- Tests for cache invalidation
- Integration tests with actual adapter classes

### End-to-End
- Connect nodes with adapter chains
- Verify data flows correctly
- Verify UI shows correct indicators
- Test hot-reload scenarios
- Test performance with large graphs

---

## Open Questions

1. **Array Element Editing**: Should we support element-wise updates in future?
   - Pro: More granular control for widgets
   - Con: Complex API, unclear mutation semantics
   - Recommendation: Defer until clear use case emerges

2. **Adapter Costs**: Should some adapters be preferred over others?
   - Pro: Can guide users to better conversions
   - Con: Adds complexity to chain resolution
   - Recommendation: Start with length-based cost, extend if needed

3. **Bidirectional Adapters**: Should adapters work both ways?
   - Pro: Reduces adapter count (FLOAT↔STRING needs one adapter)
   - Con: Not all conversions are reversible
   - Recommendation: Keep unidirectional, more explicit

4. **Dynamic Adapter Registration**: Should adapters be hot-reloadable?
   - Pro: Better developer experience
   - Con: Cache invalidation complexity
   - Recommendation: Yes, but clear cache on registration

5. **Widget Type Validation**: Should widgets validate field types at creation?
   - Pro: Catch errors early
   - Con: Less flexible
   - Recommendation: Yes, fail fast with clear error messages
