# UI Integration Guide

This guide covers how settings panels are rendered in NiceGUI, what DOM structure they produce, and how the widget dispatch works.

---

## Rendering Functions

Two public functions in `haybale_core.panels._settings_panel_base` render settings as NiceGUI panels:

### `render_reactive(obj: Settings)`

Renders all non-read-only fields of a `Settings` instance as a labelled form. Used in node panels.

```python
from haybale_core.panels._settings_panel_base import render_reactive

with ui.card():
    render_reactive(node.example)
```

- Fields with `read_only=True` are skipped entirely
- Fields are sorted by `(category, order, attr_name)` and grouped under collapsible category headers
- Mirror fields (`mirrors=`) that have been locally overridden show a `•` prefix on the label and a `restart_alt` reset button

### `render_schema(schema_cls, registry)`

Renders all fields of a `LibrarySettings` or `FrameworkSettings` class using current registry values. Used in global settings panels.

```python
from haybale_core.panels._settings_panel_base import render_schema

with ui.card():
    render_schema(TestingSettings, registry)
```

---

## DOM Structure

Each field row produces:

```text
div[data-field="<attr_name>"]        ← row container
  label                              ← field label (with • prefix if locally overridden)
  <widget element>[data-value="..."] ← current value, always readable via DOM
  button[restart_alt]                ← reset button (mirror fields only, when overridden)
div                                  ← error container (populated on validation failure)
  label[data-error="true"]           ← error message (only present when last write was rejected)
```

`data-field` and `data-value` are set on all fields regardless of widget type, making them uniformly addressable for automated testing.

---

## Widget Dispatch

`_render_widget_impl` selects the widget based on descriptor metadata:

| Condition            | Widget           |
| -------------------- | ---------------- |
| `_widget='color'`    | `ui.color_input` |
| `choices` set        | `ui.select`      |
| type is `bool`       | `ui.switch`      |
| type is `int`/`float`| `NumberDrag`     |
| otherwise            | `ui.input`       |

`NumberDrag` is the custom Blender-style drag input from `haywire.ui.components.number_drag`. It respects `min`, `max`, `step`, and `precision` from the descriptor.

---

## Mirror Fields

A mirror field declares `mirrors=SomeLibrarySettings.some_field` on its descriptor. When rendered via `render_reactive()`:

- If not locally overridden: displays the resolved global value, label has no prefix
- If locally overridden: label gets a `•` prefix, a `restart_alt` button appears
- Clicking the reset button calls `obj.reset(attr_name)` and re-renders the row

Mirror resolution requires the `Settings` instance to have `_registry` injected (extended mode). Without it, the field renders using its descriptor default (simple mode).

---

## Validation Errors

When a user submits a value that fails the field's validator, an error label appears below the row with `data-error="true"`. It is cleared when a valid value is submitted next. The validator is checked before `setattr` — invalid values are never written to the instance.

---

## Category Groups

Fields with a `category=` argument are grouped under collapsible `ui.expansion` headers. The category string is displayed as-is.

---

## Next Steps

- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Unit testing and UI harness testing
