<template>
    <div :id="containerId" ref="container" class="graph-canvas" :class="{
        dragging: dragState.isDragging,
        'box-selecting': boxSelectionState.isActive
    }" :style="[canvasSizeStyle, backgroundStyle]" tabindex="0" @click="handleCanvasClick" @contextmenu="handleContextMenu">
        <!-- Box selection rectangle -->
        <div 
            v-if="boxSelectionState.isActive" 
            class="selection-box"
            :style="selectionBoxStyle"
        ></div>

        <!-- SVG layer for connections -->
        <svg id="connection-svg" ref="svg" class="connection-svg" :style="canvasSizeStyle">
            <defs ref="defs">
                <!-- Dynamic gradients will be added here -->
            </defs>
            <!-- Dynamic paths will be added here -->
        </svg>

        <!-- Node container slot -->
        <div id="node-container" ref="nodeContainer" class="node-container" :style="nodeContainerTransform">
            <slot></slot>

            <!-- Single-node resize gadget (content space; pan/zoom transforms it
                 with the nodes). Wrapper is pointer-events:none so it never eats
                 canvas gestures; only the 8 grips are interactive. -->
            <div
                v-if="resizeGadget.visible"
                class="hw-resize-gadget"
                data-testid="resize-gadget"
                :style="{
                    position: 'absolute',
                    left: resizeGadget.left + 'px',
                    top: resizeGadget.top + 'px',
                    width: resizeGadget.width + 'px',
                    height: resizeGadget.height + 'px',
                    pointerEvents: 'none',
                }"
            >
                <div v-for="h in ['top','bottom','left','right','top-left','top-right','bottom-left','bottom-right']"
                     :key="h"
                     class="hw-resize-grip"
                     :data-handle="h"
                     @mousedown="onResizeGripDown($event, h)"></div>
            </div>
        </div>

    </div>
</template>

<script>
// In NiceGUI 3.x, libraries are ES modules in the importmap and only execute when imported.
// This side-effect import triggers graph_events.js to run, setting window.GraphEvents,
// window.EventCreators, and window.EventValidators that the component uses as globals.
import 'graph_events';

