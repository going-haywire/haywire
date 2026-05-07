## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        EdgeWrapper                          │
│  - Manages Edge instance and adapter chain                 │
│  - Handles hot reload from AdapterFactory                   │
│  - Notifies subscribers (UIEdge) of state changes           │
└────────────────────────┬────────────────────────────────────┘
                         │ Lifecycle Events
                         │ (CLASS_RELOADED, etc.)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                          UIEdge                             │
│  - Subscribes to EdgeWrapper events                         │
│  - Calculates visual state from wrapper state               │
│  - Emits SyncConnectionUpdateEvent when state changes       │
│  - Provides metrics for context menu                        │
└────────────────────────┬────────────────────────────────────┘
                         │ SyncConnectionUpdateEvent
                         │ {color, width, dasharray, opacity}
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   GraphCanvasVue                            │
│  - Receives sync event                                      │
│  - Routes to _syncConnectionUpdate()                        │
│  - Updates SVG path attributes                              │
│  - Toggles CSS classes                                      │
└─────────────────────────────────────────────────────────────┘
```

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
    ├─→ NodeFactory._on_node_reloaded()
    └─→ NodeRenderFactory._on_renderer_reloaded()/_on_widget_reloaded()
    ↓
_notify_registry_subscribers()
    └─→ NodeRegistry.event_dispatcher() (for custom type changes)
        └─→ [Cascade reload of dependent nodes]
```

### Example: Complete Data Flow
```
User moves slider
       ↓
   [ui.slider.value = 75.0]
       ↓ (binding with PrimitiveWrappingConverter)
   [Inlet DataField<FLOAT> = FLOAT(75.0)]
       ↓ (internal - part of node execution)
   [Node processes value]
       ↓
   [Outlet DataField<Temperature> = Temperature(75.0)]
       ↓ (pipe with TemperatureToFloatAdapter)
   [Inlet DataField<FLOAT> = FLOAT(75.0)]
       ↓ (binding with PrimitiveUnwrappingConverter)
   [ui.number.value = 75.0]
```

## Architecture Components

The Haywire Editor follows a clean 5-layer architecture with strict separation of concerns, event-driven communication, and multi-session support:

```
┌─────────────────────────────────────────────────────────────┐
│                    HaywireApplication                       │
│              (Bootstrap & Coordination)                     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      EditorUI                               │
│              (Layout & Visual Components)                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   HaywireEditor                             │
│              (Core Business Logic)                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   SessionManager                            │
│              (Multi-Client Coordination)                    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     GraphCanvas                             │
│              (Visual & Interactions)                        │
└─────────────────────────────────────────────────────────────┘
```