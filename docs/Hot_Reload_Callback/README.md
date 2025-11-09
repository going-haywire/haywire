# Hot Reload Callback System Documentation

This directory contains comprehensive documentation for the Hot Reload Callback System implementation in Haywire.

## Documentation Overview

### 📋 [Hot_Reload_Callback_System_Specification.md](./Hot_Reload_Callback_System_Specification.md)
**The Complete Specification** - Read this first for full understanding

- Complete architectural design
- Detailed API specifications
- Usage examples
- Event flow diagrams
- Error handling strategies
- Performance considerations
- Testing strategy
- Migration path
- Open questions and design decisions

**Audience:** Developers implementing the system, architects reviewing the design

**Length:** Comprehensive (~600 lines)

---

### ⚡ [Hot_Reload_Callback_Summary.md](./Hot_Reload_Callback_Summary.md)
**Quick Implementation Guide** - Start here if you're implementing

- Quick reference for implementation
- Code snippets for each component
- Clear integration points
- Step-by-step implementation order
- DI configuration updates

**Audience:** Developers actively implementing the callback system

**Length:** Concise (~300 lines)

---

### 📊 [Hot_Reload_Callback_Diagrams.md](./Hot_Reload_Callback_Diagrams.md)
**Visual Architecture Guide** - For understanding the flow

- System architecture diagrams
- Callback type comparisons
- Detailed flow examples (CustomType → Node cascade)
- Implementation checklist
- Error handling flow
- Performance profiles

**Audience:** Visual learners, code reviewers, new team members

**Length:** Visual-heavy (~350 lines)

---

### 🔍 [Hot_Reload_Callback_Reference.md](./Hot_Reload_Callback_Reference.md)
**Quick Reference Guide** - For daily use during implementation

- Comparison table (Customer vs Registry callbacks)
- Method reference
- Implementation locations table
- Ready-to-use code snippets
- Type definitions
- Testing checklist
- Common patterns
- Execution order guarantees
- Performance guidelines

**Audience:** Developers during active coding, quick lookups

**Length:** Reference-style (~380 lines)

---

## Reading Path

### For First-Time Readers
1. **Start:** Read the summary in `Hot_Reload_Callback_Summary.md`
2. **Visualize:** Review diagrams in `Hot_Reload_Callback_Diagrams.md`
3. **Understand:** Read full spec in `Hot_Reload_Callback_System_Specification.md`
4. **Implement:** Use `Hot_Reload_Callback_Reference.md` as you code

### For Quick Implementation
1. **Start:** Read checklist in `Hot_Reload_Callback_Diagrams.md`
2. **Code:** Copy snippets from `Hot_Reload_Callback_Reference.md`
3. **Verify:** Check against `Hot_Reload_Callback_Summary.md`

### For Code Review
1. **Architecture:** Review `Hot_Reload_Callback_Diagrams.md`
2. **Design Decisions:** Read "Key Design Decisions" in `Hot_Reload_Callback_Summary.md`
3. **Details:** Consult `Hot_Reload_Callback_System_Specification.md` for rationale

### For Debugging
1. **Flow:** Check event flow in `Hot_Reload_Callback_Diagrams.md`
2. **Order:** Review execution order in `Hot_Reload_Callback_Reference.md`
3. **Error Handling:** See error handling section in all documents

---

## Key Concepts Summary

### Two Callback Types

#### 1. Customer Callbacks
**Purpose:** Notify direct consumers (factories) about hot reload events

```python
CustomerCallback = Callable[[str, List[str], LibraryIdentity], None]
```

**Examples:**
- NodeFactory clearing caches
- NodeRenderFactory updating renderers

#### 2. Registry Subscribers
**Purpose:** Enable cross-registry dependencies and cascade reloads

```python
class HotReloadRegistry(ABC):
    def event_dispatcher(self, event: FileChangeEvent): ...
```

**Examples:**
- CustomTypeRegistry changes → NodeRegistry reload
- WidgetRegistry changes → RendererRegistry reload

### Event Flow

```
File Change
    ↓
FileWatcher → FileChangeEvent
    ↓
BaseClassRegistry.event_dispatcher()
    ↓
_reload_managed_module()
    ↓
[Internal State Updated]
    ↓
_notify_customer_callbacks()
    ├─→ NodeFactory
    └─→ NodeRenderFactory
    ↓
_notify_registry_subscribers()
    └─→ Other Registries (may cascade)
```

---

## Implementation Checklist

### Phase 1: BaseClassRegistry Infrastructure
- [ ] Add `_customer_callbacks` list to `__init__`
- [ ] Add `_registry_subscribers` list to `__init__`
- [ ] Implement `add_customer_callback()` method
- [ ] Implement `remove_customer_callback()` method
- [ ] Implement `add_registry_subscriber()` method
- [ ] Implement `remove_registry_subscriber()` method
- [ ] Implement `_notify_customer_callbacks()` method
- [ ] Implement `_notify_registry_subscribers()` method

### Phase 2: Integration Points
- [ ] Add `_notify_customer_callbacks()` calls in `_reload_managed_module()`
  - [ ] After class reload
  - [ ] After class addition
  - [ ] After class removal
- [ ] Add `_notify_registry_subscribers()` call in `event_dispatcher()`

### Phase 3: NodeFactory Integration
- [ ] Implement `_on_node_reloaded()` method
- [ ] Register callback in `__init__()`
- [ ] Add logic to notify NodeWrapper instances

