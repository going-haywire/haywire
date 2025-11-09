# Hot Reload Callback System - Quick Reference

## Callback Types Comparison Table

| Aspect | Customer Callbacks | Registry Subscribers |
|--------|-------------------|---------------------|
| **Purpose** | Notify direct consumers (factories) | Enable cross-registry dependencies |
| **Signature** | `Callable[[str, List[str], LibraryIdentity], None]` | `HotReloadRegistry.event_dispatcher(FileChangeEvent)` |
| **Parameters** | registry_key, class_names, library_identity | Complete FileChangeEvent |
| **When Called** | After each class reload/add/remove | After all customer callbacks complete |
| **Use For** | Cache clearing, state updates, notifications | Cascade reloads, dependency handling |
| **Examples** | NodeFactory, NodeRenderFactory | NodeRegistry → CustomTypeRegistry |
| **Registration** | `add_customer_callback(callback)` | `add_registry_subscriber(registry)` |
| **Error Handling** | Logged, isolated, non-blocking | Logged, isolated, non-blocking |
| **Execution Order** | Registration order | Registration order |

## Registry Method Reference

### Adding Callbacks

```python
# Customer callbacks
registry.add_customer_callback(my_callback_function)

# Registry subscribers
source_registry.add_registry_subscriber(dependent_registry)
```

### Removing Callbacks

```python
# Customer callbacks
registry.remove_customer_callback(my_callback_function)

# Registry subscribers
source_registry.remove_registry_subscriber(dependent_registry)
```

### Internal Notification (called by BaseClassRegistry)

```python
# Notify customers (called in _reload_managed_module)
self._notify_customer_callbacks(registry_key, class_names, lib_identity)

# Notify subscribers (called in event_dispatcher)
self._notify_registry_subscribers(event)
```

## Implementation Locations

| File | What to Add | Purpose |
|------|-------------|---------|
| `class_registry.py` | Callback lists and methods | Core callback infrastructure |
| `class_registry.py` | `_notify_*` calls | Trigger callbacks at right time |
| `node_factory.py` | `_on_node_reloaded()` method | Handle node reload events |
| `node_render_factory.py` | `_on_renderer_reloaded()`, `_on_widget_reloaded()` | Handle renderer/widget reload |
| `reg_node.py` | `set_custom_type_registry()`, `event_dispatcher()` | Cross-registry subscription |
| `config.py` | Registry wiring | Connect registries via DI |

## Code Snippets

### BaseClassRegistry - Add to `__init__`

```python
def __init__(self):
    # ... existing code ...
    self._customer_callbacks: List[CustomerCallback] = []
    self._registry_subscribers: List[HotReloadRegistry] = []
```

### BaseClassRegistry - Add Methods

```python
def add_customer_callback(self, callback: CustomerCallback) -> None:
    """Register a customer callback for hot reload events"""
    if callback not in self._customer_callbacks:
        self._customer_callbacks.append(callback)

def remove_customer_callback(self, callback: CustomerCallback) -> None:
    """Unregister a customer callback"""
    if callback in self._customer_callbacks:
        self._customer_callbacks.remove(callback)

def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
    """Register another registry to receive hot reload events"""
    if registry not in self._registry_subscribers:
        self._registry_subscribers.append(registry)

def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
    """Unregister a registry subscriber"""
    if registry in self._registry_subscribers:
        self._registry_subscribers.remove(registry)

def _notify_customer_callbacks(self, registry_key: str, 
                               affected_class_names: List[str],
                               library_identity: LibraryIdentity) -> None:
    """Notify all customer callbacks about a hot reload event"""
    for callback in self._customer_callbacks:
        try:
            callback(registry_key, affected_class_names, library_identity)
        except Exception as e:
            logging.error(
                f"Customer callback failed for '{registry_key}': {e}",
                exc_info=True
            )

def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
    """Notify all registry subscribers about a hot reload event"""
    for registry in self._registry_subscribers:
        try:
            registry.event_dispatcher(event)
        except Exception as e:
            logging.error(
                f"Registry subscriber callback failed for {event.file_path}: {e}",
                exc_info=True
            )
```