export default {
    name: 'GraphCanvas',

    props: {
        containerId: { type: String, required: true },
        zoomContainerId: { type: String, default: '' },
        canvasWidth:  { type: Number, default: 8000 },
        canvasHeight: { type: Number, default: 8000 },
        // Canvas appearance settings.
        bgPattern:        { type: String,  default: 'dots' },
        gridColor:        { type: String,  default: '#808080' },
        gridEnabled:      { type: Boolean, default: true },
        gridSize:         { type: Number,  default: 20 },
        gridSubdivisions: { type: Number,  default: 5 },
        snapToGrid:       { type: Boolean, default: true },
        snapScaleToGrid:  { type: Boolean, default: true },
        // Hover magnifier (readability aid; see _setupHoverObserver).
        hoverScaleEnabled:    { type: Boolean, default: true },
        hoverScaleMax:        { type: Number,  default: 1.5 },
        hoverScaleCutoffZoom: { type: Number,  default: 0.5 },
        hoverEnterDelay:      { type: Number,  default: 350 },
        hoverExitDelay:       { type: Number,  default: 0 },
    },

    data() {
        return {
            // Connection drag state machine: mode is 'idle' | 'active' | 'paused'
            edgeDrag: {
                mode: 'idle',
                anchorPin: null,         // the pin we're dragging from
                lastMousePos: { x: 0, y: 0 },  // last known screen mouse position
                previewPath: null,       // SVG path element for the in-progress connection
                lockProximityRange: 150,
                suggestionProximityRange: 200,
                suggestionPaths: new Map(),
                nearestCompatiblePin: null
            },
            
            // Unified drag state for all draggable elements
            dragState: {
                isDragging: false,
                draggedElements: [], // [{type: 'node', id: 'node1', element: HTMLElement}, ...]
                startMousePos: { x: 0, y: 0 },
                startPositions: new Map(), // elementId -> {x, y}
                dragOffset: { x: 0, y: 0 },
                hasActuallyMoved: false,
                dragThreshold: 5,
                mouseDownEvent: null
            },
            
            // Unified selection state
            selectionState: {
                selectedNodes: new Set(),
                selectedEdges: new Set(),
                activeElement: null,  // { kind: 'node'|'edge', id: string } | null — the single primary
                lastClickTime: 0,
                clickThreshold: 300
            },
            
            // Box selection state
            boxSelectionState: {
                isActive: false,
                startPos: { x: 0, y: 0 },
                currentPos: { x: 0, y: 0 },
                selectionRect: null
            },
            
            edgePaths: new Map(),
            updateEdgesThrottled: false,
            resizeObserver: null,
            mutationObserver: null,
            _pendingNodeWatcher: null,

            // Store current zoom/pan state from the zoom container
            zoomState: {
                zoom: 1,
                panX: 0,
                panY: 0,
                isDragging: false
            },

            // Toolbar gesture tracking — true while a pan/zoom drag is in progress
            // so we suppress and restore the selection-bounds toolbar during gestures.
            _toolbarHiddenForGesture: false,

            // Single-node resize gadget: an 8-handle transform box drawn in
            // content space (inside #node-container) around the sole selected
            // node. Zero per-node DOM — one gadget total. See _fitResizeGadget /
            // onResizeGripDown. left/top/width/height are content-space px.
            resizeGadget: { visible: false, nodeId: null, left: 0, top: 0, width: 0, height: 0 }
        };
    },

    computed: {
        canvasSizeStyle() {
            return { width: this.canvasWidth + 'px', height: this.canvasHeight + 'px' };
        },

        svgTransform() {
            return this.canvasSizeStyle;
        },

        nodeContainerTransform() {
            return this.canvasSizeStyle;
        },

        backgroundStyle() {
            if (this.bgPattern === 'none' || !this.gridEnabled) return {};
            const size = this.gridSize;
            const color = encodeURIComponent(this.gridColor);
            // All patterns use SVG tiles with the mark centred at (0,0) so the
            // visual grid points align with the snap coordinates (multiples of size).
            const vb = (pad) => `${-pad} ${-pad} ${size} ${size}`;
            const svgUrl = (body, pad = 0) =>
                `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='${vb(pad)}'%3E${body}%3C/svg%3E")`;

            if (this.bgPattern === 'dots') {
                const dot = `%3Ccircle cx='0' cy='0' r='1.5' fill='${color}'/%3E`;
                return { backgroundImage: svgUrl(dot, 2), backgroundSize: `${size}px ${size}px` };
            }
            if (this.bgPattern === 'lines') {
                // Two lines through (0,0): one horizontal, one vertical, spanning the tile.
                const lines = `%3Cline x1='0' y1='0' x2='${size}' y2='0' stroke='${color}' stroke-width='1'/%3E%3Cline x1='0' y1='0' x2='0' y2='${size}' stroke='${color}' stroke-width='1'/%3E`;
                return { backgroundImage: svgUrl(lines), backgroundSize: `${size}px ${size}px` };
            }
            if (this.bgPattern === 'cross') {
                const arm = 4;
                const cross = `%3Cpath d='M0 ${-arm}v${arm*2}M${-arm} 0h${arm*2}' stroke='${color}' stroke-width='1'/%3E`;
                return { backgroundImage: svgUrl(cross, arm), backgroundSize: `${size}px ${size}px` };
            }
            return {};
        },

        selectionBoxStyle() {
            if (!this.boxSelectionState.isActive) return {};
            
            const start = this.boxSelectionState.startPos;
            const current = this.boxSelectionState.currentPos;
            
            const left = Math.min(start.x, current.x);
            const top = Math.min(start.y, current.y);
            const width = Math.abs(current.x - start.x);
            const height = Math.abs(current.y - start.y);
            
            return {
                left: `${left}px`,
                top: `${top}px`,
                width: `${width}px`,
                height: `${height}px`
            };
        }
    },

    mounted() {
        console.log('GraphCanvas Vue component mounted with container ID:', this.containerId);
        this._pendingNodeIds = new Set();
        // Non-reactive on purpose (see _queueMeasurement): plain instance fields,
        // matching _pendingNodeIds above.
        this._pendingMeasurements = new Map();
        this._measureFlushHandle = null;

        // Measurement instrumentation, published for the debug overlay. Kept on
        // window (not component state) so it survives a graph switch — the point
        // is to watch whether measurement traffic settles over a whole session.
        if (!window.__hwMeasureStats) {
            window.__hwMeasureStats = { observed: 0, queued: 0, batches: 0, sent: 0 };
        }

        // Initialize component
        this._setupEventListeners();
        this._setupObservers();
        this._setupZoomPanListener();

        // Expose sync and context menu handlers for external invocation
        // used by pan.vue to forward context menu events
        this.$el._graphCanvasControls = {
            handleSyncEvent: this.handleSyncEvent,
            handleContextMenu: this.handleContextMenu
        };

        // Readiness marker: by now the event listeners are attached.
        // Playwright tests wait for [data-canvas-ready] before interacting.
        this.$el.setAttribute('data-canvas-ready', '1');
    },

    beforeUnmount() {
        this._cleanupEventListeners();
        this._cleanupObservers();
        this._cleanupZoomPanListener();
        // Clear any pending magnify timers so they don't fire post-unmount.
        this._clearAllMagnified();
        if (this._zoomPanBoundsTimer) { clearTimeout(this._zoomPanBoundsTimer); this._zoomPanBoundsTimer = null; }
        // Drop the queued measurement flush — the graph is going away, and the
        // callback would emit against a torn-down component.
        if (this._measureFlushHandle) { cancelAnimationFrame(this._measureFlushHandle); this._measureFlushHandle = null; }
        if (this._pendingMeasurements) this._pendingMeasurements.clear();
    },

    methods: {
        // =============================================================================
        // SETUP & INITIALIZATION
        // =============================================================================

        _setupEventListeners() {
            console.log('🔗 Setting up event listeners on document.body');
            document.body.addEventListener('mousedown', this.handleMouseDown, true);
            document.body.addEventListener('mousemove', this.handleMouseMove, true);
            document.body.addEventListener('mouseup', this.handleMouseUp, true);
            document.body.addEventListener('keydown', this.handleKeyDown, true);
        },

        _setupObservers() {
            this.mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.attributeName === 'style') {
                        const nodeElement = mutation.target;
                        const nodeId = nodeElement.dataset.nodeId;

                        if (nodeId && nodeElement.hasAttribute('data-node-id')) {
                            const styleText = nodeElement.style.cssText;
                            if (styleText.includes('left:') || styleText.includes('top:') || styleText.includes('transform:')) {
                                console.log(`-->  _setupObservers(): ${nodeId}`);
                                this._updateEdgesForNode(nodeId);
                                // Keep the resize gadget glued to the node it tracks.
                                if (this.resizeGadget.visible && this.resizeGadget.nodeId === nodeId) {
                                    this._fitResizeGadget();
                                }
                            }
                        }
                    }
                });
            });
        },

        _setupHoverObserver(nodeElement) {
            const lodElement = nodeElement.querySelector('.zoom-pan-lod0');
            if (!lodElement) return;

            const nodeId = nodeElement.getAttribute('data-node-id');
            if (!nodeId) return;

            const scheduleEdgeUpdates = () => {
                this._scheduleEdgeUpdates(nodeId, nodeElement);
            };

            // Listen for transform transitions (the magnifier scales `transform`,
            // which shifts pin positions — refresh edges as it animates).
            lodElement.addEventListener('transitionstart', (e) => {
                if (e.propertyName === 'transform') {
                    this._scheduleEdgeUpdates(nodeId, nodeElement);
                    // If an edge drag is in progress, the magnify shifts this
                    // node's pins — recompute the preview/suggestions against the
                    // new positions so aiming stays accurate even if the pointer
                    // is held still while the node scales up.
                    if (this.edgeDrag.mode === 'active') {
                        this._handleEdgeDragMove({
                            target: document.elementFromPoint(
                                this.edgeDrag.lastMousePos.x,
                                this.edgeDrag.lastMousePos.y
                            ) || document.body,
                            clientX: this.edgeDrag.lastMousePos.x,
                            clientY: this.edgeDrag.lastMousePos.y,
                        });
                    }
                }
            });

            // Hover magnifier: dwell to magnify, release on leave. Timers are
            // stored on the element so leave can cancel a pending enter, and so
            // cleanup can clear them. Edge refresh is driven by the transition
            // above (no extra call needed here beyond the size-change schedule).
            lodElement.addEventListener('mouseenter', () => {
                scheduleEdgeUpdates();
                this._onNodeHoverEnter(lodElement);
            });
            lodElement.addEventListener('mouseleave', () => {
                scheduleEdgeUpdates();
                this._onNodeHoverLeave(lodElement);
            });

            // Measure the host slot for AUTO axes and write the size back to props.
            this._attachSizeObserver(nodeElement);
        },

        _attachSizeObserver(nodeElement) {
            // The host slot (.ui-node-slot) carries the applied size + clip and
            // the data-size-adapt stamp (see UINode._apply_size). An auto axis
            // has no inline size, so the slot hugs content and we report the
            // measured offset back into props; a manual axis is user-owned and
            // is skipped. Idempotent: disconnect-then-attach.
            const slot = nodeElement.querySelector('.ui-node-slot');
            if (!slot) return;
            const nodeId = nodeElement.getAttribute('data-node-id');
            if (!nodeId) return;
            if (slot.__hwSizeObs) slot.__hwSizeObs.disconnect();

            const emit = () => {
                if (window.__hwResizeDragging) return;      // a gadget drag owns the axis
                // Selection can grow the node (widgets appear) after the gadget
                // was fitted — keep the gadget hugging the slot's live size.
                if (this.resizeGadget.visible && this.resizeGadget.nodeId === nodeId) {
                    this._fitResizeGadget();
                }
                const mode = slot.getAttribute('data-size-adapt') || 'auto';
                const autoW = (mode === 'auto' || mode === 'manual_height');
                const autoH = (mode === 'auto' || mode === 'manual_width');
                const width = autoW ? slot.offsetWidth : null;
                const height = autoH ? slot.offsetHeight : null;
                if (width === null && height === null) return;

                // Instrumentation (read by the debug overlay): every observer
                // firing that produced a candidate measurement, before dedupe.
                // The gap between this and `queued` is what fix-2 suppresses.
                const stats = window.__hwMeasureStats;
                if (stats) stats.observed += 1;

                // Drop measurements the server already agrees with. The server
                // applies the same ~1px epsilon (VisualLayer.process_nodes_measured),
                // so anything inside it would be a no-op round-trip. Without this
                // the steady state churns a message per observer firing.
                const last = slot.__hwLastMeasure;
                if (last
                    && (width === null || Math.abs(width - last.width) <= 1.0)
                    && (height === null || Math.abs(height - last.height) <= 1.0)) {
                    return;
                }
                slot.__hwLastMeasure = { width, height };
                if (stats) stats.queued += 1;

                this._queueMeasurement(nodeId, width, height);
            };

            const obs = new ResizeObserver(emit);
            obs.observe(slot);
            slot.__hwSizeObs = obs;
        },

        /** Coalesce this frame's measurements into ONE server message.
         *
         *  Loading a large graph fires every node's ResizeObserver in the same
         *  layout pass. Emitting per node meant one websocket message (and one
         *  console.log) per node — a 2000-node graph wedged the browser and made
         *  graph switching impossible, since a remount re-attaches every observer.
         *  Batching makes the cost O(1 message per frame) instead of O(nodes).
         *
         *  Last write wins within a frame: a node measured twice before the
         *  flush only reports its final size.
         */
        _queueMeasurement(nodeId, width, height) {
            if (!this._pendingMeasurements) this._pendingMeasurements = new Map();
            this._pendingMeasurements.set(nodeId, { nodeId, width, height });
            if (this._measureFlushHandle !== null && this._measureFlushHandle !== undefined) return;
            this._measureFlushHandle = requestAnimationFrame(() => {
                this._measureFlushHandle = null;
                this._flushMeasurements();
            });
        },

        _flushMeasurements() {
            if (!this._pendingMeasurements || this._pendingMeasurements.size === 0) return;
            const measurements = Array.from(this._pendingMeasurements.values());
            this._pendingMeasurements.clear();
            // One batch == one websocket message. In steady state this should
            // stop climbing entirely; see the debug overlay's "measure" line.
            const stats = window.__hwMeasureStats;
            if (stats) { stats.batches += 1; stats.sent += measurements.length; }
            this.emitCanvasEvent(EventCreators.createNodesMeasured(measurements));
        },

        // =============================================================================
        // RESIZE GADGET (single-node, 8 handles, content space)
        // =============================================================================

        /** Return the node's [data-node-id] container and its .ui-node-slot child,
         *  or null if either is missing. Position lives on the container (left/top);
         *  applied size + clip live on the slot. */
        _resizeParts(nodeId) {
            const container = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (!container) return null;
            const slot = container.querySelector('.ui-node-slot');
            if (!slot) return null;
            return { container, slot };
        },

        _fitResizeGadget() {
            const ids = Array.from(this.selectionState.selectedNodes);
            if (ids.length !== 1) { this.resizeGadget.visible = false; return; }
            const nodeId = ids[0];
            const parts = this._resizeParts(nodeId);
            if (!parts) { this.resizeGadget.visible = false; return; }
            const { container, slot } = parts;
            // A tracked node holds its REAL size: the gadget is fit from layout
            // size, which the hover-magnify transform doesn't change — snap any
            // active magnify back (and _magnifySuppressedFor blocks new ones).
            const lod = container.querySelector('.zoom-pan-lod0');
            if (lod && lod._magnified) {
                if (lod._magnifyExitTimer) { clearTimeout(lod._magnifyExitTimer); lod._magnifyExitTimer = null; }
                this._clearMagnify(lod);
            }
            // Content-space position is the container's inline left/top (the same
            // space #node-container — and thus the gadget — lives in).
            const left = parseFloat(container.style.left) || 0;
            const top = parseFloat(container.style.top) || 0;
            this.resizeGadget = {
                visible: true, nodeId,
                left, top, width: slot.offsetWidth, height: slot.offsetHeight,
            };
        },

        onResizeGripDown(e, handle) {
            e.preventDefault();
            e.stopPropagation();
            const nodeId = this.resizeGadget.nodeId;
            const parts = this._resizeParts(nodeId);
            if (!parts) return;
            const { container, slot } = parts;
            window.__hwResizeDragging = true;

            const scale = this.zoomState.zoom || 1;
            const startX = e.clientX, startY = e.clientY;
            const startW = slot.offsetWidth, startH = slot.offsetHeight;
            const startLeft = parseFloat(container.style.left) || 0;
            const startTop = parseFloat(container.style.top) || 0;
            const movesX = handle.includes('left');
            const movesY = handle.includes('top');
            const affW = handle !== 'top' && handle !== 'bottom';
            const affH = handle !== 'left' && handle !== 'right';

            // Merge the dragged axis with any axis already manual, so a height
            // drag on a manual_width node yields 'manual' instead of silently
            // dropping the width lock. Stamp the merged mode immediately: the
            // card-fill CSS keys off data-size-adapt, and stamping only at
            // commit would leave the card clamped (max-w-sm) during the drag.
            const prevMode = slot.getAttribute('data-size-adapt') || 'auto';
            const manW = affW || prevMode === 'manual_width' || prevMode === 'manual';
            const manH = affH || prevMode === 'manual_height' || prevMode === 'manual';
            const size_adapt = (manW && manH) ? 'manual' : manW ? 'manual_width' : 'manual_height';
            slot.setAttribute('data-size-adapt', size_adapt);

            // The dragged size is the user's intended MINIMUM (see
            // UINode._apply_size) — the slot may refuse to go below its
            // content size. Track the intent separately from the gadget, which
            // always shows the slot's ACTUAL size (so a shrink drag visibly
            // "resists" at the content floor instead of detaching).
            let intentW = startW, intentH = startH;
            // Last actual slot size seen in onMove (the content floor when a
            // shrink is resisted). Compared to intent at commit to decide if an
            // axis hit its floor → return that axis to auto.
            let actualW = startW, actualH = startH;

            // Snap the DRAGGED EDGE to the same grid step a node drag uses
            // (gridSize / gridSubdivisions), so resize and drag obey one grid.
            // We snap the moving edge's position (fixedEdge ± size), then derive
            // the size from it — so the edge under the cursor lands on a grid
            // line whatever the node's prior alignment. Gated on its OWN flag
            // (snapScaleToGrid), independent of node-move snapping; off ⇒ raw px.
            // The fixed edges (right when dragging left, etc.):
            const fixedRight = startLeft + startW;   // used when movesX
            const fixedBottom = startTop + startH;   // used when movesY
            const subSz = this.snapScaleToGrid ? this.gridSize / this.gridSubdivisions : 0;
            const snap = (v) => subSz > 0 ? Math.round(v / subSz) * subSz : v;

            const onMove = (ev) => {
                const dx = (ev.clientX - startX) / scale;
                const dy = (ev.clientY - startY) / scale;
                let left = startLeft, top = startTop;
                if (affW) {
                    // No drag floor — clamp only to > 0 (keep positive). Snap the
                    // moving edge: the left edge when movesX, else the right edge.
                    if (movesX) {
                        const newLeft = snap(startLeft + dx);
                        intentW = Math.max(1, fixedRight - newLeft);
                    } else {
                        intentW = Math.max(1, snap(startLeft + startW + dx) - startLeft);
                    }
                }
                if (affH) {
                    if (movesY) {
                        const newTop = snap(startTop + dy);
                        intentH = Math.max(1, fixedBottom - newTop);
                    } else {
                        intentH = Math.max(1, snap(startTop + startH + dy) - startTop);
                    }
                }
                // Min-size on the slot (never width/height — content may need
                // more room and must expand the node, not get clipped).
                if (affW) { slot.style.minWidth = intentW + 'px'; slot.style.width = ''; }
                if (affH) { slot.style.minHeight = intentH + 'px'; slot.style.height = ''; }
                // Read back what the layout actually produced (content floor).
                actualW = slot.offsetWidth; actualH = slot.offsetHeight;
                // Pin the opposite edge using the ACTUAL size, so a resisted
                // shrink doesn't slide the node.
                if (movesX) left = startLeft + (startW - actualW);
                if (movesY) top = startTop + (startH - actualH);
                container.style.left = left + 'px';
                container.style.top = top + 'px';
                this.resizeGadget.left = left; this.resizeGadget.top = top;
                this.resizeGadget.width = actualW; this.resizeGadget.height = actualH;
                this._updateEdgesForNode(nodeId);
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove, true);
                document.removeEventListener('mouseup', onUp, true);
                window.__hwResizeDragging = false;

                // Per-axis floor detection: if the user dragged an axis below
                // its content floor, that axis returns to AUTO — the gadget was
                // "stuck". Measure the TRUE content floor by clearing the inline
                // min and reading the content-driven size (the running actualW
                // can equal intent while shrinking freely, so it can't tell
                // "shrank" from "stuck" on its own). Restore the drag min right
                // after so nothing visibly flickers before the commit restyles.
                //
                // Measure in the PRE-DRAG mode. The manual stamp above fires on
                // mousedown, and its CSS releases the card's min-w-64/max-w-sm
                // clamp immediately — so measuring after it reads the content's
                // unclamped size as "the floor" (one node: 384px clamped vs
                // 1337px unclamped, before any movement). Restoring prevMode
                // re-applies the clamp, giving the size the node can actually
                // return to. See .insights/feedback_css_containment_node_floor.md.
                const SLOP = 4;  // px — a hair below the floor shouldn't reset
                let floorW = actualW, floorH = actualH;
                if (affW) {
                    slot.setAttribute('data-size-adapt', prevMode);
                    slot.style.minWidth = '';
                    floorW = slot.offsetWidth;
                    slot.style.minWidth = intentW + 'px';
                    slot.setAttribute('data-size-adapt', size_adapt);
                }
                if (affH) {
                    slot.setAttribute('data-size-adapt', prevMode);
                    slot.style.minHeight = '';
                    floorH = slot.offsetHeight;
                    slot.style.minHeight = intentH + 'px';
                    slot.setAttribute('data-size-adapt', size_adapt);
                }
                const wHitFloor = affW && intentW < floorW - SLOP;
                const hHitFloor = affH && intentH < floorH - SLOP;
                const keepW = manW && !wHitFloor;
                const keepH = manH && !hHitFloor;
                const commitMode = (keepW && keepH) ? 'manual'
                                 : keepW ? 'manual_width'
                                 : keepH ? 'manual_height' : 'auto';
                // A reset axis leaves its prop untouched — the ResizeObserver
                // repopulates it from content within a frame (the existing
                // return-to-auto semantics). Send the intent for kept axes, the
                // content floor for reset axes.
                const width = keepW ? intentW : floorW;
                const height = keepH ? intentH : floorH;

                let posX = null, posY = null;
                if (movesX || movesY) {
                    posX = parseFloat(container.style.left) || startLeft;
                    posY = parseFloat(container.style.top) || startTop;
                }
                this.emitCanvasEvent(
                    EventCreators.createUserResizeEnd(nodeId, width, height, commitMode, posX, posY)
                );
            };
            document.addEventListener('mousemove', onMove, true);
            document.addEventListener('mouseup', onUp, true);
        },

        // ── Hover magnifier ───────────────────────────────────────────────────

        /** Linear, zoom-compensated magnify scale for the current zoom.
         *  Returns 1.0 (no magnify) at/above the cutoff zoom, rising to
         *  hoverScaleMax as zoom approaches 0. */
        _magnifyScaleForZoom() {
            const cutoff = this.hoverScaleCutoffZoom;
            const zoom = this.zoomState.zoom || 1;
            if (zoom >= cutoff) return 1.0;
            // t: 0 at the cutoff, 1 at (or below) the inner reference zoom.
            // Reference floor of 0.1 keeps the curve well-defined when cutoff is
            // small; clamp so t stays within [0, 1].
            const floor = Math.min(0.1, cutoff * 0.5);
            const span = cutoff - floor;
            const t = span > 0 ? Math.min(1, Math.max(0, (cutoff - zoom) / span)) : 1;
            return 1.0 + t * (this.hoverScaleMax - 1.0);
        },

        /** True if a magnify would be disruptive right now (mid gesture).
         *  Node-drag suppresses it (the node you're moving shouldn't jump in
         *  scale under the cursor). Edge-drag deliberately does NOT: magnifying
         *  the hovered target node makes it — and its pins — readable and easier
         *  to aim at while connecting from a zoomed-out overview. */
        _magnifySuppressed() {
            return this.dragState.isDragging;
        },

        /** True if THIS node must not magnify: the resize gadget tracks it.
         *  The gadget is fit from layout size (offsetWidth/Height), which a
         *  magnify transform doesn't change — a magnified tracked node would
         *  render larger than its gadget. A node under resize focus holds its
         *  real size. */
        _magnifySuppressedFor(lodElement) {
            if (!this.resizeGadget.visible) return false;
            const container = lodElement.closest('[data-node-id]');
            return !!container && container.dataset.nodeId === this.resizeGadget.nodeId;
        },

        _onNodeHoverEnter(lodElement) {
            // Mark the hovered card so LOD hover-persistence can re-admit its
            // hidden descendants (pan.vue). Deliberately a JS-set class rather
            // than a CSS `.zoom-pan-lod0:hover .zoom-pan-lod2` rule: a
            // descendant-of-:hover selector makes Blink track hover state
            // across every node's subtree, which turned each LOD crossing into
            // a ~37ms restyle on a 200-node graph (0.1ms without it).
            lodElement.classList.add('hw-lod-hover');

            // Clear any pending release so re-entering keeps it magnified.
            if (lodElement._magnifyExitTimer) {
                clearTimeout(lodElement._magnifyExitTimer);
                lodElement._magnifyExitTimer = null;
            }
            if (!this.hoverScaleEnabled) return;
            if (this._magnifySuppressed() || this._magnifySuppressedFor(lodElement)) return;
            // Already magnified (re-enter after a cancelled exit) — nothing to do.
            if (lodElement._magnified) return;

            const arm = () => {
                lodElement._magnifyEnterTimer = null;
                // Re-check on fire: pointer may have moved / a gesture may have
                // started during the dwell (e.g. the node got selected).
                if (!this.hoverScaleEnabled || this._magnifySuppressed()
                    || this._magnifySuppressedFor(lodElement)) return;
                const scale = this._magnifyScaleForZoom();
                if (scale <= 1.0) return;  // nothing to do at/above cutoff
                this._applyMagnify(lodElement, scale);
            };

            if (this.hoverEnterDelay > 0) {
                lodElement._magnifyEnterTimer = setTimeout(arm, this.hoverEnterDelay);
            } else {
                arm();
            }
        },

        _onNodeHoverLeave(lodElement) {
            lodElement.classList.remove('hw-lod-hover');

            // Cancel a pending magnify that never fired.
            if (lodElement._magnifyEnterTimer) {
                clearTimeout(lodElement._magnifyEnterTimer);
                lodElement._magnifyEnterTimer = null;
            }
            if (!lodElement._magnified) return;

            const release = () => {
                lodElement._magnifyExitTimer = null;
                this._clearMagnify(lodElement);
            };
            if (this.hoverExitDelay > 0) {
                lodElement._magnifyExitTimer = setTimeout(release, this.hoverExitDelay);
            } else {
                release();
            }
        },

        _applyMagnify(lodElement, scale) {
            lodElement._magnified = true;
            // Lift above neighbours so the magnified node isn't clipped by them.
            lodElement.style.zIndex = '1001';
            lodElement.style.position = 'relative';
            lodElement.style.transform = `scale(${scale})`;
        },

        _clearMagnify(lodElement) {
            lodElement._magnified = false;
            lodElement.style.transform = '';
            lodElement.style.zIndex = '';
            // Leave position alone — node-selected / other rules may rely on it;
            // resetting transform/zIndex is enough to undo the magnify.
        },

        /** Snap any magnified node back. Called when a gesture (drag / edge
         *  connect) starts, so magnify never interferes mid-operation. */
        _clearAllMagnified() {
            document.querySelectorAll('.zoom-pan-lod0').forEach((el) => {
                if (el._magnifyEnterTimer) { clearTimeout(el._magnifyEnterTimer); el._magnifyEnterTimer = null; }
                if (el._magnifyExitTimer) { clearTimeout(el._magnifyExitTimer); el._magnifyExitTimer = null; }
                if (el._magnified) this._clearMagnify(el);
            });
        },

        _setupZoomPanListener() {
            this.handleZoomPanUpdate = (event) => {
                const { zoom, panX, panY, containerId, isDragging } = event.detail;
                // Ignore events from sibling canvases' ZoomPanContainers —
                // otherwise panning another tab's canvas clobbers this
                // instance's zoomState, and pin coords compute against the
                // wrong zoom until the user pans here to overwrite it.
                if (this.zoomContainerId && containerId && containerId !== this.zoomContainerId) {
                    return;
                }
                this.zoomState = { zoom, panX, panY, isDragging };

                // Hide toolbar while panning (isDragging=true during mouse-drag pan).
                if (isDragging && !this._toolbarHiddenForGesture) {
                    this._toolbarHiddenForGesture = true;
                    this._emitSelectionBoundsHide();
                } else if (!isDragging && this._toolbarHiddenForGesture) {
                    this._toolbarHiddenForGesture = false;
                    this._emitSelectionBounds();
                }

                // Wheel-zoom and trackpad-pan fire zoom-pan-state with isDragging=false
                // on every frame, so they never trigger the drag gate above.
                // Use a short debounce: hide once on the LEADING edge of the burst,
                // restore 120 ms after the last event settles.
                // Guard: skip this path when the drag gate just fired (isDragging→false
                // restores the toolbar above; running this branch would re-hide it for 120 ms).
                else if (!isDragging && !this._toolbarHiddenForGesture) {
                    // Leading edge only: a live timer means we already hid the toolbar
                    // for this burst, so don't re-emit selectionBoundsHide every frame.
                    if (!this._zoomPanBoundsTimer) {
                        this._emitSelectionBoundsHide();
                    } else {
                        clearTimeout(this._zoomPanBoundsTimer);
                    }
                    this._zoomPanBoundsTimer = setTimeout(() => {
                        this._zoomPanBoundsTimer = null;
                        this._emitSelectionBounds();
                    }, 120);
                }
            };

            document.addEventListener('zoom-pan-state', this.handleZoomPanUpdate);
        },

        _cleanupEventListeners() {
            document.body.removeEventListener('mousedown', this.handleMouseDown, true);
            document.body.removeEventListener('mousemove', this.handleMouseMove, true);
            document.body.removeEventListener('mouseup', this.handleMouseUp, true);
            document.body.removeEventListener('keydown', this.handleKeyDown, true);
        },

        _cleanupZoomPanListener() {
            if (this.handleZoomPanUpdate) {
                document.removeEventListener('zoom-pan-state', this.handleZoomPanUpdate);
                this.handleZoomPanUpdate = null;
            }
        },

        _cleanupObservers() {
            // Per-slot size observers (see _attachSizeObserver). They would die
            // with their DOM nodes, but teardown reflow can fire them first —
            // disconnect explicitly so no measurement is queued mid-unmount.
            document.querySelectorAll('.ui-node-slot').forEach(slot => {
                if (slot.__hwSizeObs) {
                    slot.__hwSizeObs.disconnect();
                    slot.__hwSizeObs = null;
                }
                slot.__hwLastMeasure = null;
            });
            if (this.mutationObserver) {
                this.mutationObserver.disconnect();
                this.mutationObserver = null;
            }
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
                this.resizeObserver = null;
            }
            if (this._pendingNodeWatcher) {
                this._pendingNodeWatcher.disconnect();
                this._pendingNodeWatcher = null;
            }
        },

        // =============================================================================
        // UNIFIED EVENT SYSTEM
        // =============================================================================

        emitCanvasEvent(event) {
            if (typeof event === 'object' && event.event_type) {
                console.log(`🚀 Vue→Python Event: ${event.event_type}`, event.data);
                this.$emit('canvasEvent', event);
            } else {
                console.error('emitCanvasEvent now only accepts event objects from EventCreators helper methods');
            }
        },

        async _handleClipboardPasteRequest(data) {
            let text = "";
            try {
                text = await navigator.clipboard.readText();
            } catch (err) {
                // Permission denied / unavailable — emit empty text; the Python paste
                // handler falls back to its in-process mirror.
                console.warn("clipboard.readText() failed; emitting empty text (Python uses mirror)", err);
            }
            this.emitCanvasEvent(EventCreators.createUserPasteClipboard(data.canvasX, data.canvasY, text));
        },

        handleSyncEvent(syncEvent) {
            console.log(`🔄 Python→Vue Sync: ${syncEvent.event_type}`, syncEvent.data);
            
            const { event_type, data } = syncEvent;
            
            switch (event_type) {
                case GraphEvents.SyncCommands.SYNC_NODE_POSITION:
                    this._syncNodePosition(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGE_ADDITION:
                    this._syncEdgeAddition(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_NODE_REMOVAL:
                    this._syncNodeRemoval(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGE_REMOVAL:
                    this._syncEdgeRemoval(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_SELECTIONS:
                    this._syncSelections(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CANVAS_CLEAR:
                    this._syncCanvasClear();
                    break;
                case GraphEvents.SyncCommands.SYNC_NODE_REDRAW:
                    this._syncNodeRedraw(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGES_UPDATE:
                    this._syncEdgesUpdate(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGE_RECONNECT:
                    this._syncEdgeReconnect(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGE_CONNECT_RESUME:
                    this._syncEdgeConnectResume();
                    break;
                case GraphEvents.SyncCommands.SYNC_EDGE_CONNECT_CANCEL:
                    this._syncEdgeConnectCancel();
                    break;
                case GraphEvents.SyncCommands.SYNC_REQUEST_CLIPBOARD_PASTE:
                    this._handleClipboardPasteRequest(data);
                    break;
                default:
                    console.warn(`Unknown sync event: ${event_type}`);
            }
        },

        // Sync event handlers (keeping these as-is for backward compatibility)
        _syncNodePosition(data) {
            const { nodeId, position } = data;
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                this._updateEdgesForNode(nodeId);
                // Server-driven move (undo/redo, arrange, farmhand): keep the
                // resize gadget glued to the node it tracks.
                if (this.resizeGadget.visible && this.resizeGadget.nodeId === nodeId) {
                    this._fitResizeGadget();
                }
            }
        },

        _syncEdgeAddition(data) {
            const {
                edge_id,
                sourceNodeId,
                outletPinId,
                sinkNodeId,
                inletPinId,
                outletPinFallback,
                inletPinFallback,
                isValid = true,
                hasWarning = false,
                strokeColor = 'auto',
                strokeWidth = 2,
                strokeDasharray = '',
                opacity = 1.0
            } = data;

            // Check if connection already exists
            if (this.edgePaths.has(edge_id)) {
                // Update existing connection visual properties
                const edgeInfo = this.edgePaths.get(edge_id);
                
                edgeInfo.isValid = isValid;
                edgeInfo.hasWarning = hasWarning;
                edgeInfo.strokeColor = strokeColor;
                edgeInfo.strokeWidth = strokeWidth;
                edgeInfo.strokeDasharray = strokeDasharray;
                edgeInfo.opacity = opacity;
                
                // Trigger visual update
                this.$nextTick(() => {
                    this._updateEdge(edge_id);
                });
                
                console.log(
                    `🔗 Vue updated connection: ${edge_id} -> ` +
                    `valid=${isValid}, warning=${hasWarning}, color=${strokeColor}`
                );
                return;
            }

            // Create new connection with visual properties
            const result = this._createEdge(
                edge_id,
                sourceNodeId,
                outletPinId,
                sinkNodeId,
                inletPinId,
                outletPinFallback,
                inletPinFallback,
                isValid,
                hasWarning,
                strokeColor,
                strokeWidth,
                strokeDasharray,
                opacity
            );
            
            if (result.success) {
                console.log('🔗 Vue ✅ Edge added via sync:', edge_id);
            } else {
                console.error('🔗 Vue ❌ Failed to add connection via sync:', edge_id);
            }
        },

        _syncNodeRemoval(data) {
            const { nodeId } = data;
            let selectionChanged = false;

            if (this.selectionState.selectedNodes.has(nodeId)) {
                this.selectionState.selectedNodes.delete(nodeId);
                selectionChanged = true;
            }

            const active = this.selectionState.activeElement;
            if (active && active.kind === 'node' && active.id === nodeId) {
                this.selectionState.activeElement = null;
                selectionChanged = true;
            }

            if (selectionChanged) {
                this._emitSelectionBounds();
            }

            console.log('🗑️ Vue node removed via sync:', nodeId);
        },

        _syncEdgeRemoval(data) {
            const { edge_id } = data;
            const success = this._removeEdge(edge_id);
            
            if (success) {
                console.log('🔗 Vue ✅ Edge removed via sync:', edge_id);
            } else {
                console.error('🔗 Vue ❌ Failed to remove connection via sync:', edge_id);
            }
        },

        _syncSelections(data) {
            // SyncSelectionsEvent serializes the edge list under `edges`; alias
            // it to `connections` for the rest of this handler.
            const { nodes, edges: connections } = data;

            // Get current selection sets
            const currentNodes = this.selectionState.selectedNodes;
            const currentEdges = this.selectionState.selectedEdges;
            
            // Convert arrays to sets for comparison
            const newNodes = new Set(nodes || []);
            const newEdges = new Set(connections || []);
            
            // only iterate connections if there's a change
            if (!this._setsAreEqual(currentNodes, newNodes)) {
                // Find nodes to deselect (in current but not in new)
                currentNodes.forEach(nodeId => {
                    if (!newNodes.has(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, false);
                        this._scheduleEdgeUpdates(nodeId, null, 300);
                    }
                });
                
                // Find nodes to select (in new but not in current)
                newNodes.forEach(nodeId => {
                    if (!currentNodes.has(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, true);
                        this._scheduleEdgeUpdates(nodeId, null, 300);
                    }
                });
                // Update internal state to match new selection
                this.selectionState.selectedNodes = newNodes;
            }
            
            // only iterate connections if there's a change
            if (!this._setsAreEqual(currentEdges, newEdges)) {
                // Find connections to deselect (in current but not in new)
                currentEdges.forEach(edge_id => {
                    if (!newEdges.has(edge_id)) {
                        this._updateEdgeVisualSelection(edge_id, false);
                    }
                });
                
                // Find connections to select (in new but not in current)
                newEdges.forEach(edge_id => {
                    if (!currentEdges.has(edge_id)) {
                        this._updateEdgeVisualSelection(edge_id, true);
                    }
                });
                // Update internal state to match new selection
                this.selectionState.selectedEdges = newEdges;
            }

            // Reconcile the active primary (programmatic paths e.g. paste send
            // {kind:'', id:''} to clear it).
            const active = data.active || { kind: '', id: '' };
            this._setActive(active.kind, active.id);

            // Show the resize gadget only for a single-node selection.
            this._fitResizeGadget();

            console.log(`🔄 Synced selections: ${(nodes || []).length} nodes, ${(connections || []).length} connections`);
        },

        _syncCanvasClear() {
            // ENHANCED: Use edgeInfo for cleanup
            this.edgePaths.forEach((edgeInfo, edge_id) => {
                edgeInfo.path.remove();
                const hitArea = document.getElementById(edge_id + '_hitarea');
                if (hitArea) hitArea.remove();
                const gradient = document.getElementById(`gradient_${edge_id}`);
                if (gradient) gradient.remove();
            });
            
            this.edgePaths.clear();
            const svg = this.$refs.svg;
            const paths = svg.querySelectorAll('path');
            paths.forEach(path => path.remove());
            
            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedEdges.clear();
        },

        _syncNodeRedraw(data) {
            const { nodeId } = data;
            this._addNodeObserver(nodeId);
            // The redraw replaced this node's pin elements: same ids, but new
            // positions and possibly new direction vectors. Every edge touching
            // the node is now describing DOM that no longer exists, so refresh
            // them here rather than waiting for the next incidental trigger
            // (a hover, a drag) to do it. _addNodeObserver parks the node when
            // the canvas is detached and the pending watcher redraws its edges
            // on arrival, so this is skipped for pending nodes — _updateEdge
            // bails on them anyway.
            if (!this._pendingNodeIds.has(nodeId)) {
                this._scheduleEdgeUpdates(nodeId);
            }
            // A redraw may have changed the node's measured size; refit the
            // gadget if it's tracking this node.
            if (this.resizeGadget.visible && this.resizeGadget.nodeId === nodeId) {
                this._fitResizeGadget();
            }
        },

        _syncEdgesUpdate(data) {
            const { nodeId } = data;
            this._updateEdgesForNode(nodeId);
        },

        _syncEdgeReconnect(data) {
            const { edge_id, anchorNodeId, anchorPinId } = data;
            // Remove the edge visual, then enter active connection mode from the anchor pin.
            this._syncEdgeRemoval({ edge_id });
            const pinUUID = this._buildPinUUID(anchorNodeId, anchorPinId);
            const pin = document.getElementById(pinUUID);
            if (pin) {
                this._enterActiveEdge(pin);
            } else {
                console.warn(`[syncEdgeReconnect] Anchor pin not found: ${pinUUID}`);
            }
        },

        _syncEdgeConnectResume() {
            if (this.edgeDrag.mode !== 'paused') return;
            // The anchor node may have been rebuilt while paused (context menu
            // open); resolve a live element before re-entering active mode.
            this._enterActiveEdge(this._resolveAnchorPin());
        },

        _syncEdgeConnectCancel() {
            if (this.edgeDrag.mode !== 'idle') {
                this._returnToIdleEdge();
            }
        },

        _setSelectionState(selectedNodes, selectedEdges) {
            this._clearSelection();
            selectedNodes.forEach(nodeId => this._selectElement('node', nodeId, true));
            selectedEdges.forEach(edge_id => this._selectElement('edge', edge_id, true));
        },

        // =============================================================================
        // UNIFIED EVENT HANDLERS
        // =============================================================================


        handleMouseDown(event) {
            if (event.button === 2) return; // Skip right-click
            if (event.button === 1) return; // Skip middle-click — handled by pan.vue

            const target = event.target;

            // 0. Only handle events that originate within this canvas element.
            //    The listener is on document.body (capture), so clicks anywhere on
            //    the page reach this handler — e.g. the minimap, properties panel, etc.
            //    Without this guard those clicks fall through to _startBoxSelection
            //    which calls stopPropagation(), preventing the target element from
            //    ever receiving the event.
            if (!this.$refs.container || !this.$refs.container.contains(target)) {
                return;
            }

            // Invalidate cached container rect at the start of every gesture
            this._cachedNodeContainerRect = null;

            // 0b. Skip resize-gadget grips — onResizeGripDown owns the gesture.
            //     Grips overlap the node's drag area (negative offsets), and the
            //     body capture listener runs before the grip's bubble-phase
            //     @mousedown, so this guard (not stopPropagation) is what keeps a
            //     grip drag from also starting a node move / box-select.
            if (target.closest('.hw-resize-grip')) {
                return;
            }

            // 1. Skip if clicking inside a popup - let popup handle it.
            //    This must run before active-mode so popup interactions
            //    never cancel a paused or active connection drag.
            const popupElement = target.closest(
                '[data-popup-container="true"], ' +
                '[data-popup-drag-handle="true"], ' +
                '[data-popup="true"], ' +
                '.popup-card, ' +
                '.popup-content-area, ' +
                '.popup-title-bar'
            );
            if (popupElement) {
                return;
            }

            // 2. Active connection mode: this click commits or cancels
            if (this.edgeDrag.mode === 'active') {
                event.preventDefault();
                event.stopPropagation();
                const pin = target.closest('.connection-pin');
                if (pin && pin.dataset.pinFlowType !== 'ghost') {
                    this._commitConnection(pin);
                } else if (!pin && this.edgeDrag.nearestCompatiblePin) {
                    // Clicked empty canvas but a suggestion is active — commit to it
                    this._commitConnection(null);
                } else {
                    this._returnToIdleEdge();
                }
                return;
            }

            // 3. Check for connection pin — start a new connection drag
            const pin = target.closest('.connection-pin');
            if (pin) {
                if (pin.dataset.pinFlowType === 'ghost') return;
                event.preventDefault();
                event.stopPropagation();
                this._enterActiveEdge(pin);
                return;
            }

            const clickTime = Date.now();
            this.selectionState.lastClickTime = clickTime;

            // 4. Check for interactive widgets (but NOT drag handles)
            if (this._isInteractiveWidgetElement(target)) {
                return;
            }

            // 5. Check for elements that can be dragged (nodes)
            const draggableElement = this._findDraggableElement(target);
            if (draggableElement) {
                this._startUnifiedDrag(event, draggableElement);
                return;
            }

            // 6. Start box selection on empty canvas
            this._startBoxSelection(event);
        },

        handleMouseMove(e) {
            this.edgeDrag.lastMousePos = { x: e.clientX, y: e.clientY };

            if (this.boxSelectionState.isActive) {
                this._updateBoxSelection(e);
                return;
            }

            if (this.edgeDrag.mode === 'active' && this.edgeDrag.previewPath) {
                this._handleEdgeDragMove(e);
                return;
            }

            if (this.dragState.isDragging) {
                this._handleUnifiedDragMove(e);
                return;
            }
        },

        handleMouseUp(e) {
            // Invalidate cached container rect at gesture end
            this._cachedNodeContainerRect = null;

            if (this.boxSelectionState.isActive) {
                this._endBoxSelection(e);
                return;
            }

            if (this.dragState.isDragging) {
                this._handleUnifiedDragEnd(e);
                return;
            }
        },

        handleKeyDown(e) {
            if (e.key === 'Escape' && this.edgeDrag.mode !== 'idle') {
                this._returnToIdleEdge();
            }
        },

        // =============================================================================
        // CONTEXT MENU & REMOVAL SYSTEM
        // =============================================================================

        handleCanvasClick(event) {
            // All click handling is done in handleMouseDown/Up
            return;
        },

        handleContextMenu(event) {
            event.preventDefault();

            const clientX = event.clientX;
            const clientY = event.clientY;
            const target = event.target;


            // Check for port-scope context menu (data-hw-port-menu-focus-id)
            // port_id is taken from data-port-id on the element, falling back to data-pin-id.
            // node_id is resolved by walking up to the nearest [data-node-id] ancestor.
            const portMenuEl = target.closest('[data-hw-port-menu-focus-id]');
            if (portMenuEl) {
                const scope = portMenuEl.getAttribute('data-hw-port-menu-focus-id');
                const nodeAncestor = portMenuEl.closest('[data-node-id]');
                const nodeId = nodeAncestor ? nodeAncestor.dataset.nodeId : '';
                const portId = portMenuEl.dataset.portId || portMenuEl.dataset.pinId
                    || (portMenuEl.closest('[data-port-id]') || {}).dataset?.portId
                    || (portMenuEl.closest('[data-pin-id]') || {}).dataset?.pinId
                    || '';
                if (scope && nodeId && portId) {
                    const canvasCoords = this._transformScreenToSVG(clientX, clientY);
                    this.emitCanvasEvent(EventCreators.createContextMenuPort(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, nodeId, portId, scope
                    ));
                    return;
                }
            }

            // Check for custom-scope context menu button (data-hw-custom-menu-focus-id)
            // These are skin-rendered elements that declare their own panel scope.
            // node_id is resolved by walking up to the nearest [data-node-id] ancestor.
            const customMenuEl = target.closest('[data-hw-custom-menu-focus-id]');
            if (customMenuEl) {
                const scope = customMenuEl.getAttribute('data-hw-custom-menu-focus-id');
                const nodeAncestor = customMenuEl.closest('[data-node-id]');
                const nodeId = nodeAncestor ? nodeAncestor.dataset.nodeId : '';
                if (scope && nodeId) {
                    const canvasCoords = this._transformScreenToSVG(clientX, clientY);
                    this.emitCanvasEvent(EventCreators.createContextMenuCustom(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, nodeId, scope
                    ));
                    return;
                }
            }

            // Check for node
            const nodeElement = target.closest('[data-node-id]');
            
            // Check for connection
            let edgeElement = null;
            let edge_id = null;

            if (target.tagName === 'path' && target.getAttribute('data-edge-id')) {
                edge_id = target.getAttribute('data-edge-id');
                edgeElement = target;
            } else {
                // Always query the SVG ref directly — target may be the canvas div
                // itself when the click misses all path elements.
                const svg = this.$refs.svg;
                if (svg) {
                    const paths = svg.querySelectorAll('path[data-edge-id]');
                    const clickPoint = { x: clientX, y: clientY };
                    for (const path of paths) {
                        if (this._isPointNearStroke(path, clickPoint)) {
                            edgeElement = path;
                            edge_id = path.getAttribute('data-edge-id');
                            break;
                        }
                    }
                }
            }

            const canvasCoords = this._transformScreenToSVG(clientX, clientY);

            if (nodeElement) {
                const nodeId = nodeElement.dataset.nodeId;
                // Replace-then-act: if the right-clicked node is outside the
                // current selection, replace the selection with just this node
                // and tell Python before opening the menu. If it is already in
                // the selection (incl. a lone selected node), leave selection
                // intact. Either way the menu is always the unified selection
                // menu — there is no separate single-node menu.
                if (!this.selectionState.selectedNodes.has(nodeId)) {
                    this._setSelectionState([nodeId], []);
                    this.emitCanvasEvent(EventCreators.createSelectionChanged(
                        [nodeId], []
                    ));
                }
                this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                    clientX, clientY, canvasCoords.x, canvasCoords.y,
                    Array.from(this.selectionState.selectedNodes),
                    Array.from(this.selectionState.selectedEdges)
                ));
            } else if (edgeElement && edge_id) {
                const isEdgeSelected = this.selectionState.selectedEdges.has(edge_id);
                const hasMultipleSelected = this.selectionState.selectedNodes.size > 0 || this.selectionState.selectedEdges.size > 1;
                
                if (isEdgeSelected && hasMultipleSelected) {
                    this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                        clientX, clientY, canvasCoords.x, canvasCoords.y,
                        Array.from(this.selectionState.selectedNodes),
                        Array.from(this.selectionState.selectedEdges)
                    ));
                } else {
                    // Determine which end of the edge was closer to the click point.
                    const edgeInfo = this.edgePaths.get(edge_id);
                    let atSinkEnd = false;
                    if (edgeInfo) {
                        const outletPin = document.getElementById(edgeInfo.outletPinUUID);
                        const inletPin  = document.getElementById(edgeInfo.inletPinUUID);
                        if (outletPin && inletPin) {
                            const op = this._getPinPosition(outletPin);
                            const ip = this._getPinPosition(inletPin);
                            const dOut = (op.x - canvasCoords.x) ** 2 + (op.y - canvasCoords.y) ** 2;
                            const dIn  = (ip.x - canvasCoords.x) ** 2 + (ip.y - canvasCoords.y) ** 2;
                            atSinkEnd = dIn < dOut;
                        }
                    }
                    this.emitCanvasEvent(EventCreators.createContextMenuEdge(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, edge_id, atSinkEnd
                    ));
                }
            } else {

                // Snapshot pending connection before pausing drag (used for canvas menu below).
                let pendingPinId = '', pendingNodeId = '', pendingPinDir = '',
                    pendingFlowType = '', pendingDataType = '';
                if (this.edgeDrag.mode === 'active' && this.edgeDrag.anchorPin) {
                    const sp = this.edgeDrag.anchorPin.dataset;
                    pendingPinId   = sp.pinId       || '';
                    pendingNodeId  = sp.nodeId      || '';
                    pendingPinDir  = sp.pinDir      || '';
                    pendingFlowType = sp.pinFlowType || '';
                    pendingDataType = sp.pinDataType || '';
                    this._enterPausedEdge();
                }

                this.emitCanvasEvent(EventCreators.createContextMenuCanvas(
                    clientX, clientY, canvasCoords.x, canvasCoords.y,
                    pendingPinId, pendingNodeId, pendingPinDir, pendingFlowType, pendingDataType
                ));
            }
        },

        /**
         * True if `point` (screen coords) is within `tolerance` pixels of the
         * actual path stroke. Uses SVGPathElement.getPointAtLength() to sample
         * the curve at fixed intervals — far more accurate than bounding-box
         * testing for curved bezier edges.
         */
        _isPointNearStroke(pathElement, point, tolerance = 8) {
            try {
                const totalLength = pathElement.getTotalLength();
                if (totalLength === 0) return false;
                const steps = Math.max(20, Math.floor(totalLength / 10));
                for (let i = 0; i <= steps; i++) {
                    const p = pathElement.getPointAtLength((i / steps) * totalLength);
                    // getPointAtLength returns SVG user-space coords; convert to screen
                    const svgEl = pathElement.ownerSVGElement;
                    const pt = svgEl.createSVGPoint();
                    pt.x = p.x;
                    pt.y = p.y;
                    const screen = pt.matrixTransform(svgEl.getScreenCTM());
                    const dx = screen.x - point.x;
                    const dy = screen.y - point.y;
                    if (dx * dx + dy * dy <= tolerance * tolerance) return true;
                }
                return false;
            } catch (e) {
                console.warn('Error checking point near stroke:', e);
                return false;
            }
        },

        _getSelectedElementsForRemoval() {
            const elements = [];
            
            // Add selected nodes
            this.selectionState.selectedNodes.forEach(nodeId => {
                elements.push({ type: 'node', id: nodeId });
            });
            
            // Add selected connections
            this.selectionState.selectedEdges.forEach(edge_id => {
                elements.push({ type: 'edge', id: edge_id });
            });
            
            return elements;
        },

        // =============================================================================
        // UNIFIED DRAG SYSTEM
        // =============================================================================

        _findDraggableElement(target) {
            // Check for node
            const nodeElement = target.closest('[data-node-id]');
            if (nodeElement && !target.closest('.connection-pin')) {
                return {
                    type: 'node',
                    id: nodeElement.dataset.nodeId,
                    element: nodeElement
                };
            }

            // Check for connection
            const edgeElement = target.closest('path[data-edge-id]');
            if (edgeElement) {
                return {
                    type: 'edge',
                    id: edgeElement.getAttribute('data-edge-id'),
                    element: edgeElement
                };
            }

            return null;
        },

        _startUnifiedDrag(e, draggedElement) {
            e.preventDefault();
            e.stopPropagation();

            console.log('Starting unified drag for:', draggedElement.type, draggedElement.id);

            this.dragState.isDragging = true;
            this._emitSelectionBoundsHide();
            this.dragState.startMousePos = { x: e.clientX, y: e.clientY };
            this.dragState.hasActuallyMoved = false;

            // Store mouse down event for selection handling
            this.dragState.mouseDownEvent = {
                shiftKey: e.shiftKey,
                elementType: draggedElement.type,
                elementId: draggedElement.id
            };

            // Determine what elements to drag
            this.dragState.draggedElements = this._getDraggedElements(draggedElement, e.shiftKey);

            // Store initial positions for all dragged elements.
            // If snap is on, round to the nearest sub-grid point so any
            // pre-existing misalignment is absorbed once at drag start.
            const subSize = this.snapToGrid ? this.gridSize / this.gridSubdivisions : 0;
            const snapPos = (v) => subSize > 0 ? Math.round(v / subSize) * subSize : v;
            this.dragState.startPositions.clear();
            this.dragState.draggedElements.forEach(element => {
                if (element.type === 'node') {
                    const nodeElement = element.element;
                    const currentLeft = parseInt(nodeElement.style.left) || 0;
                    const currentTop = parseInt(nodeElement.style.top) || 0;
                    this.dragState.startPositions.set(element.id, {
                        x: snapPos(currentLeft),
                        y: snapPos(currentTop),
                    });
                }
            });

            // Calculate drag offset for the primary element
            if (draggedElement.type === 'node') {
                const nodePos = this.dragState.startPositions.get(draggedElement.id);
                this.dragState.dragOffset = {
                    x: e.clientX - nodePos.x,
                    y: e.clientY - nodePos.y
                };
            }
        },

        _getDraggedElements(primaryElement, isShiftClick) {
            const elements = [];

            if (primaryElement.type === 'node') {
                const nodeId = primaryElement.id;
                const isNodeSelected = this.selectionState.selectedNodes.has(nodeId);
                const hasMultipleNodesSelected = this.selectionState.selectedNodes.size > 1;

                if (isNodeSelected && hasMultipleNodesSelected && !isShiftClick) {
                    // Drag all selected nodes
                    this.selectionState.selectedNodes.forEach(selectedNodeId => {
                        const nodeElement = document.querySelector(`[data-node-id="${selectedNodeId}"]`);
                        if (nodeElement) {
                            elements.push({
                                type: 'node',
                                id: selectedNodeId,
                                element: nodeElement
                            });
                        }
                    });
                } else {
                    // Drag only this node
                    elements.push(primaryElement);
                }
            }
            // Note: Edges can't be dragged, so we only handle nodes

            return elements;
        },

        _handleUnifiedDragMove(e) {
            // Calculate mouse movement
            const mouseDeltaX = e.clientX - this.dragState.startMousePos.x;
            const mouseDeltaY = e.clientY - this.dragState.startMousePos.y;
            const distance = Math.sqrt(mouseDeltaX * mouseDeltaX + mouseDeltaY * mouseDeltaY);

            if (!this.dragState.hasActuallyMoved && distance > this.dragState.dragThreshold) {
                this.dragState.hasActuallyMoved = true;

                // A confirmed drag (not a plain click) moves pins, so clear any
                // magnify now. Doing this here rather than on mousedown means a
                // plain click leaves the hovered node magnified — clicking a
                // magnified node no longer shrinks it permanently.
                this._clearAllMagnified();

                // Emit unified drag start event
                this.emitCanvasEvent(EventCreators.createUserDragStart(
                    this._extractNodeIds(this.dragState.draggedElements)
                ));

                // Add visual feedback
                this.dragState.draggedElements.forEach(element => {
                    if (element.type === 'node') {
                        element.element.style.cursor = 'grabbing';
                        element.element.style.zIndex = '1000';
                        element.element.classList.add('dragging-node');
                    }
                });
            }

            if (!this.dragState.hasActuallyMoved) return;

            // Apply movement to all dragged elements
            const zoomFactor = this.zoomState.zoom || 1;
            const canvasDeltaX = mouseDeltaX / zoomFactor;
            const canvasDeltaY = mouseDeltaY / zoomFactor;
            const subSz = this.snapToGrid ? this.gridSize / this.gridSubdivisions : 0;
            const snap = (v) => subSz > 0 ? Math.round(v / subSz) * subSz : v;

            this.dragState.draggedElements.forEach(element => {
                if (element.type === 'node') {
                    const startPos = this.dragState.startPositions.get(element.id);
                    if (startPos) {
                        const newX = Math.max(0, Math.min(snap(startPos.x + canvasDeltaX), this.canvasWidth - 100));
                        const newY = Math.max(0, Math.min(snap(startPos.y + canvasDeltaY), this.canvasHeight - 100));

                        element.element.style.left = `${newX}px`;
                        element.element.style.top = `${newY}px`;
                        this._updateEdgesForNode(element.id);
                        // Keep the resize gadget glued to the node it tracks
                        // (the drag writes style directly — no observer fires).
                        if (this.resizeGadget.visible && this.resizeGadget.nodeId === element.id) {
                            this._fitResizeGadget();
                        }
                    }
                }
            });
        },

        _extractNodeIds(draggedElements) {
            return draggedElements
                .filter(element => element.type === 'node')
                .map(element => element.id);
        },

        _handleUnifiedDragEnd(e) {
            console.log('Ending unified drag, hasActuallyMoved:', this.dragState.hasActuallyMoved);

            if (this.dragState.hasActuallyMoved) {
                // Remove visual feedback
                this.dragState.draggedElements.forEach(element => {
                    if (element.type === 'node') {
                        element.element.style.cursor = 'grab';
                        element.element.style.zIndex = '100';
                        element.element.classList.remove('dragging-node');
                    }
                });

                // Emit unified drag update with absolute snapped positions.
                const positions = {};
                this.dragState.draggedElements.forEach(element => {
                    if (element.type === 'node') {
                        positions[element.id] = {
                            x: parseFloat(element.element.style.left) || 0,
                            y: parseFloat(element.element.style.top)  || 0,
                        };
                    }
                });
                this.emitCanvasEvent(EventCreators.createUserDragUpdate(positions));

                // Emit unified drag end event
                this.emitCanvasEvent(EventCreators.createUserDragEnd(
                    this._extractNodeIds(this.dragState.draggedElements)
                ));
            } else {
                // This was a click - handle selection
                if (this.dragState.mouseDownEvent) {
                    this._handleElementSelection(
                        this.dragState.mouseDownEvent.shiftKey,
                        this.dragState.mouseDownEvent.elementType,
                        this.dragState.mouseDownEvent.elementId
                    );
                }
            }

            // Reset drag state
            this.dragState.isDragging = false;
            // Only re-emit bounds after a real drag (click path already emits via
            // _handleElementSelection → _emitSelectionChanged → _emitSelectionBounds).
            if (this.dragState.hasActuallyMoved) {
                this._emitSelectionBounds();
            }
            this.dragState.draggedElements = [];
            this.dragState.startMousePos = { x: 0, y: 0 };
            this.dragState.startPositions.clear();
            this.dragState.dragOffset = { x: 0, y: 0 };
            this.dragState.hasActuallyMoved = false;
            this.dragState.mouseDownEvent = null;
        },

        _serializeDraggedElements(elements) {
            return elements.map(element => ({
                type: element.type,
                id: element.id
            }));
        },

        // =============================================================================
        // UNIFIED SELECTION SYSTEM
        // =============================================================================

        _setActive(kind, id) {
            // Clear the previous active element's highlight (could be either kind).
            const prev = this.selectionState.activeElement;
            if (prev) {
                if (prev.kind === 'node') this._updateNodeVisualActive(prev.id, false);
                else if (prev.kind === 'edge') this._updateEdgeVisualActive(prev.id, false);
            }
            if (kind && id) {
                this.selectionState.activeElement = { kind, id };
                if (kind === 'node') this._updateNodeVisualActive(id, true);
                else if (kind === 'edge') this._updateEdgeVisualActive(id, true);
            } else {
                this.selectionState.activeElement = null;
            }
        },

        _handleElementSelection(isShiftClick, elementType, elementId) {
            console.log(`Element clicked: ${elementType}:${elementId}, shift: ${isShiftClick}`);

            const active = this.selectionState.activeElement;
            const isActive = active && active.kind === elementType && active.id === elementId;
            const isSelected = this._isElementSelected(elementType, elementId);

            if (isShiftClick) {
                if (isActive) {
                    // Shift-click the active element -> deselect it; active -> none.
                    this._deSelectElement(elementType, elementId);
                    this._setActive('', '');
                } else if (isSelected) {
                    // Selected but not active -> promote (selection unchanged).
                    this._setActive(elementType, elementId);
                } else {
                    // Not selected -> add and make active.
                    this._selectElement(elementType, elementId, true);
                    this._setActive(elementType, elementId);
                }
            } else {
                // Plain click: replace selection with this one element; it is active.
                this._clearSelection();
                this._selectElement(elementType, elementId, false);
                this._setActive(elementType, elementId);
            }

            this._emitSelectionChanged();
        },

        _selectElement(elementType, elementId, multiSelect = false) {
            if (!multiSelect) {
                this._clearSelection();
            }

            if (elementType === 'node') {
                this.selectionState.selectedNodes.add(elementId);
                this._updateNodeVisualSelection(elementId, true);
                this._scheduleEdgeUpdates(elementId, null, 300);
            } else if (elementType === 'edge') {
                this.selectionState.selectedEdges.add(elementId);
                this._updateEdgeVisualSelection(elementId, true);
            }

            console.log(`🎯 Selected ${elementType}: ${elementId}`);
        },

        _deSelectElement(elementType, elementId) {
            if (elementType === 'node') {
                this.selectionState.selectedNodes.delete(elementId);
                this._updateNodeVisualSelection(elementId, false);
                this._scheduleEdgeUpdates(elementId, null, 300);
            } else if (elementType === 'edge') {
                this.selectionState.selectedEdges.delete(elementId);
                this._updateEdgeVisualSelection(elementId, false);
            }

            console.log(`🎯 Deselected ${elementType}: ${elementId}`);
        },

        _isElementSelected(elementType, elementId) {
            if (elementType === 'node') {
                return this.selectionState.selectedNodes.has(elementId);
            } else if (elementType === 'edge') {
                return this.selectionState.selectedEdges.has(elementId);
            }
            return false;
        },

        _clearSelection() {
            const previouslySelectedNodes = Array.from(this.selectionState.selectedNodes);

            this.selectionState.selectedNodes.forEach(nodeId => {
                this._updateNodeVisualSelection(nodeId, false);
            });

            this.selectionState.selectedEdges.forEach(edge_id => {
                this._updateEdgeVisualSelection(edge_id, false);
            });

            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedEdges.clear();

            previouslySelectedNodes.forEach(nodeId => {
                this._scheduleEdgeUpdates(nodeId, null, 300);
            });

            // Clear the active primary too.
            if (this.selectionState.activeElement) {
                const a = this.selectionState.activeElement;
                if (a.kind === 'node') this._updateNodeVisualActive(a.id, false);
                else if (a.kind === 'edge') this._updateEdgeVisualActive(a.id, false);
                this.selectionState.activeElement = null;
            }

            console.log('🎯 Cleared all selections');
        },

        _emitSelectionChanged() {
            const a = this.selectionState.activeElement;
            const activeNodeId = a && a.kind === 'node' ? a.id : '';
            const activeEdgeId = a && a.kind === 'edge' ? a.id : '';
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedEdges),
                activeNodeId,
                activeEdgeId
            ));
            this._emitSelectionBounds();
            // Local (interactive) selection path — refit the resize gadget. The
            // programmatic path refits from _syncSelections. The gadget's own
            // "exactly one node" guard keeps this correct for any selection size.
            this._fitResizeGadget();
        },

        /** The visible viewport rect of the ZoomPanContainer (overflow:hidden),
         *  which is the true clip boundary for the canvas. Falls back to null
         *  if the zoom container ID is not set or the element is not found. */
        _getViewportRect() {
            if (!this.zoomContainerId) return null;
            const el = document.getElementById(this.zoomContainerId);
            return el ? el.getBoundingClientRect() : null;
        },

        /** Screen-space bounding box (CSS px, viewport-relative) of all
         *  currently selected nodes. Returns null if nothing selected or no
         *  rects resolvable. Edges-only selections fall back to null (toolbar hides). */
        _computeSelectionScreenBounds() {
            const ids = Array.from(this.selectionState.selectedNodes);
            if (ids.length === 0) return null;

            let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
            for (const nodeId of ids) {
                const el = this.$refs.nodeContainer
                    ? this.$refs.nodeContainer.querySelector(`[data-node-id="${nodeId}"]`)
                    : null;
                if (!el) continue;
                const r = el.getBoundingClientRect();
                if (r.left < left) left = r.left;
                if (r.top < top) top = r.top;
                if (r.right > right) right = r.right;
                if (r.bottom > bottom) bottom = r.bottom;
            }
            if (left === Infinity) return null;

            // Hide if the selection is entirely outside the visible viewport.
            const v = this._getViewportRect();
            if (v) {
                const intersects = left < v.right && right > v.left
                    && top < v.bottom && bottom > v.top;
                if (!intersects) return null;
            }

            return { left, top, right, bottom };
        },

        _emitSelectionBounds() {
            const b = this._computeSelectionScreenBounds();
            if (!b) {
                this.emitCanvasEvent(EventCreators.createSelectionBoundsHide());
                return;
            }

            // Hide if the toolbar's anchor point would land outside the viewport.
            // Mirrors the Python formula: center_x=(l+r)/2, pos_y=max(0,top-12-44).
            // Pure geometry, no Python round-trip.
            const v = this._getViewportRect();
            if (v) {
                const toolbarX = (b.left + b.right) / 2;
                const toolbarY = Math.max(0, b.top - 12 - 44);
                if (toolbarX < v.left || toolbarX > v.right
                        || toolbarY < v.top || toolbarY > v.bottom) {
                    this.emitCanvasEvent(EventCreators.createSelectionBoundsHide());
                    return;
                }
            }

            this.emitCanvasEvent(EventCreators.createSelectionBounds(
                b.left, b.top, b.right, b.bottom
            ));
        },

        _emitSelectionBoundsHide() {
            this.emitCanvasEvent(EventCreators.createSelectionBoundsHide());
        },

        // =============================================================================
        // BOX SELECTION SYSTEM
        // =============================================================================

        _startBoxSelection(e) {
            console.log('🔲 Starting box selection');
            e.preventDefault();
            e.stopPropagation();

            const canvasPos = this._transformScreenToCanvas(e.clientX, e.clientY);
            
            this.boxSelectionState.isActive = true;
            this.boxSelectionState.startPos = canvasPos;
            this.boxSelectionState.currentPos = canvasPos;

            if (!e.shiftKey) {
                this._clearSelection();
            }
        },

        _updateBoxSelection(e) {
            if (!this.boxSelectionState.isActive) return;

            const canvasPos = this._transformScreenToCanvas(e.clientX, e.clientY);
            this.boxSelectionState.currentPos = canvasPos;

            this._updateBoxSelectionTargets(e.shiftKey);
        },

        _endBoxSelection(e) {
            console.log('🔲 Ending box selection');

            if (!this.boxSelectionState.isActive) return;

            e.preventDefault();
            e.stopPropagation();

            this._updateBoxSelectionTargets(e.shiftKey);

            this.boxSelectionState.isActive = false;
            this.boxSelectionState.startPos = { x: 0, y: 0 };
            this.boxSelectionState.currentPos = { x: 0, y: 0 };

            // Bulk selection has no primary element.
            this._setActive('', '');
            this._emitSelectionChanged();
        },

        _updateBoxSelectionTargets(multiSelect) {
            const selectionRect = this._getSelectionRectangle();
            
            const intersectingNodes = this._findNodesInRectangle(selectionRect);
            const intersectingEdges = this._findEdgesInRectangle(selectionRect);

            if (multiSelect) {
                intersectingNodes.forEach(nodeId => {
                    this.selectionState.selectedNodes.add(nodeId);
                    this._updateNodeVisualSelection(nodeId, true);
                });
                
                intersectingEdges.forEach(edge_id => {
                    this.selectionState.selectedEdges.add(edge_id);
                    this._updateEdgeVisualSelection(edge_id, true);
                });
            } else {
                this.selectionState.selectedNodes.forEach(nodeId => {
                    if (!intersectingNodes.includes(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, false);
                    }
                });
                
                this.selectionState.selectedEdges.forEach(edge_id => {
                    if (!intersectingEdges.includes(edge_id)) {
                        this._updateEdgeVisualSelection(edge_id, false);
                    }
                });

                this.selectionState.selectedNodes.clear();
                this.selectionState.selectedEdges.clear();
                
                intersectingNodes.forEach(nodeId => {
                    this.selectionState.selectedNodes.add(nodeId);
                    this._updateNodeVisualSelection(nodeId, true);
                });
                
                intersectingEdges.forEach(edge_id => {
                    this.selectionState.selectedEdges.add(edge_id);
                    this._updateEdgeVisualSelection(edge_id, true);
                });
            }
        },

        _getSelectionRectangle() {
            const start = this.boxSelectionState.startPos;
            const current = this.boxSelectionState.currentPos;
            
            return {
                left: Math.min(start.x, current.x),
                top: Math.min(start.y, current.y),
                right: Math.max(start.x, current.x),
                bottom: Math.max(start.y, current.y),
                width: Math.abs(current.x - start.x),
                height: Math.abs(current.y - start.y)
            };
        },

        _findNodesInRectangle(rect) {
            const intersectingNodes = [];
            const nodeElements = document.querySelectorAll('[data-node-id]');
            
            nodeElements.forEach(nodeElement => {
                const nodeId = nodeElement.dataset.nodeId;
                if (!nodeId) return;

                const nodeRect = this._getNodeBoundingRect(nodeElement);
                
                if (this._rectanglesIntersect(rect, nodeRect)) {
                    intersectingNodes.push(nodeId);
                }
            });

            return intersectingNodes;
        },

        _findEdgesInRectangle(rect) {
            const intersectingEdges = [];
            
            // ENHANCED: Use edgeInfo for more efficient bounds checking
            this.edgePaths.forEach((edgeInfo, edge_id) => {
                try {
                    // Quick bounds check using connection positions
                    const minX = Math.min(edgeInfo.outletPos.x, edgeInfo.inletPos.x);
                    const maxX = Math.max(edgeInfo.outletPos.x, edgeInfo.inletPos.x);
                    const minY = Math.min(edgeInfo.outletPos.y, edgeInfo.inletPos.y);
                    const maxY = Math.max(edgeInfo.outletPos.y, edgeInfo.inletPos.y);

                    const edgeBounds = {
                        left: minX,
                        top: minY,
                        right: maxX,
                        bottom: maxY
                    };

                    if (this._rectanglesIntersect(rect, edgeBounds)) {
                        // More precise check with actual path bounds if needed
                        const pathBBox = edgeInfo.path.getBBox();
                        const pathRect = {
                            left: pathBBox.x,
                            top: pathBBox.y,
                            right: pathBBox.x + pathBBox.width,
                            bottom: pathBBox.y + pathBBox.height
                        };

                        if (this._rectanglesIntersect(rect, pathRect)) {
                            intersectingEdges.push(edge_id);
                        }
                    }
                } catch (e) {
                    console.warn('Error getting connection bounds for selection:', e);
                }
            });

            return intersectingEdges;
        },

        _getNodeBoundingRect(nodeElement) {
            const style = nodeElement.style;
            const left = parseInt(style.left) || 0;
            const top = parseInt(style.top) || 0;
            
            const width = nodeElement.offsetWidth || 100;
            const height = nodeElement.offsetHeight || 50;
            
            return {
                left: left,
                top: top,
                right: left + width,
                bottom: top + height
            };
        },

        _rectanglesIntersect(rect1, rect2) {
            return !(rect1.right < rect2.left || 
                    rect1.left > rect2.right || 
                    rect1.bottom < rect2.top || 
                    rect1.top > rect2.bottom);
        },

        _getNodeContainerRect() {
            if (!this._cachedNodeContainerRect) {
                this._cachedNodeContainerRect = this.$refs.nodeContainer.getBoundingClientRect();
            }
            return this._cachedNodeContainerRect;
        },

        _transformScreenToCanvas(clientX, clientY) {
            const containerRect = this._getNodeContainerRect();
            const { zoom } = this.zoomState;

            const x = (clientX - containerRect.left) / zoom;
            const y = (clientY - containerRect.top) / zoom;

            return { x, y };
        },


        // =============================================================================
        // CONNECTION DRAG STATE MACHINE
        // States: 'idle' → 'active' → 'paused' → 'active' (or 'idle')
        // =============================================================================

        /**
         * Return the live anchor-pin element, re-resolving by id if the held
         * reference has gone stale.
         *
         * During a drag (especially a reconnect) the anchor node's DOM can be
         * rebuilt by a redraw/validation sync. That detaches the element we
         * captured in `_enterActiveEdge`; `getBoundingClientRect()` on a
         * detached node returns zeros, which sent the anchor end of the preview
         * to the top-left of the canvas. Re-query by the stable pin id and
         * re-apply the active highlight the rebuild wiped.
         */
        _resolveAnchorPin() {
            const held = this.edgeDrag.anchorPin;
            if (held && held.isConnected) return held;
            if (!held || !held.id) return held;

            const fresh = document.getElementById(held.id);
            if (!fresh) return held;  // node briefly gone; keep the old ref

            // Re-apply the active highlight lost when the element was rebuilt.
            fresh.style.boxShadow = '0 0 15px #4A90E2';
            // Compose with the layout rotation — a bare scale un-rotates a
            // vertical pin for the duration of the drag.
            fresh.style.transform = 'var(--hw-pin-rotate, ) scale(1.8)';
            fresh.style.zIndex = '10003';

            this.edgeDrag.anchorPin = fresh;
            return fresh;
        },

        /** Transition to active connection mode from a pin. */
        _enterActiveEdge(pin) {
            // A magnified node shifts pins; clear magnify before wiring an edge.
            this._clearAllMagnified();

            this.edgeDrag.mode = 'active';
            this.edgeDrag.anchorPin = pin;
            this.edgeDrag.nearestCompatiblePin = null;

            // Create preview path
            const startPos = this._getPinPosition(pin);
            const [dirX, dirY] = this._getPinDirectionVector(pin);
            const pinColor = pin.dataset.pinColor || '#000000';

            this.edgeDrag.previewPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const initialPath = this._createBezierPath(startPos, startPos, [dirX, dirY], [-dirX, -dirY]);

            this.edgeDrag.previewPath.setAttribute('d', initialPath);
            this.edgeDrag.previewPath.setAttribute('stroke', pinColor);
            this.edgeDrag.previewPath.setAttribute('stroke-width', '2');
            this.edgeDrag.previewPath.setAttribute('fill', 'none');
            this.edgeDrag.previewPath.setAttribute('stroke-dasharray', '4');
            this.edgeDrag.previewPath.style.pointerEvents = 'none';

            this.$refs.svg.appendChild(this.edgeDrag.previewPath);

            // Highlight anchor pin
            pin.style.boxShadow = '0 0 15px #4A90E2';
            pin.style.transform = 'var(--hw-pin-rotate, ) scale(1.8)';
            pin.style.zIndex = '10003';
        },

        /** Transition to paused mode (context menu open). Preview path stays frozen. */
        _enterPausedEdge() {
            this.edgeDrag.mode = 'paused';
            // Remove glow from anchor pin so it doesn't look active
            if (this.edgeDrag.anchorPin) {
                this.edgeDrag.anchorPin.style.boxShadow = '';
                this.edgeDrag.anchorPin.style.transform = '';
                this.edgeDrag.anchorPin.style.zIndex = '';
            }
            this._clearSuggestions();
            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid', 'connection-compatible');
            });
        },

        /** Transition to idle — clean up all connection drag visuals. */
        _returnToIdleEdge() {
            // A target node may have magnified under the cursor during the drag
            // (suppression is lifted for edge-drag). Snap it back now so it
            // doesn't stay scaled up after the gesture ends (commit or cancel).
            this._clearAllMagnified();
            if (this.edgeDrag.previewPath) {
                this.edgeDrag.previewPath.remove();
                this.edgeDrag.previewPath = null;
            }
            if (this.edgeDrag.anchorPin) {
                this.edgeDrag.anchorPin.style.boxShadow = '';
                this.edgeDrag.anchorPin.style.transform = '';
                this.edgeDrag.anchorPin.style.zIndex = '';
            }
            this._clearSuggestions();
            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid', 'connection-compatible');
            });
            this.edgeDrag.mode = 'idle';
            this.edgeDrag.anchorPin = null;
            this.edgeDrag.nearestCompatiblePin = null;
        },

        /**
         * Commit the in-progress connection to targetPin (or nearest suggestion).
         * Always returns to idle afterward.
         */
        _commitConnection(targetPin) {
            // Fall back to nearest suggestion when clicking empty canvas
            if (!targetPin && this.edgeDrag.nearestCompatiblePin) {
                targetPin = this.edgeDrag.nearestCompatiblePin;
            }

            // The anchor element may have been rebuilt during the drag; read the
            // live one so dataset and validity reflect the current DOM.
            const anchorPin = this._resolveAnchorPin();

            if (targetPin && this._isValidEdge(anchorPin, targetPin)) {
                let sourceData = anchorPin.dataset;
                let sinkData = targetPin.dataset;

                if (targetPin.dataset.pinDir === 'outlet') {
                    sinkData = anchorPin.dataset;
                    sourceData = targetPin.dataset;
                }

                if (!this._edgeExists(sourceData.nodeId, sourceData.pinId, sinkData.nodeId, sinkData.pinId)) {
                    this.emitCanvasEvent(EventCreators.createEdgeCreated(
                        sourceData.nodeId, sourceData.pinId, sinkData.nodeId, sinkData.pinId
                    ));
                }
            }
            this._returnToIdleEdge();
        },

        _handleEdgeDragMove(e) {
            if (!this.edgeDrag.previewPath) return;

            const anchorPin = this._resolveAnchorPin();
            if (!anchorPin) return;
            const startPos = this._getPinPosition(anchorPin);
            const mousePos = this._transformScreenToSVG(e.clientX, e.clientY);
            const [dirX, dirY] = this._getPinDirectionVector(anchorPin);

            const pathData = this._createBezierPath(startPos, mousePos, [dirX, dirY], [-dirX, -dirY]);
            this.edgeDrag.previewPath.setAttribute('d', pathData);

            this._clearSuggestions();

            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid', 'connection-compatible');
            });

            const hoverPin = e.target.closest('.connection-pin');
            let nearestPin = null;
            let nearestDistance = Infinity;

            document.querySelectorAll('.connection-pin').forEach(pin => {
                if (pin === anchorPin) return;
                if (pin.dataset.pinFlowType === 'ghost') return;

                const isValid = this._isValidEdge(anchorPin, pin);

                if (isValid) {
                    const pinPos = this._getPinPosition(pin);
                    const distance = Math.sqrt(
                        Math.pow(mousePos.x - pinPos.x, 2) +
                        Math.pow(mousePos.y - pinPos.y, 2)
                    );

                    if (pin === hoverPin) {
                        pin.classList.add('connection-valid');
                        nearestPin = pin;
                        nearestDistance = 0;
                    } else if (distance <= this.edgeDrag.suggestionProximityRange) {
                        if (anchorPin.dataset.pinDataType === pin.dataset.pinDataType) {
                            pin.classList.add('connection-compatible');
                            this._createSuggestionPath(pin, distance);

                            if (distance < nearestDistance) {
                                nearestPin = pin;
                                nearestDistance = distance;
                            }
                        }
                    }
                } else if (pin === hoverPin) {
                    pin.classList.add('connection-invalid');
                }
            });

            this.edgeDrag.nearestCompatiblePin = nearestPin;

            if (nearestPin && nearestDistance <= this.edgeDrag.suggestionProximityRange && nearestDistance > 0) {
                const suggestionPath = this.edgeDrag.suggestionPaths.get(nearestPin);
                if (suggestionPath) {
                    suggestionPath.classList.add('connection-suggestion-nearest');
                }
            }
        },

        _createSuggestionPath(targetPin, distance) {
            if (this.edgeDrag.suggestionPaths.has(targetPin)) {
                return;
            }

            const startPos = this._getPinPosition(this.edgeDrag.anchorPin);
            const endPos = this._getPinPosition(targetPin);
            const [dirX, dirY] = this._getPinDirectionVector(this.edgeDrag.anchorPin);

            const pathData = this._createBezierPath(startPos, endPos, [dirX, dirY], [-dirX, -dirY]);

            const suggestionPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            suggestionPath.setAttribute('d', pathData);
            suggestionPath.setAttribute('stroke', this.edgeDrag.anchorPin.dataset.pinColor || '#4CAF50');
            suggestionPath.setAttribute('stroke-width', '2');
            suggestionPath.setAttribute('fill', 'none');
            suggestionPath.setAttribute('opacity', '0.6');
            suggestionPath.style.pointerEvents = 'none';
            suggestionPath.classList.add('connection-suggestion');

            this.$refs.svg.appendChild(suggestionPath);
            this.edgeDrag.suggestionPaths.set(targetPin, suggestionPath);
        },

        _clearSuggestions() {
            this.edgeDrag.suggestionPaths.forEach((path) => {
                path.remove();
            });
            this.edgeDrag.suggestionPaths.clear();
        },

        // =============================================================================
        // CONNECTION MANAGEMENT (keeping connection visual methods as-is)
        // =============================================================================

        _createEdge(
            edge_id,
            sourceNodeId,
            outletPinId,
            sinkNodeId,
            inletPinId,
            outletPinFallback,
            inletPinFallback,
            isValid = true,
            hasWarning = false,
            strokeColor = 'auto',
            strokeWidth = 2,
            strokeDasharray = '',
            opacity = 1.0
        ) {
            const outletPinUUID = this._buildPinUUID(sourceNodeId, outletPinId);
            const inletPinUUID = this._buildPinUUID(sinkNodeId, inletPinId);

            let outletPin = document.getElementById(outletPinUUID);
            let inletPin = document.getElementById(inletPinUUID);

            if (!outletPin) {
                outletPin = this._findPinInHierarchy(sourceNodeId, outletPinFallback);
            }
            if (!inletPin) {
                inletPin = this._findPinInHierarchy(sinkNodeId, inletPinFallback);
            }

            if (!outletPin || !inletPin) {
                console.error(`🔗 Vue could not find pins:`, {
                    outletPinUUID: outletPinUUID,
                    inletPinUUID: inletPinUUID,
                    outletPinExists: !!outletPin,
                    inletPinExists: !!inletPin
                });
                return { success: false, pathElement: null };
            }

            const outletPos = this._getPinPosition(outletPin);
            const inletPos = this._getPinPosition(inletPin);
            const outletColor = outletPin.dataset.pinColor || '#bbbbbb';
            const inletColor = inletPin.dataset.pinColor || '#333333';
            const outletConnectDir = this._getPinDirectionVector(outletPin);
            const inletConnectDir = this._getPinDirectionVector(inletPin);
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('id', edge_id);
            path.setAttribute('data-edge-id', edge_id);
            path.setAttribute('fill', 'none');
            path.style.pointerEvents = 'stroke';
            path.style.cursor = 'pointer';

            // Store comprehensive connection info with visual properties
            const edgeInfo = {
                path: path,
                outletNodeId: sourceNodeId,
                outletPinUUID: outletPinUUID,
                outletPinId: outletPinId,
                outletPos: outletPos,
                outletColor: outletColor,
                outletConnectDir: outletConnectDir,
                outletPinFallback: outletPinFallback,
                inletNodeId: sinkNodeId,
                inletPinUUID: inletPinUUID,
                inletPinId: inletPinId,
                inletPos: inletPos,
                inletColor: inletColor,
                inletConnectDir: inletConnectDir,
                inletPinFallback: inletPinFallback,
                // Visual state properties
                isValid: isValid,
                hasWarning: hasWarning,
                strokeColor: strokeColor,
                strokeWidth: strokeWidth,
                strokeDasharray: strokeDasharray,
                opacity: opacity
            };

            const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            hitArea.setAttribute('id', edge_id + '_hitarea');
            hitArea.setAttribute('data-edge-id', edge_id);
            hitArea.setAttribute('stroke', 'transparent');
            hitArea.setAttribute('stroke-width', '10');
            hitArea.setAttribute('fill', 'none');
            hitArea.style.pointerEvents = 'stroke';
            hitArea.style.cursor = 'pointer';

            this.$refs.svg.appendChild(path);
            this.$refs.svg.appendChild(hitArea);
            
            // ENHANCED: Store the full connection info instead of just the path
            this.edgePaths.set(edge_id, edgeInfo);

            const clickHandler = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.emitCanvasEvent(EventCreators.createEdgeClicked(edge_id));
            };

            path.addEventListener('click', clickHandler);
            hitArea.addEventListener('click', clickHandler);

            this.$nextTick(() => {
                this._updateEdge(edge_id);
            });

            return { success: true, pathElement: path };
        },

        _removeEdge(edge_id) {
            const edgeInfo = this.edgePaths.get(edge_id);

            if (edgeInfo) {
                edgeInfo.path.remove();

                const hitArea = document.getElementById(edge_id + '_hitarea');
                if (hitArea) {
                    hitArea.remove();
                }

                const gradient = document.getElementById(`gradient_${edge_id}`);
                if (gradient) {
                    gradient.remove();
                }

                this.edgePaths.delete(edge_id);
                return true;
            } else {
                return false;
            }
        },

        _findPinInHierarchy(nodeId, hierarchyString) {
            /**
             * Iterate through port hierarchy to find an existing pin element.
             * 
             * @param {string} nodeId - The node ID
             * @param {string} hierarchyString - Hierarchy string (e.g., 
             *     "port_id>>parent_id>>root")
             * @returns {HTMLElement|null} - First found pin element or null
             * 
             * Iterates through hierarchy levels from specific to general:
             * - First tries the leaf port (most specific)
             * - Then tries parent groups moving up the hierarchy
             * - Finally tries 'root' which is the node's ghost pin
             * 
             * Ghost pins are fallback connection points when ports are hidden
             * (e.g., when a group is collapsed). Each node has inlet and outlet
             * ghost pins to maintain connection continuity.
             */
            if (!hierarchyString) {
                return null;
            }

            // Split the hierarchy string by >>
            const portIds = hierarchyString.split('>>');
            
            // Iterate through each level in the hierarchy (including 'root')
            for (let i = 0; i < portIds.length; i++) {
                const portId = portIds[i];
                
                // Build the pin UUID and try to find the element
                const pinUUID = this._buildPinUUID(nodeId, portId);
                const pinElement = document.getElementById(pinUUID);
                
                if (pinElement) {
                    console.debug(
                        `🔍 Found fallback pin: ${pinUUID} (hierarchy level ${i})`
                    );
                    return pinElement;
                }
            }
            
            console.warn(
                `⚠️ No pins found in hierarchy for node ${nodeId}: ` +
                `${hierarchyString}`
            );
            return null;
        },

        _updateEdge(edge_id) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (!edgeInfo) {
                console.error(`Edge not found: ${edge_id}`);
                return;
            }

            // If either endpoint node is pending (canvas detached), skip silently —
            // _updateEdgesForNode will be called once the node appears in the live DOM.
            if (this._pendingNodeIds.has(edgeInfo.outletNodeId) || this._pendingNodeIds.has(edgeInfo.inletNodeId)) {
                return;
            }

            let outletPin = document.getElementById(edgeInfo.outletPinUUID);
            let inletPin = document.getElementById(edgeInfo.inletPinUUID);

            if (!outletPin) {
                outletPin = this._findPinInHierarchy(edgeInfo.outletNodeId, edgeInfo.outletPinFallback);
            }
            if (!inletPin) {
                inletPin = this._findPinInHierarchy(edgeInfo.inletNodeId, edgeInfo.inletPinFallback);
            }

            if (!outletPin || !inletPin) {
                console.error(`Failed to find pins for connection: ${edge_id}`);
                return;
            }

            // Update positions in edgeInfo
            edgeInfo.outletPos = this._getPinPosition(outletPin);
            edgeInfo.inletPos = this._getPinPosition(inletPin);

            // Update colors in edgeInfo
            edgeInfo.outletColor = outletPin.dataset.pinColor;
            edgeInfo.inletColor = inletPin.dataset.pinColor;

            // Re-read the direction vectors from the live pins. These were
            // captured once at _createEdge and treated as immutable, which held
            // only while every node was left-to-right. A LayoutDirection change
            // re-renders the pin with new data-pin-dir-x/y, so a cached vector
            // leaves the curve aiming the old way — visibly, an outlet's edge
            // doubling back into its own node.
            edgeInfo.outletConnectDir = this._getPinDirectionVector(outletPin);
            edgeInfo.inletConnectDir = this._getPinDirectionVector(inletPin);

            const pathData = this._createBezierPathForEdge(edge_id);

            edgeInfo.path.setAttribute('d', pathData);
            const hitArea = document.getElementById(edge_id + '_hitarea');
            if (hitArea) {
                hitArea.setAttribute('d', pathData);
            }

            // Apply visual properties from edgeInfo
            const stroke = this._createBezierStroke(edge_id);
            edgeInfo.path.setAttribute('stroke', stroke);
            edgeInfo.path.setAttribute(
                'stroke-width',
                edgeInfo.strokeWidth
            );
            edgeInfo.path.setAttribute(
                'stroke-dasharray',
                edgeInfo.strokeDasharray
            );
            edgeInfo.path.style.opacity = edgeInfo.opacity;
            
            // Update CSS classes for additional styling
            edgeInfo.path.classList.toggle(
                'connection-invalid',
                !edgeInfo.isValid
            );
            edgeInfo.path.classList.toggle(
                'connection-warning',
                edgeInfo.hasWarning
            );
            
            // Update hit area width
            if (hitArea) {
                hitArea.setAttribute(
                    'stroke-width',
                    edgeInfo.strokeWidth + 8
                );
            }
        },

        _updateEdgesForNode(nodeId) {
            if (!nodeId) return;
            
            // ENHANCED: More efficient iteration using edgeInfo
            this.edgePaths.forEach((edgeInfo, edge_id) => {
                if (edgeInfo.outletNodeId === nodeId || edgeInfo.inletNodeId === nodeId) {
                    this._updateEdge(edge_id);
                }
            });
        },

        _addNodeObserver(nodeId) {
            const nodeElement = document.getElementById(nodeId);
            if (nodeElement) {
                this._setupHoverObserver(nodeElement);
            } else {
                // Element not in DOM yet (e.g. canvas editor is not the active panel).
                // Park it in the pending set; _ensurePendingNodeWatcher will pick it up
                // whenever the element appears, and also redraw its edges at that point.
                console.log(`[PendingObserver] Node ${nodeId} not in DOM — parked for deferred observation. Pending count: ${this._pendingNodeIds.size + 1}`);
                this._pendingNodeIds.add(nodeId);
                this._ensurePendingNodeWatcher();
            }
        },

        _ensurePendingNodeWatcher() {
            if (this._pendingNodeWatcher) {
                console.log(`[PendingObserver] Watcher already running, skipping setup.`);
                return;
            }

            const container = this.$refs.nodeContainer;
            if (!container) {
                console.warn(`[PendingObserver] nodeContainer ref not available — cannot start watcher.`);
                return;
            }

            // Watch document.body (not nodeContainer) so the observer fires even when the
            // canvas editor is detached from the live document. When the user switches back
            // to the graph editor, the canvas re-attaches to body and this fires immediately.
            console.log(`[PendingObserver] Starting MutationObserver on document.body. nodeContainer.isConnected=${container.isConnected}`);
            this._pendingNodeWatcher = new MutationObserver((mutations) => {
                console.log(`[PendingObserver] MutationObserver fired (${mutations.length} mutations). Pending nodes: ${this._pendingNodeIds.size}`);
                if (this._pendingNodeIds.size === 0) return;

                for (const nodeId of [...this._pendingNodeIds]) {
                    const nodeElement = document.getElementById(nodeId);
                    if (nodeElement) {
                        console.log(`[PendingObserver] Found pending node ${nodeId} — setting up observer and redrawing edges.`);
                        this._pendingNodeIds.delete(nodeId);
                        this._setupHoverObserver(nodeElement);
                        this._updateEdgesForNode(nodeId);
                    } else {
                        console.log(`[PendingObserver] Still waiting for node ${nodeId}.`);
                    }
                }

                // All pending nodes resolved — stop watching to save resources
                if (this._pendingNodeIds.size === 0) {
                    console.log(`[PendingObserver] All pending nodes resolved — disconnecting watcher.`);
                    this._pendingNodeWatcher.disconnect();
                    this._pendingNodeWatcher = null;
                }
            });

            this._pendingNodeWatcher.observe(document.body, { childList: true, subtree: true });
            console.log(`[PendingObserver] Watcher active on document.body.`);
        },

        // =============================================================================
        // VISUAL SELECTION UPDATES
        // =============================================================================

        _updateNodeVisualSelection(nodeId, selected, _retries = 6) {
            const nodeElement = document.getElementById(nodeId);
            if (nodeElement) {
                if (selected) {
                    nodeElement.classList.add('node-selected');
                } else {
                    nodeElement.classList.remove('node-selected');
                }
            } else if (selected && _retries > 0) {
                // The node's DOM element may not have rendered yet — e.g. right
                // after a paste, where node-addition (a NiceGUI element pushed
                // over the socket) and the selection sync arrive close together.
                // Retry shortly until it appears.
                setTimeout(() => this._updateNodeVisualSelection(nodeId, selected, _retries - 1), 50);
            }
        },

        _updateEdgeVisualSelection(edge_id, selected, _retries = 6) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (edgeInfo && edgeInfo.path) {
                if (selected) {
                    edgeInfo.path.classList.add('connection-selected');
                    edgeInfo.path.style.strokeWidth = '3';
                } else {
                    edgeInfo.path.classList.remove('connection-selected');
                    edgeInfo.path.style.strokeWidth = '2';
                }
            } else if (selected && _retries > 0) {
                // Edge path may not be registered yet (e.g. just after a paste);
                // retry shortly until edgePaths has it.
                setTimeout(() => this._updateEdgeVisualSelection(edge_id, selected, _retries - 1), 50);
            }
        },

        _updateNodeVisualActive(nodeId, active, _retries = 6) {
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                if (active) {
                    nodeElement.classList.add('node-active');
                } else {
                    nodeElement.classList.remove('node-active');
                }
            } else if (active && _retries > 0) {
                setTimeout(() => this._updateNodeVisualActive(nodeId, active, _retries - 1), 50);
            }
        },

        _updateEdgeVisualActive(edge_id, active, _retries = 6) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (edgeInfo && edgeInfo.path) {
                if (active) {
                    edgeInfo.path.classList.add('connection-active');
                } else {
                    edgeInfo.path.classList.remove('connection-active');
                }
            } else if (active && _retries > 0) {
                setTimeout(() => this._updateEdgeVisualActive(edge_id, active, _retries - 1), 50);
            }
        },

        // =============================================================================
        // UTILITY & HELPER METHODS
        // =============================================================================

        // ENHANCED: New helper method to get connection by node and pin
        _getEdgesByNode(nodeId) {
            const edges = [];
            this.edgePaths.forEach((edgeInfo, edge_id) => {
                if (edgeInfo.outletNodeId === nodeId || edgeInfo.inletNodeId === nodeId) {
                    edges.push({ uuid: edge_id, info: edgeInfo });
                }
            });
            return edges;
        },

        // ENHANCED: New helper method to get connection by specific pin
        _getEdgesByPin(nodeId, pinId, pinType) {
            const edges = [];
            this.edgePaths.forEach((edgeInfo, edge_id) => {
                const isOutletMatch = pinType === 'outlet' && 
                    edgeInfo.outletNodeId === nodeId && 
                    edgeInfo.outletPinId === pinId;
                const isInletMatch = pinType === 'inlet' && 
                    edgeInfo.inletNodeId === nodeId && 
                    edgeInfo.inletPinId === pinId;
                    
                if (isOutletMatch || isInletMatch) {
                    edges.push({ uuid: edge_id, info: edgeInfo });
                }
            });
            return edges;
        },

        _setsAreEqual(set1, set2) {
            if (set1.size !== set2.size) {
                return false;
            }
            for (const item of set1) {
                if (!set2.has(item)) {
                    return false;
                }
            }
            return true;
        },

        _isInteractiveWidgetElement(element) {
            // Edge pins are NOT interactive widgets
            if (element.closest('.connection-pin')) {
                return false;
            }

            // Node drag handles are NOT interactive widgets - they should be draggable
            if (element.closest('.drag-handle')) {
                return false;
            }

            // Popup elements ARE interactive - handled separately in handleMouseDown
            const isPopupElement = element.closest(
                '[data-popup-container="true"], ' +
                '[data-popup-drag-handle="true"], ' +
                '.popup-card, ' +
                '.popup-content-area'
            );
            if (isPopupElement) {
                return true;
            }

            // ... rest of your existing checks ...
            const isFormElement = element.matches('input, textarea, select, button, [contenteditable]') ||
                element.closest('input, textarea, select, button, [contenteditable]');

            const isQuasarElement = element.closest('.q-field, .q-btn, .q-checkbox, .q-radio, .q-toggle, .q-slider, .q-knob, .q-select') ||
                element.closest('[role="button"], [role="checkbox"], [role="radio"], [role="slider"]');

            const isWidgetContainer = element.closest('.widget-container');
            const isMarkedInteractive = element.closest('[data-interactive="true"], .interactive, .clickable');

            return isFormElement || isQuasarElement || isWidgetContainer || isMarkedInteractive;
        },

        _parseEdgeID(edge_id) {
            // Split by :: to get prefix and the rest
            if (!edge_id.includes('::')) {
                console.error(`Invalid connection ID format: ${edge_id}. Expected format: edge::outlet_pin_id@outlet_node_id>>inlet_pin_id@inlet_node_id`);
                return null;
            }

            const [prefix, rest] = edge_id.split('::', 2);

            if (prefix !== 'edge') {
                console.error(`Edge ID must start with 'edge', got: ${prefix}`);
                return null;
            }

            // Split by >> to get outlet and inlet parts
            if (!rest.includes('>>')) {
                console.error(`Invalid connection ID format: ${edge_id}. Expected '>>' separator between outlet and inlet`);
                return null;
            }

            const [outletPart, inletPart] = rest.split('>>', 2);

            // Parse outlet part (pin_id@node_id)
            const outletParts = outletPart.split('@');
            if (outletParts.length !== 2) {
                console.error(`Invalid outlet format in connection ID: ${outletPart}. Expected pin_id@node_id`);
                return null;
            }
            const [outletPinId, outletNodeId] = outletParts;

            // Parse inlet part (pin_id@node_id)
            const inletParts = inletPart.split('@');
            if (inletParts.length !== 2) {
                console.error(`Invalid inlet format in connection ID: ${inletPart}. Expected pin_id@node_id`);
                return null;
            }
            const [inletPinId, inletNodeId] = inletParts;

            return {
                outletNodeId: outletNodeId,
                outletPinId: outletPinId,
                inletNodeId: inletNodeId,
                inletPinId: inletPinId,
                outletPinFullId: `${outletPinId}@${outletNodeId}`,
                inletPinFullId: `${inletPinId}@${inletNodeId}`
            };
        },

        _buildEdgeID(sourceNodeId, outletPinId, sinkNodeId, inletPinId) {
            const outletPin = this._buildPinUUID(sourceNodeId, outletPinId);
            const inletPin = this._buildPinUUID(sinkNodeId, inletPinId);
            return `edge::${outletPin}>>${inletPin}`;
        },

        _buildPinUUID(nodeId, pinId) {
            return `${pinId}@${nodeId}`;
        },

        _getPinPosition(pinElement) {
            if (!pinElement) return { x: 0, y: 0 };

            const pinRect = pinElement.getBoundingClientRect();
            const position = this._transformScreenToSVG(
                pinRect.left + pinRect.width / 2,
                pinRect.top + pinRect.height / 2
            );

            return position;
        },

        _transformScreenToSVG(clientX, clientY) {
            if (!this.$refs.svg) return { x: clientX, y: clientY };

            const svgRect = this.$refs.svg.getBoundingClientRect();
            const { zoom, panX, panY } = this.zoomState;

            let x = (clientX - svgRect.left) / zoom;
            let y = (clientY - svgRect.top) / zoom;

            return { x, y };
        },

        _createBezierPath(startPos, endPos, startDir = [1, 0], endDir = [-1, 0]) {
            // Control-point distance, measured along the axis the edge actually
            // leaves on. Projecting the delta onto startDir keeps this correct
            // for every LayoutDirection: for L2R (startDir [1,0]) it reduces to
            // |dx| exactly, so horizontal graphs are unchanged, while T2B/B2T
            // no longer collapse to the 50px floor just because dx is ~0.
            // Each end uses its OWN vector, so a T2B node feeding an L2R node
            // still curves correctly — nothing here assumes a shared axis.
            const dx = endPos.x - startPos.x;
            const dy = endPos.y - startPos.y;
            // Fallback covers a purely perpendicular run, where the projection
            // is 0 but the endpoints are far apart.
            const span = Math.abs(dx * startDir[0] + dy * startDir[1]) || Math.hypot(dx, dy);
            const controlDistance = Math.max(50, span * 0.5);
            
            // Calculate control points using direction vectors
            const startControl = {
                x: startPos.x + (startDir[0] * controlDistance),
                y: startPos.y + (startDir[1] * controlDistance)
            };
            
            const endControl = {
                x: endPos.x + (endDir[0] * controlDistance),
                y: endPos.y + (endDir[1] * controlDistance)
            };
            
            return `M ${startPos.x} ${startPos.y} C ${startControl.x} ${startControl.y}, ${endControl.x} ${endControl.y}, ${endPos.x} ${endPos.y}`;
        },

        // Wrapper method for established connections
        _createBezierPathForEdge(edge_id) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (!edgeInfo) {
                console.error(`Edge info not found for: ${edge_id}`);
                return 'M 0 0';
            }

            return this._createBezierPath(
                edgeInfo.outletPos,
                edgeInfo.inletPos,
                edgeInfo.outletConnectDir,
                edgeInfo.inletConnectDir
            );
        },

        _createBezierStroke(edge_id) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (!edgeInfo) {
                console.error(`Edge not found: ${edge_id}`);
                return '#000000';
            }
            
            // If strokeColor is not 'auto', use the solid color directly
            if (edgeInfo.strokeColor !== 'auto') {
                return edgeInfo.strokeColor;
            }
            
            // Otherwise create gradient (existing logic)
            const startPos = edgeInfo.outletPos;
            const endPos = edgeInfo.inletPos;
            const startColor = edgeInfo.outletColor;
            const endColor = edgeInfo.inletColor;
            
            if (!endColor || !edge_id) {
                return startColor || '#ff0000';
            }

            let defs = this.$refs.defs;
            if (!defs) {
                defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                this.$refs.svg.appendChild(defs);
            }

            const gradientId = `gradient_${edge_id}`;
            let gradient = document.getElementById(gradientId);
            if (!gradient) {
                gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
                gradient.setAttribute('id', gradientId);
                gradient.setAttribute('gradientUnits', 'userSpaceOnUse');

                gradient.setAttribute('x1', startPos.x);
                gradient.setAttribute('y1', startPos.y);
                gradient.setAttribute('x2', endPos.x);
                gradient.setAttribute('y2', endPos.y);

                const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
                stop1.setAttribute('offset', '0%');
                stop1.setAttribute('stop-color', startColor);

                const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
                stop2.setAttribute('offset', '100%');
                stop2.setAttribute('stop-color', endColor);

                gradient.appendChild(stop1);
                gradient.appendChild(stop2);
                defs.appendChild(gradient);
            } else {
                // Update gradient position to match current connection endpoints
                gradient.setAttribute('x1', startPos.x);
                gradient.setAttribute('y1', startPos.y);
                gradient.setAttribute('x2', endPos.x);
                gradient.setAttribute('y2', endPos.y);
                
                const stops = gradient.querySelectorAll('stop');
                if (stops.length >= 2) {
                    stops[0].setAttribute('stop-color', startColor);
                    stops[1].setAttribute('stop-color', endColor);
                }
            }

            return `url(#${gradientId})`;
        },

        _isValidEdge(startPin, endPin) {
            if (!startPin || !endPin || startPin === endPin) return false;

            const startDir = startPin.dataset.pinDir;
            const startNodeId = startPin.dataset.nodeId;
            const startFlowType = startPin.dataset.pinFlowType;
            const endDir = endPin.dataset.pinDir;
            const endNodeId = endPin.dataset.nodeId;
            const endFlowType = endPin.dataset.pinFlowType;

            if (startNodeId === endNodeId) {
                return false;
            }

            // Ghost pins are flow-type agnostic — they accept any connection type.
            const eitherIsGhost = startFlowType === 'ghost' || endFlowType === 'ghost';
            if (!eitherIsGhost && startFlowType !== endFlowType) {
                return false;
            }

            const valid = (startDir === 'outlet' && endDir === 'inlet') ||
                (startDir === 'inlet' && endDir === 'outlet');
            return valid;
        },

        _scheduleEdgeUpdates(nodeId, nodeElement = null, animationDuration = 300) {
            this._updateEdgesForNode(nodeId);

            if (!nodeElement && nodeId) {
                nodeElement = document.getElementById(nodeId);
            }

            if (nodeElement && nodeElement._animationTimers) {
                nodeElement._animationTimers.forEach(timer => clearTimeout(timer));
                nodeElement._animationTimers = [];
            }

            const updateCount = Math.max(3, Math.min(8, Math.ceil(animationDuration / 50)));
            const interval = animationDuration / updateCount;

            console.debug(`-->  _scheduleEdgeUpdates(): ${nodeId}`);
            for (let i = 1; i <= updateCount; i++) {
                const delay = interval * i;
                const timer = setTimeout(() => {
                    this._updateEdgesForNode(nodeId);
                }, delay);

                if (nodeElement) {
                    if (!nodeElement._animationTimers) {
                        nodeElement._animationTimers = [];
                    }
                    nodeElement._animationTimers.push(timer);
                }
            }
        },

        _edgeExists(sourceNodeId, outletPinId, sinkNodeId, inletPinId) {
            const edge_id = this._buildEdgeID(sourceNodeId, outletPinId, sinkNodeId, inletPinId);
            return this.edgePaths.has(edge_id);
        },

        _getPinDirectionVector(pinElement) {
            // Get the 2D direction vector from pin data attributes
            const dirX = pinElement.dataset.pinDirX;
            const dirY = pinElement.dataset.pinDirY;
            
            if (dirX !== undefined && dirY !== undefined) {
                return [parseFloat(dirX), parseFloat(dirY)];
            }
            
            return [1, 0]; // Default fallback
        }
    }
}
</script>

