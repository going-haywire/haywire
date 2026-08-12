---
status: stable
doc_template: canonical-example
scope: Authoring widgets — BaseWidget subclasses, the @widget decorator, the build()/bind() surface, the on_model_changed() floor, lifecycle
see-also:
  - ../datatypes/datatype-canon.md
  - ../../guides/ports.md
  - ../adapters/adapter-canon.md
  - ../../reference/glossary.md
---

# Widget — Canonical Example

## 1. What it solves

A **widget** is the inline UI control rendered inside a port on a node card. It is bound to the port's value: dragging a slider updates the port; setting the port from a worker writes the new value back into the slider. Widgets exist so node authors don't have to think about UI plumbing — declare a port with a widget, and the canvas renders the right control inside the port row.

You author a widget when:

- You have a custom datatype that needs its own input control (a `Color` type with a colour picker, a `Vector3` type with three coupled inputs, a `MathOperation` enum with a select dropdown).
- You want a richer control than the framework's defaults for an existing type (a Blender-style number drag instead of a plain spinbox).
- You need a whole-value display (a streaming image preview, a formatted label, a swatch) driven from the port value.

A widget is *not* an editor or a panel — those are workspace-level UI components. A widget lives **inside a port row** on a node card.

## 2. How it fits

```text
@widget(compatible_types=[FLOAT])  ──► WidgetRegistry  ──►  port renders the widget
class KnobWidget(BaseWidget):                                 when the canvas
    def build(self):                                          draws the node card
        knob = ui.knob(value=0)
        return self.bind(knob)          model → view : on_model_changed() / bind()-ings
                                        view → model : each bind()-ed element
```

Every widget subclasses **`BaseWidget`** and implements **`build()`**, which constructs and returns the NiceGUI root element. Inside `build()` you either:

- call **`bind()`** (the *sugar*) to wire each value-bound element to a model field, or
- override **`on_model_changed()`** (the *floor*) and drive the view yourself for whole-value or non-field widgets.

`BaseWidget` implements the minimal `IWidget` contract. The `@widget` decorator attaches `class_identity` (used by `WidgetRegistry` for hot-reload) and registers `compatible_types` (which datatypes the widget accepts).

