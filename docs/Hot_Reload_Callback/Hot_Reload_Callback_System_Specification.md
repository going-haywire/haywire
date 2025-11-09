# Hot Reload Callback System Specification

## Overview

This specification defines the callback system for `BaseClassRegistry` to notify interested parties about hot reload events. The system supports two distinct callback patterns:

1. **Customer Callbacks**: Direct consumers (NodeFactory, NodeRenderFactory) subscribe to registry events
2. **Registry-to-Registry Callbacks**: Registries subscribe to each other for cross-registry dependencies (e.g., CustomTypeRegistry changes trigger NodeRegistry updates)

## Requirements

### 1. Customer Callbacks (Factory Pattern)

Factories and other direct consumers need to respond to hot reload events to update their internal state.

#### Use Cases

- **NodeFactory**: Notify NodeWrapper instances when their registry_key has been reloaded
- **NodeRenderFactory**: Clear renderer cache when a renderer class is reloaded
- **Future Extensions**: Any consumer that caches or tracks registry classes

#### Callback Signature

```python
CustomerCallback = Callable[[str, List[str], LibraryIdentity], None]
```

**Parameters:**
- `registry_key: str` - The registry key that was affected (e.g., "example:MyNode")
- `affected_class_names: List[str]` - List of class names that were modified (supports multiple classes per module)
- `library_identity: LibraryIdentity` - The library where the change occurred

**When Invoked:**
- After a class is successfully reloaded
- After a new class is added
- After a class is removed

### 2. Registry-to-Registry Callbacks (Observer Pattern)

Registries can depend on other registries and need to react to their changes.

#### Use Cases

- **NodeRegistry → CustomTypeRegistry**: When a custom type is modified, nodes using that type must be reloaded
- **RendererRegistry → WidgetRegistry**: When a widget is modified, renderers using that widget might need updates
- **Future Extensions**: Any cross-registry dependency

#### Callback Signature

Uses the existing `HotReloadRegistry` interface:

```python
class HotReloadRegistry(ABC):
    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle file change events from dependent registries"""
        pass
```

**Parameters:**
- `event: FileChangeEvent` - Complete event information including:
  - `file_path: str`
  - `event_type: FileEventType` (CREATED, MODIFIED, DELETED)
  - `library_identity: LibraryIdentity`
  - `timestamp: float`

**When Invoked:**
- After all customer callbacks have been notified
- After the registry's own internal state has been updated
- Only for registries that have subscribed to this registry

## API Design

### BaseClassRegistry Extensions

