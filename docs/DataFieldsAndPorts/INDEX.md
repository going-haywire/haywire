# Haywire DataField Architecture - Complete Package Index

## 📚 Package Overview

### API Improvements

**Worker code:**
```python
# New
a = self.value('a')
self.out('result', a + b)
```

**Port creation:**
```python
# New
ArrayType[FLOAT].as_inlet(id='numbers')
```

### Architectural Changes

1. **Unwrapped Storage**: Fields store primitives directly (42.0 not FLOAT(42.0))
2. **CompoundType Pattern**: Unified collection type system
3. **Type Parameterization**: Clean `ArrayType[FLOAT]` syntax
4. **field_class Attribute**: Direct type-to-field mapping (no registry)
5. **Co-located Definitions**: Type and Field in same file

---

## 📋 File Reference

### Documentation Files

| File | Content | For Which Architecture? |
|------|---------|-------------------------|
| `README.md` ⭐ | Complete package guide | **New** |
| `ARCHITECTURE_SUMMARY.md` ⭐ | Architecture deep-dive | **New** |
| `WIDGET_ADAPTER_GUIDE.md` | Future features | Both |

---

## 🚀 Quick Start (New Architecture)

### 1. Read Documentation

Start with `README.md` for overview, then:
- Architecture details: `ARCHITECTURE_SUMMARY.md`


## 📊 Architecture Comparison

### Storage Strategy

| Aspect | Previous | New |
|--------|----------|-----|
| **Primitive Storage** | FLOAT(42.0) instance | 42.0 unwrapped |
| **Transfer** | Instance reference | Primitive value |
| **Memory** | ~80 bytes | ~8 bytes |
| **Speed** | 200ns (instantiation) | 5ns (assignment) |

### Port Creation

| Aspect | Previous | New |
|--------|----------|-----|
| **Arrays** | `ArrayList.as_inlet(...)` | `ArrayType[FLOAT].as_inlet(...)` |
| **Pooled** | `Pooled.as_inlet(...)` | `PooledType[FLOAT].as_inlet(...)` |
| **Type Info** | Via helper class | Via type parameterization |

### Field Mapping

| Aspect | Previous | New |
|--------|----------|-----|
| **Registration** | DataFieldFactory registry | field_class attribute |
| **Location** | Separate files | Co-located with type |
| **Discovery** | Registry lookup | Direct attribute access |

---

## 🎓 Learning Paths

### For Node Developers

1. Read `README.md` Quick Start
2. Create a test node
3. Reference examples in manual


### For Core Developers

1. Read `ARCHITECTURE_SUMMARY.md` completely
2. Understand the three-category pattern
3. Study unwrapped storage benefits
4. Review CompoundType metaclass
5. Implement following the checklist

---