**Boundaries.** What datatypes *are* lives in [components/datatypes](../datatypes/datatype-canon.md). How a port binds a widget at creation time (`as_inlet(widget=...)`) lives in [guides/ports](../../guides/ports.md). The runtime layer that converts values between incompatible *types* on an edge lives in [components/adapters](../adapters/adapter-canon.md) and [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

## 3. Important concepts

### The `@widget` decorator

`@widget(...)` registers the class with `WidgetRegistry` and attaches its identity. It is always invoked with parentheses.

```python
@widget(description="Fast number input", compatible_types=[FLOAT, INT])
class NumberWidget(BaseWidget):
    ...
```

- **`compatible_types`** (required) — the list (or set) of `IType` classes this widget can edit. A widget is offered for a port when the port's type is in — or inherits from — one of the compatible types. Pass an explicit empty list to register a widget with no type constraint.
- **`class_identity`** — derived from the class and its owning library, exposed as `class_identity.registry_key` (`<library_id>:widget:<registry_id>`). This is the key `WidgetRegistry` uses, and the value `config()` embeds for the call site.

### `build()`

Required. Construct and return the NiceGUI root element for the widget. Call `bind()` inline on each value-bound element; because `bind()` returns the element, it composes naturally inside `with ui.row():` / `with ui.column():` layout blocks. `build()` runs once per rendered widget; the base wires up the model subscription and activates bindings after it returns.

### The `bind()` sugar

`bind()` registers a binding from a model field to a NiceGUI element property and returns the element:

```python
def bind(
    self,
    element,
    *,
    to: str = "value",
    prop: str = "value",
    event: str = "update:modelValue",
    converter: BindingConverter | None = None,
    one_way: bool = False,
) -> Any: ...
```

- **`to`** — the model field path. `to="value"` (the default) binds the *whole* port value, which is the primitive / single-value case. For a composite `BaseType`, navigate component fields: `to="x"`, or a nested path `to="position.x"`.
- **`prop`** — the element property to write. Defaults to `"value"`; a label binds `prop="text"`.
- **`event`** — the NiceGUI event that signals a user-driven change (defaults to `"update:modelValue"`). Set it for elements that emit a different change event.
- **`converter`** — see below; defaults to `PrimitiveUnwrappingConverter()`.
- **`one_way=True`** — model → view only. Use for read-only elements (a display label, a derived swatch).

A composite widget calls `bind()` once per component field, each navigating a different `to` path:

```python
def build(self):
    with ui.row().classes("w-full") as root:
        self.bind(ui.number(value=0, label="X").classes("w-full"), to="x")
        self.bind(ui.number(value=0, label="Y").classes("w-full"), to="y")
        self.bind(ui.number(value=0, label="Z").classes("w-full"), to="z")
    return root
```

### The `on_model_changed()` floor

When a widget isn't a flat field map — a whole-value display, a streaming preview — override `on_model_changed(self, value)` and drive the view yourself. It fires on **every** port change and **once at render** with the current value.

```python
def on_model_changed(self, value):
    super().on_model_changed(value)          # keeps any bind()-ings live
    self._swatch.style(f"background:{value.hex}")
```

The `super()` contract is the lever:

- **Call `super().on_model_changed(value)`** to refresh every `bind()`-registered element, then add your own custom sync on top. Use this when you mix `bind()`-ed elements with hand-driven ones.
- **Omit the `super()` call** to take full ownership of model → view sync (a floor-only widget with no `bind()` calls — e.g. an image preview that pushes frames).

### `converter`

A `BindingConverter` translates between the model value and the view value in both directions.

- **`PrimitiveUnwrappingConverter`** is the default. It unwraps a `PrimitiveType` to its underlying scalar (and handles pooled fields). Pass a default to show something for an unset port:

  ```python
  self.bind(knob, converter=PrimitiveUnwrappingConverter(default_value=0.0))
  ```

- **`Converters.chain(...)`** composes converters left-to-right on the way to the view (and reversed on the way to the model) — e.g. unwrap then clamp:

  ```python
  self.bind(el, converter=Converters.chain(
      Converters.primitive(default_value=0),
      Converters.range(min_value=0, max_value=100, clamp=True),
  ))
  ```

- **`Converters.range(...)`** clamps (or rejects) numeric values to a range.
- **Custom `BindingConverter` subclasses** handle anything else — unit conversion, formatting a derived display string. Implement `to_view()` (and `to_model()` for two-way bindings); the default `to_model()` makes the converter read-only.

### `config()` call-site pattern

Every widget exposes the `config()` classmethod (from `IWidget`). `Widget.config(properties={...})` returns a `{"key": <registry_key>, "config": {...}}` dict that you hand to a port:

```python
self.add(FLOAT.as_inlet(
    "amount",
    widget=NumberWidget.config(properties={"min": 0, "max": 100, "step": 0.5}),
))
```

Inside the widget, that config is available as `self._config`; the convention is to read user-facing values from `self._config.get("properties", {})`.

### Declared size: `min_width`, `min_height`, `max_height`

A node's size floor is not computed by Haywire — it is whatever CSS intrinsic sizing produces for the card. The resize gadget writes a `min-width`/`min-height` onto the host slot and reads the resulting size back, so **a widget's content becomes its node's floor**. A widget holding an image at its natural 1280×720 floors its node there: the user can grow the node but not shrink it, and no percentage in the widget's own CSS can cap it (percentages resolve to `auto` during intrinsic sizing).

Declaring a size box on the decorator opts the widget out of that. It is opt-in: a widget that declares nothing sizes from its content, which is right for every stock widget.

```python
@widget(description="Frame viewer", min_width=160)          # inline axis contained
@widget(description="Fixed panel", min_width=160, min_height=90)   # both axes contained
```

| Declaration | Effect | Use for |
| --- | --- | --- |
| `min_width` alone | Width stops coming from content; **height still does**, so aspect-ratio content keeps growing proportionally as the node widens | Image/video viewers, anything with an intrinsic aspect ratio |
| `min_width` + `min_height` | Neither axis comes from content; the widget keeps its declared height however tall the node gets | Fixed-size or internally-scrolling content with no useful aspect |
| `min_height` alone | Ignored, with a warning — CSS has `contain: inline-size` but no block-axis equivalent | — |

The declared numbers are the size the widget claims when nothing constrains it: the node can be resized down to them, and the widget still stretches past them when the card is bigger.

`max_height` is a **separate** knob, and not part of the box: it replaces the framework's default expanded-container ceiling (200px) with your own definite px value, for a widget whose *content* is unbounded (a long label, a growing list). Content past it is clipped by the container's `overflow: hidden`. Keep it a px value — the container's reveal is a `max-height` transition, and a percentage of an auto-height ancestor resolves to `none` and snaps.

All three are overridable per call site: `NumpyViewerWidget.config(min_width=320)`.

Mechanically, `BaseSkin.render_widget` — the one funnel every skin calls — stamps the resolved values onto the widget's root element as custom properties plus a marker attribute, and `canvas.vue` turns those into `contain` / `contain-intrinsic-size`. Custom skins inherit the behaviour without doing anything. See `haywire/ui/widget/sizing.py`.

### `_on_cleanup()` and final cleanup

The base `cleanup()` is **final**: when the page client disconnects it drops the model subscription, deactivates every binding, and *then* calls the `_on_cleanup()` hook. **Never override `cleanup()`.** To release subclass-owned resources (a backend, a timer, an open stream), override `_on_cleanup()`:

```python
def _on_cleanup(self):
    self._backend.stop()
```

This template-method split guarantees base teardown always runs, so a subclass can't accidentally leak the model subscription.

### Hot-reload

`WidgetRegistry` re-registers widget classes when a library reloads. Widgets already mounted in the running UI are **not** swapped (tearing down a connected NiceGUI element is risky); newly-created widgets pick up the new class.

### The imports you need

```python
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.converters import Converters, BindingConverter, PrimitiveUnwrappingConverter
```

## 4. Live example from the codebase

Source: `barn/haybale-example/haybale_example/widgets/knob_widget.py`

`KnobWidget` is a `BaseWidget` that binds a `ui.knob` to `FLOAT` or `INT` ports. It shows the common single-value path: `build()` reads `self._config`, constructs the element, and returns it through `self.bind()` with a default-bearing converter.

```python
--8<-- "barn/haybale-example/haybale_example/widgets/knob_widget.py:10:45"
```

from: `KnobWidget` — registry_key: `example:widget:KnobWidget`

Using it from a node's `init()`:

```python
self.add(FLOAT.as_inlet(
    "angle",
    label="Angle",
    widget=KnobWidget.config(properties={"min": 0, "max": 360, "step": 1, "color": "teal"}),
))
```

**Multiple elements.** A widget can bind several elements to one port. A `Vector3` widget calls `bind()` three times, each with a different `to=` field path (`"x"`, `"y"`, `"z"`); for a worked example that mixes a two-way input with a read-only derived label, see `TemperatureWidget` in `barn/haybale-example/haybale_example/widgets/example_widget.py` — it binds a `ui.number` (custom converter, two-way) alongside a `ui.label` (`prop="text"`, `one_way=True`).

What this example exercises:

| Concept | Where |
|---|---|
| `@widget(compatible_types=[FLOAT, INT])` decorator | class decoration |
| `BaseWidget` subclass | `class KnobWidget(BaseWidget)` |
| `build()` returning a NiceGUI element | constructs `ui.knob(...)`, returns it |
| `self.bind(...)` with the default `to="value"` | `self.bind(knob, converter=...)` |
| `PrimitiveUnwrappingConverter(default_value=0.0)` | unwraps the primitive, shows `0.0` when unset |
| `config()` call-site pattern | `KnobWidget.config(properties={...})` above |

For datatype authoring (including the derived primitive types used here), see [components/datatypes](../datatypes/datatype-canon.md). For the port surface (`as_inlet`, `widget=`), see [guides/ports](../../guides/ports.md). For type-pair adapters (used when an outlet of one type connects to an inlet of a different type), see [components/adapters](../adapters/adapter-canon.md).

---

## Quick reference

### Authoring checklist

- [ ] `@widget(description="...", compatible_types=[Type1, Type2])` on the class
- [ ] Subclass `BaseWidget`
- [ ] Implement `build()` returning the NiceGUI root element
- [ ] Call `self.bind(element, ...)` for each value-bound element
- [ ] Pass `prop=` / `event=` for elements that don't use `value` / `update:modelValue`
- [ ] Pass `one_way=True` for read-only (display) elements
- [ ] Override `on_model_changed()` (call `super()` to keep `bind()`-ings live) for whole-value / custom sync
- [ ] Override `_on_cleanup()` to release subclass-owned resources — never override `cleanup()`

### Imports

```python
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.converters import Converters, BindingConverter, PrimitiveUnwrappingConverter
```

### Common `prop` / `event` pairs

| Element | `prop` | `event` |
|---|---|---|
| `ui.number`, `ui.input`, `ui.select`, `ui.slider`, `ui.switch`, `ui.checkbox` | `value` (default) | `update:modelValue` (default) |
| `ui.knob`, `ui.color_input`, `NumberDrag` (custom) | `value` (default) | `update:modelValue` (default) |
| `ui.label` | `text` | (read-only — pass `one_way=True`) |

### Per-port override at the call site

```python
# Preferred: config() builds the {key, config} dict for you.
self.add(FLOAT.as_inlet(
    "amount",
    widget=NumberWidget.config(properties={"min": 0, "max": 100}),
))

# Lower-level: pass the registry key and config explicitly.
self.add(FLOAT.as_inlet(
    "amount",
    widget_key="my_lib:widget:NumberWidget",
    widget_config={"properties": {"min": 0, "max": 100}},
))
```

The `widget_key` is `<library_id>:widget:<registry_id>`. Register the class once with `@widget` and reference it from any node.