### _reload_managed_module - Add Notifications

```python
# After reloading
if classes_to_reload:
    for old_cls_name, new_cls in classes_to_reload:
        self._unregister_class(old_cls_name)
        new_key = self._register_class(new_cls, library_identity)
        # ADD THIS:
        self._notify_customer_callbacks(new_key, [new_cls.__name__], library_identity)

# After removing
if cls_names_to_remove:
    for cls_name in cls_names_to_remove:
        removed_cls = self._unregister_class(cls_name)
        # ADD THIS:
        if removed_cls:
            self._notify_customer_callbacks(cls_name, [removed_cls.__name__], library_identity)

# After adding
if classes_to_add:
    for cls in classes_to_add:
        new_key = self._register_class(cls, library_identity)
        # ADD THIS:
        if new_key:
            self._notify_customer_callbacks(new_key, [cls.__name__], library_identity)
```

### event_dispatcher - Add Subscriber Notification

```python
def event_dispatcher(self, event: FileChangeEvent):
    try:
        # ... existing event handling ...
        
        logging.info(f"...Hot Reloading -> DONE.")
        
        # ADD THIS:
        self._notify_registry_subscribers(event)
        
    except Exception as e:
        # ... existing error handling ...
```

### NodeFactory - Customer Callback

```python
class NodeFactory:
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        # Register callback
        node_registry.add_customer_callback(self._on_node_reloaded)
    
    def _on_node_reloaded(self, registry_key: str, 
                         affected_class_names: List[str],
                         library_identity: LibraryIdentity) -> None:
        """Handle node reload events"""
        logging.info(f"Node reloaded: {registry_key}")
        # Notify NodeWrapper instances
        affected_node_ids = self._get_nodes_using_key(registry_key)
        for listener in self._hot_reload_listeners:
            listener(registry_key, affected_node_ids)
```

### NodeRenderFactory - Customer Callbacks

```python
class NodeRenderFactory:
    def __init__(self, renderers_registry: RendererRegistry, 
                 widget_registry: WidgetRegistry):
        self.renderers_registry = renderers_registry
        self.widget_registry = widget_registry
        
        # Register callbacks
        renderers_registry.add_customer_callback(self._on_renderer_reloaded)
        widget_registry.add_customer_callback(self._on_widget_reloaded)
    
    def _on_renderer_reloaded(self, registry_key: str,
                             affected_class_names: List[str],
                             library_identity: LibraryIdentity) -> None:
        """Clear cache for affected renderer"""
        for class_name in affected_class_names:
            if class_name in self._renderer_cache:
                del self._renderer_cache[class_name]
    
    def _on_widget_reloaded(self, registry_key: str,
                           affected_class_names: List[str],
                           library_identity: LibraryIdentity) -> None:
        """Clear entire cache when widgets change"""
        self.clear_cache()
```

### NodeRegistry - Registry Subscriber

```python
class NodeRegistry(BaseClassRegistry):
    def __init__(self):
        super().__init__()
        self._custom_type_registry: Optional[CustomTypeRegistry] = None
    
    def set_custom_type_registry(self, custom_type_registry: CustomTypeRegistry):
        """Set up dependency on custom types"""
        self._custom_type_registry = custom_type_registry
        # Subscribe to changes
        custom_type_registry.add_registry_subscriber(self)
    
    def event_dispatcher(self, event: FileChangeEvent):
        """
        Handle custom type changes by reloading dependent nodes.
        This is called when a subscribed registry (CustomTypeRegistry) has a change.
        """
        if event.event_type == FileEventType.MODIFIED:
            # Find affected nodes
            module_name = self.resolve_module_name(
                Path(event.file_path),
                event.library_identity.folder_path,
                event.library_identity.module_name
            )
            affected_nodes = self._find_nodes_using_module(module_name)
            
            # Reload each affected node
            for node_module in affected_nodes:
                logging.info(f"Reloading node '{node_module}' due to custom type change")
                self._on_change(node_module, event.library_identity)
```

### DI Configuration

