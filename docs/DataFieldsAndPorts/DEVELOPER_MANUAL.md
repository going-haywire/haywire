# Node Developer Manual - New Architecture

## Quick Start

Creating nodes with the new architecture is simpler than ever:

```python
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.libraries.core.types.specs import FLOAT
from haywire.libraries.core.types.array import ArrayType

@node(label='Add Numbers')
class AddNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Create inlets - simple!
        self.add(FLOAT.as_inlet(id='a', default=0.0))
        self.add(FLOAT.as_inlet(id='b', default=0.0))
        
        # Create outlet
        self.add(FLOAT.as_outlet(id='result'))
    
    def worker(self, context):
        # Read values - already unwrapped!
        a = self.inlet('a')  # Returns: 42.0 (not FLOAT(42.0))
        b = self.inlet('b')  # Returns: 3.0
        
        # Compute
        result = a + b  # 45.0
        
        # Set output - no wrapping needed!
        self.set_outlet('result', result)  # Just pass the float!
```

**Key changes from old system:**
- ✅ Direct primitive operations
- ✅ Clean, Pythonic code

---

## Creating Different Types of Inlets

### 1. Primitive Inlets

```python
from haywire.libraries.core.types.specs import FLOAT, INT, STRING, BOOL

class MyNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Float with default
        self.add(FLOAT.as_inlet(
            id='threshold',
            label='Threshold',
            default=0.5
        ))
        
        # Integer
        self.add(INT.as_inlet(
            id='count',
            label='Count',
            default=10
        ))
        
        # String
        self.add(STRING.as_inlet(
            id='name',
            label='Name',
            default='untitled'
        ))
        
        # Boolean
        self.add(BOOL.as_inlet(
            id='enabled',
            label='Enabled',
            default=True
        ))
```

**Worker access:**
```python
def worker(self, context):
    threshold = self.inlet('threshold')  # 0.5 (float)
    count = self.inlet('count')          # 10 (int)
    name = self.inlet('name')            # "untitled" (str)
    enabled = self.inlet('enabled')      # True (bool)
```

### 2. Complex Type Inlets

```python
from haywire.libraries.core.types.mesh import MeshData

class MeshProcessorNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Complex type with default
        self.add(MeshData.as_inlet(
            id='mesh',
            label='Input Mesh',
            default={'vertices': [], 'faces': []}
        ))
```

**Worker access:**
```python
def worker(self, context):
    mesh = self.inlet('mesh')  # MeshData instance
    
    # Access attributes directly
    vertices = mesh.vertices
    faces = mesh.faces
    vertex_count = len(vertices)
```

### 3. Array Inlets

```python
from haywire.libraries.core.types.array import ArrayType
from haywire.libraries.core.types.specs import FLOAT
from haywire.libraries.core.types.mesh import MeshData

class SortNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Array of primitives
        self.add(ArrayType[FLOAT].as_inlet(
            id='numbers',
            label='Numbers',
            default=[5.0, 2.0, 8.0, 1.0]
        ))
        
        # Array of complex types
        self.add(ArrayType[MeshData].as_inlet(
            id='meshes',
            label='Mesh Array',
            default=[]
        ))
```

**Worker access:**
```python
def worker(self, context):
    # Get as Python list - already unwrapped!
    numbers = self.inlet('numbers')  # [5.0, 2.0, 8.0, 1.0]
    
    # Process as normal Python list
    sorted_numbers = sorted(numbers)
    min_value = min(numbers)
    total = sum(numbers)
    
    # Meshes also as list
    meshes = self.inlet('meshes')  # [MeshData(...), MeshData(...)]
    for mesh in meshes:
        process(mesh)
```

### 4. Pooled Inlets (Multi-Source)

```python
from haywire.libraries.core.types.pooled import PooledType
from haywire.libraries.core.types.specs import FLOAT

class AverageNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Pooled inlet - accepts multiple connections!
        self.add(PooledType[FLOAT].as_inlet(
            id='values',
            label='Values to Average'
        ))
        
        self.add(FLOAT.as_outlet(id='average'))
        self.add(INT.as_outlet(id='count'))
```

