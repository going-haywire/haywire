# Hot Reload Callback System - Implementation Summary

## Quick Reference

This document summarizes the key implementation points from the full specification.

## Two Callback Types

### 1. Customer Callbacks (for NodeFactory, NodeRenderFactory)

**Signature:**
```python
CustomerCallback = Callable[[str, List[str], LibraryIdentity], None]
# Parameters: registry_key, affected_class_names, library_identity
```

**Use for:**
- Clearing caches
- Notifying dependent objects
- Updating internal state

### 2. Registry Subscribers (for cross-registry dependencies)

**Interface:**
```python
class HotReloadRegistry(ABC):
    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        pass
```

**Use for:**
- CustomTypeRegistry changes → NodeRegistry reload
- WidgetRegistry changes → RendererRegistry reload
- Any registry-to-registry dependency

## API to Add to BaseClassRegistry

```python
class BaseClassRegistry(HotReloadRegistry, FolderScanMixin):
    
    def __init__(self):
        # ... existing code ...
        self._customer_callbacks: List[CustomerCallback] = []
        self._registry_subscribers: List[HotReloadRegistry] = []
    
    # Customer callback management
    def add_customer_callback(self, callback: CustomerCallback) -> None:
        """Register a callback for hot reload events"""
        
    def remove_customer_callback(self, callback: CustomerCallback) -> None:
        """Unregister a callback"""
    
    # Registry subscription management
    def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """Register another registry to receive events"""
        
    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """Unregister a registry subscriber"""
    
    # Internal notification (called from _reload_managed_module)
    def _notify_customer_callbacks(self, registry_key: str, 
                                   affected_class_names: List[str],
                                   library_identity: LibraryIdentity) -> None:
        """Notify customer callbacks"""
        
    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """Notify registry subscribers"""
```

## Where to Call Callbacks

### In `_reload_managed_module()` method:

```python
# After reloading a class
if classes_to_reload:
    for old_cls_name, new_cls in classes_to_reload:
        self._unregister_class(old_cls_name)
        new_key = self._register_class(new_cls, library_identity)
        
        # ✅ ADD THIS
        self._notify_customer_callbacks(
            registry_key=new_key,
            affected_class_names=[new_cls.__name__],
            library_identity=library_identity
        )

# After removing a class
if cls_names_to_remove:
    for cls_name in cls_names_to_remove:
        removed_cls = self._unregister_class(cls_name)
        
        # ✅ ADD THIS
        if removed_cls:
            self._notify_customer_callbacks(
                registry_key=cls_name,
                affected_class_names=[removed_cls.__name__],
                library_identity=library_identity
            )

# After adding a new class
if classes_to_add:
    for cls in classes_to_add:
        new_key = self._register_class(cls, library_identity)
        
        # ✅ ADD THIS
        if new_key:
            self._notify_customer_callbacks(
                registry_key=new_key,
                affected_class_names=[cls.__name__],
                library_identity=library_identity
            )
```

### In `event_dispatcher()` method:

```python
def event_dispatcher(self, event: FileChangeEvent):
    try:
        # ... existing event handling ...
        
        logging.info(f"...Hot Reloading -> DONE.")
        
        # ✅ ADD THIS - After successful reload
        self._notify_registry_subscribers(event)
        
    except Exception as e:
        # ... existing error handling ...
```

## Factory Integration

### NodeFactory needs:

```python
class NodeFactory:
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        # ✅ Register callback
        node_registry.add_customer_callback(self._on_node_reloaded)
    
    def _on_node_reloaded(self, registry_key: str, 
                         affected_class_names: List[str],
                         library_identity: LibraryIdentity) -> None:
        """Handle node reload - notify NodeWrappers"""
        affected_node_ids = self._get_nodes_using_key(registry_key)
        for listener in self._hot_reload_listeners:
            listener(registry_key, affected_node_ids)
```

### NodeRenderFactory needs:

```python
class NodeRenderFactory:
    def __init__(self, renderers_registry: RendererRegistry, 
                 widget_registry: WidgetRegistry):
        self.renderers_registry = renderers_registry
        self.widget_registry = widget_registry
        
        # ✅ Register callbacks
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

## Registry-to-Registry Example

### NodeRegistry subscribes to CustomTypeRegistry:

```python
class NodeRegistry(BaseClassRegistry):
    
    def set_custom_type_registry(self, custom_type_registry: CustomTypeRegistry):
        """Set up dependency on custom types"""
        self._custom_type_registry = custom_type_registry
        
        # ✅ Subscribe to custom type changes
        custom_type_registry.add_registry_subscriber(self)
    
    def event_dispatcher(self, event: FileChangeEvent):
        """
        Handle custom type changes by reloading dependent nodes.
        This is called when CustomTypeRegistry has a change.
        """
        if event.event_type == FileEventType.MODIFIED:
            module_name = self.resolve_module_name(...)
            affected_nodes = self._find_nodes_using_module(module_name)
            
            for node_module in affected_nodes:
                self._on_change(node_module, event.library_identity)
```

## DI Configuration Updates

```python
# In config.py HaywireModule

@provider
@singleton
def provide_node_factory(self, node_registry: NodeRegistry) -> NodeFactory:
    factory = NodeFactory(node_registry)
    # Callback registration happens in NodeFactory.__init__
    return factory

@provider
@singleton
def provide_node_render_factory(self, 
                                renderer_registry: RendererRegistry,
                                widget_registry: WidgetRegistry) -> NodeRenderFactory:
    factory = NodeRenderFactory(renderer_registry, widget_registry)
    # Callback registration happens in NodeRenderFactory.__init__
    return factory

@provider
@singleton
def provide_node_registry(self, 
                         custom_type_registry: CustomTypeRegistry) -> NodeRegistry:
    registry = NodeRegistry()
    
    # ✅ Set up cross-registry subscription
    registry.set_custom_type_registry(custom_type_registry)
    
    return registry
```

## Event Flow

```
File Change → FileWatcher → FileChangeEvent
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
                    └─→ NodeRegistry (if subscribed)
                        └─→ [Cascade reload]
```

## Error Handling

- Callbacks wrapped in try/except
- Errors logged but don't stop other callbacks
- Each callback is isolated
- Failed callbacks don't cause rollback

## Implementation Order

1. ✅ Add callback lists and methods to `BaseClassRegistry`
2. ✅ Add `_notify_*` calls to `_reload_managed_module()` and `event_dispatcher()`
3. ✅ Update `NodeFactory` to register callback
4. ✅ Update `NodeRenderFactory` to register callbacks
5. ✅ Add `set_custom_type_registry()` to `NodeRegistry`
6. ✅ Update DI configuration
7. ✅ Add tests

## Key Design Decisions

- **Synchronous callbacks**: Simpler, easier to reason about
- **Two-tier system**: Customer callbacks vs registry subscribers
- **Error isolation**: One failed callback doesn't break others
- **Order guarantees**: Customers before subscribers
- **No filtering**: Subscribers filter events themselves

See `Hot_Reload_Callback_System_Specification.md` for full details.
