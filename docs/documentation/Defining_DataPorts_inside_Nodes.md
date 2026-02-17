# Node Developer Manual for Data Fields and Ports

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
    def init(self):
        
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
def worker(self, context: ExecutionContext):
    threshold = self.value('threshold')  # 0.5 (float)
    count = self.value('count')          # 10 (int)
    name = self.value('name')            # "untitled" (str)
    enabled = self.value('enabled')      # True (bool)
```

### 2. Complex Type Inlets

```python
from haywire.libraries.core.types.mesh import MeshData

class MeshProcessorNode(BaseNode):
    def init(self):
        
        # Complex type with default
        self.add(MeshData.as_inlet(
            id='mesh',
            label='Input Mesh',
            default={'vertices': [], 'faces': []}
        ))
```

**Worker access:**
```python
def worker(self, context: ExecutionContext):
    mesh = self.value('mesh')  # MeshData instance
    
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
    def init(self):
        
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
def worker(self, context: ExecutionContext):
    # Get as Python list - already unwrapped!
    numbers = self.value('numbers')  # [5.0, 2.0, 8.0, 1.0]
    
    # Process as normal Python list
    sorted_numbers = sorted(numbers)
    min_value = min(numbers)
    total = sum(numbers)
    
    # Meshes also as list
    meshes = self.value('meshes')  # [MeshData(...), MeshData(...)]
    for mesh in meshes:
        process(mesh)
```

### 4. Pooled Inlets (Multi-Source)

```python
from haywire.libraries.core.types.pooled import PooledType
from haywire.libraries.core.types.specs import FLOAT

class AverageNode(BaseNode):
    def init(self):
        
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
def worker(self, context: ExecutionContext):
    # Get as dict with source IDs
    values = self.value('values')
    # Returns: {"node_upstream_1": 20.0, "node_upstream_2": 25.0, "node_upstream_3": 30.0}
    
    # Calculate average
    if values:
        average = sum(values.values()) / len(values)
        count = len(values)
    else:
        average = 0.0
        count = 0
    
    self.out('average', average)
    self.out('count', count)
    
    # Or access the field directly for helper methods:
    inlet = self.value['values']
    values_list = inlet.data.get_values_list()  # [20.0, 25.0, 30.0]
    source_ids = inlet.data.get_source_ids()    # ["node_upstream_1", ...]
```

---

## Creating Outlets

### Primitive Outlets

```python
class MathNode(BaseNode):
    def init(self):
        
        self.add(FLOAT.as_inlet(id='a', default=0.0))
        self.add(FLOAT.as_inlet(id='b', default=0.0))
        
        # Multiple outputs
        self.add(FLOAT.as_outlet(id='sum'))
        self.add(FLOAT.as_outlet(id='difference'))
        self.add(FLOAT.as_outlet(id='product'))
        self.add(FLOAT.as_outlet(id='quotient'))
    
    def worker(self, context: ExecutionContext):
        a = self.value('a')
        b = self.value('b')
        
        # Set all outputs - no wrapping needed!
        self.out('sum', a + b)
        self.out('difference', a - b)
        self.out('product', a * b)
        if b != 0:
            self.out('quotient', a / b)
```

### Array Outlets

```python
class FilterNode(BaseNode):
    def init(self):
        
        self.add(ArrayType[FLOAT].as_inlet(id='numbers'))
        self.add(FLOAT.as_inlet(id='threshold', default=0.0))
        
        # Array output
        self.add(ArrayType[FLOAT].as_outlet(id='filtered'))
    
    def worker(self, context: ExecutionContext):
        numbers = self.value('numbers')  # [1.0, 5.0, 2.0, 8.0]
        threshold = self.value('threshold')  # 3.0
        
        # Filter
        filtered = [n for n in numbers if n > threshold]  # [5.0, 8.0]
        
        # Set output - just pass the list!
        self.out('filtered', filtered)
```

### Complex Type Outlets

```python
class MeshGeneratorNode(BaseNode):
    def init(self):
        
        self.add(INT.as_inlet(id='subdivisions', default=1))
        self.add(MeshData.as_outlet(id='mesh'))
    
    def worker(self, context: ExecutionContext):
        subdivisions = self.value('subdivisions')
        
        # Generate mesh
        mesh = MeshData(
            vertices=generate_vertices(subdivisions),
            faces=generate_faces(subdivisions)
        )
        
        # Set output - just pass the instance!
        self.out('mesh', mesh)
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
    
    def worker(self, context: ExecutionContext):
        celsius = self.value('celsius')  # e.g., 25.0
        fahrenheit = (celsius * 9/5) + 32  # 77.0
        self.out('fahrenheit', fahrenheit)
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
    def init(self):
        
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
    
    def worker(self, context: ExecutionContext):
        numbers = self.value('numbers')  # [1.0, 2.0, 3.0, 4.0, 5.0]
        
        if not numbers:
            # Handle empty array
            self.out('min', 0.0)
            self.out('max', 0.0)
            self.out('average', 0.0)
            self.out('sum', 0.0)
            self.out('count', 0)
            return
        
        # Calculate statistics
        self.out('min', min(numbers))
        self.out('max', max(numbers))
        self.out('average', sum(numbers) / len(numbers))
        self.out('sum', sum(numbers))
        self.out('count', len(numbers))
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
    def init(self):
        
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
    
    def worker(self, context: ExecutionContext):
        # Get all meshes from different sources
        meshes_dict = self.value('meshes')
        # Returns: {"node1": MeshData(...), "node2": MeshData(...), ...}
        
        if not meshes_dict:
            # No meshes connected
            self.out('combined', MeshData(vertices=[], faces=[]))
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
        self.out('combined', combined)
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
    def init(self):
        
        self.add(BOOL.as_inlet(id='condition', default=True))
        self.add(FLOAT.as_inlet(id='if_true', default=1.0))
        self.add(FLOAT.as_inlet(id='if_false', default=0.0))
        
        self.add(FLOAT.as_outlet(id='result'))
    
    def worker(self, context: ExecutionContext):
        condition = self.value('condition')  # True or False
        if_true = self.value('if_true')      # 1.0
        if_false = self.value('if_false')    # 0.0
        
        result = if_true if condition else if_false
        self.out('result', result)
