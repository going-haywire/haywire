<template>
    <div :id="containerId" ref="container" class="graph-canvas" :class="{
        dragging: dragState.isDragging,
        'box-selecting': boxSelectionState.isActive
    }" :style="canvasSizeStyle" tabindex="0" @click="handleCanvasClick" @contextmenu="handleContextMenu">
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
        </div>

    </div>
</template>

<script>
// Import auto-generated event system

export default {
    name: 'GraphCanvas',

    props: {
        containerId: { type: String, required: true },
        zoomContainerId: { type: String, default: '' },
        canvasWidth:  { type: Number, default: 8000 },
        canvasHeight: { type: Number, default: 8000 },
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
                mouseDownEvent: null,
                finalDeltaX: 0,
                finalDeltaY: 0
            },
            
            // Unified selection state
            selectionState: {
                selectedNodes: new Set(),
                selectedEdges: new Set(),
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
            }
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
    },

    beforeUnmount() {
        this._cleanupEventListeners();
        this._cleanupObservers();
        this._cleanupZoomPanListener();
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

            // Listen for transform transitions (zoom scaling effects)
            lodElement.addEventListener('transitionstart', (e) => {
                if (e.propertyName === 'transform') {
                    this._scheduleEdgeUpdates(nodeId, nodeElement);
                }
            });
        
            // Listen for hover enter/leave for size changes
            lodElement.addEventListener('mouseenter', scheduleEdgeUpdates);
            lodElement.addEventListener('mouseleave', scheduleEdgeUpdates);
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
            const { nodes, connections } = data;
            
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
            this._enterActiveEdge(this.edgeDrag.anchorPin);
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


            // Check for port-scope context menu (data-hw-port-menu-scope)
            // port_id is taken from data-port-id on the element, falling back to data-pin-id.
            // node_id is resolved by walking up to the nearest [data-node-id] ancestor.
            const portMenuEl = target.closest('[data-hw-port-menu-scope]');
            if (portMenuEl) {
                const scope = portMenuEl.getAttribute('data-hw-port-menu-scope');
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

            // Check for custom-scope context menu button (data-hw-custom-menu-scope)
            // These are skin-rendered elements that declare their own panel scope.
            // node_id is resolved by walking up to the nearest [data-node-id] ancestor.
            const customMenuEl = target.closest('[data-hw-custom-menu-scope]');
            if (customMenuEl) {
                const scope = customMenuEl.getAttribute('data-hw-custom-menu-scope');
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
                const isNodeSelected = this.selectionState.selectedNodes.has(nodeId);
                const hasMultipleSelected = this.selectionState.selectedNodes.size > 1 || this.selectionState.selectedEdges.size > 0;
                
                if (isNodeSelected && hasMultipleSelected) {
                    this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                        clientX, clientY, canvasCoords.x, canvasCoords.y,
                        Array.from(this.selectionState.selectedNodes),
                        Array.from(this.selectionState.selectedEdges)
                    ));
                } else {
                    this.emitCanvasEvent(EventCreators.createContextMenuNode(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, nodeId
                    ));
                }
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

            // Store initial positions for all dragged elements
            this.dragState.startPositions.clear();
            this.dragState.draggedElements.forEach(element => {
                if (element.type === 'node') {
                    const nodeElement = element.element;
                    const currentLeft = parseInt(nodeElement.style.left) || 0;
                    const currentTop = parseInt(nodeElement.style.top) || 0;
                    this.dragState.startPositions.set(element.id, { x: currentLeft, y: currentTop });
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

            // Store the final delta values for the drag end event
            this.dragState.finalDeltaX = canvasDeltaX;
            this.dragState.finalDeltaY = canvasDeltaY;

            this.dragState.draggedElements.forEach(element => {
                if (element.type === 'node') {
                    const startPos = this.dragState.startPositions.get(element.id);
                    if (startPos) {
                        const newX = Math.max(0, Math.min(startPos.x + canvasDeltaX, this.canvasWidth - 100));
                        const newY = Math.max(0, Math.min(startPos.y + canvasDeltaY, this.canvasHeight - 100));

                        element.element.style.left = `${newX}px`;
                        element.element.style.top = `${newY}px`;
                        this._updateEdgesForNode(element.id);
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

                // Emit unified drag update event with final position
                this.emitCanvasEvent(EventCreators.createUserDragUpdate(
                    this._extractNodeIds(this.dragState.draggedElements),
                    this.dragState.finalDeltaX || 0,
                    this.dragState.finalDeltaY || 0
                ));

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
            this.dragState.draggedElements = [];
            this.dragState.startMousePos = { x: 0, y: 0 };
            this.dragState.startPositions.clear();
            this.dragState.dragOffset = { x: 0, y: 0 };
            this.dragState.hasActuallyMoved = false;
            this.dragState.mouseDownEvent = null;
            this.dragState.finalDeltaX = 0;
            this.dragState.finalDeltaY = 0;
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

        _handleElementSelection(isShiftClick, elementType, elementId) {
            console.log(`Element clicked: ${elementType}:${elementId}, shift: ${isShiftClick}`);

            if (isShiftClick) {
                // Toggle selection
                if (this._isElementSelected(elementType, elementId)) {
                    this._deSelectElement(elementType, elementId);
                } else {
                    this._selectElement(elementType, elementId, true);
                }
            } else {
                // Clear other selections and select this element
                this._clearSelection();
                this._selectElement(elementType, elementId, false);
            }

            // Emit unified selection change event
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

            console.log('🎯 Cleared all selections');
        },

        _emitSelectionChanged() {
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedEdges)
            ));
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

        /** Transition to active connection mode from a pin. */
        _enterActiveEdge(pin) {
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
            pin.style.transform = 'scale(1.8)';
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

            if (targetPin && this._isValidEdge(this.edgeDrag.anchorPin, targetPin)) {
                let sourceData = this.edgeDrag.anchorPin.dataset;
                let sinkData = targetPin.dataset;

                if (targetPin.dataset.pinDir === 'outlet') {
                    sinkData = this.edgeDrag.anchorPin.dataset;
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

            const startPos = this._getPinPosition(this.edgeDrag.anchorPin);
            const mousePos = this._transformScreenToSVG(e.clientX, e.clientY);
            const [dirX, dirY] = this._getPinDirectionVector(this.edgeDrag.anchorPin);

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
                if (pin === this.edgeDrag.anchorPin) return;
                if (pin.dataset.pinFlowType === 'ghost') return;

                const isValid = this._isValidEdge(this.edgeDrag.anchorPin, pin);

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
                        if (this.edgeDrag.anchorPin.dataset.pinDataType === pin.dataset.pinDataType) {
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

        _updateNodeVisualSelection(nodeId, selected) {
            const nodeElement = document.getElementById(nodeId);
            if (nodeElement) {
                if (selected) {
                    nodeElement.classList.add('node-selected');
                } else {
                    nodeElement.classList.remove('node-selected');
                }
            }
        },

        _updateEdgeVisualSelection(edge_id, selected) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (edgeInfo && edgeInfo.path) {
                if (selected) {
                    edgeInfo.path.classList.add('connection-selected');
                    edgeInfo.path.style.strokeWidth = '3';
                } else {
                    edgeInfo.path.classList.remove('connection-selected');
                    edgeInfo.path.style.strokeWidth = '2';
                }
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
            // Calculate control point distance based on connection length
            const distance = Math.abs(endPos.x - startPos.x);
            const controlDistance = Math.max(50, distance * 0.5);
            
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

[data-node-id]:hover {
    z-index: 1001 !important;
    cursor: grab;
}

[data-node-id].dragging-node {
    z-index: 1001 !important;
    cursor: grabbing !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15) !important;
    transform: translateZ(0);
}

[data-node-id]:active {
    cursor: grabbing;
}

[data-node-id].node-selected {
    z-index: 1000 !important;
    outline: none !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.25),
        0 0 20px rgba(74, 144, 226, 0.4),
        0 0 0 2px rgba(74, 144, 226, 0.3) !important;
}

[data-node-id].node-selected:hover {
    outline: none !important;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.3),
        0 0 25px rgba(74, 144, 226, 0.5),
        0 0 0 2px rgba(74, 144, 226, 0.4) !important;
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

.connection-pin:hover {
    transform: scale(1.4) !important;  
    filter: brightness(1.2) !important;
    z-index: 10001 !important;
}

.connection-pin.connection-valid {
    box-shadow: 0 0 15px #4CAF50 !important;
    border-color: #4CAF50 !important;
    z-index: 10002 !important;
}

.connection-pin.connection-invalid {
    transform: scale(0.8) !important; 
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

/* Edge state styles - UIEdge visual feedback */
/* Specific to SVG path elements only */
path.connection-invalid {
    filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.5));
}

path.connection-warning {
    filter: drop-shadow(0 0 4px rgba(245, 158, 11, 0.5));
}

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