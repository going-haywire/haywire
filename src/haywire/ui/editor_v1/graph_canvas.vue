<template>
    <div :id="containerId" ref="container" class="graph-canvas" :class="{
        dragging: connectionState.isDragging,
    }" tabindex="0" @click="handleCanvasClick" @contextmenu="handleContextMenu">
        <!-- Node container slot -->
        <div id="node-container" ref="nodeContainer" class="node-container" :style="nodeContainerTransform">
            <!-- Debug info to verify component is working -->
            <div class="debug-info" v-if="!connectionState.hasNodes">
                Canvas Ready - ID: {{ containerId }}
            </div>
            <slot></slot>
        </div>
        <!-- SVG layer for connections -->
        <svg id="connection-svg" ref="svg" class="connection-svg" :style="svgTransform">
            <defs ref="defs">
                <!-- Dynamic gradients will be added here -->
            </defs>
            <!-- Dynamic paths will be added here -->
        </svg>

    </div>
</template>

<script>
// Import auto-generated event system

export default {
    name: 'GraphCanvas',

    props: {
        containerId: { type: String, required: true }
        // Note: zoomState prop removed - zoom/pan is handled by CSS transforms in parent container
    },

    data() {
        return {
            connectionState: {
                isDragging: false,
                startPin: null,
                tempPath: null,
                hasNodes: false,
                lastDragEndTime: null
            },
            // Add node dragging state
            nodeDragState: {
                isDragging: false,
                draggedNode: null,
                startMousePos: { x: 0, y: 0 },
                startNodePos: { x: 0, y: 0 },
                dragOffset: { x: 0, y: 0 },
                hasActuallyMoved: false,
                dragThreshold: 5, // pixels - minimum movement to consider it a drag
                // Store event details for selection handling on mouse up
                mouseDownEvent: null
            },
            // Add selection state
            selectionState: {
                selectedNodes: new Set(),
                selectedConnections: new Set(),
                lastClickTime: 0,
                clickThreshold: 300 // ms to distinguish between click and drag
            },
            connectionPaths: new Map(), // path_id -> path_element
            updateConnectionsThrottled: false,
            resizeObserver: null,
            mutationObserver: null,
            // Store current zoom/pan state from the zoom container
            zoomState: {
                zoom: 1,
                panX: 0,
                panY: 0,
                isDragging: false
            }
        };
    }, computed: {
        svgTransform() {
            // No transformation needed - zoom container handles all transformations
            // This is just for coordinate calculations if needed
            return '';
        },

        nodeContainerTransform() {
            // No transformation needed - zoom container handles all transformations
            return '';
        }
    },


    // Note: No watcher for zoomState needed - zoom/pan is handled by CSS transforms
    // in the zoom container, so SVG paths don't need to be recalculated on zoom/pan changes

    watch: {
        // No watchers needed - connection management is handled through sync events
    },


    // =============================================================================
    // LIFECYCLE METHODS
    // =============================================================================

    mounted() {
        console.log('GraphCanvas Vue component mounted with container ID:', this.containerId);
        console.log('Container element:', this.$el);
        console.log('Container dimensions:', this.$el.offsetWidth, 'x', this.$el.offsetHeight);

        // TEST IF LIBRARY LOADED - ADD THIS
        console.log('🔍 Testing custom library import:');
        console.log('GraphEvents available:', typeof GraphEvents !== 'undefined');

        // Initialize component
        this._setupEventListeners();
        this._setupObservers();
        this._setupZoomPanListener();

        // Expose API to parent/Python
        this.$el._graphCanvasControls = {
            // Enhanced event system API
            handleSyncEvent: this.handleSyncEvent
        };
    },

    updated() {
        // Component updated - no longer needed for connections prop
    },

    beforeDestroy() {
        this._cleanupEventListeners();
        this._cleanupObservers();
        this._cleanupZoomPanListener();
    },

    methods: {
        // =============================================================================
        // SETUP & INITIALIZATION
        // =============================================================================

        _setupEventListeners() {
            // Mouse events for connection creation
            document.body.addEventListener('mousedown', this.handleMouseDown, true);
            document.body.addEventListener('mousemove', this.handleMouseMove, true);
            document.body.addEventListener('mouseup', this.handleMouseUp, true);
        },

        _setupObservers() {
            // Mutation observer for node position changes
            this.mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.attributeName === 'style') {
                        const nodeElement = mutation.target;
                        const nodeId = nodeElement.dataset.nodeId;

                        // Only process style changes on node containers, not on children
                        if (nodeId && nodeElement.hasAttribute('data-node-id')) {

                            // Only process if the style change actually includes position properties
                            const styleText = nodeElement.style.cssText;
                            if (styleText.includes('left:') || styleText.includes('top:') || styleText.includes('transform:')) {
                                this.updateConnectionsForNode(nodeId);
                            } 
                        }
                    }
                });
            });
        },

        _setupZoomPanListener() {
            // Listen for zoom/pan state changes from the zoom container
            this.handleZoomPanUpdate = (event) => {
                const { zoom, panX, panY, containerId, isDragging } = event.detail;

                // Update our local zoom state
                this.zoomState = { zoom, panX, panY, isDragging };
            };

            document.addEventListener('zoom-pan-state', this.handleZoomPanUpdate);
        },

        _setupHoverObserver(nodeElement) {
            const lodElement = nodeElement.querySelector('.zoom-pan-lod0');
            if (!lodElement) return;

            const nodeId = nodeElement.getAttribute('data-node-id');
            if (!nodeId) return;

            const scheduleConnectionUpdates = () => {
                this._scheduleConnectionUpdates(nodeId, nodeElement);
            };

            // Listen for transform transitions
            lodElement.addEventListener('transitionstart', (e) => {
                if (e.propertyName === 'transform') {
                    this._scheduleConnectionUpdates(nodeId, nodeElement);
                }
            });
           
            lodElement.addEventListener('mouseenter', scheduleConnectionUpdates);
            lodElement.addEventListener('mouseleave', scheduleConnectionUpdates);
        },

        _cleanupEventListeners() {
            document.body.removeEventListener('mousedown', this.handleMouseDown, true);
            document.body.removeEventListener('mousemove', this.handleMouseMove, true);
            document.body.removeEventListener('mouseup', this.handleMouseUp, true);
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
        },

        // =============================================================================
        // UNIFIED EVENT SYSTEM
        // =============================================================================

        /**
         * Emit unified canvas event to Python using the new event system
         */
        emitCanvasEvent(event) {
            // Only accept complete event objects from helper methods
            if (typeof event === 'object' && event.event_type) {
                console.log(`🚀 Vue→Python Event: ${event.event_type}`, event.data);
                this.$emit('canvasEvent', event);
            } else {
                console.error('emitCanvasEvent now only accepts event objects from EventCreators helper methods');
            }
        },

        /**
         * Handle sync events from Python
         */
        handleSyncEvent(syncEvent) {
            console.log(`🔄 Python→Vue Sync: ${syncEvent.event_type}`, syncEvent.data);
            
            const { event_type, data } = syncEvent;
            
            switch (event_type) {
                case GraphEvents.SyncCommands.SYNC_NODE_POSITION:
                    this._syncNodePosition(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CONNECTION_ADDITION:
                    this._syncConnectionAddition(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CONNECTION_REMOVAL:
                    this._syncConnectionRemoval(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_SELECTION_STATE:
                    this._syncSelectionState(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CANVAS_CLEAR:
                    this._syncCanvasClear();
                    break;
                
                // NEW: Individual selection events using auto-generated constants
                case GraphEvents.SyncCommands.SYNC_NODE_SELECTION:
                    this._syncNodeSelection(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CONNECTION_SELECTION:
                    this._syncConnectionSelection(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CLEAR_ALL_SELECTIONS:
                    this._syncClearAllSelections();
                    break;
                
                // NEW: Node observer events using auto-generated constants
                case GraphEvents.SyncCommands.SYNC_NODE_OBSERVER_ADD:
                    this._syncNodeObserverAdd(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_NODE_OBSERVER_REMOVE:
                    this._syncNodeObserverRemove(data);
                    break;
                
                // NEW: Connection update events using auto-generated constants
                case GraphEvents.SyncCommands.SYNC_CONNECTIONS_UPDATE:
                    this._syncConnectionsUpdate(data);
                    break;
                
                default:
                    console.warn(`Unknown sync event: ${event_type}`);
            }
        },

        // Sync event handlers
        _syncNodePosition(data) {
            const { nodeId, position } = data;
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                this.updateConnectionsForNode(nodeId);
            }
        },

        _syncConnectionAddition(data) {
            const { connectionId, outputNodeId, outletPinId, inputNodeId, inletPinId, isValid } = data;
            console.log('🔗 Vue _syncConnectionAddition called with:', data);
            

            // Check if path already exists
            if (this.connectionPaths.has(pathId)) {
                if (path.dataset.isValid === String(isValid)) {
                    console.log(`🔗 Vue connection already exists and is valid:`, pathId);
                    return;
                } else {
                    // Remove existing path to replace with new validity state
                    console.log(`🔗 Vue connection exists but validity changed, replacing:`, pathId);
                    this._removeConnectionVisual(connectionId);
                }
            }

            // Create connection visual directly
            const result = this._createConnectionVisual(
                outputNodeId, 
                outletPinId, 
                inputNodeId, 
                inletPinId, 
                connectionId, 
                isValid,
                '[SYNC] '
            );
            
            if (result.success) {
                console.log('🔗 Vue ✅ Connection added via sync:', connectionId);
            } else {
                console.error('🔗 Vue ❌ Failed to add connection via sync:', connectionId);
            }
        },

        _syncConnectionRemoval(data) {
            const { connectionId } = data;
            console.log('🔗 Vue _syncConnectionRemoval called with:', connectionId);
            
            const success = this._removeConnectionVisual(connectionId);
            
            if (success) {
                console.log('🔗 Vue ✅ Connection removed via sync:', connectionId);
            } else {
                console.error('🔗 Vue ❌ Failed to remove connection via sync:', connectionId);
            }
        },

        _syncSelectionState(data) {
            const { selectedNodes, selectedConnections, action } = data;
            if (action === 'clear') {
                this.clearSelection();
            } else {
                this._setSelectionState(selectedNodes, selectedConnections);
            }
        },

        _syncCanvasClear() {
            console.log('🔗 Vue _syncCanvasClear called');
            
            // Clear all connections
            this.connectionPaths.forEach((path, pathId) => {
                path.remove();
                // Also remove hit areas and gradients
                const hitArea = document.getElementById(pathId + '_hitarea');
                if (hitArea) hitArea.remove();
                const gradient = document.getElementById(`gradient_${pathId}`);
                if (gradient) gradient.remove();
            });
            
            this.connectionPaths.clear();
            
            // Clear any SVG paths that might be left over
            const svg = this.$refs.svg;
            const paths = svg.querySelectorAll('path');
            paths.forEach(path => path.remove());
            
            // Clear selection
            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedConnections.clear();
            
            console.log('🔗 Vue ✅ Canvas cleared via sync');
        },

        // NEW: Individual selection sync handlers
        _syncNodeSelection(data) {
            const { nodeId, selected, multiSelect } = data;
            console.log(`🎯 Vue _syncNodeSelection: ${nodeId}, selected: ${selected}, multi: ${multiSelect}`);
            
            if (selected) {
                this.selectNode(nodeId, multiSelect);
            } else {
                this.deselectNode(nodeId);
            }
        },

        _syncConnectionSelection(data) {
            const { connectionId, selected, multiSelect } = data;
            console.log(`🎯 Vue _syncConnectionSelection: ${connectionId}, selected: ${selected}, multi: ${multiSelect}`);
            
            if (selected) {
                this.selectConnection(connectionId, multiSelect);
            } else {
                this.deselectConnection(connectionId);
            }
        },

        _syncClearAllSelections() {
            console.log('🎯 Vue _syncClearAllSelections');
            this.clearSelection();
        },

        // NEW: Node observer sync handlers
        _syncNodeObserverAdd(data) {
            const { nodeId } = data;
            console.log(`👁️ Vue _syncNodeObserverAdd: ${nodeId}`);
            this.addNodeObserver(nodeId);
        },

        _syncNodeObserverRemove(data) {
            const { nodeId } = data;
            console.log(`👁️ Vue _syncNodeObserverRemove: ${nodeId}`);
            this.removeNodeObserver(nodeId);
        },

        // NEW: Connection update sync handler
        _syncConnectionsUpdate(data) {
            const { nodeId } = data;
            console.log(`🔄 Vue _syncConnectionsUpdate: ${nodeId}`);
            this.updateConnectionsForNode(nodeId);
        },

        _setSelectionState(selectedNodes, selectedConnections) {
            // Clear current selection visually
            this.clearSelection();
            
            // Apply new selection
            selectedNodes.forEach(nodeId => this.selectNode(nodeId, true));
            selectedConnections.forEach(connectionId => this.selectConnection(connectionId, true));
        },

        // =============================================================================
        // PRIMARY EVENT HANDLERS
        // =============================================================================

        handleMouseDown(e) {
            // Skip node selection/dragging for right-clicks and two-finger clicks
            // These will be handled by the contextmenu event instead
            if (e.button === 2) { // Right mouse button or two-finger click
                return;
            }
            
            // Store click time for distinguishing clicks from drags
            const clickTime = Date.now();
            this.selectionState.lastClickTime = clickTime;

            // Check for connection pin first
            const pin = e.target.closest('.connection-pin');
            if (pin) {
                this._startConnectionDrag(e, pin);
                return;
            }

            // Check if clicking on interactive widget elements - avoid dragging if so
            const isInteractiveWidget = this._isInteractiveWidgetElement(e.target);
            if (isInteractiveWidget) {
                console.log('Click on interactive widget element - skipping node drag');
                return; // Let the widget handle its own interaction
            }

            // Check for node dragging/selection - look for node container
            const nodeElement = e.target.closest('[data-node-id]');
            if (nodeElement && !e.target.closest('.connection-pin')) {
                const nodeId = nodeElement.dataset.nodeId;
                if (nodeId) {
                    // Don't handle selection on mouse down anymore - defer to mouse up
                    // Store the event details for selection handling later
                    this._startNodeDrag(e, nodeElement);
                    return;
                }
            }
        },

        handleMouseMove(e) {
            // Handle connection dragging
            if (this.connectionState.isDragging && this.connectionState.tempPath) {
                this._handleConnectionDragMove(e);
                return;
            }

            // Handle node dragging
            if (this.nodeDragState.isDragging && this.nodeDragState.draggedNode) {
                this._handleNodeDragMove(e);
                return;
            }
        },

        handleMouseUp(e) {
            // Handle connection drag end
            if (this.connectionState.isDragging) {
                this._handleConnectionDragEnd(e);
                return;
            }

            // Handle node drag end
            if (this.nodeDragState.isDragging) {
                this._handleNodeDragEnd(e);
                return;
            }
        },

        handleCanvasClick(event) {
            // Prevent context menu handling if this was a context click
            if (event.button === 2 || event.which === 3) {
                return;
            }

            console.log('Canvas click event target:', event.target.tagName, event.target.id);

            // Don't handle clicks on SVG path elements (connections)
            if (event.target.tagName === 'path') {
                console.log('Click on SVG path - letting it handle its own click');
                return;
            }

            // Don't handle clicks on connection pins
            if (event.target.closest('.connection-pin')) {
                console.log('Click on connection pin - letting it handle its own click');
                return;
            }

            // Don't handle clicks on nodes (they have their own selection handling)
            if (event.target.closest('[data-node-id]')) {
                console.log('Click on node - letting it handle its own click');
                return;
            }

            // Only handle clicks on the canvas itself or empty space
            if (event.target === this.$el ||
                event.target === this.$refs.nodeContainer ||
                event.target === this.$refs.svg ||
                event.target.classList.contains('graph-canvas')) {

                console.log('Click on empty canvas - clearing selection');

                // Clear selection when clicking on empty canvas
                this.clearSelection();

                // Emit selection change event to Python for history tracking using new unified system
                this.emitCanvasEvent(EventCreators.createSelectionChanged([], []));

                // Note: Canvas click event can be removed as it's not part of the core event system
                // If needed, it can be added as a separate event type
            }
        },

        handleContextMenu(event) {
            event.preventDefault(); // Prevent browser context menu

            // Allow context menu on natural right-click or two-finger click (Mac trackpad)
            // This provides intuitive interaction without requiring modifier keys
            // Context menu will appear for: right-click, two-finger click, or Ctrl+click

            // Check if Ctrl key is pressed (Cmd key on Mac)
            /*
            const isCtrlPressed = event.ctrlKey || event.metaKey;
            if (!isCtrlPressed) {
                return; // Only show context menu when Ctrl is pressed
            }
            */

            const clientX = event.clientX;
            const clientY = event.clientY;

            console.log('Context menu event on:', event.target.tagName, event.target);

            // Determine what was clicked
            const target = event.target;

            // Check for node first
            const nodeElement = target.closest('[data-node-id]');

            // Check for connection (SVG path)
            let connectionElement = null;
            let connectionId = null;

            if (target.tagName === 'path') {
                // Direct click on SVG path
                connectionId = target.getAttribute('data-connection-id') || target.id;
                connectionElement = target;
                console.log('Direct path click, connection ID:', connectionId);
            } else {
                // Check if we're inside an SVG and there's a path nearby
                const svgElement = target.closest('svg');
                if (svgElement) {
                    // Find all paths in the SVG and check if click is near any of them
                    const paths = svgElement.querySelectorAll('path[data-connection-id]');
                    const clickPoint = { x: clientX, y: clientY };

                    for (const path of paths) {
                        if (this.isPointNearPath(path, clickPoint)) {
                            connectionElement = path;
                            connectionId = path.getAttribute('data-connection-id') || path.id;
                            console.log('Found nearby path, connection ID:', connectionId);
                            break;
                        }
                    }
                }
            }

            if (nodeElement) {
                // Context menu for node
                const nodeId = nodeElement.dataset.nodeId;
                console.log(`🎯 Context menu for node: ${nodeId}`);
                
                // Convert screen coordinates to canvas coordinates
                const canvasCoords = this._transformScreenToSVG(clientX, clientY);
                
                this.emitCanvasEvent(EventCreators.createContextMenuNode(
                    clientX, clientY, canvasCoords.x, canvasCoords.y, nodeId
                ));
            } else if (connectionElement && connectionId) {
                // Context menu for connection
                console.log(`🎯 Context menu for connection: ${connectionId}`);
                
                // Convert screen coordinates to canvas coordinates
                const canvasCoords = this._transformScreenToSVG(clientX, clientY);
                
                this.emitCanvasEvent(EventCreators.createContextMenuConnection(
                    clientX, clientY, canvasCoords.x, canvasCoords.y, connectionId
                ));
            } else {
                // Context menu for canvas (empty space)
                console.log(`🎯 Context menu for canvas`);

                // Convert screen coordinates to canvas coordinates for node creation
                const canvasCoords = this._transformScreenToSVG(clientX, clientY);

                this.emitCanvasEvent(EventCreators.createContextMenuCanvas(
                    clientX, clientY, canvasCoords.x, canvasCoords.y
                ));
            }
        },

        // Helper method to check if a point is near a path
        isPointNearPath(pathElement, point) {
            try {
                const rect = pathElement.getBoundingClientRect();
                const tolerance = 10; // pixels

                return point.x >= rect.left - tolerance &&
                    point.x <= rect.right + tolerance &&
                    point.y >= rect.top - tolerance &&
                    point.y <= rect.bottom + tolerance;
            } catch (e) {
                console.warn('Error checking point near path:', e);
                return false;
            }
        },

        // =============================================================================
        // CONNECTION DRAG SYSTEM
        // =============================================================================

        _startConnectionDrag(e, pin) {
            e.preventDefault();
            e.stopPropagation();

            this.connectionState.isDragging = true;
            this.connectionState.startPin = pin;

            const startPos = this._getPinPosition(pin);
            const offsetDir = pin.dataset.pinDir === 'inlet' ? -1 : 1;
            const pinColor = pin.dataset.pinColor || '#000000';

            // Create temporary path
            this.connectionState.tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const initialPath = this._createBezierPath(startPos, startPos, offsetDir);

            this.connectionState.tempPath.setAttribute('d', initialPath);
            this.connectionState.tempPath.setAttribute('stroke', pinColor);
            this.connectionState.tempPath.setAttribute('stroke-width', '2');
            this.connectionState.tempPath.setAttribute('fill', 'none');
            this.connectionState.tempPath.setAttribute('stroke-dasharray', '4');
            this.connectionState.tempPath.style.pointerEvents = 'none';

            this.$refs.svg.appendChild(this.connectionState.tempPath);

            // Visual feedback on start pin
            pin.style.boxShadow = '0 0 15px #4A90E2';
            pin.style.transform = 'scale(1.8)';
            pin.style.zIndex = '10003';
        },

        _handleConnectionDragMove(e) {
            const startPos = this._getPinPosition(this.connectionState.startPin);
            const mousePos = this._transformScreenToSVG(e.clientX, e.clientY);
            const offsetDir = this.connectionState.startPin.dataset.pinDir === 'inlet' ? -1 : 1;

            const pathData = this._createBezierPath(startPos, mousePos, offsetDir);
            this.connectionState.tempPath.setAttribute('d', pathData);

            // Highlight valid drop targets
            const targetPin = e.target.closest('.connection-pin');
            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid');
                if (pin !== this.connectionState.startPin) {
                    if (targetPin === pin) {
                        if (this._isValidConnection(this.connectionState.startPin, pin)) {
                            pin.classList.add('connection-valid');
                        } else {
                            pin.classList.add('connection-invalid');
                        }
                    }
                }
            });
        },

        _handleConnectionDragEnd(e) {
            const endPin = e.target.closest('.connection-pin');

            // Cleanup temporary visual elements
            if (this.connectionState.tempPath) {
                this.connectionState.tempPath.remove();
                this.connectionState.tempPath = null;
            }

            if (this.connectionState.startPin) {
                this.connectionState.startPin.style.boxShadow = '';
                this.connectionState.startPin.style.transform = '';
                this.connectionState.startPin.style.zIndex = '';
            }

            // Clear highlighting
            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid');
            });

            // Create connection if valid
            if (endPin && this._isValidConnection(this.connectionState.startPin, endPin)) {
                let startData = this.connectionState.startPin.dataset;
                let endData = endPin.dataset;

                // Maintain outlet->inlet convention
                if (endPin.dataset.pinDir === 'outlet') {
                    endData = this.connectionState.startPin.dataset;
                    startData = endPin.dataset;
                }

                // Emit connection created event using new unified system
                this.emitCanvasEvent(EventCreators.createConnectionCreated(
                    startData.nodeId, startData.pinId, endData.nodeId, endData.pinId
                ));
            }

            // Reset state
            this.connectionState.isDragging = false;
            this.connectionState.startPin = null;
            this.connectionState.lastDragEndTime = Date.now(); // Track when drag ended
        },

        // =============================================================================
        // NODE DRAG SYSTEM
        // =============================================================================

        _startNodeDrag(e, nodeElement) {
            e.preventDefault();
            e.stopPropagation();

            console.log('Preparing node drag for:', nodeElement.dataset.nodeId);

            this.nodeDragState.isDragging = true;
            this.nodeDragState.draggedNode = nodeElement;
            this.nodeDragState.startMousePos = { x: e.clientX, y: e.clientY };
            this.nodeDragState.hasActuallyMoved = false;

            // Store the mouse down event details for selection handling on mouse up
            this.nodeDragState.mouseDownEvent = {
                ctrlKey: e.ctrlKey,
                metaKey: e.metaKey,
                nodeId: nodeElement.dataset.nodeId
            };

            // Get current node position from style
            const computedStyle = nodeElement.style;
            const currentLeft = parseInt(computedStyle.left) || 0;
            const currentTop = parseInt(computedStyle.top) || 0;
            this.nodeDragState.startNodePos = { x: currentLeft, y: currentTop };

            // Calculate drag offset
            this.nodeDragState.dragOffset = {
                x: e.clientX - currentLeft,
                y: e.clientY - currentTop
            };

            // Don't emit drag start yet - wait for actual movement
            // Don't add visual feedback yet - wait for actual movement
        },

        _handleNodeDragMove(e) {
            const nodeElement = this.nodeDragState.draggedNode;
            const nodeId = nodeElement.dataset.nodeId;

            // Calculate mouse movement
            const mouseDeltaX = e.clientX - this.nodeDragState.startMousePos.x;
            const mouseDeltaY = e.clientY - this.nodeDragState.startMousePos.y;

            // Check if we've moved enough to be considered a drag
            const distance = Math.sqrt(mouseDeltaX * mouseDeltaX + mouseDeltaY * mouseDeltaY);

            if (!this.nodeDragState.hasActuallyMoved && distance > this.nodeDragState.dragThreshold) {
                // First time we've moved enough - this is when drag actually starts
                this.nodeDragState.hasActuallyMoved = true;

                console.log('Starting actual node drag for:', nodeId);

                // Add visual feedback now
                nodeElement.style.cursor = 'grabbing';
                nodeElement.style.zIndex = '1000';
                nodeElement.classList.add('dragging-node');

                // Emit drag start event to add fence for undo grouping using new unified system
                this.emitCanvasEvent(EventCreators.createNodeDragStart(nodeId));

                console.log('Node drag started:', {
                    nodeId: nodeId,
                    startPos: this.nodeDragState.startNodePos,
                    mousePos: this.nodeDragState.startMousePos,
                    offset: this.nodeDragState.dragOffset
                });
            }

            // Only proceed with position updates if we're actually dragging
            if (!this.nodeDragState.hasActuallyMoved) {
                return;
            }

            // Adjust for zoom level - divide by zoom to get correct canvas coordinates
            const zoomFactor = this.zoomState.zoom || 1;
            const canvasDeltaX = mouseDeltaX / zoomFactor;
            const canvasDeltaY = mouseDeltaY / zoomFactor;

            // Calculate new position relative to start position
            const newX = this.nodeDragState.startNodePos.x + canvasDeltaX;
            const newY = this.nodeDragState.startNodePos.y + canvasDeltaY;

            // Apply constraints to keep node within canvas bounds
            const constrainedX = Math.max(0, Math.min(newX, 7500)); // Leave some margin
            const constrainedY = Math.max(0, Math.min(newY, 7500));

            // Update node position
            nodeElement.style.left = `${constrainedX}px`;
            nodeElement.style.top = `${constrainedY}px`;

            // Update connections immediately for smooth dragging
            this.updateConnectionsForNode(nodeId);

            //console.log(`Node ${nodeId} dragged to: (${constrainedX}, ${constrainedY}) [zoom: ${zoomFactor}]`);
        },

        _handleNodeDragEnd(e) {
            const nodeElement = this.nodeDragState.draggedNode;
            const nodeId = nodeElement.dataset.nodeId;

            console.log('Ending node interaction for:', nodeId, 'hasActuallyMoved:', this.nodeDragState.hasActuallyMoved);

            // Get final position
            const finalX = parseInt(nodeElement.style.left) || 0;
            const finalY = parseInt(nodeElement.style.top) || 0;

            // Check if position actually changed from start
            const startX = this.nodeDragState.startNodePos.x;
            const startY = this.nodeDragState.startNodePos.y;
            const positionChanged = (finalX !== startX || finalY !== startY);

            // Remove visual feedback (if any was added)
            nodeElement.style.cursor = 'grab';
            nodeElement.style.zIndex = '100';
            nodeElement.classList.remove('dragging-node');

            // Only emit events if we actually dragged (moved beyond threshold)
            if (this.nodeDragState.hasActuallyMoved) {
                // Only emit position change if the position actually changed
                if (positionChanged) {
                    // Emit position change event to Python using new unified system
                    this.emitCanvasEvent(EventCreators.createNodePositionChanged(
                        nodeId, { x: finalX, y: finalY }
                    ));

                    console.log(`Node ${nodeId} drag ended with position change: (${startX}, ${startY}) -> (${finalX}, ${finalY})`);
                } else {
                    console.log(`Node ${nodeId} drag ended with no position change: (${finalX}, ${finalY})`);
                }

                // Emit drag end event to close fence for undo grouping using new unified system
                this.emitCanvasEvent(EventCreators.createNodeDragEnd(
                    nodeId, positionChanged
                ));
            } else {
                // This was just a click, not a drag - handle as selection now
                console.log(`Node ${nodeId} was clicked (not dragged) - handling selection`);

                // Handle selection using stored event details
                if (this.nodeDragState.mouseDownEvent) {
                    const mockEvent = {
                        ctrlKey: this.nodeDragState.mouseDownEvent.ctrlKey,
                        metaKey: this.nodeDragState.mouseDownEvent.metaKey
                    };
                    this._handleNodeSelection(mockEvent, nodeId);
                }
            }

            // Reset drag state
            this.nodeDragState.isDragging = false;
            this.nodeDragState.draggedNode = null;
            this.nodeDragState.startMousePos = { x: 0, y: 0 };
            this.nodeDragState.startNodePos = { x: 0, y: 0 };
            this.nodeDragState.dragOffset = { x: 0, y: 0 };
            this.nodeDragState.hasActuallyMoved = false;
            this.nodeDragState.mouseDownEvent = null;
        },

        // =============================================================================
        // CONNECTION MANAGEMENT - INTERNAL
        // =============================================================================

        // Shared internal method for creating connection visuals
        _createConnectionVisual(outputNodeId, outletPinId, inputNodeId, inletPinId, pathId, isValid, logPrefix = '', connectionData = null) {
            // Generate pin IDs using utility functions
            const startPinId = this._buildOutletPinId(outputNodeId, outletPinId);
            const endPinId = this._buildInletPinId(inputNodeId, inletPinId);

            console.log(`${logPrefix}Looking for pins:`, { startPinId, endPinId, pathId });

            const startPin = document.getElementById(startPinId);
            const endPin = document.getElementById(endPinId);

            if (!startPin || !endPin) {
                console.error(`🔗 Vue${logPrefix} could not find pins:`, {
                    startPinId: startPinId,
                    endPinId: endPinId,
                    startPinExists: !!startPin,
                    endPinExists: !!endPin
                });

                return { success: false, pathElement: null };
            }
            
            // Create SVG path element
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.dataset.isValid = isValid.toString();
            path.setAttribute('id', pathId);
            path.setAttribute('data-connection-id', pathId); 
            if (isValid) {
                path.setAttribute('stroke', pinColor); 
                path.dataset.startColor = startPin.dataset.pinColor || '#bbbbbb';
                path.dataset.endColor = endPin.dataset.pinColor || '#333333';
            } else {
                path.setAttribute('stroke', '#FF0000'); 
                path.setAttribute('stroke-dasharray', '2');
                path.dataset.startColor = '#FF0000';
                path.dataset.endColor = '#990000';
            }
            path.setAttribute('stroke-width', '2');
            path.setAttribute('fill', 'none');
            path.style.pointerEvents = 'stroke';
            path.style.cursor = 'pointer';

            // Add invisible thicker path for easier clicking/context menu
            const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            hitArea.setAttribute('id', pathId + '_hitarea');
            hitArea.setAttribute('data-connection-id', pathId); // Same connection ID
            hitArea.setAttribute('stroke', 'transparent');
            hitArea.setAttribute('stroke-width', '10'); // Much thicker for easier interaction
            hitArea.setAttribute('fill', 'none');
            hitArea.style.pointerEvents = 'stroke';
            hitArea.style.cursor = 'pointer';

            this.$refs.svg.appendChild(path);
            this.$refs.svg.appendChild(hitArea); // Add hit area after visible path
            this.connectionPaths.set(pathId, path);

            // Add click event to both visible path and hit area
            const clickHandler = (e) => {
                console.log(`🔗 Connection path clicked${logPrefix}!`, pathId);
                e.preventDefault();
                e.stopPropagation();
                this._handleConnectionSelection(e, pathId);

                // Emit connection-clicked event using new unified system
                this.emitCanvasEvent(EventCreators.createConnectionClicked(pathId));
            };

            path.addEventListener('click', clickHandler);
            hitArea.addEventListener('click', clickHandler);

            // Update path after a brief delay to ensure nodes are rendered
            this.$nextTick(() => {
                this.updateConnectionPath(path);
            });

            return { success: true, pathElement: path };
        },

        // Internal method to remove connection visual (used by sync events)
        _removeConnectionVisual(connectionId) {
            // Use the connection ID to find the path
            const path = this.connectionPaths.get(connectionId);

            if (path) {
                path.remove();

                // Also remove the invisible hit area
                const hitArea = document.getElementById(connectionId + '_hitarea');
                if (hitArea) {
                    hitArea.remove();
                }

                // Also remove any associated gradient
                const gradient = document.getElementById(`gradient_${connectionId}`);
                if (gradient) {
                    gradient.remove();
                }

                this.connectionPaths.delete(connectionId);
                console.log('🔗 Vue (internal) removed path element:', connectionId);
                return true;
            } else {
                console.log('🔗 Vue (internal) path not found for removal:', connectionId);
                return false;
            }
        },

        // =============================================================================
        // CONNECTION MANAGEMENT - PUBLIC API
        // =============================================================================

        updateConnectionPath(pathElement) {
            if (!pathElement || !pathElement.id) return;

            const pathId = pathElement.id;
            const connectionInfo = this._parseConnectionId(pathId);

            if (!connectionInfo) {
                console.error(`Failed to parse connection ID: ${pathId}`);
                return;
            }

            const startPin = document.getElementById(connectionInfo.outletPinFullId);
            const endPin = document.getElementById(connectionInfo.inletPinFullId);

            if (!startPin || !endPin) {
                console.error(`Failed to find pins for connection ID: ${pathId}`);
                return;
            }

            const startPos = this._getPinPosition(startPin);
            const endPos = this._getPinPosition(endPin);

            const controlOffset = Math.abs(endPos.x - startPos.x) * 0.5;
            const pathData = `M ${startPos.x} ${startPos.y} C ${startPos.x + controlOffset} ${startPos.y}, ${endPos.x - controlOffset} ${endPos.y}, ${endPos.x} ${endPos.y}`;

            pathElement.setAttribute('d', pathData);
            // Also update the hit area if it exists
            const hitArea = document.getElementById(pathId + '_hitarea');
            if (hitArea) {
                hitArea.setAttribute('d', pathData);
            }

            const isValid = pathElement.dataset.isValid === 'true';

            let startColor = pathElement.dataset.startColor || '#000000';
            let endColor = pathElement.dataset.endColor || '#000000';

            // Update stroke with gradient
            const stroke = this._createBezierStroke(startPos, endPos, startColor, endColor, pathId);

            pathElement.setAttribute('stroke', stroke);

        },

        updateAllConnections() {
            if (this.updateConnectionsThrottled) return;
            this.updateConnectionsThrottled = true;

            requestAnimationFrame(() => {
                this.connectionPaths.forEach(path => {
                    this.updateConnectionPath(path);
                });

                // Reset throttle
                setTimeout(() => {
                    this.updateConnectionsThrottled = false;
                }, 16); // ~60fps
            });
        },

        updateConnectionsForNode(nodeId) {
            if (!nodeId) return;

            // Find all paths connected to this node
            this.connectionPaths.forEach((path, pathId) => {
                if (pathId.includes(nodeId)) {
                    this.updateConnectionPath(path);
                }
            });
        },

        // =============================================================================
        // NODE OBSERVER SYSTEM
        // =============================================================================

        addNodeObserver(nodeId) {
            if (!this.mutationObserver || !nodeId) return;

            // Function to attempt adding the observer
            const attemptAddObserver = (retryCount = 0) => {
                const nodeElement = document.getElementById(nodeId);
                if (nodeElement) {
                    console.log(`[GraphCanvas] Adding observer for node ${nodeId}`, nodeElement);

                    // Setup hover observers for LOD and onhover animations
                    this._setupHoverObserver(nodeElement);
                } else if (retryCount < 3) {
                    // Retry after a short delay (up to 3 times)
                    setTimeout(() => attemptAddObserver(retryCount + 1), 100);
                } else {
                    console.warn(`[GraphCanvas] Node element with ID ${nodeId} not found after 3 retries. Unable to observe.`);
                }
            };

            // Start the attempt
            attemptAddObserver();
        },

        removeNodeObserver(nodeId) {
            if (!nodeId) return;

            // Find the node element by ID
            const nodeElement = document.getElementById(nodeId);
            if (nodeElement) {
                console.log(`[GraphCanvas] Removing observer for node ${nodeId}`);
                // Note: MutationObserver doesn't have a way to unobserve specific elements
                // This would require tracking observed elements separately if needed
                // For now, we just log the removal
            } else {
                console.warn(`[GraphCanvas] Node element with ID ${nodeId} not found for removal`);
            }
        },

        _emitNodePositionChanged(nodeElement, nodeId) {
            // Don't emit position changes when dragging connections to avoid interference
            if (this.connectionState.isDragging) {
                console.log(`🚫 Skipping node position change for ${nodeId} during connection drag`);
                return;
            }

            // Don't emit during active node dragging (we handle this in _handleNodeDragEnd)
            if (this.nodeDragState.isDragging && this.nodeDragState.draggedNode === nodeElement) {
                console.log(`🚫 Skipping node position change for ${nodeId} during node drag - will emit on drag end`);
                return;
            }

            // Also skip if we recently finished a connection drag (timing protection)
            const now = Date.now();
            if (this.connectionState.lastDragEndTime && (now - this.connectionState.lastDragEndTime) < 500) {
                console.log(`🚫 Skipping node position change for ${nodeId} - too soon after connection drag end`);
                return;
            }

            // Debounce position change notifications
            clearTimeout(nodeElement._positionTimer);
            nodeElement._positionTimer = setTimeout(() => {
                const rect = nodeElement.getBoundingClientRect();
                const containerRect = this.$refs.nodeContainer.getBoundingClientRect();
                const relativeX = rect.left - containerRect.left;
                const relativeY = rect.top - containerRect.top;

                // Debug position calculation
                const style = nodeElement.style;
                const styleLeft = parseInt(style.left) || 0;
                const styleTop = parseInt(style.top) || 0;

                // Validate position - skip if it's (0,0) and we have no good reason for it to be there
                if (styleLeft === 0 && styleTop === 0) {
                    console.log(`⚠️ Warning: Node ${nodeId} position is (0,0) - this might be erroneous. Skipping position update.`);
                    return;
                }

                // Use the style position directly instead of calculated position
                // as it's more reliable for absolute positioned elements
                this.emitCanvasEvent(EventCreators.createNodePositionChanged(
                    nodeId, { x: styleLeft, y: styleTop }
                ));
            }, 100);
        },

        // =============================================================================
        // SELECTION SYSTEM
        // =============================================================================

        clearSelection() {
            // Store previously selected nodes for connection updates
            const previouslySelectedNodes = Array.from(this.selectionState.selectedNodes);

            // Clear visual selection for all nodes
            this.selectionState.selectedNodes.forEach(nodeId => {
                this._updateNodeVisualSelection(nodeId, false);
            });

            // Clear visual selection for all connections
            this.selectionState.selectedConnections.forEach(pathId => {
                this._updateConnectionVisualSelection(pathId, false);
            });

            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedConnections.clear();

            // Schedule smooth connection updates for all previously selected nodes during fold animation
            previouslySelectedNodes.forEach(nodeId => {
                this._scheduleConnectionUpdates(nodeId, null, 300); // 300ms matches CSS transition
            });

            console.log('🎯 Cleared all selections');
        },

        getSelection() {
            return {
                selectedNodes: Array.from(this.selectionState.selectedNodes),
                selectedConnections: Array.from(this.selectionState.selectedConnections)
            };
        },

        setSelection(selection) {
            this.clearSelection();

            if (selection.selectedNodes) {
                selection.selectedNodes.forEach(nodeId => {
                    this.selectNode(nodeId, true);
                });
            }

            if (selection.selectedConnections) {
                selection.selectedConnections.forEach(pathId => {
                    this.selectConnection(pathId, true);
                });
            }
        },

        // =============================================================================
        // NODE SELECTION SYSTEM
        // =============================================================================

        // Selection Management Methods
        _handleNodeSelection(e, nodeId) {
            const multiSelect = e.ctrlKey || e.metaKey;

            if (multiSelect) {
                // Toggle selection
                if (this.selectionState.selectedNodes.has(nodeId)) {
                    this.deselectNode(nodeId);
                } else {
                    this.selectNode(nodeId, true);
                }
            } else {
                // Clear other selections and select this node
                this.clearSelection();
                this.selectNode(nodeId, false);
            }

            // Emit selection change to Python using new unified system
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedConnections)
            ));
        },

        selectNode(nodeId, multiSelect = false) {
            if (!multiSelect) {
                this.clearSelection();
            }

            this.selectionState.selectedNodes.add(nodeId);
            this._updateNodeVisualSelection(nodeId, true);

            // Schedule smooth connection updates during fold/unfold animation
            this._scheduleConnectionUpdates(nodeId, null, 300); // 300ms matches CSS transition

            console.log(`🎯 Selected node: ${nodeId}`);
        },

        deselectNode(nodeId) {
            this.selectionState.selectedNodes.delete(nodeId);
            this._updateNodeVisualSelection(nodeId, false);

            // Schedule smooth connection updates during fold/unfold animation
            this._scheduleConnectionUpdates(nodeId, null, 300); // 300ms matches CSS transition

            console.log(`🎯 Deselected node: ${nodeId}`);
        },

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

        // =============================================================================
        // CONNECTION SELECTION SYSTEM
        // =============================================================================

        _handleConnectionSelection(e, pathId) {
            console.log('🎯 _handleConnectionSelection called with pathId:', pathId);
            e.preventDefault();
            const multiSelect = e.ctrlKey || e.metaKey;

            if (multiSelect) {
                // Toggle selection
                if (this.selectionState.selectedConnections.has(pathId)) {
                    this.deselectConnection(pathId);
                } else {
                    this.selectConnection(pathId, true);
                }
            } else {
                // Clear other selections and select this connection
                this.clearSelection();
                this.selectConnection(pathId, false);
            }

            // Emit selection change to Python using new unified system
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedConnections)
            ));
        },

        selectConnection(pathId, multiSelect = false) {
            if (!multiSelect) {
                this.clearSelection();
            }

            this.selectionState.selectedConnections.add(pathId);
            this._updateConnectionVisualSelection(pathId, true);

            console.log(`🎯 Selected connection: ${pathId}`);
        },

        deselectConnection(pathId) {
            this.selectionState.selectedConnections.delete(pathId);
            this._updateConnectionVisualSelection(pathId, false);

            console.log(`🎯 Deselected connection: ${pathId}`);
        },

        _updateConnectionVisualSelection(pathId, selected) {
            console.log('🎨 _updateConnectionVisualSelection called:', { pathId, selected });
            const pathElement = this.connectionPaths.get(pathId);
            if (pathElement) {
                if (selected) {
                    pathElement.classList.add('connection-selected');
                    pathElement.style.strokeWidth = '3';
                } else {
                    pathElement.classList.remove('connection-selected');
                    pathElement.style.strokeWidth = '2';
                }
            } else {
                console.warn('🎨 Path element not found in connectionPaths map for pathId:', pathId);
            }
        },

        // =============================================================================
        // UTILITY & HELPER METHODS
        // =============================================================================

        // Interactive Widget Detection
        _isInteractiveWidgetElement(element) {
            /**
             * Check if the clicked element is an interactive widget that should not trigger node dragging.
             * This includes input fields, buttons, sliders, checkboxes, etc.
             */

            // Check for basic form controls and interactive elements
            const isFormElement = element.matches('input, textarea, select, button, [contenteditable]') ||
                element.closest('input, textarea, select, button, [contenteditable]');

            // Check for NiceGUI/Quasar specific elements
            const isQuasarElement = element.closest('.q-field, .q-btn, .q-checkbox, .q-radio, .q-toggle, .q-slider, .q-knob, .q-select') ||
                element.closest('[role="button"], [role="checkbox"], [role="radio"], [role="slider"]');

            // Check for elements within widget containers (when widgets are unfolded)
            const isWidgetContainer = element.closest('.widget-container');

            // Check for elements marked as interactive
            const isMarkedInteractive = element.closest('[data-interactive="true"], .interactive, .clickable');

            // Check for drag handle specifically - this should allow dragging
            const isDragHandle = element.closest('.drag-handle');
            if (isDragHandle) {
                return false; // Allow dragging on drag handles
            }

            return isFormElement || isQuasarElement || isWidgetContainer || isMarkedInteractive;
        },

        // Utility Methods
        _parseConnectionId(connectionId) {
            /**
             * Parse a connection ID into its components.
             * Format: connection__outlet__node_id__pin_id__inlet__node_id__pin_id
             * Returns: { outletNodeId, outletPinId, inletNodeId, inletPinId }
             */
            const parts = connectionId.split('__');
            if (parts.length !== 7) {
                console.error(`Invalid connection ID format: ${connectionId}. Expected 7 parts, got ${parts.length}`);
                return null;
            }

            if (parts[0] !== 'connection' || parts[1] !== 'outlet' || parts[4] !== 'inlet') {
                console.error(`Invalid connection ID structure: ${connectionId}`);
                return null;
            }

            return {
                outletNodeId: parts[2],
                outletPinId: parts[3],
                inletNodeId: parts[5],
                inletPinId: parts[6],
                outletPinFullId: `${parts[1]}__${parts[2]}__${parts[3]}`,  // outlet__node_id__pin_id
                inletPinFullId: `${parts[4]}__${parts[5]}__${parts[6]}`    // inlet__node_id__pin_id
            };
        },

        _buildConnectionId(outputNodeId, outletPinId, inputNodeId, inletPinId) {
            /**
             * Build a connection ID from components.
             * Format: connection__outlet__outputNodeId__outletPinId__inlet__inputNodeId__inletPinId
             * This is the inverse of parseConnectionId()
             */
            const outletPin = this._buildOutletPinId(outputNodeId, outletPinId);
            const inletPin = this._buildInletPinId(inputNodeId, inletPinId);
            return `connection__${outletPin}__${inletPin}`;
        },

        _buildOutletPinId(nodeId, pinId) {
            /**
             * Build an outlet pin ID from components.
             * Format: outlet__nodeId__pinId
             */
            return `outlet__${nodeId}__${pinId}`;
        },

        _buildInletPinId(nodeId, pinId) {
            /**
             * Build an inlet pin ID from components.
             * Format: inlet__nodeId__pinId
             */
            return `inlet__${nodeId}__${pinId}`;
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

            // Use current zoom/pan state from zoom container events
            const { zoom, panX, panY } = this.zoomState;

            // Apply inverse transform accounting for current zoom/pan
            // This matches the old implementation's coordinate transformation
            let x = (clientX - svgRect.left) / zoom;
            let y = (clientY - svgRect.top) / zoom;

            return { x, y };
        },

        _createBezierPath(start, end, offsetDir) {
            const controlOffset = Math.abs(end.x - start.x) * 0.5 * offsetDir;
            return `M ${start.x} ${start.y} C ${start.x + controlOffset} ${start.y}, ${end.x - controlOffset} ${end.y}, ${end.x} ${end.y}`;
        },

        _createBezierStroke(startPos, endPos, startColor, endColor, pathId) {
            if (!endColor || !pathId) {
                return startColor || '#ff0000';
            }

            // Ensure we have defs element
            let defs = this.$refs.defs;
            if (!defs) {
                defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                this.$refs.svg.appendChild(defs);
            }

            const gradientId = `gradient_${pathId}`;

            // Check if gradient already exists
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
                // Update existing gradient colors
                const stops = gradient.querySelectorAll('stop');
                if (stops.length >= 2) {
                    stops[0].setAttribute('stop-color', startColor);
                    stops[1].setAttribute('stop-color', endColor);
                }
            }

            return `url(#${gradientId})`;
        },

        _isValidConnection(startPin, endPin) {
            if (!startPin || !endPin || startPin === endPin) return false;

            const startDir = startPin.dataset.pinDir;
            const startNodeId = startPin.dataset.nodeId;
            const startFlowType = startPin.dataset.pinFlowType;
            const endDir = endPin.dataset.pinDir;
            const endNodeId = endPin.dataset.nodeId;
            const endFlowType = endPin.dataset.pinFlowType;

            // Cannot connect to same node
            if (startNodeId === endNodeId) {
                return false;
            }

            // Must have matching flow types
            if (startFlowType !== endFlowType) {
                return false;
            }

            // Must connect output to input or input to output
            const valid = (startDir === 'outlet' && endDir === 'inlet') ||
                (startDir === 'inlet' && endDir === 'outlet');
            return valid;
        },

        _scheduleConnectionUpdates(nodeId, nodeElement = null, animationDuration = 300) {
            /**
             * Schedule connection updates during animations to ensure smooth transitions.
             * This method provides immediate update + multiple updates during animation.
             * 
             * @param {string} nodeId - The node ID to update connections for
             * @param {HTMLElement} nodeElement - Optional node element for timer cleanup
             * @param {number} animationDuration - Animation duration in milliseconds (default: 300ms)
             */

            // Immediate update
            this.updateConnectionsForNode(nodeId);

            // Find node element if not provided
            if (!nodeElement && nodeId) {
                nodeElement = document.getElementById(nodeId);
            }

            // Clear any existing animation timers to avoid conflicts
            if (nodeElement && nodeElement._animationTimers) {
                nodeElement._animationTimers.forEach(timer => clearTimeout(timer));
                nodeElement._animationTimers = [];
            }

            // Calculate update intervals during animation
            const updateCount = Math.max(3, Math.min(8, Math.ceil(animationDuration / 50))); // 3-8 updates based on duration
            const interval = animationDuration / updateCount;

            // Schedule multiple updates during the animation
            for (let i = 1; i <= updateCount; i++) {
                const delay = interval * i;
                const timer = setTimeout(() => {
                    this.updateConnectionsForNode(nodeId);
                }, delay);

                // Store timer for cleanup if we have a node element
                if (nodeElement) {
                    if (!nodeElement._animationTimers) {
                        nodeElement._animationTimers = [];
                    }
                    nodeElement._animationTimers.push(timer);
                }
            }
        },

        // =============================================================================
        // DEBUG METHODS
        // =============================================================================

        // Debug method to list available pin elements
        _debugListPinElements() {
            const pinElements = Array.from(document.querySelectorAll('[id*="__"]')).filter(el =>
                el.id.startsWith('outlet__') || el.id.startsWith('inlet__')
            );
            return pinElements.map(el => ({ id: el.id, exists: true }));
        }
    }
}
</script>

