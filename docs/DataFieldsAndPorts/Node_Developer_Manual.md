# Node Developer Manual

## Creating Inlets and Outlets for Your Nodes

This manual explains how to create different types of inlets and outlets in your Haywire nodes, and how to access and write data from the worker method.

---

## Table of Contents

1. [Basic Concepts](#basic-concepts)
2. [Creating Simple Inlets](#creating-simple-inlets)
3. [Creating Simple Outlets](#creating-simple-outlets)
4. [Creating Pooled Inlets](#creating-pooled-inlets)
5. [Creating Array Inlets and Outlets](#creating-array-inlets-and-outlets)
6. [Accessing Data in Worker Methods](#accessing-data-in-worker-methods)
7. [Writing Data to Outlets](#writing-data-to-outlets)
8. [Complete Examples](#complete-examples)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)

---

## Basic Concepts

### Port Types

Haywire nodes have four types of ports:

1. **Inlets**: Input ports that receive data from upstream nodes
2. **Outlets**: Output ports that send data to downstream nodes
3. **Configs**: Hidden inlets for configuration (no visible pin)
4. **Properties**: Node-specific data (not covered in this guide)

### Field Types

Each inlet/outlet has an underlying DataField that determines how data is stored:

- **PrimitiveField**: Single primitive value (int, float, str, bool)
- **ComplexField**: Single complex object (MeshData, custom dataclasses)
- **PooledField**: Multiple values from different sources (inlet only)
- **ArrayField**: Homogeneous list of values

### Type Classes

Your ports are created using Type classes:

- **Core primitives**: `FLOAT`, `INT`, `STRING`, `BOOL`, `BYTES`
- **Collections**: `LIST`, `DICT`
- **Control flow**: `EXEC`, `CALLBACK`
- **Custom types**: Your own `@type` decorated classes

---

## Creating Simple Inlets

### Primitive Type Inlets

Use the `Type.as_inlet()` class method to create primitive inlets:

```python
from haywire.libraries.core.types.specs import FLOAT, INT, STRING, BOOL

class MyNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Float inlet with default value
        self.add(FLOAT.as_inlet(
            id='input_value',
            label='Input Value',
            default=0.0  # Default when not connected
        ))
        
        # Integer inlet
        self.add(INT.as_inlet(
            id='count',
            label='Count',
            default=10
        ))
        
        # String inlet
        self.add(STRING.as_inlet(
            id='name',
            label='Name',
            default='untitled'
        ))
        
        # Boolean inlet
        self.add(BOOL.as_inlet(
            id='enabled',
            label='Enabled',
            default=True
        ))
```

### Custom Widget Configuration

Inlets can be configured with custom widgets:

```python
# Slider widget for float input
self.add(FLOAT.as_inlet(
    id='threshold',
    label='Threshold',
    default=0.5,
    widget='core:widget:slider.widget',
    ui={'properties': {
        'min': 0.0,
        'max': 1.0,
        'step': 0.01
    }}
))

# Dropdown selection for string
self.add(STRING.as_inlet(
    id='mode',
    label='Mode',
    default='automatic',
    widget='core:widget:select.widget',
    ui={'properties': {
        'options': ['automatic', 'manual', 'custom']
    }}
))

# Toggle switch for boolean
self.add(BOOL.as_inlet(
    id='invert',
    label='Invert Result',
    default=False,
    widget='core:widget:switch.widget',
    ui={'properties': {
        'text': 'Invert'
    }}
))
```

### Complex Type Inlets

For custom data types (like MeshData), use the same pattern:

```python
from haywire.libraries.core.types.mesh_data import MeshData

self.add(MeshData.as_inlet(
    id='mesh_input',
    label='Input Mesh',
    default={'vertices': [], 'faces': []}  # Constructor kwargs
))
```

### Derived Type Inlets

Derived types inherit from base types and use the same API:

```python
from haywire.libraries.core.types.specs import Temperature  # Extends FLOAT

self.add(Temperature.as_inlet(
    id='temperature',
    label='Temperature',
    default=20.0  # Uses inherited FLOAT behavior
))
```

---

## Creating Simple Outlets

### Primitive Type Outlets

Outlets use the same type classes but typically don't need defaults:

```python
class MyNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Float outlet
        self.add(FLOAT.as_outlet(
            id='result',
            label='Result'
        ))
        
        # String outlet
        self.add(STRING.as_outlet(
            id='message',
            label='Message'
        ))
```

### Complex Type Outlets

```python
self.add(MeshData.as_outlet(
    id='mesh_output',
    label='Output Mesh'
))
```

### Multiple Outlets

Nodes can have any number of outlets:

```python
# Math node with multiple results
self.add(FLOAT.as_outlet(id='sum', label='Sum'))
self.add(FLOAT.as_outlet(id='difference', label='Difference'))
self.add(FLOAT.as_outlet(id='product', label='Product'))
self.add(FLOAT.as_outlet(id='quotient', label='Quotient'))
```

---

## Creating Pooled Inlets

### What Are Pooled Inlets?

Pooled inlets accept connections from **multiple upstream nodes** and aggregate their values into a dictionary or list. Perfect for:

- Averaging multiple sensor readings
- Combining meshes from multiple sources
- Aggregating results from parallel computations

### Basic Pooled Inlet

Use the `Pooled` helper class:

```python
from haywire.core.types.port_helpers import Pooled

class AverageNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Pooled float inlet - accepts multiple connections
        self.add(Pooled.as_inlet(
            element_type_cls=FLOAT,
            id='values',
            label='Input Values'
        ))
        
        # Single output
        self.add(FLOAT.as_outlet(
            id='average',
            label='Average'
        ))
```

### Pooled Complex Types

```python
# Pool multiple mesh objects
self.add(Pooled.as_inlet(
    element_type_cls=MeshData,
    id='mesh_collection',
    label='Mesh Collection'
))
```

### Important Notes About Pooled Inlets

⚠️ **Restrictions:**
- Pooled inlets **cannot be used with outlets** (inlet only!)
- Pooled inlets **cannot connect to other pooled inlets**
- Pooled inlets **cannot connect to array outlets**
- Pooled inlets are **read-only from widgets**

✅ **Features:**
- Each source is tracked by its node ID
- Sources can be updated independently
- Sources can be disconnected individually
- Access as dict or list in worker

---

## Creating Array Inlets and Outlets

### What Are Array Inlets/Outlets?

Array ports handle **homogeneous lists** of a specific type. Perfect for:

- Lists of numbers to sort or process
- Collections of objects to filter
- Batch operations on similar data

### Basic Array Inlet

Use the `ArrayList` helper class:

```python
from haywire.core.types.port_helpers import ArrayList

class SortNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Array of floats
        self.add(ArrayList.as_inlet(
            element_type_cls=FLOAT,
            id='numbers',
            label='Numbers',
            default=[5.0, 2.0, 8.0, 1.0]
        ))
        
        # Array output
        self.add(ArrayList.as_outlet(
            element_type_cls=FLOAT,
            id='sorted_numbers',
            label='Sorted Numbers'
        ))
```

### Array of Complex Types

```python
# Array of mesh objects
self.add(ArrayList.as_inlet(
    element_type_cls=MeshData,
    id='mesh_array',
    label='Mesh Array',
    default=[]  # Empty array
))

self.add(ArrayList.as_outlet(
    element_type_cls=MeshData,
    id='filtered_meshes',
    label='Filtered Meshes'
))
```

### Important Notes About Arrays

⚠️ **Restrictions:**
- Arrays **must connect to other arrays** with compatible element types
- Arrays **cannot connect to single-value ports**
- Arrays **cannot connect to pooled inlets**
- Array widgets are **advanced/rare** (usually for read-only display)

✅ **Features:**
- Type-safe: Array[FLOAT] only connects to Array[FLOAT] (or compatible)
- Efficient storage: Elements are unwrapped internally
- Convenient access: Worker gets native Python list

---

## Accessing Data in Worker Methods

### The `self.inlet()` Helper

The primary way to read inlet values is via `self.inlet(id)`:

```python
def worker(self, context: dict) -> dict | None:
    # Simple primitive access
    value = self.inlet('input_value')  # Returns: 42.0
    count = self.inlet('count')        # Returns: 10
    name = self.inlet('name')          # Returns: 'hello'
    enabled = self.inlet('enabled')    # Returns: True
```

### Accessing Different Field Types

#### Primitive Values

```python
def worker(self, context: dict) -> dict | None:
    # Float inlet - returns unwrapped float
    temperature = self.inlet('temperature')  # 23.5
    
    # Integer inlet - returns unwrapped int
    count = self.inlet('count')  # 42
    
    # String inlet - returns unwrapped string
    mode = self.inlet('mode')  # "automatic"
    
    # Boolean inlet - returns unwrapped bool
    invert = self.inlet('invert')  # True
```

#### Complex Objects

```python
def worker(self, context: dict) -> dict | None:
    # Complex type inlet - returns the instance
    mesh = self.inlet('mesh_input')  # Returns: MeshData(...)
    
    # Access attributes directly
    vertices = mesh.vertices
    faces = mesh.faces
    vertex_count = len(vertices)
```

#### Pooled Values

```python
def worker(self, context: dict) -> dict | None:
    # Pooled inlet - returns dict of values
    values = self.inlet('values')
    # Returns: {"node1": 20.0, "node2": 25.0, "node3": 30.0}
    
    # Calculate average
    if values:
        average = sum(values.values()) / len(values)
    else:
        average = 0.0
    
    # Or use the helper methods on the inlet directly
    inlet = self.inlets['values']
    values_list = inlet.data.get_values_list()  # [20.0, 25.0, 30.0]
    source_ids = inlet.data.get_source_ids()    # ["node1", "node2", "node3"]
```

#### Array Values

```python
def worker(self, context: dict) -> dict | None:
    # Array inlet - returns list of values
    numbers = self.inlet('numbers')
    # Returns: [5.0, 2.0, 8.0, 1.0]
    
    # Process as normal Python list
    sorted_numbers = sorted(numbers)
    min_value = min(numbers)
    max_value = max(numbers)
    sum_total = sum(numbers)
```

### Checking for Connected Data

```python
def worker(self, context: dict) -> dict | None:
    # Check if inlet is connected
    if self.inlets['optional_input'].is_connected:
        value = self.inlet('optional_input')
        # Process value
    else:
        value = 0.0  # Use default
```

### Error Handling

```python
def worker(self, context: dict) -> dict | None:
    try:
        value = self.inlet('input_value')
        result = 1.0 / value  # Might raise ZeroDivisionError
    except KeyError:
        # Inlet doesn't exist
        return None
    except ZeroDivisionError:
        # Handle division by zero
        result = float('inf')
    
    self.set_outlet('result', result)
```

---

## Writing Data to Outlets

### The `self.set_outlet()` Helper

The primary way to write outlet values is via `self.set_outlet(id, value)`:

```python
def worker(self, context: dict) -> dict | None:
    # Read inputs
    a = self.inlet('input_a')
    b = self.inlet('input_b')
    
    # Compute result
    result = a + b
    
    # Write to outlet
    self.set_outlet('result', result)  # Automatically wraps in FLOAT
    
    return None
```

### Writing Different Types

#### Primitive Values

```python
def worker(self, context: dict) -> dict | None:
    # Write float
    self.set_outlet('float_out', 42.0)
    
    # Write int
    self.set_outlet('int_out', 10)
    
    # Write string
    self.set_outlet('string_out', 'success')
    
    # Write boolean
    self.set_outlet('bool_out', True)
```

#### Complex Objects

```python
def worker(self, context: dict) -> dict | None:
    # Create new mesh
    mesh = MeshData(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        faces=[[0, 1, 2]]
    )
    
    # Write to outlet
    self.set_outlet('mesh_output', mesh)
```

#### Arrays

```python
def worker(self, context: dict) -> dict | None:
    # Read array input
    numbers = self.inlet('numbers')
    
    # Process
    sorted_numbers = sorted(numbers)
    
    # Write array output
    self.set_outlet('sorted_numbers', sorted_numbers)
    # Automatically wraps as [FLOAT(1), FLOAT(2), FLOAT(5), FLOAT(8)]
```

### Multiple Outputs

```python
def worker(self, context: dict) -> dict | None:
    a = self.inlet('input_a')
    b = self.inlet('input_b')
    
    # Set multiple outlets
    self.set_outlet('sum', a + b)
    self.set_outlet('difference', a - b)
    self.set_outlet('product', a * b)
    if b != 0:
        self.set_outlet('quotient', a / b)
```

### Conditional Outputs

```python
def worker(self, context: dict) -> dict | None:
    value = self.inlet('input_value')
    threshold = self.inlet('threshold')
    
    if value > threshold:
        self.set_outlet('high', value)
        self.set_outlet('passed', True)
    else:
        self.set_outlet('low', value)
        self.set_outlet('passed', False)
```

---

## Complete Examples

### Example 1: Simple Math Node

```python
@node(
    label='Add Numbers',
    description='Adds two numbers together',
    search_tags=['math', 'add', 'arithmetic'],
    menu='math/basic'
)
class AddNode(BaseNode):
    """Adds two float values"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Configuration
        self.behavior.is_data_node = True
        
        # Inlets
        self.add(FLOAT.as_inlet(
            id='a',
            label='A',
            default=0.0
        ))
        
        self.add(FLOAT.as_inlet(
            id='b',
            label='B',
            default=0.0
        ))
        
        # Outlet
        self.add(FLOAT.as_outlet(
            id='result',
            label='Result'
        ))
    
    def worker(self, context: dict) -> dict | None:
        # Read inputs
        a = self.inlet('a')  # Returns: 5.0
        b = self.inlet('b')  # Returns: 3.0
        
        # Compute
        result = a + b  # 8.0
        
        # Write output
        self.set_outlet('result', result)
        
        return None
```

### Example 2: Array Processing Node

```python
@node(
    label='Sort Numbers',
    description='Sorts an array of numbers',
    search_tags=['array', 'sort', 'order'],
    menu='arrays/processing'
)
class SortNode(BaseNode):
    """Sorts an array of numbers in ascending or descending order"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        # Array input
        self.add(ArrayList.as_inlet(
            element_type_cls=FLOAT,
            id='numbers',
            label='Numbers',
            default=[5.0, 2.0, 8.0, 1.0]
        ))
        
        # Reverse order option
        self.add(BOOL.as_inlet(
            id='reverse',
            label='Descending',
            default=False
        ))
        
        # Array output
        self.add(ArrayList.as_outlet(
            element_type_cls=FLOAT,
            id='sorted',
            label='Sorted Numbers'
        ))
    
    def worker(self, context: dict) -> dict | None:
        # Read inputs
        numbers = self.inlet('numbers')   # Returns: [5.0, 2.0, 8.0, 1.0]
        reverse = self.inlet('reverse')   # Returns: False
        
        # Sort
        sorted_numbers = sorted(numbers, reverse=reverse)
        # Result: [1.0, 2.0, 5.0, 8.0]
        
        # Write output
        self.set_outlet('sorted', sorted_numbers)
        
        return None
```

### Example 3: Pooled Aggregation Node

```python
@node(
    label='Average Values',
    description='Calculates average of multiple input values',
    search_tags=['math', 'average', 'aggregate', 'mean'],
    menu='math/aggregation'
)
class AverageNode(BaseNode):
    """Averages values from multiple sources"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        # Pooled inlet - accepts multiple connections
        self.add(Pooled.as_inlet(
            element_type_cls=FLOAT,
            id='values',
            label='Values to Average'
        ))
        
        # Outputs
        self.add(FLOAT.as_outlet(
            id='average',
            label='Average'
        ))
        
        self.add(INT.as_outlet(
            id='count',
            label='Count'
        ))
    
    def worker(self, context: dict) -> dict | None:
        # Read pooled input
        values = self.inlet('values')
        # Returns: {"node1": 20.0, "node2": 25.0, "node3": 30.0}
        
        # Calculate average
        if values:
            average = sum(values.values()) / len(values)
            count = len(values)
        else:
            average = 0.0
            count = 0
        
        # Write outputs
        self.set_outlet('average', average)  # 25.0
        self.set_outlet('count', count)      # 3
        
        return None
```

### Example 4: Complex Type Processing

```python
@node(
    label='Scale Mesh',
    description='Scales a mesh by a factor',
    search_tags=['mesh', 'scale', 'transform'],
    menu='geometry/transform'
)
class ScaleMeshNode(BaseNode):
    """Scales a mesh by a uniform factor"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.behavior.is_data_node = True
        
        # Mesh input
        self.add(MeshData.as_inlet(
            id='mesh',
            label='Input Mesh',
            default={'vertices': [], 'faces': []}
        ))
        
        # Scale factor
        self.add(FLOAT.as_inlet(
            id='scale',
            label='Scale Factor',
            default=1.0,
            widget='core:widget:slider.widget',
            ui={'properties': {'min': 0.1, 'max': 10.0, 'step': 0.1}}
        ))
        
        # Mesh output
        self.add(MeshData.as_outlet(
            id='scaled_mesh',
            label='Scaled Mesh'
        ))
    
    def worker(self, context: dict) -> dict | None:
        # Read inputs
        mesh = self.inlet('mesh')    # Returns: MeshData(...)
        scale = self.inlet('scale')  # Returns: 2.0
        
        # Scale vertices
        scaled_vertices = [
            [v[0] * scale, v[1] * scale, v[2] * scale]
            for v in mesh.vertices
        ]
        
        # Create new mesh
        scaled_mesh = MeshData(
            vertices=scaled_vertices,
            faces=mesh.faces  # Faces unchanged
        )
        
        # Write output
        self.set_outlet('scaled_mesh', scaled_mesh)
        
        return None
```

---

## Common Patterns

### Pattern 1: Optional Inputs with Defaults

```python
def worker(self, context: dict) -> dict | None:
    # Use connected value or fall back to default
    if self.inlets['optional_input'].is_connected:
        value = self.inlet('optional_input')
    else:
        value = 10.0  # Fallback default
    
    # Process value
    result = value * 2
    self.set_outlet('result', result)
```

### Pattern 2: Conditional Processing Based on Input

```python
def worker(self, context: dict) -> dict | None:
    mode = self.inlet('mode')  # "add", "subtract", "multiply"
    a = self.inlet('a')
    b = self.inlet('b')
    
    if mode == 'add':
        result = a + b
    elif mode == 'subtract':
        result = a - b
    elif mode == 'multiply':
        result = a * b
    else:
        result = 0.0
    
    self.set_outlet('result', result)
```

### Pattern 3: Processing Arrays Element-wise

```python
def worker(self, context: dict) -> dict | None:
    numbers = self.inlet('numbers')  # [1.0, 2.0, 3.0]
    factor = self.inlet('factor')    # 2.0
    
    # Process each element
    scaled = [n * factor for n in numbers]  # [2.0, 4.0, 6.0]
    
    self.set_outlet('scaled_numbers', scaled)
```

### Pattern 4: Aggregating Pooled Sources

```python
def worker(self, context: dict) -> dict | None:
    # Get all values from pooled inlet
    inlet = self.inlets['pooled_input']
    
    # Access as dict (with source IDs)
    values_dict = inlet.data.get_value()  # {"node1": 10, "node2": 20}
    
    # Or as list (just values)
    values_list = inlet.data.get_values_list()  # [10, 20]
    
    # Or get source IDs
    source_ids = inlet.data.get_source_ids()  # ["node1", "node2"]
    
    # Aggregate
    total = sum(values_list)
    self.set_outlet('total', total)
```

### Pattern 5: Error Handling with Status Output

```python
def worker(self, context: dict) -> dict | None:
    try:
        value = self.inlet('input')
        result = expensive_computation(value)
        self.set_outlet('result', result)
        self.set_outlet('success', True)
        self.set_outlet('error_message', '')
    except Exception as e:
        self.set_outlet('result', 0.0)
        self.set_outlet('success', False)
        self.set_outlet('error_message', str(e))
    
    return None
```

---

## Troubleshooting

### Common Errors and Solutions

#### Error: "Inlet ID already exists"

**Problem**: Trying to add multiple inlets with the same ID

```python
# ❌ Wrong
self.add(FLOAT.as_inlet(id='value', default=1.0))
self.add(FLOAT.as_inlet(id='value', default=2.0))  # Error!
```

**Solution**: Use unique IDs

```python
# ✅ Correct
self.add(FLOAT.as_inlet(id='value_a', default=1.0))
self.add(FLOAT.as_inlet(id='value_b', default=2.0))
```

#### Error: "KeyError: 'inlet_name'"

**Problem**: Trying to access an inlet that doesn't exist

```python
# ❌ Wrong
value = self.inlet('non_existent_inlet')
```

**Solution**: Check inlet ID matches

```python
# ✅ Correct
self.add(FLOAT.as_inlet(id='my_inlet', default=0.0))
# ...
value = self.inlet('my_inlet')  # ID must match!
```

#### Error: "PooledField requires source_id"

**Problem**: Trying to set pooled field without source_id

**Cause**: You probably shouldn't be calling set_value() directly on pooled fields—this is handled by the connection system

#### Error: "Cannot connect pooled to pooled"

**Problem**: Trying to connect a pooled outlet to a pooled inlet

**Solution**: Pooled inlets can only connect to regular outlets, not other pooled inlets

#### Error: "Cannot connect non-array to array inlet"

**Problem**: Trying to connect a single-value outlet to an array inlet

**Solution**: Arrays can only connect to other arrays:

```python
# ❌ Wrong
FLOAT outlet -> ArrayList[FLOAT] inlet

# ✅ Correct
ArrayList[FLOAT] outlet -> ArrayList[FLOAT] inlet
```

### Best Practices

1. **Use Descriptive IDs**: `id='input_temperature'` not `id='in1'`
2. **Provide Sensible Defaults**: Make nodes work without connections
3. **Add Labels**: Help users understand what each port does
4. **Document Complex Types**: Add docstrings explaining custom types
5. **Handle Empty Pooled/Arrays**: Always check if collections are empty
6. **Validate Input Ranges**: Check for division by zero, negative values, etc.
7. **Use Type Hints**: Help IDEs and type checkers

```python
def worker(self, context: dict) -> dict | None:
    """
    Process temperature data.
    
    Reads temperature in Celsius from 'temp_celsius' inlet,
    converts to Fahrenheit, and outputs to 'temp_fahrenheit'.
    """
    celsius: float = self.inlet('temp_celsius')
    fahrenheit: float = (celsius * 9/5) + 32
    self.set_outlet('temp_fahrenheit', fahrenheit)
    return None
```

---

## Quick Reference

### Port Creation Cheat Sheet

```python
# Primitive inlet
FLOAT.as_inlet(id='name', default=0.0)

# Primitive outlet
FLOAT.as_outlet(id='name')

# Complex inlet
MeshData.as_inlet(id='name', default={...})

# Complex outlet
MeshData.as_outlet(id='name')

# Pooled inlet
Pooled.as_inlet(element_type_cls=FLOAT, id='name')

# Array inlet
ArrayList.as_inlet(element_type_cls=FLOAT, id='name', default=[...])

# Array outlet
ArrayList.as_outlet(element_type_cls=FLOAT, id='name')
```

### Worker Access Cheat Sheet

```python
# Read primitive
value = self.inlet('inlet_id')  # Returns unwrapped value

# Read complex
obj = self.inlet('inlet_id')  # Returns instance

# Read pooled
values = self.inlet('inlet_id')  # Returns dict
values_list = self.inlets['inlet_id'].data.get_values_list()

# Read array
items = self.inlet('inlet_id')  # Returns list

# Write any type
self.set_outlet('outlet_id', value)  # Auto-wraps
```

---

## Need More Help?

- Check existing nodes in `haywire/libraries/core/nodes/` for examples
- Review type definitions in `haywire/libraries/core/types/specs.py`
- See widget configuration in `haywire/ui/widgets/`
- Ask in the Haywire developer community