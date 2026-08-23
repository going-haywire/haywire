<template>
  <div
    :id="containerId"
    ref="container"
    class="zoom-pan-container"
    :class="{
      dragging: isDragging,
      [zoomClass]: true
    }"
    tabindex="0"
    @wheel.prevent="handleWheel"
    @contextmenu="handleContextMenu"
  >
    <div
      ref="content"
      class="zoom-pan-content"
    >
      <slot></slot>
    </div>
    <slot name="overlay"></slot>
  </div>
</template>

<script>
export default {
  name: 'ZoomPanContainer',
  
  props: {
    containerId: { type: String, required: true },
    maxZoom: { type: Number, default: 5.0 },
    // 0 = automatic (canvas-fills-viewport). >0 overrides as the absolute min.
    minZoom: { type: Number, default: 0.0 },
    initialZoom: { type: Number, default: 1.0 },
    zoomSensitivity: { type: Number, default: 0.1 },
    panSensitivity: { type: Number, default: 1.0 },
    smoothZoom: { type: Boolean, default: true },
    enableKeyboard: { type: Boolean, default: true },
    canvasWidth: { type: Number, default: 8000 },
    canvasHeight: { type: Number, default: 8000 },
    // false pins the canvas at full detail ('high') regardless of zoom.
    lodEnabled: { type: Boolean, default: true },
  },
  
  data() {
    return {
      isDragging: false,
      lastMouseX: 0,
      lastMouseY: 0,
      updateTimeout: null
    };
  },
  
  // Remove computed properties entirely
  
  mounted() {
    console.log('[ZoomPan] mounted, container:', this.containerId);
    // Non-reactive transform state
    this._zoom = this.initialZoom;
    this._panX = 0;
    this._panY = 0;
    this._minZoom = 0.01; // will be computed properly after first layout

    // Cached container rect — populated on first gesture, cleared on mouseup/resize
    this._cachedRect = null;

    // Compute initial min zoom and re-compute on resize
    this._updateMinZoom();

    // Initialize
    this._updateTransformDirect(true);

    // Setup keyboard listeners
    this._setupListeners();

    // API exposure
    this.$el._zoomPanControls = {
      setZoom: (zoom, centerX, centerY) => this._setZoomDirect(zoom, centerX, centerY),
      setPan: (x, y) => this._setPanDirect(x, y),
      getZoom: () => this._zoom,
      getPan: () => ({ x: this._panX, y: this._panY }),
      zoomIn: () => this._setZoomDirect(this._zoom + this.zoomSensitivity),
      zoomOut: () => this._setZoomDirect(this._zoom - this.zoomSensitivity),
      reset: () => {
        this._zoom = this.initialZoom;
        this._panX = 0;
        this._panY = 0;
        this._updateTransformDirect(true);
      },
      fitToContent: this.fitToContent,
      getMinZoom: () => this._minZoom,
      getState: () => ({
        zoom: this._zoom,
        panX: this._panX,
        panY: this._panY,
        isDragging: this.isDragging
      })
    };
  },
  
  methods: {

    _getContainerRect() {
      if (!this._cachedRect) {
        this._cachedRect = this.$el.getBoundingClientRect();
      }
      return this._cachedRect;
    },

    _invalidateRectCache() {
      this._cachedRect = null;
      this._updateMinZoom();
    },

    _updateMinZoom() {
      // Explicit override: the minZoom setting becomes the absolute floor,
      // ignoring the auto-fit computation. This can allow zooming out past the
      // canvas-fills-viewport point; _clampPanValues already centers any axis
      // where the scaled canvas is smaller than the viewport, so panning stays
      // well-behaved.
      if (this.minZoom > 0) {
        this._minZoom = this.minZoom;
        return;
      }
      // Automatic (minZoom == 0): most zoomed-out is when the canvas exactly
      // fills the viewport.
      const rect = this.$el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        this._minZoom = Math.max(rect.width / this.canvasWidth, rect.height / this.canvasHeight);
      }
    },

    _setupListeners() {
      this._onMouseDown = (e) => {
        this._invalidateRectCache();
        if (e.button === 1) {
          // Middle-mouse button — start pan drag
          e.preventDefault();
          this.isDragging = true;
          this.lastMouseX = e.clientX;
          this.lastMouseY = e.clientY;
        }
      };
      this._onMouseMove = (e) => {
        if (!this.isDragging) return;
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
        this._setPanDirect(this._panX + dx, this._panY + dy);
      };
      this._onMouseUp = (e) => {
        this._invalidateRectCache();
        if (e.button === 1) {
          this.isDragging = false;
        }
      };

      this.$el.addEventListener('mousedown', this._onMouseDown);
      document.addEventListener('mousemove', this._onMouseMove);
      document.addEventListener('mouseup', this._onMouseUp);
      window.addEventListener('resize', this._invalidateRectCache);
    },

    _cleanupListeners() {
      this.$el.removeEventListener('mousedown', this._onMouseDown);
      document.removeEventListener('mousemove', this._onMouseMove);
      document.removeEventListener('mouseup', this._onMouseUp);
      window.removeEventListener('resize', this._invalidateRectCache);
    },

    handleContextMenu(event) {
      const isCanvasTarget = event.target.closest('[data-graph_canvas="true"], .graph-canvas');
      if (isCanvasTarget) {
        return;
      }

      const insideContent = this.$refs.content && this.$refs.content.contains(event.target);
      if (!insideContent && event.target !== this.$el) {
        return;
      }

      const graphCanvas = this.$el.querySelector('[data-graph_canvas="true"], .graph-canvas');
      const controls = graphCanvas && graphCanvas._graphCanvasControls;
      if (!controls || typeof controls.handleContextMenu !== 'function') {
        return;
      }

      controls.handleContextMenu(event);
    },
    
    handleWheel(e) {
      if (e.ctrlKey) {
        // Trackpad pinch gesture (browser sets ctrlKey synthetically) OR Ctrl+scroll
        const zoomDelta = -e.deltaY * this.zoomSensitivity * 0.01;
        this._setZoomDirect(this._zoom + zoomDelta, e.clientX, e.clientY);
        return;
      }

      // Distinguish mouse wheel from trackpad by delta magnitude.
      // Mouse wheels produce large discrete steps (≥ 100 on most systems, often 120).
      // Trackpad produces small continuous pixel deltas (typically < 50 per event).
      const isMouseWheel = e.deltaMode === 1 || (e.deltaMode === 0 && Math.abs(e.deltaY) >= 50 && e.deltaX === 0);

      if (isMouseWheel) {
        if (e.shiftKey) {
          // Shift + mouse wheel → pan horizontally
          this._setPanDirect(this._panX + (-e.deltaY) * this.panSensitivity, this._panY);
        } else {
          // Plain mouse wheel → zoom centered on cursor
          const zoomDelta = -e.deltaY * this.zoomSensitivity * 0.01;
          this._setZoomDirect(this._zoom + zoomDelta, e.clientX, e.clientY);
        }
      } else {
        // Trackpad two-finger swipe → pan both axes
        const deltaX = (-e.deltaX) * this.panSensitivity;
        const deltaY = (-e.deltaY) * this.panSensitivity;
        this._setPanDirect(this._panX + deltaX, this._panY + deltaY);
      }
    },


    _setZoomDirect(newZoom, centerX = null, centerY = null) {
      const oldZoom = this._zoom;
      this._zoom = Math.max(this._minZoom, Math.min(this.maxZoom, newZoom));

      if (centerX !== null && centerY !== null) {
        const rect = this._getContainerRect();
        const offsetX = centerX - rect.left;
        const offsetY = centerY - rect.top;

        const contentX = (offsetX - this._panX) / oldZoom;
        const contentY = (offsetY - this._panY) / oldZoom;

        this._panX = offsetX - contentX * this._zoom;
        this._panY = offsetY - contentY * this._zoom;
      }

      // Clamp pan after zoom — keeps the canvas filling the viewport
      // as the user zooms out toward the minimum zoom level.
      this._clampPanValues();

      this._updateTransformDirect(true);
    },

    // prevent extremely large pan values:
    _clampPanValues() {
      const containerRect = this._getContainerRect();

      const canvasW = this.canvasWidth  * this._zoom;
      const canvasH = this.canvasHeight * this._zoom;

      // Canvas larger than viewport: clamp so neither edge escapes the viewport.
      // Canvas smaller than viewport (at min zoom, one axis may be smaller):
      //   center it — no panning allowed in that axis.
      if (canvasW >= containerRect.width) {
        const minX = -(canvasW - containerRect.width);
        this._panX = Math.max(minX, Math.min(0, this._panX));
      } else {
        this._panX = (containerRect.width - canvasW) / 2;
      }

      if (canvasH >= containerRect.height) {
        const minY = -(canvasH - containerRect.height);
        this._panY = Math.max(minY, Math.min(0, this._panY));
      } else {
        this._panY = (containerRect.height - canvasH) / 2;
      }
    },

    _setPanDirect(newPanX, newPanY) {
      this._panX = newPanX;
      this._panY = newPanY;

      // Clamp pan values to prevent Chrome performance issues
      this._clampPanValues();

      this._updateTransformDirect(false);
    },
   
    _lodLevelFor(zoom) {
      // LOD disabled: every layer stays visible at every zoom, so nothing is
      // ever hidden and no crossing can occur.
      if (!this.lodEnabled) return 'high';

      if (zoom <= 0.3) return 'raw';       // Show only lod0
      if (zoom <= 0.5) return 'low';       // Show lod0 and lod1
      if (zoom <= 0.75) return 'medium';   // Show lod0, lod1 and lod2
      return 'high';                       // Show lod0, lod1, lod2 and lod3
    },

    _updateZoomAndLODClass() {
      const container = this.$el;
      const current = container.getAttribute('data-lod-level');
      const lodLevel = this._lodLevelFor(this._zoom);

      // Only write on an actual change — this runs on every zoom frame, not
      // just at crossings.
      if (lodLevel === current) return;

      container.setAttribute('data-lod-level', lodLevel);
    },

    // NEW - Optimized transform with Chrome-specific handling:
    _updateTransformDirect(zoomChanged) {
      // Chrome optimization: use matrix3d for better GPU handling
      let transform;

      if (this._zoom < 0.5) {
        // For very low zoom, use matrix3d which Chrome handles better
        transform = `matrix3d(${this._zoom}, 0, 0, 0, 0, ${this._zoom}, 0, 0, 0, 0, 1, 0, ${this._panX}, ${this._panY}, 0, 1)`;
      } else {
        // For normal zoom, use regular transform
        transform = `translate(${this._panX}px, ${this._panY}px) scale(${this._zoom})`;
      }

      this.$refs.content.style.transform = transform;
      // LOD only depends on zoom level — skip during pure pan frames
      if (zoomChanged) {
        this._updateZoomAndLODClass();
      }
      
      // Dispatch custom event with zoom/pan state to document
      document.dispatchEvent(new CustomEvent('zoom-pan-state', {
        detail: {
          zoom: this._zoom,
          panX: this._panX,
          panY: this._panY,
          containerId: this.containerId,
          isDragging: this.isDragging
        }
      }));
      
      if (this.updateTimeout) return;
      this.updateTimeout = setTimeout(() => {
        this.$emit('transform-changed', { panX: this._panX, panY: this._panY, zoom: this._zoom });
        this.updateTimeout = null;
      }, 8);
    },

    zoomIn() { this._setZoomDirect(this._zoom + this.zoomSensitivity); },
    zoomOut() { this._setZoomDirect(this._zoom - this.zoomSensitivity); },
    resetView() { this._zoom = this.initialZoom; this._panX = 0; this._panY = 0; this._updateTransformDirect(true); },
    setZoom(zoom, centerX, centerY) { this._setZoomDirect(zoom, centerX ?? null, centerY ?? null); },
    setPan(x, y) { this._setPanDirect(x, y); },
    centerOn(contentX, contentY) {
      const rect = this._getContainerRect();
      this._setPanDirect(
        rect.width  / 2 - contentX * this._zoom,
        rect.height / 2 - contentY * this._zoom
      );
    },

    fitToContent() {
      console.log('[ZoomPan] fitToContent called');
      // Double rAF: first frame lets any pending WebSocket DOM updates apply,
      // second frame ensures the browser has completed layout (offsetWidth/offsetHeight valid).
      requestAnimationFrame(() => requestAnimationFrame(() => this._doFitToContent()));
    },

    _doFitToContent() {
      const content = this.$refs.content;
      // Only top-level node containers: [data-node-id] elements that are NOT nested
      // inside another [data-node-id] (ports and sub-elements also carry this attr).
      const allNodes = content ? Array.from(content.querySelectorAll('[data-node-id]')) : [];
      const nodes = allNodes.filter(el => !el.parentElement?.closest('[data-node-id]'));
      const rect = this._getContainerRect();
      console.log(`[ZoomPan] _doFitToContent: ${nodes.length} top-level nodes, viewport=${Math.round(rect.width)}x${Math.round(rect.height)}`);
      nodes.forEach(n => console.log(`  node ${n.getAttribute('data-node-id')} left=${n.style.left} top=${n.style.top} w=${n.offsetWidth} h=${n.offsetHeight}`));

      let minX, minY, maxX, maxY;

      if (nodes.length > 0) {
        minX = Infinity; minY = Infinity; maxX = -Infinity; maxY = -Infinity;
        for (const node of nodes) {
          const x = parseFloat(node.style.left) || 0;
          const y = parseFloat(node.style.top) || 0;
          const w = node.offsetWidth || 200;
          const h = node.offsetHeight || 100;
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x + w > maxX) maxX = x + w;
          if (y + h > maxY) maxY = y + h;
        }
      } else {
        // No nodes: center on canvas midpoint
        minX = 3650; minY = 3650; maxX = 4350; maxY = 4350;
        console.log('[ZoomPan] _doFitToContent: no nodes, centering on canvas midpoint');
      }

      const PADDING = 80;
      const contentW = maxX - minX + PADDING * 2;
      const contentH = maxY - minY + PADDING * 2;

      const scaleX = rect.width / contentW;
      const scaleY = rect.height / contentH;
      const newZoom = Math.max(this._minZoom, Math.min(this.maxZoom, Math.min(scaleX, scaleY)));

      const contentCenterX = (minX + maxX) / 2;
      const contentCenterY = (minY + maxY) / 2;
      const newPanX = rect.width / 2 - contentCenterX * newZoom;
      const newPanY = rect.height / 2 - contentCenterY * newZoom;

      console.log(`[ZoomPan] _doFitToContent: bbox=(${Math.round(minX)},${Math.round(minY)})→(${Math.round(maxX)},${Math.round(maxY)}) zoom=${newZoom.toFixed(3)} pan=(${Math.round(newPanX)},${Math.round(newPanY)})`);
      this._zoom = newZoom;
      this._panX = newPanX;
      this._panY = newPanY;
      this._clampPanValues();
      this._updateTransformDirect(true);
    },

  },

  beforeUnmount() {
    this._cleanupListeners();
    if (this._wheelTimeout) clearTimeout(this._wheelTimeout);
    if (this.updateTimeout) clearTimeout(this.updateTimeout);
  },

  watch: {
    // Toggling LOD must take effect at the current zoom, not wait for the next
    // zoom gesture.
    lodEnabled() {
      const container = this.$el;
      const level = this._lodLevelFor(this._zoom);
      container.setAttribute('data-lod-level', level);
    },
    // Watch for prop changes and update internal state
    initialZoom(newVal) {
      if (this._zoom === this.initialZoom) { // Only if not manually changed
        this._zoom = newVal;
        this._updateTransformDirect(true);
      }
    },
    canvasWidth() {
      this._updateMinZoom();
      this._clampPanValues();
      this._updateTransformDirect(true);
    },
    canvasHeight() {
      this._updateMinZoom();
      this._clampPanValues();
      this._updateTransformDirect(true);
    },
    minZoom() {
      // Recompute the floor and pull the current zoom up to it if the new floor
      // is higher than where we are (e.g. user raised the setting while zoomed
      // far out). Then re-clamp pan and redraw.
      this._updateMinZoom();
      if (this._zoom < this._minZoom) {
        this._zoom = this._minZoom;
      }
      this._clampPanValues();
      this._updateTransformDirect(true);
    },
  }
}
</script>

