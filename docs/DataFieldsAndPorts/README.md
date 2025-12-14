# Haywire DataField System - New Architecture (Complete)

This package contains the complete implementation of the new Haywire type and data field architecture with unwrapped storage, CompoundType pattern, and clean separation of concerns.

## 🎯 Key Improvements

### Architecture
- **Three-category pattern**: PrimitiveType ↔ PrimitiveField, BaseType ↔ ComplexField, CompoundType ↔ CompoundField
- **Type parameterization**: `ArrayType[FLOAT].as_inlet(id='numbers')`
- **Co-located definitions**: Type and Field in same file
- **Clean API**: `self.inlet('id')` and `self.set_outlet('id', value)`
- **field_class attribute**: Direct type-to-field mapping (no registry)
- **Pythonic**: Direct primitive operations

---

## 📦 Package Contents

### Documentation Files

#### 1. **ARCHITECTURE_SUMMARY.md** ⭐
Complete architectural overview including:
- Three-category pattern explanation
- Updated access matrix for all use cases
- Type-field mapping via field_class
- CompoundType metaclass design
- Adapter system with unwrapped values
- Performance characteristics
- Design decisions and rationale
- Migration guide

**Read this for:** Understanding the complete architecture

#### 2. **DEVELOPER_MANUAL.md** ⭐
Comprehensive developer guide:
- Quick start examples
- Creating all inlet types (primitive, complex, array, pooled)
- Creating outlets
- Complete working examples
- Common patterns
- Troubleshooting guide
- Best practices

**Read this for:** Learning how to create nodes

---

## 🚀 Quick Start Example

```python
from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.libraries.core.types.specs import FLOAT
from haywire.libraries.core.types.array import ArrayType

@node(label='Array Sort')
class SortNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Clean type parameterization syntax!
        self.add(ArrayType[FLOAT].as_inlet(
            id='numbers',
            default=[5.0, 2.0, 8.0, 1.0]
        ))
        
        self.add(ArrayType[FLOAT].as_outlet(id='sorted'))
    
    def worker(self, context):
        # Get unwrapped list - no manual unwrapping!
        numbers = self.inlet('numbers')  # [5.0, 2.0, 8.0, 1.0]
        
        # Process as normal Python list
        sorted_numbers = sorted(numbers)  # [1.0, 2.0, 5.0, 8.0]
        
        # Set output - no manual wrapping!
        self.set_outlet('sorted', sorted_numbers)
```

---

## 📊 Architecture Patterns

### The Three Categories

```
TYPE                  FIELD                   STORAGE
────────────         ────────────            ────────
PrimitiveType[T] ←→  PrimitiveField[T]      42.0 (unwrapped)
BaseType         ←→  ComplexField            MeshData(...) (instance)
CompoundType[T]  ←→  CompoundField[T]        [1.0, 2.0] (unwrapped)
  ├─ ArrayType         ├─ ArrayField          List[T]
  └─ PooledType        └─ PooledField         Dict[str, T]
```

### Type Parameterization

```python
# Old (helpers)
Pooled.as_inlet(element_type_cls=FLOAT, id='pool')
ArrayList.as_inlet(element_type_cls=FLOAT, id='array')

# New (type parameterization)
PooledType[FLOAT].as_inlet(id='pool')
ArrayType[FLOAT].as_inlet(id='array')
```

### Worker API

```python
# New (automatic)
a = self.inlet('a')
result = a + b
self.set_outlet('result', result)
```

---

## 🎯 Key Features

### 1. Unwrapped Storage

**Primitives stored directly:**
```python
class PrimitiveField:
    _value: float  # 42.0 (NOT FLOAT(42.0))
```

### 2. Type-Field Mapping

**Each type declares its field:**
```python
class FLOAT(PrimitiveType[float]):
    field_class = PrimitiveField  # Direct reference

class ArrayType(CompoundType[T]):
    field_class = ArrayField  # Direct reference
```

### 3. CompoundType Pattern

**Clean syntax for collections:**
```python
ArrayType[FLOAT].as_inlet(id='numbers')
PooledType[MeshData].as_inlet(id='meshes')

# Metaclass magic:
# ArrayType[FLOAT] → ParameterizedCompound
# .as_inlet(...) → ArrayType._create_inlet(element_type_cls=FLOAT, ...)
```

**Benefits:**
- Type-safe at connection time
- Adapter support for elements
- Extensible (add SetType, MapType, etc.)

### 4. Separation of Concerns

**DataField: Pure data storage**
- get_value() - Read data
- set_value() - Write data
- get_for_transfer() - Prepare for transfer
- is_compatible_with() - Type checking

**PropertyBinding: Widget logic**
- _navigate_path() - Read properties
- _update_nested_property() - Write properties
- Validation and conversion

---

## 📖 Documentation Guide

1. **Start here:** Read this README
2. **Understand architecture:** Read `ARCHITECTURE_SUMMARY.md`
3. **Learn to create nodes:** Read `DEVELOPER_MANUAL.md`
4. **Reference implementation:** Check the 8 Python files

---

## 🎓 Learning Path

### For Node Developers

1. Read Quick Start in this README
2. Read DEVELOPER_MANUAL.md
3. Try the examples
4. Create your first node

### For Core Developers

1. Read ARCHITECTURE_SUMMARY.md completely
2. Study the three-category pattern
3. Understand unwrapped storage benefits
4. Review the 8 implementation files
5. Follow the implementation checklist

### For Contributors

1. Understand the architecture (ARCHITECTURE_SUMMARY.md)
2. Learn the patterns (three categories, type-field mapping)
3. Review design decisions
4. Consider extending (SetType, MapType, etc.)

---

## 💡 Key Insights

### 1. ITypes are Metadata, Not Storage

ITypes describe data (color, icon, widget, adapters).
DataFields store data (efficiently, in natural form).

### w. field_class = Simplicity

Direct type-to-field mapping (no registry) creates:
- Clear relationships
- Co-located code
- Easy discovery

### e. CompoundType = Extensibility

Pattern for all collections creates:
- Consistent API
- Type safety
- Adapter support
- Room to grow

---


**This is a complete, production-ready implementation of the new Haywire type and data field architecture!**

Start with the Quick Start example, read the documentation, and begin migrating your nodes. The new system is simpler, faster, and more maintainable.