<style scoped>
.graph-canvas {
    position: relative;
    overflow: visible;
}

.debug-info {
    position: absolute;
    top: 10px;
    left: 10px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 12px;
    z-index: 1000;
}

.connection-svg {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: auto;
    z-index: 1;
}

.node-container {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
    z-index: 2;
}

.graph-canvas.dragging {
    cursor: grabbing;
}

.selection-box {
    position: absolute;
    border: 2px solid rgba(74, 144, 226, 0.8);
    background-color: rgba(74, 144, 226, 0.1);
    pointer-events: none;
    z-index: 999;
    border-radius: 2px;
}

/* Single-node resize gadget: a thin accent outline + 8 edge/corner grips.
   Wrapper is pointer-events:none (set inline); only the grips are interactive.
   Colors ride the selection token (falls back to the accent) — no hardcoded
   blues (design rule). */
.hw-resize-gadget {
    --hw-grip: var(--hw-node-selected, var(--hw-accent, #4a90e2));
    z-index: 1002;
    outline: 1px solid color-mix(in srgb, var(--hw-grip) 70%, transparent);
    outline-offset: 0;
}

.hw-resize-grip {
    position: absolute;
    pointer-events: auto;
    z-index: 1003;
}

/* Edge grips: invisible strips spanning the edge (hit area only). */
.hw-resize-grip[data-handle="right"]  { top: 0; right: -4px; width: 8px; height: 100%; cursor: ew-resize; background: transparent; }
.hw-resize-grip[data-handle="left"]   { top: 0; left: -4px; width: 8px; height: 100%; cursor: ew-resize; background: transparent; }
.hw-resize-grip[data-handle="bottom"] { left: 0; bottom: -4px; height: 8px; width: 100%; cursor: ns-resize; background: transparent; }
.hw-resize-grip[data-handle="top"]    { left: 0; top: -4px; height: 8px; width: 100%; cursor: ns-resize; background: transparent; }

/* Corner grips: hollow circles — canvas-fill center, accent ring, so they
   read over any node content. Centered on the corner via a -50% offset. */
.hw-resize-grip[data-handle="bottom-right"],
.hw-resize-grip[data-handle="top-left"],
.hw-resize-grip[data-handle="top-right"],
.hw-resize-grip[data-handle="bottom-left"] {
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: var(--hw-canvas-bg, #12141a);
    border: 1.5px solid var(--hw-grip);
    box-sizing: border-box;
    transition: transform 0.08s ease, background 0.08s ease;
}
.hw-resize-grip[data-handle="bottom-right"] { right: 0; bottom: 0; transform: translate(50%, 50%);   cursor: nwse-resize; }
.hw-resize-grip[data-handle="top-left"]     { left: 0;  top: 0;    transform: translate(-50%, -50%); cursor: nwse-resize; }
.hw-resize-grip[data-handle="top-right"]    { right: 0; top: 0;    transform: translate(50%, -50%);  cursor: nesw-resize; }
.hw-resize-grip[data-handle="bottom-left"]  { left: 0;  bottom: 0; transform: translate(-50%, 50%);  cursor: nesw-resize; }

/* Hover: fill the circle and swell slightly (compose with the corner's own
   translate so the dot stays centered on its corner). */
.hw-resize-grip[data-handle="bottom-right"]:hover { background: var(--hw-grip); transform: translate(50%, 50%)   scale(1.25); }
.hw-resize-grip[data-handle="top-left"]:hover     { background: var(--hw-grip); transform: translate(-50%, -50%) scale(1.25); }
.hw-resize-grip[data-handle="top-right"]:hover    { background: var(--hw-grip); transform: translate(50%, -50%)  scale(1.25); }
.hw-resize-grip[data-handle="bottom-left"]:hover  { background: var(--hw-grip); transform: translate(-50%, 50%)  scale(1.25); }

.graph-canvas.box-selecting {
    cursor: crosshair !important;
}

.graph-canvas.box-selecting * {
    cursor: crosshair !important;
}

[data-node-id] {
    z-index: 10;
    pointer-events: auto;
    cursor: grab;
    user-select: none;
}

/* Hover — subtle accent border; distinct from selected glow and active ring */
[data-node-id]:hover {
    z-index: 1001 !important;
    cursor: grab;
    outline: 1px solid var(--hw-accent-hover) !important;
    outline-offset: 1px;
}

[data-node-id].dragging-node {
    z-index: 1001 !important;
    cursor: grabbing !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15) !important;
    transform: translateZ(0);
    outline: none !important;
}

[data-node-id]:active {
    cursor: grabbing;
}

/* Selected — soft shadow glow ring; suppress default outline */
[data-node-id].node-selected {
    z-index: 1000 !important;
    outline: none !important;
    box-shadow: 0 8px 25px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}

[data-node-id].node-selected:hover {
    outline: none !important;
    box-shadow: 0 12px 35px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}

/* Active — crisp accent ring layered on top; must survive hover and selected */
[data-node-id].node-active {
    outline: 2px solid var(--hw-node-active) !important;
    outline-offset: 2px;
}

[data-node-id].node-active:hover {
    outline: 2px solid var(--hw-node-active) !important;
    outline-offset: 2px;
}

[data-node-id].node-selected.node-active {
    outline: 2px solid var(--hw-node-active) !important;
    outline-offset: 2px;
    box-shadow: 0 8px 25px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}

[data-node-id].node-selected.node-active:hover {
    outline: 2px solid var(--hw-node-active) !important;
    outline-offset: 2px;
    box-shadow: 0 12px 35px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}
</style>

<style>
/* Global styles for connection pins */
.connection-pin {
    transition: all 0.2s ease !important;
    pointer-events: all !important;
    position: relative !important;
    z-index: 10000 !important;

    /* Force the element to be exactly the size of the icon */
    line-height: 1 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    
    /* Remove any text spacing that extends the box */
    letter-spacing: 0 !important;
    word-spacing: 0 !important;
    
    /* Clip the hover area to the element bounds */
    overflow: hidden !important;
}

/* Pin transforms compose scale with the layout rotation.
 *
 * A vertical LayoutDirection rotates the pin glyph 90deg via --hw-pin-rotate
 * (set inline by render_pin). Every scale below must carry that rotation
 * through, because `transform` is a single property: writing `scale(1.4)`
 * alone silently un-rotates the pin for as long as the state lasts, which is
 * what made pins snap back to horizontal on hover. Same reason the JS
 * magnifier/drag paths write `var(--hw-pin-rotate,) scale(...)` rather than a
 * bare scale. The empty fallback (`,`) resolves to nothing for horizontal
 * layouts, leaving the transform exactly as it was. */
.connection-pin {
    transform: var(--hw-pin-rotate, );
}

.connection-pin:hover {
    transform: var(--hw-pin-rotate, ) scale(1.4) !important;
    filter: brightness(1.2) !important;
    z-index: 10001 !important;
}

.connection-pin.connection-valid {
    box-shadow: 0 0 15px #4CAF50 !important;
    border-color: #4CAF50 !important;
    z-index: 10002 !important;
}

.connection-pin.connection-invalid {
    transform: var(--hw-pin-rotate, ) scale(0.8) !important;
    box-shadow: 0 0 15px #f44336 !important;
    border-color: #f44336 !important;
    z-index: 10002 !important;
    opacity: 0.8 !important;
}

.connection-pin.connection-compatible {
    box-shadow: 0 0 6px rgba(76, 175, 80, 0.6) !important;
    border-color: rgba(76, 175, 80, 0.8) !important;
    transform: scale(1.15) !important;
    z-index: 10001 !important;
}

.connection-selected {
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
}

path.connection-selected {
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
}

.connection-active {
    stroke: var(--hw-edge-active) !important;
    stroke-width: 4 !important;
}

/* Edge state styles - UIEdge visual feedback */
/* Specific to SVG path elements only */
path.connection-invalid {
    filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.5));
}