<style scoped>
.zoom-pan-container {
  position: relative;
  overflow: hidden;
  width: 100%;
  height: 100%;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* Allow user selection and interactions for interactive elements */
.zoom-pan-container input,
.zoom-pan-container textarea,
.zoom-pan-container select,
.zoom-pan-container button,
.zoom-pan-container [contenteditable],
.zoom-pan-container .q-field,
.zoom-pan-container .q-field__native,
.zoom-pan-container .q-field__input,
.zoom-pan-container .q-btn,
.zoom-pan-container .node-card,
.zoom-pan-container .drag-handle,
.zoom-pan-container .port,
.zoom-pan-container .output-port,
.zoom-pan-container .input-port,
.zoom-pan-container [data-draggable="true"],
.zoom-pan-container [draggable="true"],
.zoom-pan-container .clickable,
.zoom-pan-container [data-interactive="true"],
.zoom-pan-container .interactive,
.zoom-pan-container [data-node-id],
.zoom-pan-container [data-port-name],
.zoom-pan-container .no-pan {
  user-select: auto;
  -webkit-user-select: auto;
  -moz-user-select: auto;
  -ms-user-select: auto;
  pointer-events: auto;
  cursor: auto;
}
.zoom-pan-container .popup-content-area,
.zoom-pan-container .popup-content-area *,
.zoom-pan-container .draggable-popup,
.zoom-pan-container .q-card {
  user-select: text !important;
  -webkit-user-select: text !important;
  -moz-user-select: text !important;
  -ms-user-select: text !important;
  pointer-events: auto;
  cursor: auto;
}

/* Specific cursor styles for different interactive elements */
.zoom-pan-container .drag-handle {
  cursor: grab;
}

.zoom-pan-container .drag-handle:active {
  cursor: grabbing;
}

.zoom-pan-container .port,
.zoom-pan-container .output-port,
.zoom-pan-container .input-port {
  cursor: crosshair;
}

.zoom-pan-container .clickable,
.zoom-pan-container [data-interactive="true"],
.zoom-pan-container .interactive {
  cursor: pointer;
}

.zoom-pan-container.dragging {
  cursor: grabbing;
}

.zoom-pan-container:focus {
  outline: 2px solid #1976d2;
  outline-offset: 2px;
}

.zoom-pan-content {
  position: absolute;
  transform-origin: 0 0;
  width: max-content;
  height: max-content;
  min-width: 100%;
  min-height: 100%;
  
  /* Chrome optimizations */
  will-change: transform;
  transform: translateZ(0);
  backface-visibility: hidden;
  
  /* Prevent subpixel rendering issues */
  image-rendering: optimizeSpeed;
  image-rendering: -webkit-optimize-contrast;
  
  /* Force GPU compositing */
  -webkit-transform: translateZ(0);
  -webkit-backface-visibility: hidden;
  -webkit-perspective: 1000;
}

/* Chrome-specific optimizations */
@media screen and (-webkit-min-device-pixel-ratio: 0) {
  .zoom-pan-content {
    /* Additional Chrome-only optimizations */
    -webkit-font-smoothing: subpixel-antialiased;
    -webkit-transform-style: preserve-3d;
  }
}

</style>

<style>
//* LOD-based visibility rules with hover persistence - Optimized Version */

/* Base transitions for appearing/disappearing elements */
.zoom-pan-lod1,
.zoom-pan-lod2,
.zoom-pan-lod3 {
  transition: opacity 0.3s ease-out;
}

/* CSS Custom Properties for LOD management.
 *
 * These drive opacity/pointer-events. The companion `display: none` rules
 * further down additionally take hidden layers out of the render tree, since an
 * element hidden by opacity alone still gets restyled at every LOD crossing.
 * Port labels dominate that cost because text is expensive to restyle — a
 * crossing measured ~32ms of RecalcStyle for 1200 labels on a 200-node graph.
 *
 * Be aware the display rules did NOT eliminate that cost in practice: crossings
 * still measured ~31ms end-to-end. Removing elements from the tree is directionally
 * right, but the remaining cost scales with how many elements the restyle must
 * walk, so the real fix is fewer mounted nodes (viewport culling), not more CSS. */
:root {
  --lod-1-opacity: 1;
  --lod-1-pointer-events: auto;
  --lod-2-opacity: 1;
  --lod-2-pointer-events: auto;
  --lod-3-opacity: 1;
  --lod-3-pointer-events: auto;
}

/* LOD Level Overrides: Set visibility based on zoom level */
[data-lod-level="raw"] {
  --lod-1-opacity: 0;
  --lod-1-pointer-events: none;
  --lod-2-opacity: 0;
  --lod-2-pointer-events: none;
  --lod-3-opacity: 0;
  --lod-3-pointer-events: none;
}

[data-lod-level="low"] {
  --lod-2-opacity: 0;
  --lod-2-pointer-events: none;
  --lod-3-opacity: 0;
  --lod-3-pointer-events: none;
}

[data-lod-level="medium"] {
  --lod-3-opacity: 0;
  --lod-3-pointer-events: none;
}

/* Apply custom properties to LOD elements */
.zoom-pan-lod1 {
  opacity: var(--lod-1-opacity);
  pointer-events: var(--lod-1-pointer-events);
}

.zoom-pan-lod2 {
  opacity: var(--lod-2-opacity);
  pointer-events: var(--lod-2-pointer-events);
}

.zoom-pan-lod3 {
  opacity: var(--lod-3-opacity);
  pointer-events: var(--lod-3-pointer-events);
}

/* Take hidden LOD layers OUT OF THE RENDER TREE, not just make them invisible.
 *
 * An element hidden with opacity alone stays in the tree, so every LOD crossing
 * makes Blink restyle all of them: measured at ~32ms of RecalcStyle for the
 * 1200 port labels on a 200-node graph, which is the hitch felt when wheeling
 * across a threshold (text is the expensive thing to restyle, which is why the
 * jumps line up with pin labels appearing). `display: none` drops that to
 * ~0.2ms.
 *
 * These MUST be direct descendant rules, never `display: var(--lod-N-display)`.
 * A custom property invalidates every element referencing it, so routing
 * display through a variable reintroduces exactly the whole-subtree restyle it
 * is meant to avoid — measured at 26.7ms via var() versus 0.2ms here.
 *
 * Hover-persistence is preserved by the `:not(.hw-lod-hover *)` guard, which
 * keeps the hovered card's own subtree out of these rules entirely.
 *
 * The guard is written as an exclusion rather than a companion `display: revert`
 * override, because `revert` rolls back to the USER-AGENT value, not to the
 * author `display` the element would otherwise have. A `<div>` reverts to
 * `block`, which silently destroys any author `display: flex` on the same
 * element — e.g. `.number-drag` (the NumberWidget root carries
 * `widget-container zoom-pan-lod2`) collapsed to a block on node hover, pushing
 * its value text and right arrow out of the fixed-height box, where
 * `.widget-container { overflow: hidden }` clipped them away.
 *
 * `.hw-lod-hover` is a class canvas.vue sets in its existing mouseenter/
 * mouseleave handlers — NOT `:hover`. A descendant-of-:hover selector
 * (`.zoom-pan-lod0:hover .zoom-pan-lod2`) forces Blink to track hover state
 * through every node's subtree, and that alone cost ~37ms of RecalcStyle per LOD
 * crossing on a 200-node graph versus 0.1ms without it. */
[data-lod-level="raw"] .zoom-pan-lod1:not(.hw-lod-hover *),
[data-lod-level="raw"] .zoom-pan-lod2:not(.hw-lod-hover *),
[data-lod-level="low"] .zoom-pan-lod2:not(.hw-lod-hover *),
[data-lod-level="raw"] .zoom-pan-lod3:not(.hw-lod-hover *),
[data-lod-level="low"] .zoom-pan-lod3:not(.hw-lod-hover *),
[data-lod-level="medium"] .zoom-pan-lod3:not(.hw-lod-hover *) {
  display: none;
}

/* HOVER PERSISTENCE: Override LOD when hovering - Simplified */

/* Hover persistence. Keyed off the JS-set `.hw-lod-hover` class rather than
 * `:hover` for the reason documented on the display rules above: these set
 * inherited custom properties, so a `:hover`-keyed version makes every LOD
 * crossing re-resolve hover state across the whole canvas subtree. */
.hw-lod-hover {
  --lod-1-opacity: 1;
  --lod-1-pointer-events: auto;
  --lod-2-opacity: 1;
  --lod-2-pointer-events: auto;
  --lod-3-opacity: 1;
  --lod-3-pointer-events: auto;
}

/* Card hover affordance + magnifier transition.
 * The hover magnifier (canvas.vue) sets an inline `transform: scale(...)` on
 * `.zoom-pan-lod0` after a dwell delay; the transform transition here animates
 * that magnify/shrink. A subtle box-shadow gives the "hovered" cue. The
 * magnifier is gated by a setting and a dwell timer, so it no longer fires on
 * every accidental fly-over the way the old CSS `:hover` scale did. */
.zoom-pan-lod0 {
  transition: box-shadow 0.2s ease-out, transform 0.14s ease-out;
  cursor: pointer;
}

.zoom-pan-lod0:hover {
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  z-index: 10;
  position: relative;
}

/* Controls styles */
.zoom-pan-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.zoom-pan-info {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 1000;
}
</style>
