---
status: draft
doc_template: canonical-example
scope: Authoring widgets — SimpleWidget / BaseWidget subclasses, the @widget decorator, type binding, lifecycle
see-also:
  - ../datatypes/datatype-canon.md
  - ../../guides/ports.md
  - ../adapters/adapter-canon.md
  - ../../reference/glossary.md
---

# Widget — Canonical Example

## 1. What it solves

A **widget** is the inline UI control rendered inside a port on a node card. It binds bidirectionally to the port's value: dragging a slider updates the port; setting the port from a worker writes the new value to the slider. Widgets exist so node authors don't have to think about UI plumbing — declare a port type with a widget binding, and the canvas renders the right control.

You author a widget when:

- You have a custom datatype that needs its own input control (a `Color` type with a colour picker, a `MathOperation` enum with a select dropdown, a `Vector3` type with three coupled inputs).
- You want a richer control than the framework's defaults for an existing type (a Blender-style number drag instead of a plain spinbox).
- You're building a read-only display widget for an outlet or pooled inlet (table, list, formatted preview).

A widget is *not* an editor or a panel — those are workspace-level UI components. A widget lives **inside a port row** on a node card.

## 2. How it fits

```text
@widget(compatible_types=[FLOAT])  ──► WidgetRegistry  ──►  port renders a widget
class FastNumberWidget(SimpleWidget):                          when the canvas
    def create_element(self):                                  draws the node card
        return ui.number(value=0)
                                       Bidirectional binding:
                                         port → ui_element     (worker write)
                                         ui_element → port    (user interaction)
```

Two base classes cover the surface:

| Class | Use when… |
|---|---|
| **`SimpleWidget`** | Single UI element bound to one DataPort. Direct two-way sync. No converter, no validator, no debouncing. ~95% of widgets in the codebase use this. |
| **`BaseWidget`** | Multiple UI elements bound to one DataPort (e.g. a Vector3 with x/y/z inputs), or per-element validation, or read-only display widgets that transform the port value into a custom view. |

Both implement `IWidget`. The `@widget` decorator attaches `class_identity` (used by `WidgetRegistry` for hot-reload) and registers `compatible_types` (which datatypes the widget accepts).