path.connection-warning {
    filter: drop-shadow(0 0 4px rgba(245, 158, 11, 0.5));
}

/* Manual-size axes are user MINIMUMS applied to the host slot (min-width /
   min-height in UINode._apply_size); content needing more space expands the
   node — nothing clips. The card must track the slot both ways, so the skin's
   own clamps (w-full min-w-64 max-w-sm) are released. Flex mechanics (the
   slot is a flex column) rather than percentages: `align-self: stretch` fills
   the cross axis (width) whatever the slot resolves to, `flex: 1 0 auto`
   grows the card into a min-height slot without ever shrinking below its
   content. */
/* --8<-- [start:node-card-manual-resize] */
.ui-node-slot[data-size-adapt="manual"] .node-card,
.ui-node-slot[data-size-adapt="manual_width"] .node-card {
    align-self: stretch !important;
    width: auto !important;
    min-width: 0 !important;
    max-width: none !important;
}
.ui-node-slot[data-size-adapt="manual"] .node-card,
.ui-node-slot[data-size-adapt="manual_height"] .node-card {
    flex: 1 0 auto !important;
}
/* --8<-- [end:node-card-manual-resize] */

/* --8<-- [start:widget-container-reveal] */
[data-node-id] .widget-container {
    opacity: 0 !important;
    transition: opacity 0.3s ease, max-height 0.3s ease !important;
    max-height: 0 !important;
    overflow: hidden !important;
}

