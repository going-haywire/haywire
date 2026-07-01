# `ui.input` emits `update:value`, not `update:modelValue`

## Symptom

A `BaseWidget` wrapping `ui.input` (e.g. `TextWidget`) renders fine and shows the
seeded value, but **user edits never reach the model in-browser**. Typing into the
field, emptying it, pressing Enter, blurring — none of it fires the panel's
validating setter. In a Playwright harness the DOM shows the edited value
(`input_value() == ''`) yet the bound `set_value` is only ever called once, with
the *original* value (a focus-transfer artifact at click time).

## Cause

`PropertyBinding` / `BaseWidget.bind()` default to `target_event="update:modelValue"`.
That is correct for **custom Vue components** (NumberDrag) and most Quasar-wrapped
NiceGUI elements (`ui.checkbox`, `ui.switch`, `ui.select`, `ui.color_input` all emit
`update:modelValue`). But **`ui.input` emits `update:value`** — a different event.
Binding to `update:modelValue` silently subscribes to an event the input never fires,
so every keystroke is dropped.

Verify per-element with:

```python
from nicegui import ui
i = ui.input(value="")
[l.type for l in i._event_listeners.values()]   # -> ['update:value']
ui.checkbox()  # -> ['update:modelValue']
```

## Fix

Bind `ui.input`-based widgets with the matching event:

```python
self.bind(ui.input(...), event="update:value", converter=...)
```

See `barn/builtin/widgets/basic_widgets.py::TextWidget.build`.

## Trap for harness tests

Even with the event fixed, emptying then refilling a *validated* string field needs a
re-`click()` (re-focus) before the second `fill()`: a rejected empty value triggers a
model→view sync that can overwrite an unfocused input. Pattern:
`click()` → `fill("")` → `Enter` → assert error → `click()` → `fill("valid")` → `Enter`.
`Control+A`+`Delete` is unreliable in Chromium-on-macOS (Ctrl+A ≠ select-all); use `fill()`.
