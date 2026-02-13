# Defining Data Types

This manual covers how to create and register your own data types for use in Haywire nodes. It assumes you have read [Creating Nodes](Creating_Nodes.md) and [Defining DataPorts inside Nodes](Defining_DataPorts_inside_Nodes.md).

---

## How Types Fit into the System

A type in Haywire is a **descriptor** — it tells the system what kind of data flows through a port. It does **not** store runtime data itself. That's the job of the DataField, which is selected automatically based on which type category you use.

```
You define        The system creates       Workers see
─────────        ───────────────────       ───────────
FLOAT            → PrimitiveField          42.0
MeshData         → BaseField               MeshData(vertices=[], faces=[])
ArrayType[FLOAT] → ArrayField              [1.0, 2.0, 3.0]
PooledType[FLOAT]→ PooledField             {"node1": 20.0, "node2": 25.0}
```

You never instantiate a DataField yourself. You define a type, use it in `as_inlet()` / `as_outlet()`, and the framework handles the rest.

---

## The Three Type Categories

Every type belongs to one of three categories. Choose based on what kind of data you need to represent:

| I need to represent... | Use | Example |
|---|---|---|
| A single Python primitive (`float`, `int`, `str`, `bool`, `bytes`) | `PrimitiveType[T]` | `FLOAT`, `INT`, `BOOL` |
| A structured object with multiple attributes | `BaseType` (as `@dataclass`) | `MeshData`, `FRAME`, `Color` |
| A collection of a typed element | `CompoundType[T]` | `ArrayType[FLOAT]`, `PooledType[MeshData]` |

CompoundType is provided by the core library (`ArrayType`, `PooledType`). You will rarely need to define a new CompoundType — typically you just parameterize the existing ones. This manual focuses on the first two categories, which are what library developers create.

### The Three-Category Pattern

```
TYPE HIERARCHY              FIELD HIERARCHY           STORAGE
───────────────            ───────────────           ───────

PrimitiveType[T]     ←→    PrimitiveField[T]        T (unwrapped)
  FLOAT                                               42.0
  INT                                                 10
  STRING                                              "hello"
  BOOL                                                True

BaseType             ←→    BaseField              BaseType instance
  MeshData                                            MeshData(...)
  CustomClass                                         CustomClass(...)

CompoundType[T]      ←→    CompoundField[T]          Container[T]
  ArrayType[T]             ArrayField[T]              List[T]
  PooledType[T]            PooledField[T]             Dict[str, T]
```

---

## Defining a Primitive Type

Primitive types wrap a single Python built-in value.

### Minimal Definition

```python
from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type
from haywire.core.data.enums import FlowType

@type(
    default={'value': 0.0},
)
class FLOAT(PrimitiveType[float]):
    pass
```

That's all you need for a working type. The `Generic[T]` parameter (`float` in this case) tells the system what Python type is stored. The `default` dict must contain a `'value'` key.

### Full Definition with All Options

```python
@type(
    registry_id='float',           # unique ID within your library (default: class name)
    label='Float',                 # display name in the UI
    description='Decimal number',  # tooltip / description
    color='#50b0ff',               # hex color for pins on the canvas
    icon='circle',                 # icon for pins (optional)
    flow_type=FlowType.DATA,      # DATA, CONTROL, CALLBACK, or NONE
    default={'value': 0.0},        # REQUIRED — must be {'value': <default>}
    store_data=False,              # True to persist field values on save
    help_url='',                   # link to external docs
)
class FLOAT(PrimitiveType[float]):
    """Float data type"""

    @classmethod
    def to_dict(cls, value: float) -> dict:
        """Serialize the unwrapped value to a dict for persistence."""
        return {"value": float(value)}

    @classmethod
    def from_dict(cls, data: dict) -> float:
        """Deserialize back to the unwrapped value."""
        return float(data.get("value", 0.0))
```

### What the Decorator Sets Up