```python
class BaseClassRegistry(HotReloadRegistry, FolderScanMixin):
    """Abstract base class for all class registries"""
  
    def __init__(self):
        # Existing attributes...
        
        # NEW: Customer callback management
        self._customer_callbacks: List[CustomerCallback] = []
        
        # NEW: Registry-to-registry subscriptions
        self._registry_subscribers: List[HotReloadRegistry] = []
    
    # ============================================================================
    # Customer Callback Management
    # ============================================================================
    
    def add_customer_callback(self, callback: CustomerCallback) -> None:
        """
        Register a customer callback to be notified of hot reload events.
        
        Customer callbacks are invoked immediately after a class is reloaded,
        added, or removed. They receive the registry key and affected class names.
        
        Args:
            callback: Function to call on hot reload events
        """
        if callback not in self._customer_callbacks:
            self._customer_callbacks.append(callback)
    
    def remove_customer_callback(self, callback: CustomerCallback) -> None:
        """
        Unregister a customer callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._customer_callbacks:
            self._customer_callbacks.remove(callback)
    
    # ============================================================================
    # Registry-to-Registry Subscription Management
    # ============================================================================
    
    def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Register another registry to be notified of hot reload events.
        
        Registry subscribers are invoked after customer callbacks and receive
        complete FileChangeEvent information for their own processing.
        
        Args:
            registry: Another registry that needs to react to changes in this registry
        """
        if registry not in self._registry_subscribers:
            self._registry_subscribers.append(registry)
    
    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Unregister a registry subscriber.
        
        Args:
            registry: The registry to unsubscribe
        """
        if registry in self._registry_subscribers:
            self._registry_subscribers.remove(registry)
    
    # ============================================================================
    # Internal Notification Methods
    # ============================================================================
    
    def _notify_customer_callbacks(self, registry_key: str, 
                                   affected_class_names: List[str],
                                   library_identity: LibraryIdentity) -> None:
        """
        Notify all customer callbacks about a hot reload event.
        
        This method is called internally during hot reload operations.
        Errors in individual callbacks are logged but don't stop other callbacks.
        
        Args:
            registry_key: The registry key affected
            affected_class_names: List of class names modified
            library_identity: The library where the change occurred
        """
        for callback in self._customer_callbacks:
            try:
                callback(registry_key, affected_class_names, library_identity)
            except Exception as e:
                logging.error(
                    f"Customer callback failed for registry_key '{registry_key}': {e}",
                    exc_info=True
                )
    
    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """
        Notify all registry subscribers about a hot reload event.
        
        This method is called after customer callbacks have been notified.
        Registry subscribers receive the complete event information and can
        perform their own dependency analysis and reloading.
        
        Args:
            event: The file change event that triggered the reload
        """
        for registry in self._registry_subscribers:
            try:
                registry.event_dispatcher(event)
            except Exception as e:
                logging.error(
                    f"Registry subscriber callback failed for {event.file_path}: {e}",
                    exc_info=True
                )
```

## Integration Points

### 1. Modify `_reload_managed_module` Method

Update the existing TODO markers to invoke callbacks:

```python
def _reload_managed_module(self, module_name: str, library_identity: LibraryIdentity):
    """
    Reload a single managed module with registry-specific handling.
    Called by the _on_change method.
    """
    # ... existing snapshot and reload logic ...
    
    if classes_to_reload:
        for old_cls_name, new_cls in classes_to_reload:
            self._unregister_class(old_cls_name)
            new_key = self._register_class(new_cls, library_identity)
            logging.info(
                f"Library '{library_identity.label}': "
                f"...Re-loaded and re-registered from {module_name}")
            
            # NEW: Notify customer callbacks about reload
            self._notify_customer_callbacks(
                registry_key=new_key,
                affected_class_names=[new_cls.__name__],
                library_identity=library_identity
            )
            
    if cls_names_to_remove:
        for cls_name in cls_names_to_remove:
            removed_cls = self._unregister_class(cls_name)
            
            # NEW: Notify customer callbacks about removal
            if removed_cls:
                self._notify_customer_callbacks(
                    registry_key=cls_name,
                    affected_class_names=[removed_cls.__name__],
                    library_identity=library_identity
                )
                
    if classes_to_add:
        for cls in classes_to_add:
            new_key = self._register_class(cls, library_identity)
            
            # NEW: Notify customer callbacks about addition
            if new_key:
                self._notify_customer_callbacks(
                    registry_key=new_key,
                    affected_class_names=[cls.__name__],
                    library_identity=library_identity
                )
```

### 2. Modify `event_dispatcher` Method

Add registry subscriber notification at the end of successful event handling:

```python
def event_dispatcher(self, event: FileChangeEvent):
    """
    Dispatch file change events to the appropriate handlers based on event type.
    """
    try:
        # ... existing event handling logic ...
        
        logging.info(
            f"Library '{event.library_identity.label}': "
            f"...Hot Reloading -> DONE.")
        
        # NEW: Notify registry subscribers after successful reload
        self._notify_registry_subscribers(event)

    except Exception as e:
        # ... existing error handling ...
```

## Usage Examples

### Example 1: NodeFactory Registration