### Phase 4: NodeRenderFactory Integration
- [ ] Implement `_on_renderer_reloaded()` method
- [ ] Implement `_on_widget_reloaded()` method
- [ ] Register callbacks in `__init__()`
- [ ] Add cache clearing logic

### Phase 5: Cross-Registry Dependencies
- [ ] Implement `NodeRegistry.set_custom_type_registry()`
- [ ] Implement `NodeRegistry.event_dispatcher()`
- [ ] Add logic to find nodes using custom types
- [ ] Trigger reload of dependent nodes

### Phase 6: DI Configuration
- [ ] Update `provide_node_registry()` to wire custom type dependency
- [ ] Verify all factory providers are correct
- [ ] Test initialization order

### Phase 7: Testing
- [ ] Unit tests for callback registration
- [ ] Unit tests for callback invocation
- [ ] Unit tests for error isolation
- [ ] Integration test: NodeFactory hot reload
- [ ] Integration test: NodeRenderFactory cache clearing
- [ ] Integration test: CustomType → Node cascade

### Phase 8: Documentation
- [ ] Update BaseClassRegistry docstrings
- [ ] Update factory docstrings
- [ ] Add usage examples
- [ ] Document callback guarantees

---

## Files Modified

| File | Changes | Purpose |
|------|---------|---------|
| `src/haywire/core/library/class_registry.py` | Add callback infrastructure | Core callback system |
| `src/haywire/core/node/node_factory.py` | Add `_on_node_reloaded()` | Handle node reloads |
| `src/haywire/ui/node_render_factory.py` | Add reload callbacks | Handle renderer/widget reloads |
| `src/haywire/core/library/registries/reg_node.py` | Add cross-registry subscription | Handle custom type dependencies |
| `src/haywire/core/di/config.py` | Wire registry dependencies | Connect registries via DI |

---

## Key Design Decisions

1. **Synchronous Callbacks** - Simpler, easier to reason about, sufficient for current needs
2. **Two-Tier System** - Customer callbacks separate from registry subscribers for clarity
3. **Error Isolation** - Failed callbacks don't break the reload or other callbacks
4. **Order Guarantees** - Customer callbacks execute before registry subscribers
5. **No Filtering** - Subscribers filter events themselves for flexibility
6. **Manual Registration** - Explicit callback registration for visibility

---

## Performance Targets

- **Customer Callbacks:** < 100ms per callback
- **Registry Subscribers:** < 500ms including cascade reloads
- **Total Event Handling:** < 1 second for typical reload
- **Subscription Depth:** Maximum 2-3 levels to prevent deep cascades

---

## Error Handling

### Rules
1. Callback errors are isolated - one failure doesn't stop others
2. Errors are logged with full exception info
3. No rollback on callback failure - original reload remains valid
4. Each callback wrapped in try/except automatically

### Guarantees
- Registry state is always consistent
- Callbacks called only after successful state update
- Customer callbacks complete before registry subscribers
- Execution order within each group is deterministic (registration order)

---

## Common Use Cases

### Use Case 1: NodeFactory Hot Reload
**Trigger:** Node class file modified  
**Flow:** NodeRegistry reload → Customer callback → NodeFactory notifies NodeWrappers  
**See:** Example in `Hot_Reload_Callback_Reference.md`

### Use Case 2: NodeRenderFactory Cache Clearing
**Trigger:** Renderer or widget file modified  
**Flow:** RendererRegistry/WidgetRegistry reload → Customer callback → Cache cleared  
**See:** Example in `Hot_Reload_Callback_Reference.md`

### Use Case 3: Custom Type Cascade Reload
**Trigger:** Custom type file modified  
**Flow:** CustomTypeRegistry reload → Registry subscriber → NodeRegistry finds dependent nodes → Reload cascade  
**See:** Detailed flow in `Hot_Reload_Callback_Diagrams.md`

---

## Testing Strategy

### Unit Tests
- Callback registration/unregistration
- Callback invocation timing
- Error isolation
- Order guarantees

### Integration Tests
- NodeFactory hot reload flow
- NodeRenderFactory cache clearing
- CustomType → Node cascade
- Error recovery

### Performance Tests
- 100+ callbacks
- Deep subscription chains
- Concurrent reload events

---

## Future Enhancements

Potential future improvements (not in initial implementation):

1. **Async Callbacks** - For long-running operations
2. **Priority Ordering** - Critical callbacks execute first
3. **Callback Filtering** - Subscribe to specific event types
4. **Cycle Detection** - Prevent circular registry dependencies
5. **Metrics/Monitoring** - Track callback performance
6. **Batch Notifications** - Combine multiple changes

---

## Support

For questions or issues:

1. **Architecture Questions** - Review `Hot_Reload_Callback_System_Specification.md`
2. **Implementation Help** - Check `Hot_Reload_Callback_Summary.md`
3. **Visual Understanding** - See `Hot_Reload_Callback_Diagrams.md`
4. **Quick Lookup** - Use `Hot_Reload_Callback_Reference.md`

---

## Related Documentation

- [Library System Developer Guide](./Library_System_Developer_Guide.md)
- [Library System Technical Reference](./Library_System_Technical_Reference.md)
- [Haywire Design Whitepaper](../whitepaper/Haywire_design.md)

---

**Last Updated:** 2025-11-09  
**Status:** Specification Complete - Ready for Implementation  
**Version:** 1.0