The `@type` decorator:
1. Validates that `default` is present and serializable
2. Creates a `DataTypeIdentity` and attaches it as `class_identity`
3. Detects the library from the module path and attaches it as `class_library`
4. For primitives: auto-wraps bare values in `default` — writing `default=0.0` is equivalent to `default={'value': 0.0}`

### What Gets Set Automatically

| Attribute | How it's set | Value for `FLOAT` |
|---|---|---|
| `element_type_cls` | Extracted from `Generic[T]` | `float` |
| `field_class` | Inherited from `PrimitiveType` | `PrimitiveField` |
| `class_identity` | Created by `@type` decorator | `DataTypeIdentity(...)` |
| `class_library` | Derived from module path | `LibraryIdentity(...)` |

### Methods You Can Override

| Method | Signature | Purpose | When to Override |
|---|---|---|---|
| `to_dict` | `cls, value: T → dict` | Serialize unwrapped value | Always — default returns the decorator default, not the actual value |
| `from_dict` | `cls, data: dict → T` | Deserialize to unwrapped value | Always — paired with `to_dict` |
| `create_default` | `cls → instance` | Create a default type instance | Rarely — only if `cls(**default)` doesn't work |

### Custom Field for Type Coercion

If incoming values need to be cast to the correct Python type, define a custom field class:

```python
from haywire.core.data.fields import PrimitiveField

class FLOATField(PrimitiveField):
    """Guarantees stored value is always a Python float."""
    def set_value(self, value, source_id=None):
        value = float(value)
        return super().set_value(value, source_id)

# Assign AFTER both classes are defined
FLOAT.field_class = FLOATField
```

This is how the built-in `FLOAT`, `INT`, and `BOOL` types guarantee type safety when values arrive from adapters or connections. If your primitive type can receive values that need casting, follow this pattern.

---

## Defining a Derived Primitive Type (Variant)

You can create specialized versions of existing primitive types. The derived type inherits all decorator settings from its parent and can override any of them.

```python
@type(
    registry_id='temperature',
    label='Temperature',
    color='#ff5722',
    default={'value': 20.0},      # override parent's default
)
class Temperature(FLOAT):
    """Temperature in Celsius."""
    pass
```

`Temperature` inherits `FLOAT`'s serialization, field class, and everything else — but overrides `registry_id`, `label`, `color`, and `default`.

Derived types are automatically **compatible with their ancestor types** for connections. The adapter system walks the type hierarchy:

- **Child → parent** (e.g. `Temperature` outlet → `FLOAT` inlet): works as a passthrough, no adapter needed.
- **Child → sibling of parent** (e.g. `Temperature` outlet → `INT` inlet): resolves via the parent's adapters (`FLOAT → INT`).
- **Parent → child** (e.g. `FLOAT` outlet → `Temperature` inlet): **not** automatic — requires an explicit adapter, since not every float is a valid temperature.

### Using a Widget with a Variant

```python
@type(
    registry_id='math_operation',
    label='Operation',
    widget_key='core:widget:SelectWidget',
    widget_config={'properties': {'options': ['add', 'subtract', 'multiply', 'divide']}},
    default={'value': 'add'},
)
class MathOperation(STRING):
    """Selection of math operations."""
    pass
```

`widget_key` and `widget_config` are useful at the type level when every port of this type should use the same widget. For per-port widget overrides, pass `widget_key` to `as_inlet()` instead.

**DO NOT USE** as_inlet() pattern, as this requires the import of the widget in the node file, which creates a circular dependency if the widget also needs to import the type. Instead, set the widget at the type level as shown above.

---

## Defining a Complex Type (BaseType)

Complex types represent structured data with multiple attributes. Use `@dataclass` for clean attribute definitions.

### Minimal Definition

```python
from dataclasses import dataclass
from haywire.core.types.base import BaseType
from haywire.core.types.decorator import type

@type(
    default={'vertices': [], 'faces': []},
)
@dataclass
class MeshData(BaseType):
    vertices: list = None
    faces: list = None
```

The `default` dict keys must match the dataclass constructor arguments.

### Full Definition

