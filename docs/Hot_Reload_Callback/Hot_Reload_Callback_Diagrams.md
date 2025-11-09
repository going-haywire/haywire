# Hot Reload Callback Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Hot Reload Callback System                       │
└─────────────────────────────────────────────────────────────────────┘

                              File Change
                                   │
                                   ▼
                           ┌───────────────┐
                           │ FileWatcher   │
                           └───────┬───────┘
                                   │
                                   ▼ FileChangeEvent
                           ┌───────────────┐
                           │ BaseClass     │
                           │ Registry      │
                           └───────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              _on_creation   _on_change    _on_delete
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                        _reload_managed_module()
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              Reload Classes  Add Classes   Remove Classes
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                    _notify_customer_callbacks()
                                   │
        ┌──────────────┬───────────┴───────────┬──────────────┐
        ▼              ▼                       ▼              ▼
   NodeFactory    NodeRender              Custom         Other
   Callback       Factory                Callback      Callbacks
                  Callback
        │              │                       │              │
        │              │                       │              │
        └──────────────┴───────────┬───────────┴──────────────┘
                                   ▼
                    _notify_registry_subscribers()
                                   │
        ┌──────────────┬───────────┴───────────┬──────────────┐
        ▼              ▼                       ▼              ▼
   NodeRegistry   Renderer                Widget         Other
   (subscriber)   Registry               Registry      Registries
                  (subscriber)          (subscriber)
        │
        │ event_dispatcher()
        ▼
   [Cascade Reload]
   (Find dependent nodes)
   (Reload affected nodes)
```

## Callback Type Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CUSTOMER CALLBACKS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Purpose: Notify direct consumers (factories) about changes         │
│                                                                      │
│  Signature:                                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Callable[[str, List[str], LibraryIdentity], None]              │ │
│  │                                                                 │ │
│  │ Parameters:                                                     │ │
│  │   - registry_key: str                                           │ │
│  │   - affected_class_names: List[str]                            │ │
│  │   - library_identity: LibraryIdentity                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Use Cases:                                                          │
│    ✓ NodeFactory updates NodeWrapper instances                      │
│    ✓ NodeRenderFactory clears renderer cache                        │
│    ✓ Any service that caches registry classes                       │
│                                                                      │
│  Registration:                                                       │
│    registry.add_customer_callback(my_callback)                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    REGISTRY SUBSCRIBERS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Purpose: Enable cross-registry dependencies and cascade reloads    │
│                                                                      │
│  Interface:                                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ class HotReloadRegistry(ABC):                                  │ │
│  │     @abstractmethod                                             │ │
│  │     def event_dispatcher(self, event: FileChangeEvent):        │ │
│  │         pass                                                    │ │
│  │                                                                 │ │
│  │ FileChangeEvent contains:                                       │ │
│  │   - file_path: str                                              │ │
│  │   - event_type: FileEventType                                   │ │
│  │   - library_identity: LibraryIdentity                          │ │
│  │   - timestamp: float                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Use Cases:                                                          │
│    ✓ CustomTypeRegistry change → NodeRegistry reload                │
│    ✓ WidgetRegistry change → RendererRegistry reload                │
│    ✓ Any registry-to-registry dependency                            │
│                                                                      │
│  Registration:                                                       │
│    source_registry.add_registry_subscriber(dependent_registry)      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Dependency Example: Custom Types → Nodes

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Scenario: Custom Type Changes                     │
└─────────────────────────────────────────────────────────────────────┘

Step 1: File Change
───────────────────
   User edits: libraries/mylib/types/my_type.py
                        │
                        ▼
   FileWatcher detects change
                        │
                        ▼
   FileChangeEvent(
       file_path="libraries/mylib/types/my_type.py",
       event_type=MODIFIED,
       library_identity=mylib,
       timestamp=...
   )

Step 2: CustomTypeRegistry Reload
──────────────────────────────────
   CustomTypeRegistry.event_dispatcher()
                        │
                        ▼
   _reload_managed_module('mylib.types.my_type')
                        │
                        ▼
   [MyType class reloaded]
                        │
                        ▼
   _notify_customer_callbacks(
       registry_key='mylib:MyType',
       affected_class_names=['MyType'],
       library_identity=mylib
   )
                        │
                        ▼
   [Customer callbacks execute - none in this case]
                        │
                        ▼
   _notify_registry_subscribers(FileChangeEvent)
                        │
                        ▼
   ┌───────────────────────────────────┐
   │  NodeRegistry subscribed!         │
   │  Its event_dispatcher() is called │
   └───────────────────────────────────┘

Step 3: NodeRegistry Cascade Reload
────────────────────────────────────
   NodeRegistry.event_dispatcher(FileChangeEvent)
                        │
                        ▼
   Analyze: Find nodes that import MyType
                        │
                        ▼
   Found: ['mylib.nodes.processor', 'mylib.nodes.workflow']
                        │
                        ▼
   For each affected node:
       _on_change('mylib.nodes.processor', mylib)
           │
           ▼
       _reload_managed_module('mylib.nodes.processor')
           │
           ▼
       [ProcessorNode class reloaded]
           │
           ▼
       _notify_customer_callbacks(
           registry_key='mylib:ProcessorNode',
           affected_class_names=['ProcessorNode'],
           library_identity=mylib
       )
           │
           ▼
       ┌───────────────────────────────────┐
       │  NodeFactory callback executes!   │
       │  Notifies NodeWrapper instances   │
       └───────────────────────────────────┘

Step 4: NodeFactory Updates NodeWrappers
─────────────────────────────────────────
   NodeFactory._on_node_reloaded(
       registry_key='mylib:ProcessorNode',
       affected_class_names=['ProcessorNode'],
       library_identity=mylib
   )
                        │
                        ▼
   Find all NodeWrappers using 'mylib:ProcessorNode'
                        │
                        ▼
   For each NodeWrapper:
       Trigger migration to new class
       Re-initialize node instance
       Update UI
```