**Worker access:**
```python
def worker(self, context):
    # Get as dict with source IDs
    values = self.inlet('values')
    # Returns: {"node_upstream_1": 20.0, "node_upstream_2": 25.0, "node_upstream_3": 30.0}
    
    # Calculate average
    if values:
        average = sum(values.values()) / len(values)
        count = len(values)
    else:
        average = 0.0
        count = 0
    
    self.set_outlet('average', average)
    self.set_outlet('count', count)
    
    # Or access the field directly for helper methods:
    inlet = self.inlets['values']
    values_list = inlet.data.get_values_list()  # [20.0, 25.0, 30.0]
    source_ids = inlet.data.get_source_ids()    # ["node_upstream_1", ...]
```

---

## Creating Outlets

### Primitive Outlets

```python
class MathNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(FLOAT.as_inlet(id='a', default=0.0))
        self.add(FLOAT.as_inlet(id='b', default=0.0))
        
        # Multiple outputs
        self.add(FLOAT.as_outlet(id='sum'))
        self.add(FLOAT.as_outlet(id='difference'))
        self.add(FLOAT.as_outlet(id='product'))
        self.add(FLOAT.as_outlet(id='quotient'))
    
    def worker(self, context):
        a = self.inlet('a')
        b = self.inlet('b')
        
        # Set all outputs - no wrapping needed!
        self.set_outlet('sum', a + b)
        self.set_outlet('difference', a - b)
        self.set_outlet('product', a * b)
        if b != 0:
            self.set_outlet('quotient', a / b)
```

### Array Outlets

```python
class FilterNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(ArrayType[FLOAT].as_inlet(id='numbers'))
        self.add(FLOAT.as_inlet(id='threshold', default=0.0))
        
        # Array output
        self.add(ArrayType[FLOAT].as_outlet(id='filtered'))
    
    def worker(self, context):
        numbers = self.inlet('numbers')  # [1.0, 5.0, 2.0, 8.0]
        threshold = self.inlet('threshold')  # 3.0
        
        # Filter
        filtered = [n for n in numbers if n > threshold]  # [5.0, 8.0]
        
        # Set output - just pass the list!
        self.set_outlet('filtered', filtered)
```

### Complex Type Outlets

```python
class MeshGeneratorNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(INT.as_inlet(id='subdivisions', default=1))
        self.add(MeshData.as_outlet(id='mesh'))
    
    def worker(self, context):
        subdivisions = self.inlet('subdivisions')
        
        # Generate mesh
        mesh = MeshData(
            vertices=generate_vertices(subdivisions),
            faces=generate_faces(subdivisions)
        )
        
        # Set output - just pass the instance!
        self.set_outlet('mesh', mesh)
```

---

## Complete Examples

### Example 1: Temperature Converter

```python
@node(
    label='Celsius to Fahrenheit',
    description='Converts temperature from Celsius to Fahrenheit',
    search_tags=['temperature', 'convert', 'celsius', 'fahrenheit'],
    menu='conversion/temperature'
)
class CelsiusToFahrenheitNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        self.add(FLOAT.as_inlet(
            id='celsius',
            label='Celsius',
            default=0.0
        ))
        
        self.add(FLOAT.as_outlet(
            id='fahrenheit',
            label='Fahrenheit'
        ))
    
    def worker(self, context):
        celsius = self.inlet('celsius')  # e.g., 25.0
        fahrenheit = (celsius * 9/5) + 32  # 77.0
        self.set_outlet('fahrenheit', fahrenheit)
```

### Example 2: Array Statistics

```python
@node(
    label='Array Statistics',
    description='Calculate statistics for an array of numbers',
    search_tags=['array', 'statistics', 'min', 'max', 'average'],
    menu='arrays/analysis'
)
class ArrayStatsNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        self.add(ArrayType[FLOAT].as_inlet(
            id='numbers',
            label='Numbers',
            default=[1.0, 2.0, 3.0, 4.0, 5.0]
        ))
        
        self.add(FLOAT.as_outlet(id='min', label='Minimum'))
        self.add(FLOAT.as_outlet(id='max', label='Maximum'))
        self.add(FLOAT.as_outlet(id='average', label='Average'))
        self.add(FLOAT.as_outlet(id='sum', label='Sum'))
        self.add(INT.as_outlet(id='count', label='Count'))
    
    def worker(self, context):
        numbers = self.inlet('numbers')  # [1.0, 2.0, 3.0, 4.0, 5.0]
        
        if not numbers:
            # Handle empty array
            self.set_outlet('min', 0.0)
            self.set_outlet('max', 0.0)
            self.set_outlet('average', 0.0)
            self.set_outlet('sum', 0.0)
            self.set_outlet('count', 0)
            return
        
        # Calculate statistics
        self.set_outlet('min', min(numbers))
        self.set_outlet('max', max(numbers))
        self.set_outlet('average', sum(numbers) / len(numbers))
        self.set_outlet('sum', sum(numbers))
        self.set_outlet('count', len(numbers))
```