```python
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np

from haywire.core.types.base import BaseType
from haywire.core.types.decorator import type
from haywire.core.data.enums import FlowType

@type(
    registry_id='frame',
    label='Frame',
    description='Video frame data with metadata',
    color='#9c27b0',
    flow_type=FlowType.DATA,
    default={
        'data': None,
        'timestamp': 0.0,
        'frame_number': 0,
        'width': 0,
        'height': 0,
        'channels': 0,
    },
)
@dataclass
class FRAME(BaseType):
    """Video frame data type with metadata."""
    data: Optional[np.ndarray] = None
    timestamp: float = 0.0
    frame_number: int = 0
    width: int = 0
    height: int = 0
    channels: int = 0

    def __post_init__(self):
        """Derive width/height/channels from the numpy array."""
        if self.data is not None and isinstance(self.data, np.ndarray):
            if len(self.data.shape) >= 2:
                self.height, self.width = self.data.shape[:2]
                self.channels = self.data.shape[2] if len(self.data.shape) > 2 else 1

    def is_valid(self) -> bool:
        """Check if frame contains valid data."""
        return (self.data is not None
                and isinstance(self.data, np.ndarray)
                and self.data.size > 0)
```

### What Gets Set Automatically

| Attribute | How it's set | Value for `FRAME` |
|---|---|---|
| `element_type_cls` | Auto-set to the class itself | `FRAME` |
| `field_class` | Inherited from `BaseType` | `BaseField` |

### Methods You Can Override

| Method | Signature | Purpose | When to Override |
|---|---|---|---|
| `to_dict` | `self → dict` | Serialize instance | When attributes contain non-serializable types (numpy arrays, custom objects) |
| `from_dict` | `cls, data: dict → Self` | Deserialize instance | Paired with `to_dict` |
| `create_default` | `cls → instance` | Create default instance | When `cls(**default_dict)` doesn't work for your type |

**Default behavior** (no override needed for simple dataclasses):
- `to_dict()` uses `dataclasses.asdict(self)`
- `from_dict(data)` uses `cls(**data)`

**Override when you have non-serializable attributes:**

```python
@dataclass
class FRAME(BaseType):
    data: Optional[np.ndarray] = None
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            'data': self.data.tolist() if self.data is not None else None,
            'timestamp': self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FRAME':
        raw = data.get('data')
        return cls(
            data=np.array(raw) if raw is not None else None,
            timestamp=data.get('timestamp', 0.0),
        )
```

### Adding Custom Methods

You can add any helper methods to your type. Since instances are stored directly in the field, workers have full access:

```python
@dataclass
class BoundingBox(BaseType):
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def area(self) -> float:
        return self.width * self.height

    def contains(self, px: float, py: float) -> bool:
        return (self.x <= px <= self.x + self.width
                and self.y <= py <= self.y + self.height)
```

```python
# In a worker:
def worker(self, context, bbox: BoundingBox):
    area = bbox.area()               # call methods directly
    hit = bbox.contains(10.0, 20.0)  # the instance IS the value
```

---

## Defining a Non-Data Type (Control Flow)

Control flow types signal execution order rather than carry data.

### EXEC — Execution Signal

```python
@type(
    registry_id='exec',
    flow_type=FlowType.CONTROL,
    label='Execution Signal',
    color='#004cff',
    widget=None,
    default={},
)
class EXEC(BaseType):
    """Execution signal — represents control flow, not data."""

    @classmethod
    def create_default(cls) -> 'EXEC':
        return cls()
```

Key differences from data types:
- `flow_type=FlowType.CONTROL` — the system treats these as execution edges, not data edges
- `widget=None` — no property panel widget
- `default={}` — no meaningful default value
- Override `create_default()` since `cls(**{})` needs to work

### CALLBACK — Event Registration

```python
@type(
    registry_id='callback',
    flow_type=FlowType.CALLBACK,
    label='Callback Signal',
    color='#ff3c00',
    widget=None,
    default={},
)
class CALLBACK(STRING):
    """Callback signal — inherits from STRING for payload compatibility."""
    pass
```

---