<style scoped>
.graph-canvas {
    position: relative;
    width: 8000px;
    height: 8000px;
    overflow: visible;
    /* Allow content to extend beyond bounds */
    /* border: 2px solid red; /* Temporary debug border - remove in production */
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
    width: 8000px;
    height: 8000px;
    pointer-events: none;
    z-index: 10;
    /* Above nodes to ensure path clicks work */
}

.connection-svg path {
    pointer-events: stroke;
    /* stroke-width is set by SVG attributes, not overridden by CSS */
}

.node-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 8000px;
    height: 8000px;
    z-index: 2;
    /* In front of canvas background */
}

.graph-canvas.dragging {
    cursor: grabbing;
}

/* Node dragging styles */
[data-node-id] {
    cursor: grab;
    user-select: none;
}

[data-node-id]:hover {
    cursor: grab;
}

[data-node-id].dragging-node {
    cursor: grabbing !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15) !important;
    transform: translateZ(0);
    /* Force hardware acceleration */
}

[data-node-id]:active {
    cursor: grabbing;
}

/* Node selection styles - Shadow-based instead of outline */
[data-node-id].node-selected {
    /* Remove outline, use shadow only */
    outline: none !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.25),
        0 0 20px rgba(74, 144, 226, 0.4),
        0 0 0 2px rgba(74, 144, 226, 0.3) !important;
}