```python
class NodeFactory:
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        
        # Register for hot reload notifications
        self.node_registry.add_customer_callback(self._on_node_reloaded)
    
    def _on_node_reloaded(self, registry_key: str, 
                         affected_class_names: List[str],
                         library_identity: LibraryIdentity) -> None:
        """Handle node hot reload events"""
        logging.info(f"Node reloaded: {registry_key}")
        
        # Notify NodeWrapper instances about the reload
        affected_node_ids = self._get_nodes_using_key(registry_key)
        for listener in self._hot_reload_listeners:
            listener(registry_key, affected_node_ids)
```

### Example 2: NodeRenderFactory Registration

```python
class NodeRenderFactory:
    def __init__(self, renderers_registry: RendererRegistry, 
                 widget_registry: WidgetRegistry):
        self.renderers_registry = renderers_registry
        self.widget_registry = widget_registry
        
        # Register for hot reload notifications
        self.renderers_registry.add_customer_callback(self._on_renderer_reloaded)
        self.widget_registry.add_customer_callback(self._on_widget_reloaded)
    
    def _on_renderer_reloaded(self, registry_key: str,
                             affected_class_names: List[str],
                             library_identity: LibraryIdentity) -> None:
        """Handle renderer hot reload events"""
        logging.info(f"Renderer reloaded: {registry_key}")
        
        # Clear cache for affected renderer
        for class_name in affected_class_names:
            if class_name in self._renderer_cache:
                del self._renderer_cache[class_name]
    
    def _on_widget_reloaded(self, registry_key: str,
                           affected_class_names: List[str],
                           library_identity: LibraryIdentity) -> None:
        """Handle widget hot reload events"""
        logging.info(f"Widget reloaded: {registry_key}")
        
        # Clear entire cache as widgets might be used by any renderer
        self.clear_cache()
```

### Example 3: Registry-to-Registry Dependencies

```python
class NodeRegistry(BaseClassRegistry):
    def __init__(self):
        super().__init__()
        # Will be set during DI initialization
        self._custom_type_registry: Optional[CustomTypeRegistry] = None
    
    def set_custom_type_registry(self, custom_type_registry: CustomTypeRegistry):
        """Set the custom type registry and subscribe to its changes"""
        self._custom_type_registry = custom_type_registry
        
        # Subscribe to custom type changes
        custom_type_registry.add_registry_subscriber(self)
    
    def event_dispatcher(self, event: FileChangeEvent):
        """
        Handle events from subscribed registries (e.g., CustomTypeRegistry).
        
        When a custom type changes, we need to reload all nodes that use it.
        """
        if event.event_type == FileEventType.MODIFIED:
            # Extract the custom type name from the event
            module_name = self.resolve_module_name(
                Path(event.file_path),
                event.library_identity.folder_path,
                event.library_identity.module_name
            )
            
            # Find all nodes that import this custom type
            affected_nodes = self._find_nodes_using_module(module_name)
            
            # Reload affected nodes
            for node_module in affected_nodes:
                logging.info(
                    f"Reloading node '{node_module}' due to custom type change")
                self._on_change(node_module, event.library_identity)
```

## Dependency Injection Setup

Update `HaywireModule` in `config.py` to wire up registry dependencies:

```python
class HaywireModule(Module):
    @provider
    @singleton
    def provide_node_factory(self, node_registry: NodeRegistry) -> NodeFactory:
        factory = NodeFactory(node_registry)
        
        # Register factory as customer callback
        node_registry.add_customer_callback(factory._on_node_reloaded)
        
        return factory
    
    @provider
    @singleton
    def provide_node_render_factory(self, 
                                    renderer_registry: RendererRegistry,
                                    widget_registry: WidgetRegistry) -> NodeRenderFactory:
        factory = NodeRenderFactory(renderer_registry, widget_registry)
        
        # Register factory for hot reload callbacks
        renderer_registry.add_customer_callback(factory._on_renderer_reloaded)
        widget_registry.add_customer_callback(factory._on_widget_reloaded)
        
        return factory
    
    @provider
    @singleton
    def provide_node_registry(self, 
                             custom_type_registry: CustomTypeRegistry) -> NodeRegistry:
        registry = NodeRegistry()
        
        # Set up registry-to-registry subscriptions
        custom_type_registry.add_registry_subscriber(registry)
        
        return registry
```

