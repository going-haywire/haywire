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

---

class IWidget(ABC):

    @abstractmethod
    def __init__(self, element: DataPort):
        pass

    @abstractmethod
    def render(self):
        pass

---

## Architectural Layers
```
┌─────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (UI)                            │
│  - NiceGUI elements                                 │
│  - Widgets (BaseWidget subclasses)                  │
└─────────────────┬───────────────────────────────────┘
                  │ Bindings (TransformationPipeline)
                  ↓
┌─────────────────────────────────────────────────────┐
│  DATA LAYER (ViewModels)                            │
│  - DataField instances (in DataPort)                │
│  - Observable pattern (on_changed events)           │
└─────────────────┬───────────────────────────────────┘
                  │ Pipes (TransformationPipeline)
                  ↓
┌─────────────────────────────────────────────────────┐
│  BUSINESS LOGIC LAYER (Model)                       │
│  - BaseNode instances                               │
│  - Graph structure (edges, nodes)                   │
│  - Execution engine                                 │
└─────────────────────────────────────────────────────┘

CROSS-CUTTING CONCERNS:
┌─────────────────────────────────────────────────────┐
│  TRANSFORMATION LAYER                               │
│  - TransformerRegistry (adapters + converters)      │
│  - TransformationPipeline (execution engine)        │
│  - Hot-reload integration                           │
└─────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           SIMPLE NUMBER WIDGET                               │
│                   (After render() - Ready for interaction)                   │
└─────────────────────────────────────────────────────────────────────────────┘

                              USER INTERACTION
                                     ↓
                                     ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                            VIEW LAYER (UI)                                 │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  ui.number (NiceGUI Element)                                     │    │
│  │                                                                   │    │
│  │  Properties:                                                      │    │
│  │    .value = 42.0           ← User sees this                      │    │
│  │    .min = 0                                                       │    │
│  │    .max = 100                                                     │    │
│  │                                                                   │    │
│  │  Events:                                                          │    │
│  │    'update:modelValue' ────────┐  Fires when user changes value  │    │
│  └────────────────────────────────┼───────────────────────────────┘    │
│                                    │                                      │
└────────────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     │ (1) User changes slider
                                     │     → Event fires
                                     ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                      BINDING ENGINE (Active Binding)                       │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  PropertyBinding Instance                                        │    │
│  │                                                                   │    │
│  │  Configuration:                                                   │    │
│  │    source_field: DataField  ──────────┐                          │    │
│  │    target_property: "value"           │                          │    │
│  │    target_event: "update:modelValue" ←┼─ Registered listener    │    │
│  │    converter: PrimitiveUnwrappingConverter                       │    │
│  │    mode: TWO_WAY                                                  │    │
│  │    _is_active: True                                               │    │
│  │                                                                   │    │
│  │  Event Handler (registered):                                      │    │
│  │    def handler(e):                                                │    │
│  │      view_value = e.sender.value  # (2) Get: 42.0               │    │
│  │      ↓                                                            │    │
│  │      _sync_to_model(view_value)                                  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ↓                                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Converter Pipeline                                              │    │
│  │                                                                   │    │
│  │  (3) converter.to_model(42.0)                                    │    │
│  │      ↓                                                            │    │
│  │      PrimitiveUnwrappingConverter:                               │    │
│  │        - Input: 42.0 (raw float from UI)                         │    │
│  │        - Output: 42.0 (unwrapped value for DataField)           │    │
│  │                                                                   │    │
│  │  (4) Optional: converter.validate(42.0)                          │    │
│  │      ↓                                                            │    │
│  │      Returns: (True, None)  # Valid                              │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ↓                                      │
│                          (5) Update DataField                            │
│                              source_field.set_inner_value(42.0)          │
└────────────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Model - ViewModel)                        │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  DataField (SingleField)                                         │    │
│  │                                                                   │    │
│  │  State:                                                           │    │
│  │    _value: FLOAT(42.0)    ← PrimitiveType wrapper               │    │
│  │    _default: FLOAT(0.0)                                          │    │
│  │    is_dirty: True                                                 │    │
│  │    type_cls: FLOAT                                                │    │
│  │    is_pooled: False                                               │    │
│  │                                                                   │    │
│  │  Observable Pattern:                                              │    │
│  │    on_changed: Event[Any]  ──────┐  (6) Event triggered         │    │
│  │      Subscribers:                 │                               │    │
│  │        [binding_handler, ...]     │                               │    │
│  └───────────────────────────────────┼───────────────────────────────┘    │
│                                      │                                    │
│                                      │  fire()                            │
│                                      │    → Notifies all subscribers      │
└──────────────────────────────────────┼────────────────────────────────────┘
                                       │
                                       ↓
              ┌────────────────────────┴─────────────────────────┐
              │                                                   │
              ↓                                                   ↓
┌─────────────────────────────┐              ┌──────────────────────────────┐
│   GRAPH PROPAGATION         │              │   UI UPDATE (Model → View)   │
│   (If connected to outlet)  │              │                              │
│                             │              │  (7) Binding Engine handles  │
│   Pipe executes:            │              │      reverse flow            │
│     outlet.data → inlet.data│              │                              │
│                             │              │  Event Handler (registered): │
│   (Separate system)         │              │    def on_model_changed(val):│
│                             │              │      view_val = converter.   │
│                             │              │        to_view(val)          │
│                             │              │      ↓                       │
│                             │              │      (8) Convert:            │
│                             │              │        FLOAT(42.0) → 42.0   │
│                             │              │      ↓                       │
│                             │              │      ui_element.value = 42.0 │
│                             │              │                              │
│                             │              │  (UI stays in sync!)         │
└─────────────────────────────┘              └──────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                    INITIALIZATION PHASE (What happened earlier)
═══════════════════════════════════════════════════════════════════════════════

During NumberWidget.render():

  1. create_element() called
     ↓
     ui.number(value=0) created
     ↓
  
  2. configure_bindings() called
     ↓
     PropertyBinding created with:
       - source_field: self.data_field
       - converter: PrimitiveUnwrappingConverter()
       - mode: TWO_WAY
     ↓
     add_binding(binding) called
     ↓
  
  3. BindingEngine.activate(binding, ui_element) called
     ↓
     ┌─────────────────────────────────────────────────────┐
     │  _setup_model_to_view():                            │
     │    ✓ Creates: on_model_changed handler              │
     │    ✓ Subscribes: data_field.on_changed += handler   │
     │    ✓ Initial sync: Reads DataField → Updates UI     │
     │                                                      │
     │  _setup_view_to_model():                            │
     │    ✓ Creates: on_ui_change handler                  │
     │    ✓ Registers: ui_element.on('update:modelValue')  │
     └─────────────────────────────────────────────────────┘
     ↓
  
  4. Widget is now LIVE and reactive!
     - User changes UI → DataField updates
     - DataField changes → UI updates
     - Both directions work automatically


═══════════════════════════════════════════════════════════════════════════════
                         MEMORY LAYOUT (Simplified)
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│  NumberWidget Instance                                                      │
│                                                                             │
│    .ui_element ────────────────┐                                           │
│    .data_field ──────────┐     │                                           │
│    ._bindings = {         │     │                                           │
│      '__main__': [        │     │                                           │
│        PropertyBinding {  │     │                                           │
│          source_field ────┼─────┼─→ Points to DataField                    │
│          converter: PrimitiveUnwrappingConverter                            │
│          _is_active: True                                                   │
│          _cleanup_callbacks: [unsubscribe_fn, remove_handler_fn]           │
│        }                  │     │                                           │
│      ]                    │     │                                           │
│    }                      │     │                                           │
│    ._binding_engine ──────┼─────┼─→ BindingEngine (shared)                 │
└───────────────────────────┼─────┼─────────────────────────────────────────┘
                            │     │
                            ↓     ↓
              ┌─────────────────────────────┐    ┌────────────────────────┐
              │  DataField (in DataPort)    │    │  ui.number Element     │
              │                             │    │                        │
              │  ._value: FLOAT(42.0)       │    │  .value: 42.0         │
              │  .on_changed: Event         │    │  ._event_handlers: {  │
              │    subscribers: [           │    │    'update:modelValue':│
              │      binding_handler ───────┼────┼─→  [handler_fn]       │
              │    ]                        │    │  }                     │
              └─────────────────────────────┘    └────────────────────────┘
                      ↑                                      │
                      │                                      │
                      └──────── Two-way binding ─────────────┘
                         (Both directions active)


═══════════════════════════════════════════════════════════════════════════════
                    COMPLEX EXAMPLE: Temperature Widget
═══════════════════════════════════════════════════════════════════════════════

                         TWO BINDINGS IN ONE WIDGET

┌─────────────────────────────────────────────────────────────────────────────┐
│  TemperatureWidget                                                          │
│                                                                             │
│  ┌───────────────────────────────┐      ┌─────────────────────────────┐   │
│  │  ui.number (temp_input)       │      │  ui.label (conversion_label)│   │
│  │    .value = 75.0 (°F)         │      │    .text = "(23.9°C)"       │   │
│  └────────┬──────────────────────┘      └────────┬────────────────────┘   │
│           │                                       │                         │
│           │ Binding 1 (TWO_WAY)                  │ Binding 2 (ONE_WAY)     │
│           │                                       │                         │
│           ↓                                       ↓                         │
│  ┌──────────────────────────┐        ┌─────────────────────────────────┐  │
│  │  PropertyBinding          │        │  PropertyBinding                │  │
│  │    converter:             │        │    converter:                   │  │
│  │      UnitConversionConv   │        │      ConversionDisplayConv      │  │
│  │    target_property: value │        │    target_property: text        │  │
│  │    mode: TWO_WAY          │        │    mode: ONE_WAY                │  │
│  └──────────┬────────────────┘        └─────────────┬───────────────────┘  │
│             │                                        │                      │
│             └────────────────┬───────────────────────┘                      │
│                              │                                              │
│                              ↓                                              │
│                    ┌──────────────────────┐                                │
│                    │  DataField           │                                │
│                    │    _value: FLOAT(    │                                │
│                    │      value=23.9      │                                │
│                    │    )                 │                                │
│                    │  Stored in Celsius!  │                                │
│                    └──────────────────────┘                                │
│                                                                             │
│  User changes input to 80°F:                                               │
│    1. Binding 1 converts: 80°F → 26.7°C → DataField                       │
│    2. DataField.fire() triggers both bindings:                             │
│       - Binding 1: 26.7°C → 80°F → input.value (stays 80°F)              │
│       - Binding 2: 26.7°C → "(80.0°F)" → label.text (updates!)           │
└─────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                           KEY OBSERVATIONS
═══════════════════════════════════════════════════════════════════════════════

1. BIDIRECTIONAL FLOW:
   - User interaction → Binding → DataField (View → Model)
   - DataField.fire() → Binding → UI update (Model → View)

2. SINGLE SOURCE OF TRUTH:
   - DataField holds the canonical value
   - UI is a "view" of that value
   - Converters translate between representations

3. REACTIVE UPDATES:
   - Everything happens automatically via event subscriptions
   - No manual update() calls needed
   - Fire-and-forget from widget implementation perspective

4. MEMORY EFFICIENCY:
   - PropertyBinding: ~128 bytes
   - Event subscription: ~64 bytes
   - Total per binding: ~200 bytes
   - For 100 widgets: ~20 KB (negligible)

5. CLEANUP:
   - widget.cleanup() → deactivate all bindings
   - Bindings unsubscribe from events
   - No memory leaks

6. PERFORMANCE:
   - User interaction → DataField: ~500 ns
   - DataField → UI update: ~500 ns
   - Round trip: ~1 microsecond
   - Acceptable for UI (happens < 60 times/second)