[data-node-id].node-selected .widget-container {
    opacity: 1 !important;
    max-height: 200px !important;
}
/* --8<-- [end:widget-container-reveal] */

/* ---- Declared size box (@widget(min_width=, min_height=, max_height=)) ----
   Stamped by haywire/ui/widget/sizing.py through the one render funnel every
   skin calls (BaseSkin.render_widget), so custom skins inherit this without
   cooperating. See docs/components/widgets/widget-canon.md. */

/* max_height — a definite px ceiling replacing the 200px default, for a widget
   whose CONTENT is unbounded (a long label, a growing list). Must stay a fixed
   px value, never a percentage: max-height transitions need a definite
   reference to animate, and a percentage of an auto-height ancestor resolves
   to none, so the browser snaps instead of easing. */
[data-node-id].node-selected .widget-container[data-hw-widget-max-height] {
    max-height: var(--hw-widget-max-height) !important;
}

/* min_width alone — inline-axis containment. The width stops coming from
   content (killing the floor, see below) while the height still does, so
   content with an intrinsic aspect ratio keeps growing proportionally as the
   node widens. Full containment would flatten it to a fixed-height box. */
[data-node-id] .widget-container[data-hw-widget-inline-box] {
    contain: inline-size !important;
    contain-intrinsic-width: var(--hw-widget-min-width) !important;
}