### Example 3: Mesh Combiner (Pooled)

```python
@node(
    label='Combine Meshes',
    description='Combines multiple mesh inputs into one',
    search_tags=['mesh', 'combine', 'merge'],
    menu='geometry/operations'
)
class CombineMeshesNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        # Pooled inlet - accepts multiple mesh connections!
        self.add(PooledType[MeshData].as_inlet(
            id='meshes',
            label='Input Meshes'
        ))
        
        self.add(MeshData.as_outlet(
            id='combined',
            label='Combined Mesh'
        ))
    
    def worker(self, context):
        # Get all meshes from different sources
        meshes_dict = self.inlet('meshes')
        # Returns: {"node1": MeshData(...), "node2": MeshData(...), ...}
        
        if not meshes_dict:
            # No meshes connected
            self.set_outlet('combined', MeshData(vertices=[], faces=[]))
            return
        
        # Combine all meshes
        all_vertices = []
        all_faces = []
        vertex_offset = 0
        
        for mesh in meshes_dict.values():
            # Add vertices
            all_vertices.extend(mesh.vertices)
            
            # Add faces with offset
            for face in mesh.faces:
                offset_face = [v + vertex_offset for v in face]
                all_faces.append(offset_face)
            
            vertex_offset += len(mesh.vertices)
        
        # Create combined mesh
        combined = MeshData(vertices=all_vertices, faces=all_faces)
        self.set_outlet('combined', combined)
```

### Example 4: Conditional Processing

```python
@node(
    label='Conditional Value',
    description='Output different values based on condition',
    search_tags=['if', 'condition', 'branch'],
    menu='logic/conditional'
)
class ConditionalNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(BOOL.as_inlet(id='condition', default=True))
        self.add(FLOAT.as_inlet(id='if_true', default=1.0))
        self.add(FLOAT.as_inlet(id='if_false', default=0.0))
        
        self.add(FLOAT.as_outlet(id='result'))
    
    def worker(self, context):
        condition = self.inlet('condition')  # True or False
        if_true = self.inlet('if_true')      # 1.0
        if_false = self.inlet('if_false')    # 0.0
        
        result = if_true if condition else if_false
        self.set_outlet('result', result)
```

---

## Common Patterns

### Pattern 1: Input Validation

```python
def worker(self, context):
    value = self.inlet('value')
    
    # Validate range
    if value < 0 or value > 100:
        # Set error state
        self.error_info = NodeErrorInfo(
            message=f"Value {value} out of range [0, 100]"
        )
        return
    
    # Process valid value
    result = process(value)
    self.set_outlet('result', result)
```

### Pattern 2: Optional Inputs

```python
def worker(self, context):
    # Check if inlet is connected
    if self.inlets['optional_input'].is_connected:
        value = self.inlet('optional_input')
        result = process_with(value)
    else:
        result = process_without()
    
    self.set_outlet('result', result)
```

### Pattern 3: Array Element Processing

```python
def worker(self, context):
    numbers = self.inlet('numbers')  # [1.0, 2.0, 3.0]
    factor = self.inlet('factor')    # 2.0
    
    # Process each element
    scaled = [n * factor for n in numbers]  # [2.0, 4.0, 6.0]
    
    self.set_outlet('scaled', scaled)
```

### Pattern 4: Error Handling

