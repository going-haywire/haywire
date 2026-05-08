---
name: Haywire Popup Vue SFC
description: Popup component converted to Vue SFC (2026-04-06) — architecture, API, gotchas
type: project
---

## Status: IMPLEMENTED 2026-04-06

Files:
- `packages/haywire-core/src/haywire/ui/graph_canvas/popup.vue` — Vue SFC
- `packages/haywire-core/src/haywire/ui/graph_canvas/popup.py` — thin Python wrapper

## Why it was converted

Old `popup.py` used `ui.run_javascript()` with `window._popupDragState` global state,
`requestAnimationFrame` enforcement loops, and class-level `_CSS_INJECTED` / `_global_handlers_initialized`
guards — fragile and session-unsafe. Vue SFC owns all drag/position/visibility state locally.

## Architecture

**Vue component owns:**
- Position state (`currentX`, `currentY`, `isDragging`, `dragOffset`)
- Drag logic (title bar mousedown → document mousemove/mouseup with capture)
- Visibility toggle (`startVisible` prop + `open()`/`close()` methods called via `run_method`)
- Backdrop click handling, escape-key forwarding, clamp-to-viewport

**Python wrapper (`Popup(ui.element)`):**
- Props forwarded: `title`, `popup-width`, `popup-height`, `closable`, `backdrop-click-close`,
  `backdrop-color`, `initial-x`, `initial-y`, `draggable`, `clamp-to-viewport`, `start-visible`
- Events listened: `popup-close`, `popup-position-update`
- `__enter__`/`__exit__` delegate to `self._content` (a `ui.column` inside `default_slot`)

## Critical: `__enter__` must return a `ui.column`, not the slot

`self._content = ui.column()...` is created inside `with self.default_slot:` in `__init__`.
`__enter__` returns `self._content.__enter__()` — this gives callers a real NiceGUI container
that can be `with`-ed multiple times.

**Why:** `PanelLayout` stores the container and does `with self._container:` for each widget call.
If `__enter__` returned the slot object instead of a column, widgets would render as flat siblings
rather than stacked in a column.

## Public API additions (2026-04-06)

- `Popup.content` — property exposing `_content` (the inner `ui.column`)
- `PanelLayout.container` — property exposing `_container`; all panels should use `with layout.container:` not `with layout._container:`

`_open_menu` in `context_menu.py` uses `PanelLayout(popup.content)` — does NOT pre-enter the container with `with popup as container:`. This prevents double-slot-push when panels do `with layout:` in power mode.

## Factory helper

```python
Popup.create_context_menu(title, x, y, **kwargs)
# Defaults: backdrop_click_close=True, backdrop_color="transparent",
#           closable=True, draggable=True, clamp_to_viewport=True
```

Used by `popup_context_menu.py` for all right-click context menus.

## Vue 3 gotcha: underscore-prefixed data() properties

Vue 3 does NOT proxy `data()` properties starting with `_` or `$` onto the component instance.
`this._dragStartX` would always be `undefined`. Use plain names: `dragStartX`.

## Teleport

The Vue template uses `<teleport to="body">` so the popup is always above the NiceGUI layout
stacking context, regardless of where it is instantiated in the Python tree.