## Event Flow Diagram

```
File Change Detected
        ↓
FileWatcher → FileChangeEvent
        ↓
BaseClassRegistry.event_dispatcher()
        ↓
  ├─→ _on_creation()
  ├─→ _on_change()  ───→  _reload_managed_module()
  └─→ _on_delete()
        ↓
  [Internal State Updated]
        ↓
  _notify_customer_callbacks()  ← Execute in sequence
        ├─→ NodeFactory callback
        ├─→ NodeRenderFactory callback
        └─→ [Other customer callbacks]
        ↓
  _notify_registry_subscribers()  ← Execute in sequence
        ├─→ NodeRegistry.event_dispatcher()
        ├─→ [Other registry subscribers]
        └─→ [Recursive reload cascade]
        ↓
  Event Complete
```

## Error Handling

### Customer Callback Errors
- Errors in customer callbacks are logged but don't prevent other callbacks
- Failed callbacks don't cause rollback of successful reload
- Each callback is isolated with try/except

### Registry Subscriber Errors
- Errors in registry subscribers are logged but don't prevent other subscribers
- Cascading failures are prevented by isolation
- Each subscriber handles its own rollback if needed

### Callback Order Guarantees
1. Internal state update completes first
2. All customer callbacks execute before registry subscribers
3. Within each group, callbacks execute in registration order
4. No guarantees across different registries (parallel reloads possible)

## Performance Considerations

### Callback Limits
- No artificial limit on number of callbacks
- Callbacks should be lightweight and fast
- Heavy operations should be deferred to background tasks

### Registry Subscription Depth
- Watch for circular dependencies between registries
- Implement cycle detection if deep subscription chains emerge
- Document subscription relationships clearly

### Callback Execution Time
- Log warnings if callbacks take >100ms
- Consider async callbacks for long operations in future versions

## Testing Strategy

### Unit Tests
- Test callback registration/unregistration
- Test callback invocation on reload/add/remove
- Test error isolation between callbacks
- Test registry subscriber chains

### Integration Tests
- Test NodeFactory hot reload flow
- Test NodeRenderFactory cache clearing
- Test CustomType → Node reload cascade
- Test error recovery and rollback

### Performance Tests
- Test with 100+ registered callbacks
- Test deep registry subscription chains
- Test concurrent reload events

## Migration Path

### Phase 1: Add Infrastructure (Current)
- Add callback lists to BaseClassRegistry
- Add registration methods
- Update documentation

### Phase 2: Integrate Factories
- Update NodeFactory to use callbacks
- Update NodeRenderFactory to use callbacks
- Update DI configuration

### Phase 3: Registry Dependencies
- Implement NodeRegistry → CustomTypeRegistry subscription
- Implement other cross-registry dependencies as needed
- Add cycle detection

### Phase 4: Optimization
- Profile callback performance
- Consider async callbacks if needed
- Add monitoring and metrics

## Open Questions

1. **Should we support priority ordering for callbacks?**
   - Pro: Allows critical updates first
   - Con: Adds complexity
   - Decision: Start without, add if needed

2. **Should we support async callbacks?**
   - Pro: Non-blocking for heavy operations
   - Con: Adds complexity, harder to reason about state
   - Decision: Start synchronous, consider async in future

3. **Should we implement callback filtering by library?**
   - Pro: Reduce unnecessary callback invocations
   - Con: More complex API
   - Decision: Start without, subscribers can filter internally

4. **How deep should registry subscription chains go?**
   - Pro: Full flexibility
   - Con: Risk of cycles and hard-to-debug cascades
   - Decision: Document carefully, add cycle detection if issues arise

## Conclusion

This callback system provides a flexible, extensible mechanism for hot reload notifications while maintaining clean separation of concerns between registries, factories, and other consumers. The dual-pattern approach (customer callbacks + registry subscriptions) handles both direct consumer needs and cross-registry dependencies elegantly.