```python
def worker(self, context):
    try:
        value = self.inlet('value')
        result = risky_operation(value)
        
        self.set_outlet('result', result)
        self.set_outlet('success', True)
        self.set_outlet('error', '')
        
    except ValueError as e:
        self.set_outlet('result', 0.0)
        self.set_outlet('success', False)
        self.set_outlet('error', str(e))
    
    except Exception as e:
        self.error_info = NodeErrorInfo(message=str(e))
        return
```

---

## Key Differences from Old System

### Old System (Manual Wrapping)

```python
# ❌ Old way - lots of boilerplate
def worker(self, context):
    # Manual unwrapping
    a = self.inlets['a'].data.get_container().value
    b = self.inlets['b'].data.get_container().value
    
    # Compute
    result = a + b
    
    # Manual wrapping
    self.outlets['result'].data.set_value(FLOAT(value=result))
```

### New System (Automatic)

```python
# ✅ New way - clean and simple
def worker(self, context):
    # Automatic unwrapping
    a = self.inlet('a')
    b = self.inlet('b')
    
    # Compute
    result = a + b
    
    # Automatic wrapping
    self.set_outlet('result', result)
```

---

## Quick Reference

### Port Creation

```python
# Primitives
FLOAT.as_inlet(id='name', default=0.0)
FLOAT.as_outlet(id='name')

# Complex
MeshData.as_inlet(id='name', default={'vertices': [], 'faces': []})
MeshData.as_outlet(id='name')

# Arrays
ArrayType[FLOAT].as_inlet(id='name', default=[1.0, 2.0])
ArrayType[FLOAT].as_outlet(id='name')

# Pooled (inlet only!)
PooledType[FLOAT].as_inlet(id='name')
```

### Worker Access

```python
# Read (always unwrapped)
value = self.inlet('inlet_id')

# Write (always unwrapped)
self.set_outlet('outlet_id', value)

# Check connection
if self.inlets['inlet_id'].is_connected:
    ...
```

### Field-Specific Helpers

```python
# Pooled helpers
inlet = self.inlets['pooled_inlet']
values_list = inlet.data.get_values_list()  # [v1, v2, v3]
source_ids = inlet.data.get_source_ids()    # ["n1", "n2", "n3"]

# Array helpers
inlet = self.inlets['array_inlet']
item = inlet.data.get_item(0)  # First item
length = len(inlet.data)       # Array length
```

---

## Troubleshooting

### "Inlet not found"

**Problem**: `KeyError: 'inlet_name'`

**Solution**: Check inlet ID matches exactly
```python
# Wrong
self.add(FLOAT.as_inlet(id='myInlet', ...))
value = self.inlet('my_inlet')  # ❌ Doesn't match!

# Correct
self.add(FLOAT.as_inlet(id='my_inlet', ...))
value = self.inlet('my_inlet')  # ✅ Matches
```

### "Cannot connect pooled to outlet"

**Problem**: Trying to create pooled outlet

**Solution**: Pooled is inlet-only
```python
# Wrong
PooledType[FLOAT].as_outlet(id='pool')  # ❌ Raises error!

# Correct
PooledType[FLOAT].as_inlet(id='pool')  # ✅ Inlet only
```

### "Cannot connect array to single"

**Problem**: Connecting array outlet to single-value inlet

**Solution**: Use array inlet
```python
# Wrong
ArrayType[FLOAT].as_outlet(...)  # Array
FLOAT.as_inlet(...)              # Single ❌

# Correct
ArrayType[FLOAT].as_outlet(...)  # Array
ArrayType[FLOAT].as_inlet(...)   # Array ✅
```

---

## Best Practices

1. **Use descriptive IDs**: `'input_temperature'` not `'in1'`
2. **Provide sensible defaults**: Make nodes work without connections
3. **Handle empty collections**: Check `if values:` before processing
4. **Validate inputs**: Check ranges, types, special cases
5. **Set all outputs**: Even in error cases
6. **Use type hints**: Help IDEs and type checkers
7. **Document complex logic**: Add comments explaining non-obvious code

---

## Summary

The new architecture makes node development simpler:

✅ **No manual wrapping/unwrapping**
✅ **Clean, Pythonic API**
✅ **Type-safe port creation**
✅ **Automatic value handling**
✅ **Consistent patterns across all types**

Just use `self.inlet()` to read and `self.set_outlet()` to write - the system handles everything else!