```

---

## Dynamic Port Reconfiguration (`rejig`)

Use the `rejig()` context manager to dynamically add/remove ports at runtime. Ports re-added inside the block keep their connections; ports not re-added are destroyed.

```python
def hb_reconfigure(self, port=None, *args):
    count = self.value('port_count')

    with self.rejig(include=r'^dynamic_'):
        # Only ports matching '^dynamic_' are flagged for removal.
        # Static ports are untouched.
        for i in range(count):
            self.add(FLOAT.as_inlet(f'dynamic_inlet_{i}', label=f'Input {i}'))
            self.add(FLOAT.as_outlet(f'dynamic_outlet_{i}', label=f'Output {i}'))
```

Trigger reconfiguration via an `on_change` callback on a config port:

```python
def init(self):
    self.add(INT.as_inlet(
        'port_count', label='Port Count', default=2,
        on_change='hb_reconfigure'
    ))
    self._build_dynamic_ports(2)
```

See the [Creating Nodes](Creating_Nodes.md) guide for a complete example.

---

## Port Groups and Sections

### Groups

Create collapsible port containers in the node UI:

```python
with self.group(GROUP.as_inlet('advanced', label='Advanced Options')):
    self.add(FLOAT.as_inlet('epsilon', default=0.001))
    self.add(FLOAT.as_inlet('tolerance', default=0.1))
```

Child ports are hidden when the group is collapsed. Connections are preserved via ghost pins.

### Sections

Organize ports into property panel categories (hidden from node body):

```python
with self.section('validation'):
    self.add(FLOAT.as_inlet('min_value', default=0.0))
    self.add(FLOAT.as_inlet('max_value', default=100.0))
```

---

## Common Patterns

### Pattern 1: Input Validation

```python
def worker(self, context: ExecutionContext):
    value = self.value('value')
    
    # Validate range
    if value < 0 or value > 100:
        # Set error state
        self.error_info = NodeErrorInfo(
            message=f"Value {value} out of range [0, 100]"
        )
        return
    
    # Process valid value
    result = process(value)
    self.out('result', result)
```

### Pattern 2: Optional Inputs

```python
def worker(self, context: ExecutionContext):
    # Check if inlet is connected
    if self.inlets['optional_input'].is_connected:
        value = self.value('optional_input')
        result = process_with(value)
    else:
        result = process_without()
    
    self.out('result', result)
```

### Pattern 3: Array Element Processing

```python
def worker(self, context: ExecutionContext):
    numbers = self.value('numbers')  # [1.0, 2.0, 3.0]
    factor = self.value('factor')    # 2.0
    
    # Process each element
    scaled = [n * factor for n in numbers]  # [2.0, 4.0, 6.0]
    
    self.out('scaled', scaled)
```

### Pattern 4: Error Handling

```python
def worker(self, context: ExecutionContext):
    try:
        value = self.value('value')
        result = risky_operation(value)
        
        self.out('result', result)
        self.out('success', True)
        self.out('error', '')
        
    except ValueError as e:
        self.out('result', 0.0)
        self.out('success', False)
        self.out('error', str(e))
    
    except Exception as e:
        self.error_info = NodeErrorInfo(message=str(e))
        return
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
value = self.value('inlet_id')

# Write (always unwrapped)
self.out('outlet_id', value)

# Check connection
if self.ports['inlet_id'].is_connected:
    ...
```

### Field-Specific Helpers

```python
# Pooled helpers
inlet = self.ports['pooled_inlet']
values_list = inlet.data.get_values_list()  # [v1, v2, v3]
source_ids = inlet.data.get_source_ids()    # ["n1", "n2", "n3"]

# Array helpers
inlet = self.ports['array_inlet']
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
value = self.value('my_inlet')  # ❌ Doesn't match!

# Correct
self.add(FLOAT.as_inlet(id='my_inlet', ...))
value = self.value('my_inlet')  # ✅ Matches
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