## The `@type` Decorator Reference

### Required Parameters

| Parameter | Type | Description |
|---|---|---|
| `default` | `dict` | Constructor kwargs for default instances. For primitives: `{'value': <val>}` (or just `<val>`, auto-wrapped). For complex types: `{'attr1': val1, 'attr2': val2}`. |

### Optional Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `registry_id` | `str` | class name | Unique ID within your library |
| `label` | `str` | class name | Display name in UI |
| `description` | `str` | docstring | Description / tooltip |
| `color` | `str` | `'#757575'` | Hex color for pins |
| `icon` | `str` | `None` | Pin icon (applies to all pin variants unless overridden) |
| `icon_in` | `str` | `None` | Inlet-specific icon |
| `icon_out` | `str` | `None` | Outlet-specific icon |
| `icon_in_multi` | `str` | `None` | Multi-connection inlet icon |
| `icon_out_multi` | `str` | `None` | Multi-connection outlet icon |
| `flow_type` | `FlowType` | `NONE` | `DATA`, `CONTROL`, `CALLBACK`, or `NONE` |
| `widget_key` | `str` | `None` | Widget registry key (e.g., `'core:widget:NumberWidget'`) |
| `widget_config` | `dict` | `{}` | Widget configuration properties |
| `store_data` | `bool` | `False` | Whether field values persist on save |
| `help_url` | `str` | `''` | External documentation link |

### Inheritance Behavior

When a decorated type inherits from another decorated type, the child starts with a copy of the parent's identity and then overwrites only the parameters you provide:

```python
@type(registry_id='float', color='#50b0ff', default={'value': 0.0})
class FLOAT(PrimitiveType[float]): ...

@type(registry_id='temperature', default={'value': 20.0})
class Temperature(FLOAT): ...
# Temperature gets: color='#50b0ff' (inherited), default={'value': 20.0} (overridden)
```

---

## Using Your Types in Nodes

Once defined, types are used in nodes through `as_inlet()`, `as_outlet()`, and `as_config()`. These methods return a port specification dict that `self.add()` consumes.

### Port Creation Methods

```python
# Inlet — receives data from upstream or from widget
MyType.as_inlet('id', **kwargs)

# Outlet — sends data downstream
MyType.as_outlet('id', **kwargs)

# Config — internal parameter, no visible pin on the canvas
MyType.as_config('id', **kwargs)
```

### Port `kwargs` (all optional)

