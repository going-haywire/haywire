# Haywire DataField System - Complete Implementation Package

## 🎯 Key Concepts

### The Four Field Types

1. **PrimitiveField**: Single primitive wrapper
   - Storage: `FLOAT(42.0)` instance
   - Worker gets: `42.0` (unwrapped)
   - Used for: Single values like numbers, strings, booleans

2. **ComplexField**: Single complex object
   - Storage: `MeshData(...)` instance
   - Worker gets: `MeshData(...)` instance
   - Used for: Custom data types, structures

3. **PooledField**: Multi-source dictionary
   - Storage: `{"node1": 42.0, "node2": 15.0}` (unwrapped values)
   - Worker gets: Dict or list of values
   - Used for: Aggregating multiple inputs

4. **ArrayField**: Homogeneous list
   - Storage: `[1.0, 2.0, 3.0]` (unwrapped values)
   - Worker gets: `[1.0, 2.0, 3.0]` list
   - Used for: Collections of same type

### Access Patterns

**Node-to-Node Transfer:**
```
Outlet → get_for_transfer() → [wrapped] → Connection → set_value() → Inlet
```

**Worker Access:**
```
Worker → inlet('id') → get_value() → [unwrapped] → Worker logic
Worker logic → set_outlet('id', value) → set_value() → [wrapped storage]
```

**Widget Binding:**
```
UI → update_property('value', x) → [update container] → Observer notification
Container change → get_value() → [unwrapped] → Update UI
```

---

## 📊 Access Matrix Summary

| Field Type | Worker Gets | Outlet Sends | Widget Updates |
|------------|-------------|--------------|----------------|
| **Primitive** | Unwrapped `T` (42.0) | `FLOAT(42.0)` | ✅ `value` property |
| **Complex** | Instance (`MeshData`) | Instance | ✅ Any property |
| **Pooled** | `Dict[str, T]` | ❌ Inlet only | ❌ Read-only |
| **Array** | `List[T]` | `List[FLOAT]` | ❌ Wholesale only |

---

## 🔧 Common Usage Examples

### Creating a Simple Math Node
```python
class AddNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(FLOAT.as_inlet(id='a', default=0.0))
        self.add(FLOAT.as_inlet(id='b', default=0.0))
        self.add(FLOAT.as_outlet(id='result'))
    
    def worker(self, context):
        result = self.inlet('a') + self.inlet('b')
        self.set_outlet('result', result)
```

### Creating an Array Processing Node
```python
class SortNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(ArrayList.as_inlet(
            element_type_cls=FLOAT,
            id='numbers',
            default=[5.0, 2.0, 8.0]
        ))
        self.add(ArrayList.as_outlet(
            element_type_cls=FLOAT,
            id='sorted'
        ))
    
    def worker(self, context):
        numbers = self.inlet('numbers')
        self.set_outlet('sorted', sorted(numbers))
```

### Creating a Pooled Aggregation Node
```python
class AverageNode(BaseNode):
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        self.add(Pooled.as_inlet(
            element_type_cls=FLOAT,
            id='values'
        ))
        self.add(FLOAT.as_outlet(id='average'))
    
    def worker(self, context):
        values = self.inlet('values')  # Dict[str, float]
        avg = sum(values.values()) / len(values) if values else 0.0
        self.set_outlet('average', avg)
```

---

## 📞 Support and Questions

- **Architecture questions:** See `Implementation_Summary.md`
- **How to create nodes:** See `Node_Developer_Manual.md`
- **Future features:** See `WidgetsAndAdapterGuide.md`
- **Code examples:** All three documentation files contain examples

---

## ⚡ Performance Notes

- **PrimitiveField**: Stores wrapper instance, updates via setter (efficient!)
- **ArrayField**: Unwrapped storage for iteration performance
- **PooledField**: Dict overhead, but O(1) source lookup
- **Connection transfer**: Re-wrapping only happens at boundaries

See `Implementation_Summary.md` section "Performance Considerations" for details.

---

## 🎓 Learning Path

1. **Understand the why:** Read "Core Architectural Principles" in `Implementation_Summary.md`
2. **See it in action:** Read "Complete Examples" in `Node_Developer_Manual.md`
3. **Build your first node:** Follow "Quick Start" patterns
4. **Master the system:** Study "Updated Access Matrix" in `Implementation_Summary.md`
5. **Extend the system:** Review "Extension Points" and future features

---
