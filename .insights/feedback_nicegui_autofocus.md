---
name: NiceGUI autofocus in dynamic containers
description: How to autofocus an input field in NiceGUI when it's inside a dynamically shown popup/dialog
type: feedback
---

HTML `autofocus` attribute and `.props("autofocus")` do NOT work for inputs inside dynamically shown containers (popups, dialogs) because the element is not visible at DOM ready time.

**Working solution** — added as `autofocus=True` param on `hui.input_field()`:
```python
def _focus_search():
    ui.run_javascript(f'document.getElementById("c{search_input.id}")?.focus();')
ui.timer(0.1, _focus_search, once=True)
```

**Why:** The 0.1s timer lets the popup finish rendering before the JS focus call. The `?.` null-safe operator prevents the "can't access property focus" error that fires if the timer runs before the element is mounted.

**Gotcha:** The element ID is `c{element.id}` (NiceGUI prefixes the numeric id with 'c'). Using `document.getElementById(str(el.id))` won't find it.

**How to apply:** Use `hui.input_field(autofocus=True, ...)` for any search/input that should auto-focus when a popup opens. Implemented in `hui.input_field()` in `haywire/ui/elements/elements.py` (2026-04-08).