| Parameter | Type | Description |
|---|---|---|
| `label` | `str` | Display label (defaults to type's label) |
| `default` | varies | Override the type's default value |
| `widget_key` | `str` | Override the type's widget |
| `widget_config` | `dict` | Override widget config |
| `flow_type` | `FlowType` | Override the type's flow type |
| `on_change` | `str` | Name of a node method to call when value changes |
| `on_connect` | `str` | Name of a node method to call when a connection is made |
| `on_disconnect` | `str` | Name of a node method to call when a connection is removed |
| `store_data` | `bool` | Override the type's store_data setting |

### Examples in a Node

```python
from haywire.core.types.decorator import type
from haywire.core.data.enums import FlowType

@node(label='Frame Processor')
class FrameProcessorNode(BaseNode):

    def init(self):
        from my_library.types import FRAME
        from haybale_core.types.specs import FLOAT, INT, BOOL, EXEC
        from haybale_core.types.array_type import ArrayType

        # Control flow
        self.add(EXEC.as_inlet('trigger', label='Execute'))
        self.add(EXEC.as_outlet('done', label='Done'))

        # Primitive with default override
        self.add(FLOAT.as_inlet('brightness', label='Brightness', default=1.0))

        # Complex type
        self.add(FRAME.as_inlet('frame', label='Input Frame'))
        self.add(FRAME.as_outlet('processed', label='Output Frame'))

        # Array of primitives
        self.add(ArrayType[FLOAT].as_inlet('weights', default=[1.0, 1.0, 1.0]))

        # Config — no pin on canvas, just a property panel entry
        self.add(BOOL.as_config('debug', default=False))

    def worker(self, context, frame: 'FRAME', brightness: float = 1.0):
        frame.data = (frame.data * brightness).clip(0, 255).astype('uint8')
        self.out('processed', frame)
        return 'done'
```

---

## Writing Adapters for Your Types

Adapters enable automatic conversion when an outlet of one type connects to an inlet of a different type. Adapters work with **unwrapped values** — they receive and return raw Python objects, not type wrappers.

### Minimal Adapter

```python
from haywire.core.adapter.base import BaseAdapter, adapter

@adapter(
    converts_from=INT,
    converts_to=FLOAT,
)
class IntToFloatAdapter(BaseAdapter):

    def convert(self, value: int) -> float:
        return float(value)

    def get_test_value(self) -> int:
        return 42
```

### Full Adapter with All Options

```python
from haywire.core.adapter.base import BaseAdapter, adapter

@adapter(
    registry_id='int_to_float',          # unique ID within library (default: class name)
    label='Int to Float',                # display name
    description='Convert integer to float',
    converts_from=INT,                   # source IType class
    converts_to=FLOAT,                   # target IType class
    priority=5,                          # higher = preferred when multiple adapters match
)
class IntToFloatAdapter(BaseAdapter):

    def convert(self, value: int) -> float:
        """Convert a single value. Receives and returns unwrapped values."""
        return float(value)

    def get_test_value(self) -> int:
        """Return a sample input value for automated testing."""
        return 42

    def get_test_repetitions(self) -> int:
        """Number of times to repeat the test (default: 1)."""
        return 10
```

### Methods You Must Implement

| Method | Purpose |
|---|---|
| `convert(value) -> Any` | Transform a single unwrapped value |
| `get_test_value() -> Any` | Return a sample input for testing |

### Methods You Can Override

| Method | Default | Purpose |
|---|---|---|
| `get_test_repetitions()` | `1` | Number of test iterations |
| `test(value) -> Any` | Calls `execute(value)` | Custom test logic |
| `execute(value) -> Any` | `convert(value)` then delegates to chain | Full chain execution |

### Adapter Chains

Adapters are chained automatically. If you have `INT → FLOAT` and `FLOAT → STRING`, the system can create a chain `INT → FLOAT → STRING` without you writing an explicit adapter for `INT → STRING`.

The `execute()` method handles chaining. In most cases you only implement `convert()` and the base class does the rest.

---

## Decision Checklist

Use this when deciding how to define your type:

```
Is it a single Python built-in value (int, float, str, bool, bytes)?
  YES → PrimitiveType[T]
    └─ Is it a specialization of an existing type (e.g., Temperature from FLOAT)?
         YES → Inherit from the existing type
         NO  → Inherit from PrimitiveType[T] directly

  NO → BaseType (with @dataclass)
    └─ Does it contain non-serializable attributes (numpy, file handles)?
         YES → Override to_dict() and from_dict()
         NO  → Default serialization works, no overrides needed

Do you need a collection of your type?
  YES → Use ArrayType[YourType] or PooledType[YourType] in as_inlet/as_outlet
        (no new type definition needed)

Should a FLOAT outlet connect to your new type?
  YES → Write an adapter with converts_from=FLOAT, converts_to=YourType
```

---

## Complete Walkthrough: Creating a Custom Type from Scratch

Let's create a `Color` type for an image processing library.

### Step 1: Define the Type

```python
# my_library/types/color.py

from dataclasses import dataclass
from haywire.core.types.base import BaseType
from haywire.core.types.decorator import type
from haywire.core.data.enums import FlowType

@type(
    registry_id='color',
    label='Color',
    description='RGBA color',
    color='#e91e63',
    flow_type=FlowType.DATA,
    default={'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
)
@dataclass
class Color(BaseType):
    """RGBA color with values in 0.0 - 1.0 range."""
    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    def to_hex(self) -> str:
        """Convert to hex string."""
        return '#{:02x}{:02x}{:02x}'.format(
            int(self.r * 255), int(self.g * 255), int(self.b * 255)
        )

    @classmethod
    def from_hex(cls, hex_str: str) -> 'Color':
        """Create from hex string."""
        h = hex_str.lstrip('#')
        return cls(
            r=int(h[0:2], 16) / 255.0,
            g=int(h[2:4], 16) / 255.0,
            b=int(h[4:6], 16) / 255.0,
        )
```

Since `Color` is a simple dataclass with only serializable fields, `to_dict()` and `from_dict()` work automatically. No overrides needed.

### Step 2: Write Adapters (optional)

```python
# my_library/adapters/color_adapters.py

from haywire.core.adapter.base import BaseAdapter, adapter
from haybale_core.types.specs import STRING
from ..types.color import Color

@adapter(
    description='Convert Color to hex string',
    converts_from=Color,
    converts_to=STRING,
)
class ColorToStringAdapter(BaseAdapter):

    def convert(self, value: Color) -> str:
        return value.to_hex()

    def get_test_value(self) -> Color:
        return Color(r=1.0, g=0.5, b=0.0)


@adapter(
    description='Convert hex string to Color',
    converts_from=STRING,
    converts_to=Color,
)
class StringToColorAdapter(BaseAdapter):

    def convert(self, value: str) -> Color:
        return Color.from_hex(value)

    def get_test_value(self) -> str:
        return '#ff8000'
```

### Step 3: Use in a Node

```python
# my_library/nodes/color_mix.py

from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.execution.execution_context import ExecutionContext
from haybale_core.types.specs import FLOAT
from ..types.color import Color

@node(
    label='Mix Colors',
    menu='color/operations',
)
class MixColorsNode(BaseNode):

    def init(self):
        self.add(Color.as_inlet('color_a', label='Color A',
                                default={'r': 1.0, 'g': 0.0, 'b': 0.0, 'a': 1.0}))
        self.add(Color.as_inlet('color_b', label='Color B',
                                default={'r': 0.0, 'g': 0.0, 'b': 1.0, 'a': 1.0}))
        self.add(FLOAT.as_inlet('mix', label='Mix Factor', default=0.5))
        self.add(Color.as_outlet('result', label='Result'))

    def worker(self, context: ExecutionContext,
               color_a: Color, color_b: Color, mix: float = 0.5):
        t = max(0.0, min(1.0, mix))
        result = Color(
            r=color_a.r * (1 - t) + color_b.r * t,
            g=color_a.g * (1 - t) + color_b.g * t,
            b=color_a.b * (1 - t) + color_b.b * t,
            a=color_a.a * (1 - t) + color_b.a * t,
        )
        self.out('result', result)
```

---

## Quick Reference

### Primitive Type Template

```python
@type(
    registry_id='my_type',
    flow_type=FlowType.DATA,
    color='#hexcolor',
    default={'value': <default_value>},
)
class MY_TYPE(PrimitiveType[<python_type>]):

    @classmethod
    def to_dict(cls, value):
        return {"value": value}

    @classmethod
    def from_dict(cls, data):
        return data.get("value", <default_value>)
```

### Complex Type Template

```python
@type(
    registry_id='my_type',
    flow_type=FlowType.DATA,
    color='#hexcolor',
    default={'attr1': val1, 'attr2': val2},
)
@dataclass
class MyType(BaseType):
    attr1: Type1 = val1
    attr2: Type2 = val2
```

### Adapter Template

```python
@adapter(
    converts_from=SourceType,
    converts_to=TargetType,
)
class SourceToTargetAdapter(BaseAdapter):

    def convert(self, value):
        return <converted_value>

    def get_test_value(self):
        return <sample_source_value>
```

### FlowType Values

| Value | Purpose | Example Types |
|---|---|---|
| `FlowType.DATA` | Carries data between nodes | `FLOAT`, `STRING`, `MeshData` |
| `FlowType.CONTROL` | Controls execution order | `EXEC` |
| `FlowType.CALLBACK` | Event registration | `CALLBACK` |
| `FlowType.NONE` | Config ports (no pin) | Used with `as_config()` |
