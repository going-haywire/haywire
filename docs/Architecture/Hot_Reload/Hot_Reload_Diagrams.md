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
│    ✓ WidgetRegistry change → SkinRegistry reload                │
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