**Boundaries.** What datatypes *are* lives in [components/datatypes](../datatypes/datatype-canon.md). How a port binds a widget at creation time (the `widget_key` / `widget_config` kwargs on `as_inlet`) lives in [guides/ports](../../guides/ports.md). The runtime layer that converts values between incompatible types lives in [components/adapters](../adapters/adapter-canon.md) and [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

## 3. Important concepts

**The `@widget` decorator.** Sets `class_identity` and `class_library` on the widget class so `WidgetRegistry` (a `BaseRegistry` subclass) can find it. The `compatible_types` parameter is the list of `IType` classes this widget can edit. A widget is offered for a port when the port's type is in (or inherits from) one of the compatible types.

```python
@widget(description='Fast number input', compatible_types=[FLOAT, INT])
class NumberWidget(SimpleWidget):
    ...
```

**`SimpleWidget` lifecycle.** Three methods you override; the rest is handled by the base:

```python
class MyWidget(SimpleWidget):
    UI_PROPERTY = "value"            # default — the NiceGUI element prop to bind
    UI_EVENT = "update:modelValue"   # default — the event that fires on user change
    IS_READONLY = False              # default

    def create_element(self):        # required: build and return the NiceGUI element
        return ui.number(value=0)

    def get_default_value(self):     # optional: what to show when the port has no value
        return 0.0
```

The base class handles:

- **Two-way binding.** `port._data.on_changed += self._sync_to_view` (model → view); `ui_element.on(UI_EVENT, self._sync_to_model)` (view → model).
- **Initial sync.** Reads from the port and writes to the element on first render.
- **Cleanup.** When the page client disconnects (browser tab closed), `cleanup()` unsubscribes from events and detaches the element.

**`SimpleWidget` constraints (when to graduate to `BaseWidget`).**

- Single UI element only.
- Single value binding only.
- No custom converters between port value and UI value (the framework unwraps `PrimitiveType` automatically; for anything else you need `BaseWidget`).
- No debouncing or per-keystroke validation.

**Configuration via `widget_config`.** The port author passes config to the widget when wiring it up:

```python
# In a node's init():
self.add(FLOAT.as_inlet(
    'amount',
    widget_key='haybale_core:widget:NumberWidget',
    widget_config={
        'properties': {'min': 0, 'max': 100, 'step': 0.5, 'precision': 2},
    },
))
```

Inside the widget, `self._config` holds the `widget_config` dict. Convention: read user-facing properties from `self._config.get('properties', {})`:

```python
def create_element(self):
    props = self._config.get('properties', {})
    kwargs: dict[str, Any] = {'value': 0}
    for prop in ['min', 'max', 'step', 'precision']:
        if prop in props:
            kwargs[prop] = props[prop]
    return NumberDrag(**kwargs).classes('w-full')
```

**The `T.config(...)` pattern.** Widget classes expose a `config()` classmethod that returns a `widget_config` dict — letting node authors call `NumberWidget.config(properties={'min': 0, 'max': 100})` instead of manually constructing the dict and passing the registry key.

**Read-only display widgets.** Set `IS_READONLY = True`. The base class skips registering the view-to-model handler, so user interaction (if any UI element is interactive) won't propagate back. Useful for outlet display, pooled-value tables, status indicators.

**`BaseWidget` for multi-element widgets.** When one DataPort has multiple UI elements (a Vector3 with x/y/z inputs, a colour picker with both a swatch and a hex input). You override more methods, manage your own bindings, and read/write the port directly. Less common; use `SimpleWidget` first and graduate only when necessary.

**Hot-reload.** `WidgetRegistry` extends `BaseRegistry`, so when a library reloads, widget classes are re-registered. Existing widgets in the running UI are *not* swapped (tearing down a NiceGUI element while it's connected is risky); newly-created widgets pick up the new class.

**Imports** (verified against codebase 2026-05):

```python
from haywire.ui.widget.simple import SimpleWidget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.interface import IWidget
```

## 4. Live example from the codebase

Source: [`barn/haybale-example/haybale_example/widgets/knob_widget.py`](../../../barn/haybale-example/haybale_example/widgets/knob_widget.py)

`KnobWidget` — a `SimpleWidget` binding a `ui.knob` element to `FLOAT` or `INT` ports. Demonstrates the full `SimpleWidget` authoring surface: `@widget` decorator with `compatible_types`, `create_element()` reading `self._config`, and `get_default_value()`:

```python
--8<-- "barn/haybale-example/haybale_example/widgets/knob_widget.py:knob_widget"
```

Using it from a node's `init()`:

```python
self.add(FLOAT.as_inlet(
    'angle',
    label='Angle',
    widget=KnobWidget.config(properties={'min': 0, 'max': 360, 'step': 1, 'color': 'teal'}),
))
```

What this example exercises:

| Concept | Where |
|---|---|
| `@widget(compatible_types=[FLOAT, INT])` decorator | class decoration |
| `SimpleWidget` subclass for two-way primitive binding | `KnobWidget(SimpleWidget)` |
| `create_element()` returning a NiceGUI element | `ui.knob(...)` |
| `self._config.get('properties', {})` driving element kwargs | `min`, `max`, `step`, `color`, `size` |
| `get_default_value()` override | returns `0.0` |
| `UI_PROPERTY` / `UI_EVENT` at defaults (`'value'` / `'update:modelValue'`) | not overridden — knob uses the defaults |
| `T.config(properties={...})` call-site pattern | usage example above |

For datatype authoring (including the `MathOperation` derived primitive used here), see [components/datatypes](../datatypes/datatype-canon.md). For the underlying port surface (`as_inlet`, `widget_config`, `widget_key`), see [guides/ports](../../guides/ports.md). For type-pair adapters (used when an outlet of one type connects to an inlet of a different type), see [components/adapters](../adapters/adapter-canon.md).

---

## Quick reference

### Authoring checklist

- [ ] `@widget(description='...', compatible_types=[Type1, Type2])` decorator
- [ ] Inherit from `SimpleWidget` (default) or `BaseWidget` (for multi-element)
- [ ] Implement `create_element()` returning a NiceGUI element
- [ ] Implement `get_default_value()` for the type
- [ ] Override `UI_PROPERTY` / `UI_EVENT` if the element doesn't use `'value'` / `'update:modelValue'`
- [ ] Set `IS_READONLY = True` for display-only widgets
- [ ] Override `_sync_to_view` if you need value formatting before display

### Imports

```python
from haywire.ui.widget.simple import SimpleWidget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.interface import IWidget
```

### Common UI_PROPERTY / UI_EVENT pairs

| Element | `UI_PROPERTY` | `UI_EVENT` |
|---|---|---|
| `ui.number`, `ui.input`, `ui.select`, `ui.slider`, `ui.switch`, `ui.checkbox` | `value` (default) | `update:modelValue` (default) |
| `ui.label` | `text` | (read-only — set `IS_READONLY = True`) |
| `NumberDrag` (custom) | `value` | `update:modelValue` |
| `ui.color_input` | `value` | `update:modelValue` |

### Per-port override at the call site

```python
self.add(FLOAT.as_inlet(
    'amount',
    widget_key='my_lib:widget:NumberWidget',
    widget_config={'properties': {'min': 0, 'max': 100}},
))
```

The `widget_key` is `<library_id>:widget:<class_name>`. Register it once via `@widget` and you can reference it from any node.
