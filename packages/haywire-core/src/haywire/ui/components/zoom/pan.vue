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
    // Unmount off-screen node bodies from the render walk. See _applyCulling.
    cullEnabled: { type: Boolean, default: false },
    // Both thresholds must be met for culling to do anything. See _cullingApplies.
    cullMinNodes: { type: Number, default: 100 },
    cullMinZoom: { type: Number, default: 0.5 },
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

    // Wheel-gesture latch: 'wheel' | 'trackpad' | null. See handleWheel.
    //
    // Quiet period that ends a gesture. Comfortably above a trackpad's event
    // spacing (~8-16ms, and its momentum tail stays well inside this), and
    // below the gap between two deliberate wheel notches — and mis-chaining
    // two wheel notches would be harmless anyway, since they latch the same
    // mode.
    this.WHEEL_GESTURE_GAP_MS = 100;
    this._wheelMode = null;
    this._wheelLastT = 0;

    // Deferred `transform-changed`: see _updateTransformDirect. Kept separate
    // from _wheelMode on purpose — that latch is resolved lazily, by comparing
    // timestamps on the NEXT wheel event, so it stays non-null indefinitely
    // after a gesture stops and would suppress every later emit.
    this._transformDirty = false;
    this._gestureEndTimer = null;

    // --- Viewport culling ---------------------------------------------------
    // Cached node boxes in CONTENT space: [{ cull, x, y, w, h }]. Rebuilt only
    // when the graph could have changed shape, never during a gesture —
    // offsetWidth forces layout, and 300 of those per frame is the cost this
    // whole feature exists to avoid.
    this._cullItems = null;
    this._cullFrame = null;
    // Culling stays OFF until the graph has finished loading, because an edge
    // is created by looking up its two PIN elements, and a culled node has
    // none. That lookup failing is not recoverable — canvas.vue drops the
    // connection and never retries — so culling during load silently loses
    // most of the graph's edges (162 of 204 on 60nodes-edges, with 424
    // console errors). Armed by the first completed gesture, or immediately
    // when the setting is switched on by hand, both of which mean the graph is
    // already up. After that, culling only suppresses edge UPDATES, which is
    // harmless: a culled node cannot move, so its edges stay correct.
    this._cullArmed = false;
    // Whether anything is currently hidden, so dropping below a threshold can
    // restore in one pass without scanning the DOM on every frame.
    this._cullHidden = false;
    // Hysteresis, in viewports of margin around the visible area. Reveal early
    // so a node is mounted before it is needed; cull later so a node sitting on
    // the boundary during a slow pan does not thrash mount/unmount.
    this.CULL_REVEAL_MARGIN = 0.5;
    this.CULL_DROP_MARGIN = 1.0;

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
          // The drag's explicit end — send the viewport it settled on.
          if (this._transformDirty) this._flushTransform();
          if (this.cullEnabled) {
            this._cullArmed = true;
            this._refreshCullItems();
            this._applyCulling();
          }
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
      // Both branches below move the viewport, so the settle timer is armed for
      // either one — it is what ends the gesture for `transform-changed`.
      this._noteGestureActivity();
      if (e.ctrlKey) {
        // Trackpad pinch gesture (browser sets ctrlKey synthetically) OR Ctrl+scroll
        const zoomDelta = -e.deltaY * this.zoomSensitivity * 0.01;
        this._setZoomDirect(this._zoom + zoomDelta, e.clientX, e.clientY);
        return;
      }

      // Mouse wheel (zoom) vs trackpad swipe (pan), decided ONCE PER GESTURE.
      //
      // Per-event classification cannot work here, and the bug it caused was
      // ugly: a vigorous straight-down trackpad swipe reaches 60-80px per
      // event, and a deliberate vertical swipe has deltaX exactly 0 — so the
      // middle of every fast pan matched "large and vertical", flipped to
      // zoom, and the canvas lurched. Panning to the bottom of the viewport
      // slammed zoom 0.30 -> 0.02; panning to the top took it to 2.96.
      //
      // What separates the two is the SHAPE OF THE STREAM, not any one event:
      //
      //   trackpad — a dense burst (events ~8-16ms apart) that RAMPS UP from
      //              small deltas, because it tracks finger velocity
      //   wheel    — sparse discrete notches, each already at full magnitude
      //
      // So classify the first event of a gesture and latch that decision until
      // the stream goes quiet. A trackpad swipe always opens small, which the
      // first-event test reads correctly; the latch then holds through the
      // fast middle that used to misfire.
      const now = e.timeStamp || performance.now();
      if (now - this._wheelLastT > this.WHEEL_GESTURE_GAP_MS) this._wheelMode = null;
      this._wheelLastT = now;

      if (this._wheelMode === null) {
        this._wheelMode = this._looksLikeMouseWheel(e) ? 'wheel' : 'trackpad';
      } else if (this._wheelMode === 'wheel' && (e.deltaX !== 0 || Math.abs(e.deltaY) < 50)) {
        // A gesture that opened wheel-shaped but is now producing two-axis or
        // small deltas is a trackpad after all. Only this direction is allowed:
        // a trackpad gesture must never be able to flip INTO zoom mid-swipe,
        // which is the whole failure being fixed.
        this._wheelMode = 'trackpad';
      }

      if (this._wheelMode === 'wheel') {
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


    /** Is this the FIRST event of a mouse-wheel gesture rather than a swipe?
     *
     *  Only ever consulted for a gesture's opening event — handleWheel latches
     *  the answer — so it can afford to be strict about what counts as a wheel.
     */
    _looksLikeMouseWheel(e) {
      // Line/page deltas are only ever produced by a real wheel (Firefox
      // reports deltaMode 1 for one). A trackpad is always pixel-mode.
      if (e.deltaMode !== 0) return true;
      // Two axes at once: no wheel does that (bar shift-scroll, handled below).
      if (e.deltaX !== 0) return false;
      // A wheel notch arrives at full size; a swipe opens small.
      if (Math.abs(e.deltaY) < 50) return false;
      // Chrome and Safari report wheelDeltaY in ±120 multiples for a real
      // wheel, and -3*deltaY for a trackpad. Not decisive on its own — a
      // trackpad deltaY of 40 or 80 also lands on a multiple of 120 — but as
      // a tiebreak on an opening event it removes the common false positives.
      const legacy = e.wheelDeltaY;
      if (typeof legacy === 'number' && legacy !== 0 && Math.abs(legacy) % 120 !== 0) return false;
      return true;
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

    _updateTransformDirect(zoomChanged) {
      // Always the 2D form. There used to be a matrix3d branch below zoom 0.5,
      // on the claim that Chrome handled it better; nothing had measured that.
      // It was one of five 3D hints on this layer, and it applied at exactly
      // the zooms where the framerate collapsed — a 3D matrix on a layer that
      // is already in a 3D rendering context is the case where a compositor is
      // least able to derive a raster scale from the transform.
      const transform = `translate(${this._panX}px, ${this._panY}px) scale(${this._zoom})`;

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
      
      // Python only needs the SETTLED viewport, never the frames on the way to
      // it. This used to emit on an 8ms throttle, which put ~11 websocket round
      // trips on the wire per pan gesture and ~13 per zoom — every one of them
      // superseded by the next, so the server was decoding a value only the
      // last of which is ever read. On a studio that also runs the node graph
      // in that same process, that is execution budget spent on nothing.
      //
      // Deferring is safe because nothing consumes this live: `on_zoom_change`
      // and `on_pan_change` have no callers in the repo, and `_on_ready` is a
      // one-shot that fires on the first settled emit either way (a programmatic
      // move — resetView / setZoom / fitToContent — is not a gesture, so it
      // still takes the 8ms path below and fires promptly).
      //
      // The live consumers are all client-side and untouched: the
      // `zoom-pan-state` CustomEvent above still fires every frame, which is
      // what the minimap and the debug overlay read.
      // Culling follows the viewport, so it is re-evaluated on every frame of a
      // gesture (coalesced to one rAF). It reads no DOM — see _applyCulling.
      this._scheduleCulling();

      this._transformDirty = true;
      if (this.isDragging || this._gestureEndTimer) return;

      if (this.updateTimeout) return;
      this.updateTimeout = setTimeout(() => {
        this.updateTimeout = null;
        this._flushTransform();
      }, 8);
    },

    /**
     * Re-measure every node's box, in content space.
     *
     * `offsetWidth` forces layout, so this is a settle-time operation only —
     * never inside a gesture. A culled node measures its placeholder, which is
     * held at the size the node had when it was culled, so the cache stays
     * correct while a node is unmounted.
     */
    _refreshCullItems() {
      const content = this.$refs.content;
      if (!content) { this._cullItems = null; return; }
      const items = [];
      content.querySelectorAll('.hw-node-cull').forEach((cull) => {
        const holder = cull.parentElement;   // the positioned [data-node-id] wrapper
        if (!holder) return;
        items.push({
          cull,
          nodeId: holder.id,
          x: parseFloat(holder.style.left) || 0,
          y: parseFloat(holder.style.top) || 0,
          w: holder.offsetWidth,
          h: holder.offsetHeight,
        });
      });
      // Empty means "not mounted yet", not "no nodes" — the first fit runs
      // before the cards exist. Staying null keeps it retrying rather than
      // caching an empty graph forever.
      this._cullItems = items.length ? items : null;
    },

    /** Show everything again — setting switched off, or a threshold no longer met. */
    _uncullAll() {
      const content = this.$refs.content;
      this._cullHidden = false;
      if (!content) return;
      const revealed = [];
      content.querySelectorAll('.hw-node-cull').forEach((el) => {
        if (el._hwCull && !el._hwCull.isVisible()) {
          el._hwCull.setVisible(true);
          const holder = el.parentElement;
          if (holder && holder.id) revealed.push(holder.id);
        }
      });
      this._dispatchNodesUncull(revealed);
    },

    /**
     * Tell canvas.vue which nodes just came back from being culled, so it can
     * repaint their edges.
     *
     * A culled node's card is fully unmounted (see cull.vue) — a settings
     * change made while it was culled (e.g. a graph-level NodeDetail rank
     * flip) never reached the `data-node-props-detail` MutationObserver in
     * canvas.vue, because there was no element for it to observe. The pin
     * that moved is invisible until this fires; without it, the edge stays
     * frozen at its pre-change geometry until some incidental trigger (a
     * drag, a hover) refreshes it — see `_updateEdge`'s "culled node cannot
     * move" comment, which is true for position but not for a rank change.
     *
     * Dispatched as a DOM CustomEvent (mirrors `zoom-pan-state` above) rather
     * than a Vue emit: canvas.vue and this component are sibling NiceGUI
     * mounts, not parent/child in the Vue tree.
     */
    _dispatchNodesUncull(nodeIds) {
      if (!nodeIds.length) return;
      document.dispatchEvent(new CustomEvent('zoom-pan-nodes-uncull', {
        detail: { nodeIds },
      }));
    },

    /**
     * Is culling worth doing at the current zoom, on a graph this size?
     *
     * Culling pays off when few of many nodes are on screen. Zoomed out, the
     * opposite holds: most of the graph is visible, so there is little to cull,
     * while a pan sweeps many nodes across the boundary at once and every
     * crossing costs a mount or an unmount. That is felt as stutter, for no
     * gain. A small graph is cheap to render whole, so it never needs culling
     * either.
     */
    _cullingApplies(nodeCount) {
      return this._zoom >= this.cullMinZoom && nodeCount >= this.cullMinNodes;
    },

    _scheduleCulling() {
      if (!this.cullEnabled || this._cullFrame) return;
      this._cullFrame = requestAnimationFrame(() => {
        this._cullFrame = null;
        this._applyCulling();
      });
    },

    /**
     * Mount the nodes near the viewport, unmount the ones far from it.
     *
     * The saving is NOT about paint. NiceGUI renders the whole page as one Vue
     * component and rebuilds a VNode for every element on every update, so a
     * mounted node costs on every interaction anywhere in the studio — even
     * ones with nothing to do with the canvas. A node whose slot is withheld is
     * skipped by that walk entirely (see cull.vue).
     *
     * Uses only cached geometry plus the current transform: no DOM reads, so it
     * is safe to run on every frame of a gesture.
     */
    _applyCulling() {
      if (!this.cullEnabled || !this._cullArmed) return;
      if (!this._cullItems) this._refreshCullItems();
      const items = this._cullItems;
      if (!items || !items.length) return;

      // Below either threshold everything must come BACK, not merely stop being
      // culled — otherwise zooming out past the threshold would leave whatever
      // was hidden at the time permanently missing.
      if (!this._cullingApplies(items.length)) {
        if (this._cullHidden) this._uncullAll();
        return;
      }

      const rect = this._getContainerRect();
      if (!rect) return;

      // Visible region, converted from screen pixels into content space.
      const z = this._zoom;
      const vx0 = -this._panX / z;
      const vy0 = -this._panY / z;
      const vw = rect.width / z;
      const vh = rect.height / z;

      const rIn = this.CULL_REVEAL_MARGIN;
      const rOut = this.CULL_DROP_MARGIN;

      const revealed = [];
      for (const it of items) {
        const el = it.cull;
        if (!el._hwCull || !el.isConnected) continue;
        const visible = el._hwCull.isVisible();
        // Distance test against the two bands. A node is revealed as soon as it
        // enters the inner band and only dropped once it leaves the outer one.
        const m = visible ? rOut : rIn;
        const near =
          it.x + it.w >= vx0 - vw * m &&
          it.x <= vx0 + vw * (1 + m) &&
          it.y + it.h >= vy0 - vh * m &&
          it.y <= vy0 + vh * (1 + m);
        if (near !== visible) {
          el._hwCull.setVisible(near);
          if (!near) this._cullHidden = true;
          else if (it.nodeId) revealed.push(it.nodeId);
        }
      }
      // Un-culling can happen every frame of a pan/zoom gesture; batch into
      // one CustomEvent per _applyCulling pass rather than one per node.
      this._dispatchNodesUncull(revealed);
    },

    /** Send the current viewport to Python, cancelling any pending debounce. */
    _flushTransform() {
      if (this.updateTimeout) {
        clearTimeout(this.updateTimeout);
        this.updateTimeout = null;
      }
      this._transformDirty = false;
      this.$emit('transform-changed', { panX: this._panX, panY: this._panY, zoom: this._zoom });
    },

    /**
     * Mark a wheel/trackpad gesture in flight and (re)arm its settle timer.
     *
     * A drag has an explicit end (mouseup); a wheel gesture does not, so the
     * same quiet period that ends the wheel-mode latch ends this one.
     */
    _noteGestureActivity() {
      if (this._gestureEndTimer) clearTimeout(this._gestureEndTimer);
      this._gestureEndTimer = setTimeout(() => {
        this._gestureEndTimer = null;
        if (this._transformDirty) this._flushTransform();
        // Settle time is the only safe moment to pay for layout, and nodes
        // revealed during the gesture have only just been measurable.
        if (this.cullEnabled) {
          this._cullArmed = true;
          this._refreshCullItems();
          this._applyCulling();
        }
      }, this.WHEEL_GESTURE_GAP_MS);
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
    if (this._gestureEndTimer) clearTimeout(this._gestureEndTimer);
    if (this._cullFrame) cancelAnimationFrame(this._cullFrame);
  },

  watch: {
    // Toggling LOD must take effect at the current zoom, not wait for the next
    // zoom gesture.
    lodEnabled() {
      const container = this.$el;
      const level = this._lodLevelFor(this._zoom);
      container.setAttribute('data-lod-level', level);
    },
    // Toggling the setting must take effect now, not at the next gesture —
    // this is the A/B switch the feature is evaluated with.
    cullEnabled(on) {
      if (on) {
        // Switched on by hand, so the graph is already drawn — safe to arm now.
        this._cullArmed = true;
        this._refreshCullItems();
        this._applyCulling();
      } else {
        this._cullItems = null;
        this._uncullAll();
      }
    },
    // Tuning a threshold must apply now — these are knobs the user turns while
    // watching the canvas, so waiting for the next gesture reads as broken.
    cullMinNodes() {
      if (this.cullEnabled && this._cullArmed) this._applyCulling();
    },
    cullMinZoom() {
      if (this.cullEnabled && this._cullArmed) this._applyCulling();
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
  
  /* This layer carries no 3D hints, deliberately.
   *
   * It used to hold five — translateZ(0), backface-visibility, a -webkit-
   * perspective, preserve-3d in the Chrome-only block below, and a matrix3d
   * transform branch (see _updateTransformDirect). All of them put this layer
   * into a 3D rendering context, which is what makes a compositor give up on
   * deriving a raster scale from the transform: raster a ~12000x11000 layer
   * near scale 1.0 while the transform is 0.084 and the resulting 130
   * megapixel raster accounts for a whole 80ms frame on its own.
   *
   * They were labelled "Chrome optimizations" and -webkit- prefixed. Removing
   * the group is worth +19.5% fps and -38.6% p99 in Firefox on a 200-node
   * graph at zoom 0.09, and is free in Chrome (-2.8%, spreads overlap). The
   * five were removed together, so the group's value is measured but the
   * individual contributions are not.
   *
   * will-change: transform is REMOVED, on correctness grounds (2026-09-03).
   *
   * It used to be kept: removing it made no difference in Firefox and trended
   * worse in Chrome on fps. That judgement was made on framerate alone, and
   * framerate was the wrong instrument — promotion was costing whole regions
   * of the canvas.
   *
   * Promoted, Chrome will not paint the entire layer once the content in view
   * gets large. Measured on graphs/10x300nodes.haywire, counting cards that
   * actually carry pixels (.scratch/pan-perf/paintcheck.py):
   *
   *     zoom 0.069 (fit, 300 cards in view)   152 of 300 never painted
   *     zoom 0.09  (208 in view)               53 of 208 never painted
   *     zoom 0.15  (62 in view)                 0  — under the threshold
   *
   * It is a hard horizontal cut, not a flicker: everything below a fixed line
   * is simply absent, at rest, indefinitely. That is the reported "only
   * sections of the nodes render, sometimes only half of them". Unpromoted,
   * the same scenes paint 300 of 300, at rest and mid-pan.
   *
   * The cost is framerate: ~87 -> ~38 fps at zoom 0.09 on that graph. A
   * correct 38 fps beats a fast half-drawn canvas, so this is deliberate. If
   * promotion is ever restored, gate it on zoom (it is harmless at >= 0.15,
   * where the painted area is small) and re-run paintcheck.py at 0.069 —
   * an fps run cannot see this regression. */

  /* Re-measured post-flatten-3d (2026-09-02, see .scratch/pan-perf/RESULTS.md):
   * removing this showed no regression and a directional gain at FULL detail
   * (+19.5% fps, -33% p99 on the less-confounded pair) — the rank where a
   * card actually carries enough raster content for a downscale filter choice
   * to matter. One run per cell, not the full 3-run protocol, so treat the
   * number as directional; nothing in it supports keeping the rule. Removed. */
}

@media screen and (-webkit-min-device-pixel-ratio: 0) {
  .zoom-pan-content {
    /* preserve-3d was here, and was the strongest of the five 3D hints: it
     * establishes a 3D rendering context for the whole node subtree, which
     * disables layer squashing and forces the compositor to keep descendants
     * separately sorted. */
    -webkit-font-smoothing: subpixel-antialiased;
  }
}

</style>

<style>
/* LOD-driven display:none rules removed (design session, 2026-09): measured
 * at 2.15x pan cost for a 0.2%/0.04% framerate gain (see
 * internals/handoff/node-detail-and-lod-classes.md, decision B, and
 * .scratch/pan-perf/RESULTS.md for the full matrix). The crossing itself —
 * not what it hides — was the cost; the collapsed-sweep control measured
 * flat (68.60 vs 68.57 fps) with nothing to hide, ruling out "not enough was
 * hidden" as the explanation.
 *
 * data-lod-level is STILL computed and written below (_updateZoomAndLODClass)
 * as a dormant hook for a future PAINT-ONLY, per-frame change — the zoom
 * value it needs is already tracked here. Nothing currently reads it. */

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