## Implementation Checklist

```
BaseClassRegistry Implementation
─────────────────────────────────
 ☐ Add _customer_callbacks list
 ☐ Add _registry_subscribers list
 ☐ Implement add_customer_callback()
 ☐ Implement remove_customer_callback()
 ☐ Implement add_registry_subscriber()
 ☐ Implement remove_registry_subscriber()
 ☐ Implement _notify_customer_callbacks()
 ☐ Implement _notify_registry_subscribers()
 ☐ Update _reload_managed_module() to call _notify_customer_callbacks()
 ☐ Update event_dispatcher() to call _notify_registry_subscribers()

NodeFactory Integration
───────────────────────
 ☐ Add _on_node_reloaded() method
 ☐ Register callback in __init__()
 ☐ Implement logic to notify NodeWrapper instances

NodeRenderFactory Integration
──────────────────────────────
 ☐ Add _on_renderer_reloaded() method
 ☐ Add _on_widget_reloaded() method
 ☐ Register callbacks in __init__()
 ☐ Implement cache clearing logic

NodeRegistry Cross-Registry Subscription
─────────────────────────────────────────
 ☐ Add set_custom_type_registry() method
 ☐ Subscribe to CustomTypeRegistry
 ☐ Implement event_dispatcher() to handle custom type changes
 ☐ Implement logic to find nodes using custom types
 ☐ Trigger reload of dependent nodes

DI Configuration Updates
────────────────────────
 ☐ Update provide_node_factory() if needed
 ☐ Update provide_node_render_factory() if needed
 ☐ Update provide_node_registry() to set custom_type_registry
 ☐ Verify all registries are properly wired

Testing
───────
 ☐ Unit test: Customer callback registration/removal
 ☐ Unit test: Registry subscriber registration/removal
 ☐ Unit test: Callback invocation on reload
 ☐ Unit test: Error isolation between callbacks
 ☐ Integration test: NodeFactory hot reload flow
 ☐ Integration test: NodeRenderFactory cache clearing
 ☐ Integration test: CustomType → Node cascade reload
 ☐ Integration test: Error recovery and rollback

Documentation
─────────────
 ☐ Update BaseClassRegistry docstrings
 ☐ Update NodeFactory docstrings
 ☐ Update NodeRenderFactory docstrings
 ☐ Add usage examples
 ☐ Document callback order guarantees
```

## Error Handling Flow

```
Callback Execution with Error Isolation
────────────────────────────────────────

_notify_customer_callbacks(registry_key, class_names, lib_identity)
    │
    ├─→ Try: Callback 1
    │   ├─ Success ✓
    │   └─ Continue to next
    │
    ├─→ Try: Callback 2
    │   ├─ Exception ✗
    │   ├─ Log error
    │   ├─ DON'T rollback registry
    │   └─ Continue to next
    │
    └─→ Try: Callback 3
        ├─ Success ✓
        └─ Done

Key Points:
  • Each callback wrapped in try/except
  • Errors logged but don't stop other callbacks
  • Failed callbacks don't trigger rollback
  • Original reload remains successful
```

## Performance Considerations

```
Callback Performance Profile
────────────────────────────

                           Time Budget per Callback
                           ────────────────────────
Fast (< 10ms)             ████████████████████████ Preferred
Acceptable (10-100ms)     ████████████            OK
Slow (100-1000ms)         ████                    ⚠ Warning
Very Slow (> 1000ms)      █                       ❌ Problem

Guidelines:
  • Keep callbacks lightweight
  • Defer heavy operations
  • Consider async for slow operations (future)
  • Log warnings for callbacks > 100ms
  • Profile callback execution time

Registry Subscription Depth
───────────────────────────

Depth 1:  CustomTypeRegistry → NodeRegistry
          [Simple, Fast] ✓

Depth 2:  CustomTypeRegistry → NodeRegistry → RendererRegistry
          [Acceptable] ✓

Depth 3+: [Watch for cycles!] ⚠
          Consider adding cycle detection

Recommendation:
  • Keep subscription chains shallow
  • Document all cross-registry dependencies
  • Add cycle detection if depth > 2
```