[data-node-id].node-selected:hover {
    /* Enhanced shadow on hover */
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
}

.connection-pin:hover {
    transform: scale(1.3) !important;
    filter: brightness(1.2) !important;
    z-index: 10001 !important;
}

.connection-pin.connection-valid {
    box-shadow: 0 0 15px #4CAF50 !important;
    border-color: #4CAF50 !important;
    transform: scale(1.5) !important;
    z-index: 10002 !important;
}

.connection-pin.connection-invalid {
    box-shadow: 0 0 15px #f44336 !important;
    border-color: #f44336 !important;
    transform: scale(1.2) !important;
    z-index: 10002 !important;
}

/* Connection selection styles - Enhanced shadow-based */
.connection-selected {
    /* Enhanced drop shadow with blue glow */
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
}

path.connection-selected {
    /* Enhanced drop shadow with blue glow */
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
}

/* Widget fold/unfold functionality - widgets are hidden by default */
[data-node-id] .widget-container {
    opacity: 0 !important;
    transition: opacity 0.3s ease, max-height 0.3s ease !important;
    max-height: 0 !important;
    overflow: hidden !important;
}

/* Show widgets only when node is selected */
[data-node-id].node-selected .widget-container {
    opacity: 1 !important;
    max-height: 200px !important;
}
</style>
