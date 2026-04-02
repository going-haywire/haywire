# Spec: Auto-Expanding Canvas
## Problem
The canvas is fixed at 8000×8000px. When nodes approach the boundary, there's nowhere to go. The value is hardcoded in 4 files across CSS, JS, and Python.

## Goal
The canvas expands automatically when nodes are dragged or placed within a configurable margin of any edge. The minimap, pan clamp, and min-zoom all adapt to the new size without manual intervention.

## Trigger Condition
Expansion fires when any node's bounding box comes within 400px of any canvas edge (in content-space coordinates). Expansion adds 2000px to the relevant axis/axes, symmetrically extended on both sides to keep existing content centred.

## Changes Required

1. graph_canvas.vue — make canvas size a reactive prop
   * Add canvasSize: { type: Number, default: 8000 } prop (or separate canvasWidth / canvasHeight if non-square is desired later).
   * Replace hardcoded width: 8000px; height: 8000px in .graph-canvas, .connection-svg, .node-container with :style="{ width: canvasSize + 'px', height: canvasSize + 'px' }".
   * After a node drag ends (mouseup), call a new _checkBoundaryExpansion() method that scans all [data-node-id] nodes, finds the max extent, and emits canvas-resize with the new size if expansion is needed.
   * anvas-resize event payload: { width, height }.
2. graph_canvas_manager.py — own the canvas size, propagate changes
   * Add canvas_size: int = 8000 instance attribute.
   * Listen to the canvas-resize event from canvas_vue (via canvas_vue.on('canvas-resize', ...)).
   * On receipt: update self.canvas_size, push the new size to canvas_vue as a prop, and notify zoom_container via a new set_canvas_size(w, h) method.
   * Store the authoritative canvas size here — it's the single source of truth.
3. zoom_pan_container.vue — replace hardcoded CANVAS_SIZE
   * Add canvasWidth: { type: Number, default: 8000 } and canvasHeight: { type: Number, default: 8000 } props.
   * Replace every local const CANVAS_SIZE = 8000 in _updateMinZoom() and _clampPanValues() with this.canvasWidth / this.canvasHeight.
   * When props change (via watch), call _updateMinZoom() and _clampPanValues() so the viewport constraints adapt immediately.
4. zoom_pan_vue.py — expose set_canvas_size
   * Add set_canvas_size(width: int, height: int) that sets _props['canvas-width'] and _props['canvas-height'] and calls self.update().
5. mini_map_vue.py — receive canvas size from zoom container
   * Replace hardcoded { minX: 0, minY: 0, maxX: 8000, maxY: 8000 } in both scanAndDraw() and _scan_content() with the actual canvas size, passed in as a JS variable or read from a data attribute on the container element.
   * Simplest approach: zoom_container sets data-canvas-width / data-canvas-height on its DOM element whenever set_canvas_size is called; the minimap JS reads those attributes.
   * Data Flow on Expansion

## node dragged near edge
  → graph_canvas.vue: _checkBoundaryExpansion()
  → emits canvas-resize {width, height}
  → graph_canvas_manager.py: updates canvas_size, pushes prop to canvas_vue
  → calls zoom_container.set_canvas_size(w, h)
  → zoom_pan_vue.py: updates props, calls update()
  → zoom_pan_container.vue: watch fires → _updateMinZoom() + _clampPanValues()
  → mini_map_vue.py: reads data-canvas-* from DOM → correct bounds on next scan

## Out of Scope
* Shrinking the canvas (canvas only grows).
* Saving the canvas size to the graph file (nodes' positions implicitly define the used area; canvas size is a runtime concern).
* Non-square canvases (keep width == height for now; the infrastructure supports it trivially later).