[data-node-id].node-selected .widget-container[data-hw-widget-inline-box] {
    max-height: var(--hw-widget-max-height, none) !important;
}

/* min_width + min_height — the widget's declared INTRINSIC box. Size containment
   makes the browser size this element as if it had no contents, so its children
   stop contributing to the node's size floor.

   That floor is not computed in Python: the resize gadget writes a min-width /
   min-height onto the host slot and reads offsetWidth/offsetHeight back
   (onResizeGripDown above), so it is whatever CSS intrinsic sizing produces —
   the max-content size of the card subtree. A widget holding an <img> floors
   its node at the image's NATURAL pixel size (1280px for a 720p frame), and no
   percentage can cap it: percentages resolve to auto during intrinsic sizing.
   contain-intrinsic-size substitutes the declared box for that vote, so the
   node shrinks to the box while the widget still grows into a bigger card —
   containment removes content from the calculation, it does not stop the
   element being stretched by its parent.

   Growth needs the ceiling gone, so a boxed widget opts out of the 200px
   default. Declaring max_height too puts an animatable ceiling back (the var
   resolves) at the cost of capping growth there; without it, the reveal snaps
   instead of easing because none is not an animatable length. */
[data-node-id] .widget-container[data-hw-widget-box] {
    contain: size !important;
    contain-intrinsic-size: var(--hw-widget-min-width) var(--hw-widget-min-height) !important;
}

[data-node-id].node-selected .widget-container[data-hw-widget-box] {
    max-height: var(--hw-widget-max-height, none) !important;
}

.connection-suggestion {
    opacity: 0.3 !important;
    stroke-width: 2 !important;
    stroke-dasharray: 12 6 !important;
}

.connection-suggestion-nearest {
    opacity: 0.8 !important;
    stroke-dasharray: 8 4 !important;
    stroke-width: 3 !important;
}
</style>