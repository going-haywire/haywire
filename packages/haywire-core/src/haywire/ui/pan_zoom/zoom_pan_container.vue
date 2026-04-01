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
  >
    <div 
      ref="content"
      class="zoom-pan-content"
    >
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ZoomPanContainer',
  
  props: {
    containerId: { type: String, required: true },
    maxZoom: { type: Number, default: 5.0 },
    initialZoom: { type: Number, default: 1.0 },
    zoomSensitivity: { type: Number, default: 0.1 },
    panSensitivity: { type: Number, default: 1.0 },
    smoothZoom: { type: Boolean, default: true },
    enableKeyboard: { type: Boolean, default: true }
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
      const rect = this.$el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const CANVAS_SIZE = 8000;
        this._minZoom = Math.max(rect.width / CANVAS_SIZE, rect.height / CANVAS_SIZE);
      }
    },

    _setupListeners() {
      // Invalidate rect cache at gesture boundaries and on resize
      this.$el.addEventListener('mousedown', this._invalidateRectCache);
      document.addEventListener('mouseup', this._invalidateRectCache);
      window.addEventListener('resize', this._invalidateRectCache);
    },

    _cleanupListeners() {
      this.$el.removeEventListener('mousedown', this._invalidateRectCache);
      document.removeEventListener('mouseup', this._invalidateRectCache);
      window.removeEventListener('resize', this._invalidateRectCache);
    },
    
    handleWheel(e) {
      // e.ctrlKey is set by the browser for both physical Ctrl+scroll AND trackpad
      // pinch gestures — it is more reliable than tracking keydown/keyup state.
      if (e.ctrlKey) {
        // Zoom: Ctrl+scroll or trackpad pinch
        const zoomDelta = -e.deltaY * this.zoomSensitivity * 0.01;
        this._setZoomDirect(this._zoom + zoomDelta, e.clientX, e.clientY);
      } else {
        // Pan: plain scroll or two-finger trackpad swipe
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
      const CANVAS_SIZE = 8000;

      const canvasW = CANVAS_SIZE * this._zoom;
      const canvasH = CANVAS_SIZE * this._zoom;

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
   
    _updateZoomAndLODClass() {
      const container = this.$el;
      let hoverScale, lodLevel;
      
      if (this._zoom <= 0.3) {
        hoverScale = 1.5;
        lodLevel = 'raw';  // Show only lod0
      } else if (this._zoom <= 0.5) {
        hoverScale = 1.25;
        lodLevel = 'low';   // Show lod0 and lod1
      } else if (this._zoom <= 0.75) {
        hoverScale = 1.0;
        lodLevel = 'medium';  // Show lod0, lod1 and lod2
      } else if (this._zoom <= 1.0) {
        hoverScale = 1.0;
        lodLevel = 'high';  // Show lod0, lod1, lod2 and lod3
      } else {
        hoverScale = 1.0;
        lodLevel = 'high';  // Show lod0, lod1, lod2 and lod3
      }
      
      // Set CSS variable for hover scaling
      container.style.setProperty('--hover-scale', hoverScale);
      
      // Set LOD level for visibility control
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

    beforeDestroy() {
      // Clean up any pending timers
      if (this._wheelTimeout) {
        clearTimeout(this._wheelTimeout);
      }
      if (this.updateTimeout) {
        clearTimeout(this.updateTimeout);
      }
    },
  },
  
  watch: {
    // Watch for prop changes and update internal state
    initialZoom(newVal) {
      if (this._zoom === this.initialZoom) { // Only if not manually changed
        this._zoom = newVal;
        this._updateTransformDirect(true);
      }
    }
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

  --hover-scale: 1.1;
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

/* CSS Custom Properties for LOD management */
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

/* HOVER PERSISTENCE: Override LOD when hovering - Simplified */

/* When hovering LOD0, show all children */
.zoom-pan-lod0:hover {
  --lod-1-opacity: 1;
  --lod-1-pointer-events: auto;
  --lod-2-opacity: 1;
  --lod-2-pointer-events: auto;
  --lod-3-opacity: 1;
  --lod-3-pointer-events: auto;
}

/* When hovering LOD1, show LOD2 and LOD3 children */
.zoom-pan-lod1:hover {
  --lod-2-opacity: 1;
  --lod-2-pointer-events: auto;
  --lod-3-opacity: 1;
  --lod-3-pointer-events: auto;
}

/* When hovering LOD2, show LOD3 children */
.zoom-pan-lod2:hover {
  --lod-3-opacity: 1;
  --lod-3-pointer-events: auto;
}

/* Hover scaling for cards based on zoom level */
.zoom-pan-lod0 {
  transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;
  cursor: pointer;
}

.zoom-pan-lod0:hover {
  /* This inherits --hover-scale from .zoom-pan-container */
  transform: scale(var(--hover-scale, 1.1));
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
