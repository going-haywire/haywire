---
name: Haywire minimap integration
description: MinimapCanvas architecture, ZoomPanContainer ownership, DOM placement gotcha, node scanning strategy
type: project
---

## Status: IMPLEMENTED (2026-04-01), drag bug fixed 2026-04-06; 2026-04-08 canvas.vue refactor broke minimap drag again (under investigation)

## Minimap drag bug (fixed 2026-04-06)

**Symptom:** After dragging the viewport rectangle and releasing, it jumped to center on the mouse position.
**Root cause:** After a drag sequence, the browser still fires a `click` event at the mouseup position. `handleClick` responded by re-centering the viewport — undoing the drag.
**Fix:** Added `dragMoved` boolean flag in Vue `data()`. Set to `true` in `handleMouseMove` when drag occurs. `handleClick` early-returns when `dragMoved` is true, then resets it.
**Note:** Vue 3 does NOT proxy `data()` properties prefixed with `_` or `$` onto the component instance — avoid `_dragState` style names in Vue SFC data.

Key files:
- `packages/haywire-core/src/haywire/ui/minimap/mini_map_vue.py` — `MinimapCanvas` (ui.element subclass)
- `packages/haywire-core/src/haywire/ui/minimap/settings.py` — `MinimapSettings` (FrameworkSettings)
- `packages/haywire-core/src/haywire/ui/pan_zoom/zoom_pan_vue.py` — `ZoomPanContainer` (owns minimap)
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — `_canvas_wrapper` needs `position: relative`

## Ownership model

`ZoomPanContainer` owns and creates `MinimapCanvas`. Rationale:
- Already has `position: relative; overflow: hidden` context
- Follows same pattern as `EditorPanZoomSettings` subscription
- `MinimapCanvas` needs the container ref anyway — no extra passing needed
- `GraphCanvasManager` stays decoupled from minimap concerns

## Critical DOM placement rule

**MinimapCanvas must NOT be placed inside `with zoom_container:`** — that routes through the Vue `<slot>` which lands inside `.zoom-pan-content` (the transformed div). The minimap would then pan/zoom with the canvas.

**Correct placement:** create `MinimapCanvas` AFTER closing `with self:` in `_setup_container()`. This places it as a sibling of `ZoomPanContainer` in the parent's NiceGUI context. The parent must have `position: relative` for `absolute` positioning to anchor correctly.

In `ZoomPanContainer._setup_container()`:
```python
with self:
    self.content_container = ...  # transformed div — slot goes here
# minimap created OUTSIDE with self: block — sibling in parent context
self.minimap = MinimapCanvas(zoom_container=self, ...)
```

In `GraphEditor`, `_canvas_wrapper` must have `position: relative` (added 2026-04-01).

## MinimapSettings fields (as of 2026-04-01)

```python
class MinimapSettings(FrameworkSettings, namespace="ui.minimap"):
    enabled: bool   # default True
    position: str   # default "bottom-right", choices: top-left/top-right/bottom-left/bottom-right
    width: int      # default 200, range 100-400
    # height removed — auto-derived from container aspect ratio
    # opacity removed
    # show_on_hover removed
```

Settings changes are subscribed in `ZoomPanContainer._on_minimap_setting_changed()` and routed to `minimap.set_enabled()`, `set_position()`, `set_width()`.

## MinimapCanvas API

- `__init__(zoom_container, width, position, visible)` — takes initial values
- `toggle_visibility()` / `set_enabled(bool)` — show/hide
- `set_position(str)` — reposition via JS
- `set_width(int)` — resize + re-derive height from aspect ratio
- `refresh_content()` — force rescan of node positions
- Zoom/pan hooking: monkey-patches `zoom_container.on_zoom_change` / `on_pan_change` (chaining pattern)

## Node scanning — correct approach

`_scan_content()` uses `content.querySelectorAll('[data-node-id]')` to find node containers (set by `GraphCanvasManager` at creation time). Node positions are read from **`el.style.left` / `el.style.top`** (inline styles, content-space coordinates already set by `graph_canvas_manager.py`).

**Do NOT use `offsetLeft/offsetTop`** — these are relative to the nearest positioned ancestor (not `.zoom-pan-content`), producing wrong values for nested elements.

**Do NOT use `getBoundingClientRect()`** — requires un-doing the CSS transform, fragile.

Node rects are passed to JS `updateContentBounds(bounds, nodes)` alongside the bounding box.
`drawMinimap()` renders actual node rectangles from `nodeRects[]`, not a grid pattern.

## ZoomPan Vue template structure (important for future work)

```html
<div id="container">           ← position: relative ($el, the ZoomPanContainer)
  <div class="zoom-pan-content">  ← gets CSS transform (translate + scale)
    <slot></slot>              ← ALL Python children via with self: land here
  </div>
</div>
```

Anything placed with `with zoom_container:` OR `with zoom_container.content_container:` goes inside the transformed div.
