<template>
  <div
    ref="minimap"
    v-show="visible"
    class="minimap-container"
    :style="containerStyle"
    @mouseenter="blendIn"
    @mouseleave="scheduleBlendOut"
  >
    <canvas
      ref="canvas"
      :width="minimapWidth"
      :height="minimapHeight"
      style="display: block; width: 100%; height: 100%;"
      @click="handleClick"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseLeave"
    />
  </div>
</template>

<script>
export default {
  name: 'MinimapCanvas',

  props: {
    containerId:   { type: String,  required: true },
    minimapWidth:  { type: Number,  default: 200 },
    position:      { type: String,  default: 'top-right' },
    activeOpacity: { type: Number,  default: 0.88 },
    ghostOpacity:  { type: Number,  default: 0.15 },
    debugInfo:     { type: Boolean, default: false },
    visible:       { type: Boolean, default: true },
    canvasWidth:   { type: Number,  default: 8000 },
    canvasHeight:  { type: Number,  default: 8000 },
  },

  data() {
    return {
      // Constants — defined here so vbuild includes them in the compiled component.
      PADDING:      10,
      // Reactive height — re-derived whenever content bounds change.
      minimapHeight: this.minimapWidth,
    };
  },

  computed: {
    containerStyle() {
      const POSITIONS = {
        'top-right':    'top: 10px; right: 10px;',
        'top-left':     'top: 10px; left: 10px;',
        'bottom-right': 'bottom: 10px; right: 10px;',
        'bottom-left':  'bottom: 10px; left: 10px;',
      };
      // Note: opacity is intentionally absent — it is managed via direct DOM
      // manipulation in blendIn / scheduleBlendOut to avoid Vue re-renders on
      // every animation frame.
      return (
        'position: absolute; ' +
        `width: ${this.minimapWidth}px; ` +
        `height: ${this.minimapHeight}px; ` +
        'z-index: 1001; ' +
        'border: 1px solid var(--hw-border); ' +
        'border-radius: 6px; ' +
        'background: var(--hw-bg-overlay, #1e1e2e); ' +
        'transition: opacity 0.3s ease; ' +
        'box-shadow: 0 2px 12px rgba(0,0,0,0.4); ' +
        'cursor: crosshair; ' +
        'backdrop-filter: blur(2px); ' +
        (POSITIONS[this.position] || POSITIONS['top-right'])
      );
    },
  },

  mounted() {
    // Non-reactive canvas state — updated on every viewport event, React reactivity
    // overhead is not needed here.
    this._contentBounds = { minX: 0, minY: 0, maxX: this.canvasWidth, maxY: this.canvasHeight };
    this._nodeRects     = [];
    this._scaleFactor   = 1.0;
    this._viewportRect  = { x: 0, y: 0, width: 50, height: 50 };
    this._zoom          = 1.0;
    this._panX          = 0;
    this._panY          = 0;
    this._isDragging    = false;
    this._lastMouseX    = 0;
    this._lastMouseY    = 0;
    this._fadeTimer     = null;

    // Set initial resting opacity directly — no Vue binding needed.
    this.$refs.minimap.style.opacity = this.ghostOpacity;

    // Listen to 'zoom-pan-state' DOM events dispatched by ZoomPanContainer.
    // This avoids a Python round-trip on every frame.
    this._onZoomPanState = (e) => {
      if (e.detail.containerId === this.containerId) {
        this._updateViewport(e.detail.zoom, e.detail.panX, e.detail.panY);
        this.blendIn();
        this.scheduleBlendOut();
      }
    };
    document.addEventListener('zoom-pan-state', this._onZoomPanState);

    // Initial scan after the first two animation frames (same timing as fitToContent).
    requestAnimationFrame(() => requestAnimationFrame(() => this.scanContent()));

    // Periodic rescan to pick up node moves / additions.
    this._scanInterval = setInterval(() => this.scanContent(), 5000);
  },

  beforeDestroy() {
    document.removeEventListener('zoom-pan-state', this._onZoomPanState);
    clearInterval(this._scanInterval);
    if (this._fadeTimer) clearTimeout(this._fadeTimer);
  },

  methods: {
    // ── Helpers ──────────────────────────────────────────────────────────────

    _getThemeColor(varName, fallback) {
      return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || fallback;
    },

    _getMainContainer() {
      return document.getElementById(this.containerId);
    },

    _setOpacity(value) {
      if (this.$refs.minimap) this.$refs.minimap.style.opacity = value;
    },

    _stopDragging() {
      this._isDragging = false;
      this.$el.classList.remove('dragging');
    },

    // ── Drawing ──────────────────────────────────────────────────────────────

    _draw() {
      const canvas = this.$refs.canvas;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      const w   = this.minimapWidth;
      const h   = this.minimapHeight;

      const canvasColor   = this._getThemeColor('--hw-canvas-bg',    '#13131a');
      const borderColor   = this._getThemeColor('--hw-border',       '#333355');
      const nodeColor     = this._getThemeColor('--hw-accent',       '#7c6af7');
      const viewportColor = this._getThemeColor('--hw-accent-hover', '#a89af9');

      ctx.clearRect(0, 0, w, h);

      const { minX, minY, maxX, maxY } = this._contentBounds;
      const sf = this._scaleFactor;
      const bw = (maxX - minX) * sf;
      const bh = (maxY - minY) * sf;

      // Canvas area background + border
      ctx.fillStyle = canvasColor + 'cc';
      ctx.fillRect(this.PADDING, this.PADDING, bw, bh);
      ctx.strokeStyle = borderColor;
      ctx.lineWidth = 1;
      ctx.strokeRect(this.PADDING, this.PADDING, bw, bh);

      // Node rectangles
      ctx.fillStyle = nodeColor + 'cc';
      for (const n of this._nodeRects) {
        ctx.fillRect(
          this.PADDING + (n.x - minX) * sf,
          this.PADDING + (n.y - minY) * sf,
          Math.max(2, n.w * sf),
          Math.max(2, n.h * sf),
        );
      }

      // Viewport rectangle — clamped to minimap bounds
      const vp = this._viewportRect;
      const cx = Math.max(0, Math.min(vp.x, w));
      const cy = Math.max(0, Math.min(vp.y, h));
      const cw = Math.max(1, Math.min(vp.width,  w - cx));
      const ch = Math.max(1, Math.min(vp.height, h - cy));

      ctx.fillStyle   = viewportColor + '33';
      ctx.strokeStyle = viewportColor;
      ctx.lineWidth   = 2;
      ctx.fillRect(cx, cy, cw, ch);
      ctx.strokeRect(cx, cy, cw, ch);

      if (this.debugInfo) {
        ctx.fillStyle = 'rgba(0,0,0,0.75)';
        ctx.fillRect(0, h - 80, w, 80);
        ctx.fillStyle = this._getThemeColor('--hw-text-body', '#e0e0f0');
        ctx.font = '9px monospace';
        const lines = [
          `zoom: ${this._zoom.toFixed(3)}`,
          `pan:  ${this._panX.toFixed(0)}, ${this._panY.toFixed(0)}`,
          `view: ${Math.round(cw)} x ${Math.round(ch)}`,
          `scale: ${sf.toFixed(4)}`,
          `canvas: ${Math.round(maxX)} x ${Math.round(maxY)}`,
        ];
        lines.forEach((line, i) => ctx.fillText(line, 4, h - 80 + 11 + i * 13));
      }
    },

    // ── State ─────────────────────────────────────────────────────────────────

    _recalcScale() {
      if (!this._contentBounds) return;
      const cw = this._contentBounds.maxX - this._contentBounds.minX;
      const ch = this._contentBounds.maxY - this._contentBounds.minY;
      if (cw <= 0 || ch <= 0) return;

      const contentW = this.minimapWidth - this.PADDING * 2;
      const newH     = Math.round(contentW * ch / cw) + this.PADDING * 2;
      this.minimapHeight = newH;

      const contentH    = this.minimapHeight - this.PADDING * 2;
      this._scaleFactor = Math.min(contentW / cw, contentH / ch, 1.0);
    },

    _updateViewport(zoom, panX, panY) {
      this._zoom = zoom;
      this._panX = panX;
      this._panY = panY;

      const el = this._getMainContainer();
      if (!el) return;

      const rect       = el.getBoundingClientRect();
      const sf         = this._scaleFactor;
      const { minX, minY } = this._contentBounds;

      this._viewportRect = {
        x:      this.PADDING + (-panX / zoom - minX) * sf,
        y:      this.PADDING + (-panY / zoom - minY) * sf,
        width:  Math.max(2, (rect.width  / zoom) * sf),
        height: Math.max(2, (rect.height / zoom) * sf),
      };

      this._draw();
    },

    // ── Public API (also callable from Python via run_method) ─────────────────

    scanContent() {
      const el = this._getMainContainer();
      if (!el) return;

      const content = el.querySelector('.zoom-pan-content');
      if (!content) return;

      const nodes = [];
      content.querySelectorAll('[data-node-id]').forEach(node => {
        // Skip port/sub-elements nested inside another [data-node-id].
        if (node.parentElement && node.parentElement.closest('[data-node-id]')) return;
        nodes.push({
          x: parseFloat(node.style.left) || 0,
          y: parseFloat(node.style.top)  || 0,
          w: node.offsetWidth,
          h: node.offsetHeight,
        });
      });

      this._contentBounds = { minX: 0, minY: 0, maxX: this.canvasWidth, maxY: this.canvasHeight };
      this._nodeRects     = nodes;
      this._recalcScale();

      if (el._zoomPanControls) {
        const z = el._zoomPanControls.getZoom();
        const p = el._zoomPanControls.getPan();
        this._updateViewport(z, p.x, p.y);
      } else {
        this._draw();
      }
    },

    // ── Mouse interactions ────────────────────────────────────────────────────

    _minimapToContent(mx, my) {
      const { minX, minY } = this._contentBounds;
      return {
        x: minX + (mx - this.PADDING) / this._scaleFactor,
        y: minY + (my - this.PADDING) / this._scaleFactor,
      };
    },

    handleClick(e) {
      const rect = this.$refs.canvas.getBoundingClientRect();
      const pos  = this._minimapToContent(e.clientX - rect.left, e.clientY - rect.top);

      const el = this._getMainContainer();
      if (!el || !el._zoomPanControls) return;

      const cRect = el.getBoundingClientRect();
      const zoom  = el._zoomPanControls.getZoom();
      el._zoomPanControls.setPan(
        -(pos.x * zoom - cRect.width  / 2),
        -(pos.y * zoom - cRect.height / 2),
      );
    },

    handleMouseDown(e) {
      if (e.button !== 0) return;
      this._isDragging = true;
      const rect       = this.$refs.canvas.getBoundingClientRect();
      this._lastMouseX = e.clientX - rect.left;
      this._lastMouseY = e.clientY - rect.top;
      this.$el.classList.add('dragging');
      e.preventDefault();
    },

    handleMouseMove(e) {
      if (!this._isDragging) return;
      const rect     = this.$refs.canvas.getBoundingClientRect();
      const currentX = e.clientX - rect.left;
      const currentY = e.clientY - rect.top;
      const sf       = this._scaleFactor;

      const el = this._getMainContainer();
      if (el && el._zoomPanControls) {
        const pan  = el._zoomPanControls.getPan();
        const zoom = el._zoomPanControls.getZoom();
        el._zoomPanControls.setPan(
          pan.x - ((currentX - this._lastMouseX) / sf) * zoom,
          pan.y - ((currentY - this._lastMouseY) / sf) * zoom,
        );
      }

      this._lastMouseX = currentX;
      this._lastMouseY = currentY;
    },

    handleMouseUp()    { this._stopDragging(); },
    handleMouseLeave() { this._stopDragging(); },

    // ── Opacity / fade ────────────────────────────────────────────────────────

    blendIn() {
      if (this._fadeTimer) clearTimeout(this._fadeTimer);
      this._setOpacity(this.activeOpacity);
    },

    scheduleBlendOut() {
      if (this._fadeTimer) clearTimeout(this._fadeTimer);
      this._fadeTimer = setTimeout(() => {
        this._setOpacity(this.ghostOpacity);
        this._fadeTimer = null;
      }, 1200);
    },
  },

  watch: {
    canvasWidth(newVal) {
      this._contentBounds = { minX: 0, minY: 0, maxX: newVal, maxY: this.canvasHeight };
      this._recalcScale();
      this._draw();
    },
    canvasHeight(newVal) {
      this._contentBounds = { minX: 0, minY: 0, maxX: this.canvasWidth, maxY: newVal };
      this._recalcScale();
      this._draw();
    },

    minimapWidth() {
      this._recalcScale();
      this._draw();
      this.blendIn();
      this.scheduleBlendOut();
    },

    debugInfo() {
      this._draw();
    },

    visible(newVal) {
      if (newVal) {
        // Became visible — do a fresh scan so content + viewport are current.
        this.$nextTick(() => this.scanContent());
      }
    },

    ghostOpacity(newVal) {
      // Apply new resting opacity immediately unless currently blended in.
      if (!this._fadeTimer) this._setOpacity(newVal);
    },
  },
};
</script>

<style scoped>
.minimap-container {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.minimap-container canvas {
  border-radius: 4px;
}

.minimap-container.dragging {
  cursor: grabbing !important;
}
</style>
