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
    minZoom: { type: Number, default: 0.1 },
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
      updateTimeout: null,
      
      // Add gesture state
      gestureState: {
        ctrlPressed: false,
        shiftPressed: false,
        isGesturing: false
      }
    };
  },
  
  // Remove computed properties entirely
  
  mounted() {
    // Non-reactive transform state
    this._zoom = this.initialZoom;
    this._panX = 0;
    this._panY = 0;
    
    // Initialize
    this._updateTransformDirect();
    
    // Setup keyboard listeners
    this._setupKeyboardListeners();

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
        this._updateTransformDirect();
      },
      fitToContent: this.fitToContent,
      getState: () => ({ 
        zoom: this._zoom, 
        panX: this._panX, 
        panY: this._panY, 
        isDragging: this.isDragging 
      })
    };
  },
  
  methods: {

    _setupKeyboardListeners() {
      // Listen for modifier key changes
      document.addEventListener('keydown', this.handleGlobalKeyDown);
      document.addEventListener('keyup', this.handleGlobalKeyUp);
    },
    
    _cleanupKeyboardListeners() {
      document.removeEventListener('keydown', this.handleGlobalKeyDown);
      document.removeEventListener('keyup', this.handleGlobalKeyUp);
    },
    
    handleGlobalKeyDown(e) {
      // Track modifier key states
      if (e.key === 'Control' || e.key === 'Meta') { // Meta for Cmd on Mac
        // currently ignored
        this.gestureState.ctrlPressed = true;
      }
      
      if (e.key === 'Shift') {
        this.gestureState.shiftPressed = true;
      }
    },
    
    handleGlobalKeyUp(e) {
      // Track modifier key states
      if (e.key === 'Control' || e.key === 'Meta') {
        // currently ignored
        this.gestureState.ctrlPressed = false;
      }
      
      if (e.key === 'Shift') {
        this.gestureState.shiftPressed = false;
      }
    },
    
    handleWheel(e) {
      // Immediate processing - no batching
      // Check if we're in a special gesture mode
      // const isCtrlGesture = this.gestureState.ctrlPressed; -> currently ignored
      const isShiftGesture = this.gestureState.shiftPressed;
       
      if (!isShiftGesture) {
        const zoomDelta = -e.deltaY * this.zoomSensitivity * 0.01;
        this._setZoomDirect(this._zoom + zoomDelta, e.clientX, e.clientY);
      }
      else if (isShiftGesture) {
        const deltaX = (-e.deltaX) * this.panSensitivity;
        const deltaY = (-e.deltaY) * this.panSensitivity;
        this._setPanDirect(this._panX + deltaX, this._panY + deltaY);
      }
    },


    _setZoomDirect(newZoom, centerX = null, centerY = null) {
      const oldZoom = this._zoom;
      this._zoom = Math.max(this.minZoom, Math.min(this.maxZoom, newZoom));
      
      if (centerX !== null && centerY !== null) {
        const rect = this.$el.getBoundingClientRect();
        const offsetX = centerX - rect.left;
        const offsetY = centerY - rect.top;
        
        const contentX = (offsetX - this._panX) / oldZoom;
        const contentY = (offsetY - this._panY) / oldZoom;
        
        this._panX = offsetX - contentX * this._zoom;
        this._panY = offsetY - contentY * this._zoom;
      }
      
      this._updateTransformDirect();
    },

    // prevent extremely large pan values:
    _clampPanValues() {
      const containerRect = this.$el.getBoundingClientRect();
      const maxPan = Math.max(containerRect.width, containerRect.height) * 5; // Reasonable limit
      
      this._panX = Math.max(-maxPan, Math.min(maxPan, this._panX));
      this._panY = Math.max(-maxPan, Math.min(maxPan, this._panY));
    },

    _setPanDirect(newPanX, newPanY) {
      this._panX = newPanX;
      this._panY = newPanY;
      
      // Clamp pan values to prevent Chrome performance issues
      this._clampPanValues();
      
      this._updateTransformDirect();
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
    _updateTransformDirect() {
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
      this._updateZoomAndLODClass();
      
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
        this._updateTransformDirect();
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