```python
# In config.py HaywireModule

@provider
@singleton
def provide_node_registry(self, 
                         custom_type_registry: CustomTypeRegistry) -> NodeRegistry:
    registry = NodeRegistry()
    # Set up cross-registry subscription
    registry.set_custom_type_registry(custom_type_registry)
    return registry
```

## Type Definitions

```python
from typing import Callable, List
from haywire.core.library.library_identity import LibraryIdentity
from haywire.core.library.class_registry import FileChangeEvent, HotReloadRegistry

# Customer callback type
CustomerCallback = Callable[[str, List[str], LibraryIdentity], None]

# Registry subscriber is any class implementing HotReloadRegistry
class HotReloadRegistry(ABC):
    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        pass
```

## Testing Checklist

- [ ] Customer callback registration/removal
- [ ] Registry subscriber registration/removal  
- [ ] Callback invocation on class reload
- [ ] Callback invocation on class addition
- [ ] Callback invocation on class removal
- [ ] Error in callback doesn't stop other callbacks
- [ ] Error in callback doesn't cause rollback
- [ ] Customer callbacks execute before subscribers
- [ ] Registry subscriber cascade reload
- [ ] NodeFactory hot reload integration
- [ ] NodeRenderFactory cache clearing
- [ ] CustomType → Node dependency handling

## Common Patterns

### Pattern 1: Cache Invalidation

```python
def _on_class_reloaded(self, registry_key: str, 
                      affected_class_names: List[str],
                      library_identity: LibraryIdentity) -> None:
    """Clear cache entries for reloaded classes"""
    for class_name in affected_class_names:
        if class_name in self._cache:
            del self._cache[class_name]
```

### Pattern 2: Instance Notification

```python
def _on_class_reloaded(self, registry_key: str,
                      affected_class_names: List[str],
                      library_identity: LibraryIdentity) -> None:
    """Notify instances using this class"""
    affected_ids = self._find_instances_using(registry_key)
    for instance_id in affected_ids:
        self._notify_instance(instance_id, registry_key)
```

### Pattern 3: Cascade Reload

```python
def event_dispatcher(self, event: FileChangeEvent):
    """Reload dependent classes when dependency changes"""
    if event.event_type == FileEventType.MODIFIED:
        module_name = self._extract_module_name(event.file_path)
        dependents = self._find_dependents(module_name)
        for dependent in dependents:
            self._on_change(dependent, event.library_identity)
```

## Execution Order Guarantee

```
1. File Change Detected
2. BaseClassRegistry.event_dispatcher() called
3. _on_change() / _on_creation() / _on_delete()
4. _reload_managed_module()
5. Internal state updated (classes registered/unregistered)
6. _notify_customer_callbacks() ← Factories notified
   ├─ Callback 1 executes
   ├─ Callback 2 executes
   └─ Callback N executes
7. _notify_registry_subscribers() ← Other registries notified
   ├─ Registry 1.event_dispatcher() (may cascade)
   ├─ Registry 2.event_dispatcher() (may cascade)
   └─ Registry N.event_dispatcher() (may cascade)
8. Event complete
```

## Error Handling Rules

1. **Callback errors are isolated** - One failed callback doesn't stop others
2. **Errors are logged** - Full exception info captured
3. **No rollback on callback failure** - Original reload remains valid
4. **Each callback wrapped in try/except** - Automatic protection
5. **Registry state always consistent** - Callbacks called after state update

## Performance Guidelines

- Keep callbacks under 100ms
- Log warnings for slow callbacks
- Defer heavy operations to background tasks
- Clear only necessary cache entries
- Avoid deep registry subscription chains (limit to 2-3 levels)

## Documentation Requirements

Each callback implementation should document:

1. **What it does** - Clear purpose statement
2. **When it's called** - Which events trigger it
3. **What it modifies** - State changes, cache clearing, etc.
4. **Performance expectations** - Execution time budget
5. **Error handling** - What happens on failure

---

**See Also:**
- `Hot_Reload_Callback_System_Specification.md` - Full specification
- `Hot_Reload_Callback_Summary.md` - Implementation summary
- `Hot_Reload_Callback_Diagrams.md` - Visual diagrams
