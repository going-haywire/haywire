<template>
    <div :id="containerId" ref="container" class="graph-canvas" :class="{
        dragging: dragState.isDragging,
        'box-selecting': boxSelectionState.isActive
    }" tabindex="0" @click="handleCanvasClick" @contextmenu="handleContextMenu">
        <!-- Box selection rectangle -->
        <div 
            v-if="boxSelectionState.isActive" 
            class="selection-box"
            :style="selectionBoxStyle"
        ></div>

        <!-- SVG layer for connections -->
        <svg id="connection-svg" ref="svg" class="connection-svg" :style="svgTransform">
            <defs ref="defs">
                <!-- Dynamic gradients will be added here -->
            </defs>
            <!-- Dynamic paths will be added here -->
        </svg>

        <!-- Node container slot -->
        <div id="node-container" ref="nodeContainer" class="node-container" :style="nodeContainerTransform">
            <!-- Debug info to verify component is working -->
            <div class="debug-info" v-if="!connectionState.hasNodes">
                Canvas Ready - ID: {{ containerId }}
            </div>
            <slot></slot>
        </div>

    </div>
</template>

<script>
// Import auto-generated event system

export default {
    name: 'GraphCanvas',

    props: {
        containerId: { type: String, required: true }
    },

    data() {
        return {
            connectionState: {
                isDragging: false,
                startPin: null,
                tempPath: null,
                hasNodes: false,
                lastDragEndTime: null,
                lockProximityRange: 150, 
                suggestionProximityRange: 200,
                suggestedConnections: new Map(),
                nearestSuggestedPin: null
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
                selectedConnections: new Set(),
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
            
            connectionPaths: new Map(),
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
    },

    computed: {
        svgTransform() {
            return '';
        },

        nodeContainerTransform() {
            return '';
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
        
        // Initialize component
        this._setupEventListeners();
        this._setupObservers();
        this._setupZoomPanListener();

        // Expose API to parent/Python
        this.$el._graphCanvasControls = {
            handleSyncEvent: this.handleSyncEvent
        };
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
            console.log('🔗 Setting up event listeners on document.body');
            document.body.addEventListener('mousedown', this.handleMouseDown, true);
            document.body.addEventListener('mousemove', this.handleMouseMove, true);
            document.body.addEventListener('mouseup', this.handleMouseUp, true);
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
                                this._updateConnectionsForNode(nodeId);
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

            const scheduleConnectionUpdates = () => {
                this._scheduleConnectionUpdates(nodeId, nodeElement);
            };

            // Listen for transform transitions (zoom scaling effects)
            lodElement.addEventListener('transitionstart', (e) => {
                if (e.propertyName === 'transform') {
                    this._scheduleConnectionUpdates(nodeId, nodeElement);
                }
            });
        
            // Listen for hover enter/leave for size changes
            lodElement.addEventListener('mouseenter', scheduleConnectionUpdates);
            lodElement.addEventListener('mouseleave', scheduleConnectionUpdates);
        },

        _setupZoomPanListener() {
            this.handleZoomPanUpdate = (event) => {
                const { zoom, panX, panY, containerId, isDragging } = event.detail;
                this.zoomState = { zoom, panX, panY, isDragging };
            };

            document.addEventListener('zoom-pan-state', this.handleZoomPanUpdate);
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
                case GraphEvents.SyncCommands.SYNC_CONNECTION_ADDITION:
                    this._syncConnectionAddition(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CONNECTION_REMOVAL:
                    this._syncConnectionRemoval(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_SELECTIONS:
                    this._syncSelections(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CANVAS_CLEAR:
                    this._syncCanvasClear();
                    break;
                case GraphEvents.SyncCommands.SYNC_NODE_OBSERVER_ADD:
                    this._syncNodeObserverAdd(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_NODE_OBSERVER_REMOVE:
                    this._syncNodeObserverRemove(data);
                    break;
                case GraphEvents.SyncCommands.SYNC_CONNECTIONS_UPDATE:
                    this._syncConnectionsUpdate(data);
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
                this._updateConnectionsForNode(nodeId);
            }
        },

        _syncConnectionAddition(data) {
            const {
                connectionUUID,
                outputNodeId,
                outletPinId,
                inputNodeId,
                inletPinId,
                isValid = true,
                hasWarning = false,
                strokeColor = 'auto',
                strokeWidth = 2,
                strokeDasharray = '',
                opacity = 1.0
            } = data;
            
            // Check if connection already exists
            if (this.connectionPaths.has(connectionUUID)) {
                // Update existing connection visual properties
                const connectionInfo = this.connectionPaths.get(connectionUUID);
                
                connectionInfo.isValid = isValid;
                connectionInfo.hasWarning = hasWarning;
                connectionInfo.strokeColor = strokeColor;
                connectionInfo.strokeWidth = strokeWidth;
                connectionInfo.strokeDasharray = strokeDasharray;
                connectionInfo.opacity = opacity;
                
                // Trigger visual update
                this._updateConnection(connectionUUID);
                
                console.log(
                    `🔗 Vue updated connection: ${connectionUUID} -> ` +
                    `valid=${isValid}, warning=${hasWarning}, color=${strokeColor}`
                );
                return;
            }

            // Create new connection with visual properties
            const result = this._createConnection(
                connectionUUID,
                outputNodeId,
                outletPinId,
                inputNodeId,
                inletPinId,
                isValid,
                hasWarning,
                strokeColor,
                strokeWidth,
                strokeDasharray,
                opacity
            );
            
            if (result.success) {
                console.log('🔗 Vue ✅ Connection added via sync:', connectionUUID);
            } else {
                console.error('🔗 Vue ❌ Failed to add connection via sync:', connectionUUID);
            }
        },

        _syncConnectionRemoval(data) {
            const { connectionUUID } = data;
            const success = this._removeConnection(connectionUUID);
            
            if (success) {
                console.log('🔗 Vue ✅ Connection removed via sync:', connectionUUID);
            } else {
                console.error('🔗 Vue ❌ Failed to remove connection via sync:', connectionUUID);
            }
        },

        _syncSelections(data) {
            const { nodes, connections } = data;
            
            // Get current selection sets
            const currentNodes = this.selectionState.selectedNodes;
            const currentConnections = this.selectionState.selectedConnections;
            
            // Convert arrays to sets for comparison
            const newNodes = new Set(nodes || []);
            const newConnections = new Set(connections || []);
            
            // only iterate connections if there's a change
            if (!this._setsAreEqual(currentNodes, newNodes)) {
                // Find nodes to deselect (in current but not in new)
                currentNodes.forEach(nodeId => {
                    if (!newNodes.has(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, false);
                        this._scheduleConnectionUpdates(nodeId, null, 300);
                    }
                });
                
                // Find nodes to select (in new but not in current)
                newNodes.forEach(nodeId => {
                    if (!currentNodes.has(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, true);
                        this._scheduleConnectionUpdates(nodeId, null, 300);
                    }
                });
                // Update internal state to match new selection
                this.selectionState.selectedNodes = newNodes;
            }
            
            // only iterate connections if there's a change
            if (!this._setsAreEqual(currentConnections, newConnections)) {
                // Find connections to deselect (in current but not in new)
                currentConnections.forEach(connectionUUID => {
                    if (!newConnections.has(connectionUUID)) {
                        this._updateConnectionVisualSelection(connectionUUID, false);
                    }
                });
                
                // Find connections to select (in new but not in current)
                newConnections.forEach(connectionUUID => {
                    if (!currentConnections.has(connectionUUID)) {
                        this._updateConnectionVisualSelection(connectionUUID, true);
                    }
                });
                // Update internal state to match new selection
                this.selectionState.selectedConnections = newConnections;
            }
            
            console.log(`🔄 Synced selections: ${(nodes || []).length} nodes, ${(connections || []).length} connections`);
        },

        _syncCanvasClear() {
            // ENHANCED: Use connectionInfo for cleanup
            this.connectionPaths.forEach((connectionInfo, connectionUUID) => {
                connectionInfo.path.remove();
                const hitArea = document.getElementById(connectionUUID + '_hitarea');
                if (hitArea) hitArea.remove();
                const gradient = document.getElementById(`gradient_${connectionUUID}`);
                if (gradient) gradient.remove();
            });
            
            this.connectionPaths.clear();
            const svg = this.$refs.svg;
            const paths = svg.querySelectorAll('path');
            paths.forEach(path => path.remove());
            
            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedConnections.clear();
        },



        _syncNodeObserverAdd(data) {
            const { nodeId } = data;
            this._addNodeObserver(nodeId);
        },

        _syncNodeObserverRemove(data) {
            const { nodeId } = data;
            this._removeNodeObserver(nodeId);
        },

        _syncConnectionsUpdate(data) {
            const { nodeId } = data;
            this._updateConnectionsForNode(nodeId);
        },

        _setSelectionState(selectedNodes, selectedConnections) {
            this._clearSelection();
            selectedNodes.forEach(nodeId => this._selectElement('node', nodeId, true));
            selectedConnections.forEach(connectionUUID => this._selectElement('connection', connectionUUID, true));
        },

        // =============================================================================
        // UNIFIED EVENT HANDLERS
        // =============================================================================


        handleMouseDown(e) {
            if (e.button === 2) return; // Skip right-click

            // 1. Check for connection pin FIRST - before anything else
            const pin = e.target.closest('.connection-pin');
            if (pin) {
                this._startConnectionDrag(e, pin);
                return;
            }

            // 2. Skip if clicking inside a popup - let popup handle it
            const popupElement = e.target.closest(
                '[data-popup-container="true"], ' +
                '[data-popup-drag-handle="true"], ' +
                '[data-popup="true"], ' +
                '.popup-card, ' +
                '.popup-content-area, ' +
                '.popup-title-bar'
            );
            if (popupElement) {
                console.log('Click inside popup - letting popup handle it');
                return;
            }

            const clickTime = Date.now();
            this.selectionState.lastClickTime = clickTime;

            // 3. Check for interactive widgets (but NOT drag handles)
            if (this._isInteractiveWidgetElement(e.target)) {
                console.log('Click on interactive widget element - skipping drag');
                return;
            }

            // 4. Check for elements that can be dragged (nodes)
            const draggableElement = this._findDraggableElement(e.target);
            if (draggableElement) {
                this._startUnifiedDrag(e, draggableElement);
                return;
            }

            // 5. Start box selection on empty canvas
            this._startBoxSelection(e);
        },

        handleMouseMove(e) {
            if (this.boxSelectionState.isActive) {
                this._updateBoxSelection(e);
                return;
            }

            if (this.connectionState.isDragging && this.connectionState.tempPath) {
                this._handleConnectionDragMove(e);
                return;
            }

            if (this.dragState.isDragging) {
                this._handleUnifiedDragMove(e);
                return;
            }
        },

        handleMouseUp(e) {
            if (this.boxSelectionState.isActive) {
                this._endBoxSelection(e);
                return;
            }

            if (this.connectionState.isDragging) {
                this._handleConnectionDragEnd(e);
                return;
            }

            if (this.dragState.isDragging) {
                this._handleUnifiedDragEnd(e);
                return;
            }
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
            const connectionElement = target.closest('path[data-connection-uuid]');
            if (connectionElement) {
                return {
                    type: 'connection',
                    id: connectionElement.getAttribute('data-connection-uuid'),
                    element: connectionElement
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
            // Note: Connections can't be dragged, so we only handle nodes

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
                        const newX = Math.max(0, Math.min(startPos.x + canvasDeltaX, 7500));
                        const newY = Math.max(0, Math.min(startPos.y + canvasDeltaY, 7500));

                        element.element.style.left = `${newX}px`;
                        element.element.style.top = `${newY}px`;
                        this._updateConnectionsForNode(element.id);
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
                this._scheduleConnectionUpdates(elementId, null, 300);
            } else if (elementType === 'connection') {
                this.selectionState.selectedConnections.add(elementId);
                this._updateConnectionVisualSelection(elementId, true);
            }

            console.log(`🎯 Selected ${elementType}: ${elementId}`);
        },

        _deSelectElement(elementType, elementId) {
            if (elementType === 'node') {
                this.selectionState.selectedNodes.delete(elementId);
                this._updateNodeVisualSelection(elementId, false);
                this._scheduleConnectionUpdates(elementId, null, 300);
            } else if (elementType === 'connection') {
                this.selectionState.selectedConnections.delete(elementId);
                this._updateConnectionVisualSelection(elementId, false);
            }

            console.log(`🎯 Deselected ${elementType}: ${elementId}`);
        },

        _isElementSelected(elementType, elementId) {
            if (elementType === 'node') {
                return this.selectionState.selectedNodes.has(elementId);
            } else if (elementType === 'connection') {
                return this.selectionState.selectedConnections.has(elementId);
            }
            return false;
        },

        _clearSelection() {
            const previouslySelectedNodes = Array.from(this.selectionState.selectedNodes);

            this.selectionState.selectedNodes.forEach(nodeId => {
                this._updateNodeVisualSelection(nodeId, false);
            });

            this.selectionState.selectedConnections.forEach(connectionUUID => {
                this._updateConnectionVisualSelection(connectionUUID, false);
            });

            this.selectionState.selectedNodes.clear();
            this.selectionState.selectedConnections.clear();

            previouslySelectedNodes.forEach(nodeId => {
                this._scheduleConnectionUpdates(nodeId, null, 300);
            });

            console.log('🎯 Cleared all selections');
        },

        _emitSelectionChanged() {
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedConnections)
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
            const intersectingConnections = this._findConnectionsInRectangle(selectionRect);

            if (multiSelect) {
                intersectingNodes.forEach(nodeId => {
                    this.selectionState.selectedNodes.add(nodeId);
                    this._updateNodeVisualSelection(nodeId, true);
                });
                
                intersectingConnections.forEach(connectionUUID => {
                    this.selectionState.selectedConnections.add(connectionUUID);
                    this._updateConnectionVisualSelection(connectionUUID, true);
                });
            } else {
                this.selectionState.selectedNodes.forEach(nodeId => {
                    if (!intersectingNodes.includes(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, false);
                    }
                });
                
                this.selectionState.selectedConnections.forEach(connectionUUID => {
                    if (!intersectingConnections.includes(connectionUUID)) {
                        this._updateConnectionVisualSelection(connectionUUID, false);
                    }
                });

                this.selectionState.selectedNodes.clear();
                this.selectionState.selectedConnections.clear();
                
                intersectingNodes.forEach(nodeId => {
                    this.selectionState.selectedNodes.add(nodeId);
                    this._updateNodeVisualSelection(nodeId, true);
                });
                
                intersectingConnections.forEach(connectionUUID => {
                    this.selectionState.selectedConnections.add(connectionUUID);
                    this._updateConnectionVisualSelection(connectionUUID, true);
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

        _findConnectionsInRectangle(rect) {
            const intersectingConnections = [];
            
            // ENHANCED: Use connectionInfo for more efficient bounds checking
            this.connectionPaths.forEach((connectionInfo, connectionUUID) => {
                try {
                    // Quick bounds check using connection positions
                    const minX = Math.min(connectionInfo.outletPos.x, connectionInfo.inletPos.x);
                    const maxX = Math.max(connectionInfo.outletPos.x, connectionInfo.inletPos.x);
                    const minY = Math.min(connectionInfo.outletPos.y, connectionInfo.inletPos.y);
                    const maxY = Math.max(connectionInfo.outletPos.y, connectionInfo.inletPos.y);

                    const connectionBounds = {
                        left: minX,
                        top: minY,
                        right: maxX,
                        bottom: maxY
                    };

                    if (this._rectanglesIntersect(rect, connectionBounds)) {
                        // More precise check with actual path bounds if needed
                        const pathBBox = connectionInfo.path.getBBox();
                        const pathRect = {
                            left: pathBBox.x,
                            top: pathBBox.y,
                            right: pathBBox.x + pathBBox.width,
                            bottom: pathBBox.y + pathBBox.height
                        };

                        if (this._rectanglesIntersect(rect, pathRect)) {
                            intersectingConnections.push(connectionUUID);
                        }
                    }
                } catch (e) {
                    console.warn('Error getting connection bounds for selection:', e);
                }
            });

            return intersectingConnections;
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

        _transformScreenToCanvas(clientX, clientY) {
            const containerRect = this.$refs.nodeContainer.getBoundingClientRect();
            const { zoom, panX, panY } = this.zoomState;
            
            const x = (clientX - containerRect.left) / zoom;
            const y = (clientY - containerRect.top) / zoom;
            
            return { x, y };
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

            // Check for node
            const nodeElement = target.closest('[data-node-id]');
            
            // Check for connection
            let connectionElement = null;
            let connectionUUID = null;

            if (target.tagName === 'path') {
                connectionUUID = target.getAttribute('data-connection-uuid') || target.id;
                connectionElement = target;
            } else {
                const svgElement = target.closest('svg');
                if (svgElement) {
                    const paths = svgElement.querySelectorAll('path[data-connection-uuid]');
                    const clickPoint = { x: clientX, y: clientY };

                    for (const path of paths) {
                        if (this._isPointNearPath(path, clickPoint)) {
                            connectionElement = path;
                            connectionUUID = path.getAttribute('data-connection-uuid') || path.id;
                            break;
                        }
                    }
                }
            }

            const canvasCoords = this._transformScreenToSVG(clientX, clientY);

            if (nodeElement) {
                const nodeId = nodeElement.dataset.nodeId;
                const isNodeSelected = this.selectionState.selectedNodes.has(nodeId);
                const hasMultipleSelected = this.selectionState.selectedNodes.size > 1 || this.selectionState.selectedConnections.size > 0;
                
                if (isNodeSelected && hasMultipleSelected) {
                    this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                        clientX, clientY, canvasCoords.x, canvasCoords.y,
                        Array.from(this.selectionState.selectedNodes),
                        Array.from(this.selectionState.selectedConnections)
                    ));
                } else {
                    this.emitCanvasEvent(EventCreators.createContextMenuNode(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, nodeId
                    ));
                }
            } else if (connectionElement && connectionUUID) {
                const isConnectionSelected = this.selectionState.selectedConnections.has(connectionUUID);
                const hasMultipleSelected = this.selectionState.selectedNodes.size > 0 || this.selectionState.selectedConnections.size > 1;
                
                if (isConnectionSelected && hasMultipleSelected) {
                    this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                        clientX, clientY, canvasCoords.x, canvasCoords.y,
                        Array.from(this.selectionState.selectedNodes),
                        Array.from(this.selectionState.selectedConnections)
                    ));
                } else {
                    this.emitCanvasEvent(EventCreators.createContextMenuConnection(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, connectionUUID
                    ));
                }
            } else {
                this.emitCanvasEvent(EventCreators.createContextMenuCanvas(
                    clientX, clientY, canvasCoords.x, canvasCoords.y
                ));
            }
        },

        _isPointNearPath(pathElement, point) {
            try {
                const rect = pathElement.getBoundingClientRect();
                const tolerance = 10;

                return point.x >= rect.left - tolerance &&
                    point.x <= rect.right + tolerance &&
                    point.y >= rect.top - tolerance &&
                    point.y <= rect.bottom + tolerance;
            } catch (e) {
                console.warn('Error checking point near path:', e);
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
            this.selectionState.selectedConnections.forEach(connectionUUID => {
                elements.push({ type: 'connection', id: connectionUUID });
            });
            
            return elements;
        },

        // =============================================================================
        // CONNECTION DRAG SYSTEM (keeping as-is)
        // =============================================================================

        _startConnectionDrag(e, pin) {
            e.preventDefault();
            e.stopPropagation();

            this.connectionState.isDragging = true;
            this.connectionState.startPin = pin;

            const startPos = this._getPinPosition(pin);
            const [dirX, dirY] = this._getPinDirectionVector(this.connectionState.startPin);

            const pinColor = pin.dataset.pinColor || '#000000';

            this.connectionState.tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const initialPath = this._createBezierPath(startPos, startPos, [dirX, dirY], [-dirX, -dirY]);

            this.connectionState.tempPath.setAttribute('d', initialPath);
            this.connectionState.tempPath.setAttribute('stroke', pinColor);
            this.connectionState.tempPath.setAttribute('stroke-width', '2');
            this.connectionState.tempPath.setAttribute('fill', 'none');
            this.connectionState.tempPath.setAttribute('stroke-dasharray', '4');
            this.connectionState.tempPath.style.pointerEvents = 'none';
            
            this.$refs.svg.appendChild(this.connectionState.tempPath);

            pin.style.boxShadow = '0 0 15px #4A90E2';
            pin.style.transform = 'scale(1.8)';
            pin.style.zIndex = '10003';
        },

        _handleConnectionDragMove(e) {
            if (!this.connectionState.tempPath) return;
            
            const startPos = this._getPinPosition(this.connectionState.startPin);
            const mousePos = this._transformScreenToSVG(e.clientX, e.clientY);
            const [dirX, dirY] = this._getPinDirectionVector(this.connectionState.startPin);

            const pathData = this._createBezierPath(startPos, mousePos, [dirX, dirY], [-dirX, -dirY]);
            this.connectionState.tempPath.setAttribute('d', pathData);

            this._clearConnectionSuggestions();

            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid', 'connection-compatible');
            });

            const targetPin = e.target.closest('.connection-pin');
            let nearestCompatiblePin = null;
            let nearestDistance = Infinity;
            
            document.querySelectorAll('.connection-pin').forEach(pin => {
                if (pin === this.connectionState.startPin) return;

                const isValid = this._isValidConnection(this.connectionState.startPin, pin);
                
                if (isValid) {
                    const pinPos = this._getPinPosition(pin);
                    const distance = Math.sqrt(
                        Math.pow(mousePos.x - pinPos.x, 2) + 
                        Math.pow(mousePos.y - pinPos.y, 2)
                    );

                    if (pin === targetPin) {
                        pin.classList.add('connection-valid');
                        nearestCompatiblePin = pin;
                        nearestDistance = 0;
                    } else if (distance <= this.connectionState.suggestionProximityRange) {
                        if(this.connectionState.startPin.dataset.pinDataType === pin.dataset.pinDataType) {
                            pin.classList.add('connection-compatible');
                            this._createSuggestionPath(pin, distance);

                            if (distance < nearestDistance) {
                                nearestCompatiblePin = pin;
                                nearestDistance = distance;
                            }
                        }
                    }
                } else if (pin === targetPin) {
                    pin.classList.add('connection-invalid');
                }
            });

            this.connectionState.nearestSuggestedPin = nearestCompatiblePin;
            
            if (nearestCompatiblePin && nearestDistance <= this.connectionState.suggestionProximityRange && nearestDistance > 0) {
                const suggestionPath = this.connectionState.suggestedConnections.get(nearestCompatiblePin);
                if (suggestionPath) {
                    suggestionPath.classList.add('connection-suggestion-nearest');
                }
            }
        },

        _handleConnectionDragEnd(e) {
            let endPin = e.target.closest('.connection-pin');
            
            if (!endPin && this.connectionState.nearestSuggestedPin) {
                endPin = this.connectionState.nearestSuggestedPin;
            }

            if (this.connectionState.tempPath) {
                this.connectionState.tempPath.remove();
                this.connectionState.tempPath = null;
            }

            if (this.connectionState.startPin) {
                this.connectionState.startPin.style.boxShadow = '';
                this.connectionState.startPin.style.transform = '';
                this.connectionState.startPin.style.zIndex = '';
            }

            this._clearConnectionSuggestions();

            document.querySelectorAll('.connection-pin').forEach(pin => {
                pin.classList.remove('connection-valid', 'connection-invalid', 'connection-compatible');
            });

            if (endPin && this._isValidConnection(this.connectionState.startPin, endPin)) {
                let startData = this.connectionState.startPin.dataset;
                let endData = endPin.dataset;

                if (endPin.dataset.pinDir === 'outlet') {
                    endData = this.connectionState.startPin.dataset;
                    startData = endPin.dataset;
                }

                if (!this._connectionExists(startData.nodeId, startData.pinId, endData.nodeId, endData.pinId)) {
                    this.emitCanvasEvent(EventCreators.createConnectionCreated(
                        startData.nodeId, startData.pinId, endData.nodeId, endData.pinId
                    ));
                }
            }

            this.connectionState.isDragging = false;
            this.connectionState.startPin = null;
            this.connectionState.nearestSuggestedPin = null;
            this.connectionState.lastDragEndTime = Date.now();
        },

        _createSuggestionPath(targetPin, distance) {
            if (this.connectionState.suggestedConnections.has(targetPin)) {
                return;
            }

            const startPos = this._getPinPosition(this.connectionState.startPin);
            const endPos = this._getPinPosition(targetPin);
            const [dirX, dirY] = this._getPinDirectionVector(this.connectionState.startPin);

            const pathData = this._createBezierPath(startPos, endPos, [dirX, dirY], [-dirX, -dirY]);

            const suggestionPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            suggestionPath.setAttribute('d', pathData);
            suggestionPath.setAttribute('stroke', this.connectionState.startPin.dataset.pinColor || '#4CAF50');
            suggestionPath.setAttribute('stroke-width', '2');
            suggestionPath.setAttribute('fill', 'none');
            suggestionPath.setAttribute('opacity', '0.6');
            suggestionPath.style.pointerEvents = 'none';
            suggestionPath.classList.add('connection-suggestion');

            this.$refs.svg.appendChild(suggestionPath);
            this.connectionState.suggestedConnections.set(targetPin, suggestionPath);
        },

        _clearConnectionSuggestions() {
            this.connectionState.suggestedConnections.forEach((path, pin) => {
                path.remove();
            });
            this.connectionState.suggestedConnections.clear();
        },

        // =============================================================================
        // CONNECTION MANAGEMENT (keeping connection visual methods as-is)
        // =============================================================================

        _createConnection(
            connectionUUID,
            outputNodeId,
            outletPinId,
            inputNodeId,
            inletPinId,
            isValid = true,
            hasWarning = false,
            strokeColor = 'auto',
            strokeWidth = 2,
            strokeDasharray = '',
            opacity = 1.0
        ) {
            const outletPinUUID = this._buildOutletPinUUID(outputNodeId, outletPinId);
            const inletPinUUID = this._buildInletPinUUID(inputNodeId, inletPinId);

            const outletPin = document.getElementById(outletPinUUID);
            const inletPin = document.getElementById(inletPinUUID);

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
            path.setAttribute('id', connectionUUID);
            path.setAttribute('data-connection-uuid', connectionUUID);
            path.setAttribute('fill', 'none');
            path.style.pointerEvents = 'stroke';
            path.style.cursor = 'pointer';

            // Store comprehensive connection info with visual properties
            const connectionInfo = {
                path: path,
                outletNodeId: outputNodeId,
                outletPinUUID: outletPinUUID,
                outletPinId: outletPinId,
                outletPos: outletPos,
                outletColor: outletColor,
                outletConnectDir: outletConnectDir,
                inletNodeId: inputNodeId,
                inletPinUUID: inletPinUUID,
                inletPinId: inletPinId,
                inletPos: inletPos,
                inletColor: inletColor,
                inletConnectDir: inletConnectDir,
                // Visual state properties
                isValid: isValid,
                hasWarning: hasWarning,
                strokeColor: strokeColor,
                strokeWidth: strokeWidth,
                strokeDasharray: strokeDasharray,
                opacity: opacity
            };

            const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            hitArea.setAttribute('id', connectionUUID + '_hitarea');
            hitArea.setAttribute('data-connection-uuid', connectionUUID);
            hitArea.setAttribute('stroke', 'transparent');
            hitArea.setAttribute('stroke-width', '10');
            hitArea.setAttribute('fill', 'none');
            hitArea.style.pointerEvents = 'stroke';
            hitArea.style.cursor = 'pointer';

            this.$refs.svg.appendChild(path);
            this.$refs.svg.appendChild(hitArea);
            
            // ENHANCED: Store the full connection info instead of just the path
            this.connectionPaths.set(connectionUUID, connectionInfo);

            const clickHandler = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.emitCanvasEvent(EventCreators.createConnectionClicked(connectionUUID));
            };

            path.addEventListener('click', clickHandler);
            hitArea.addEventListener('click', clickHandler);

            this.$nextTick(() => {
                this._updateConnection(connectionUUID);
            });

            return { success: true, pathElement: path };
        },

        _removeConnection(connectionUUID) {
            const connectionInfo = this.connectionPaths.get(connectionUUID);

            if (connectionInfo) {
                connectionInfo.path.remove();

                const hitArea = document.getElementById(connectionUUID + '_hitarea');
                if (hitArea) {
                    hitArea.remove();
                }

                const gradient = document.getElementById(`gradient_${connectionUUID}`);
                if (gradient) {
                    gradient.remove();
                }

                this.connectionPaths.delete(connectionUUID);
                return true;
            } else {
                return false;
            }
        },

        _updateConnection(connectionUUID) {
            const connectionInfo = this.connectionPaths.get(connectionUUID);
            if (!connectionInfo) {
                console.error(`Connection not found: ${connectionUUID}`);
                return;
            }

            const outletPin = document.getElementById(connectionInfo.outletPinUUID);
            const inletPin = document.getElementById(connectionInfo.inletPinUUID);

            if (!outletPin || !inletPin) {
                console.error(`Failed to find pins for connection: ${connectionUUID}`);
                return;
            }

            // Update positions in connectionInfo
            connectionInfo.outletPos = this._getPinPosition(outletPin);
            connectionInfo.inletPos = this._getPinPosition(inletPin);

            // Update colors in connectionInfo
            connectionInfo.outletColor = document.getElementById(connectionInfo.outletPinUUID).dataset.pinColor;
            connectionInfo.inletColor = document.getElementById(connectionInfo.inletPinUUID).dataset.pinColor;

            const pathData = this._createBezierPathForConnection(connectionUUID);

            connectionInfo.path.setAttribute('d', pathData);
            const hitArea = document.getElementById(connectionUUID + '_hitarea');
            if (hitArea) {
                hitArea.setAttribute('d', pathData);
            }

            // Apply visual properties from connectionInfo
            const stroke = this._createBezierStroke(connectionUUID);
            connectionInfo.path.setAttribute('stroke', stroke);
            connectionInfo.path.setAttribute(
                'stroke-width',
                connectionInfo.strokeWidth
            );
            connectionInfo.path.setAttribute(
                'stroke-dasharray',
                connectionInfo.strokeDasharray
            );
            connectionInfo.path.style.opacity = connectionInfo.opacity;
            
            // Update CSS classes for additional styling
            connectionInfo.path.classList.toggle(
                'connection-invalid',
                !connectionInfo.isValid
            );
            connectionInfo.path.classList.toggle(
                'connection-warning',
                connectionInfo.hasWarning
            );
            
            // Update hit area width
            if (hitArea) {
                hitArea.setAttribute(
                    'stroke-width',
                    connectionInfo.strokeWidth + 8
                );
            }
        },

        _updateConnectionsForNode(nodeId) {
            if (!nodeId) return;
            
            // ENHANCED: More efficient iteration using connectionInfo
            this.connectionPaths.forEach((connectionInfo, connectionUUID) => {
                if (connectionInfo.outletNodeId === nodeId || connectionInfo.inletNodeId === nodeId) {
                    this._updateConnection(connectionUUID);
                }
            });
        },

        _addNodeObserver(nodeId) {
            const attemptAddObserver = (retryCount = 0) => {
                const nodeElement = document.getElementById(nodeId);
                if (nodeElement) {
                    console.log(`[GraphCanvas] Adding observer for node ${nodeId}`, nodeElement);
                    this._setupHoverObserver(nodeElement);
                } else if (retryCount < 3) {
                    setTimeout(() => attemptAddObserver(retryCount + 1), 100);
                } else {
                    console.warn(`[GraphCanvas] Node element with ID ${nodeId} not found after 3 retries. Unable to observe.`);
                }
            };
            attemptAddObserver();
        },

        _removeNodeObserver(nodeId) {
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

        _updateConnectionVisualSelection(connectionUUID, selected) {
            const connectionInfo = this.connectionPaths.get(connectionUUID);
            if (connectionInfo && connectionInfo.path) {
                if (selected) {
                    connectionInfo.path.classList.add('connection-selected');
                    connectionInfo.path.style.strokeWidth = '3';
                } else {
                    connectionInfo.path.classList.remove('connection-selected');
                    connectionInfo.path.style.strokeWidth = '2';
                }
            }
        },

        // =============================================================================
        // UTILITY & HELPER METHODS
        // =============================================================================

        // ENHANCED: New helper method to get connection by node and pin
        _getConnectionsByNode(nodeId) {
            const connections = [];
            this.connectionPaths.forEach((connectionInfo, connectionUUID) => {
                if (connectionInfo.outletNodeId === nodeId || connectionInfo.inletNodeId === nodeId) {
                    connections.push({ uuid: connectionUUID, info: connectionInfo });
                }
            });
            return connections;
        },

        // ENHANCED: New helper method to get connection by specific pin
        _getConnectionsByPin(nodeId, pinId, pinType) {
            const connections = [];
            this.connectionPaths.forEach((connectionInfo, connectionUUID) => {
                const isOutletMatch = pinType === 'outlet' && 
                    connectionInfo.outletNodeId === nodeId && 
                    connectionInfo.outletPinId === pinId;
                const isInletMatch = pinType === 'inlet' && 
                    connectionInfo.inletNodeId === nodeId && 
                    connectionInfo.inletPinId === pinId;
                    
                if (isOutletMatch || isInletMatch) {
                    connections.push({ uuid: connectionUUID, info: connectionInfo });
                }
            });
            return connections;
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
            // Connection pins are NOT interactive widgets
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

        _parseconnectionUUID(connectionUUID) {
            const parts = connectionUUID.split('__');
            if (parts.length !== 7) {
                console.error(`Invalid connection ID format: ${connectionUUID}. Expected 7 parts, got ${parts.length}`);
                return null;
            }

            if (parts[0] !== 'connection' || parts[1] !== 'outlet' || parts[4] !== 'inlet') {
                console.error(`Invalid connection ID structure: ${connectionUUID}`);
                return null;
            }

            return {
                outletNodeId: parts[2],
                outletPinId: parts[3],
                inletNodeId: parts[5],
                inletPinId: parts[6],
                outletPinFullId: `${parts[1]}__${parts[2]}__${parts[3]}`,
                inletPinFullId: `${parts[4]}__${parts[5]}__${parts[6]}`
            };
        },

        _buildconnectionUUID(outputNodeId, outletPinId, inputNodeId, inletPinId) {
            const outletPin = this._buildOutletPinUUID(outputNodeId, outletPinId);
            const inletPin = this._buildInletPinUUID(inputNodeId, inletPinId);
            return `connection__${outletPin}__${inletPin}`;
        },

        _buildOutletPinUUID(nodeId, pinId) {
            return `outlet__${nodeId}__${pinId}`;
        },

        _buildInletPinUUID(nodeId, pinId) {
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
        _createBezierPathForConnection(connectionUUID) {
            const connectionInfo = this.connectionPaths.get(connectionUUID);
            if (!connectionInfo) {
                console.error(`Connection info not found for: ${connectionUUID}`);
                return 'M 0 0';
            }

            return this._createBezierPath(
                connectionInfo.outletPos,
                connectionInfo.inletPos,
                connectionInfo.outletConnectDir,
                connectionInfo.inletConnectDir
            );
        },

        _createBezierStroke(connectionUUID) {
            const connectionInfo = this.connectionPaths.get(connectionUUID);
            if (!connectionInfo) {
                console.error(`Connection not found: ${connectionUUID}`);
                return '#000000';
            }
            
            // If strokeColor is not 'auto', use the solid color directly
            if (connectionInfo.strokeColor !== 'auto') {
                return connectionInfo.strokeColor;
            }
            
            // Otherwise create gradient (existing logic)
            const startPos = connectionInfo.outletPos;
            const endPos = connectionInfo.inletPos;
            const startColor = connectionInfo.outletColor;
            const endColor = connectionInfo.inletColor;
            
            if (!endColor || !connectionUUID) {
                return startColor || '#ff0000';
            }

            let defs = this.$refs.defs;
            if (!defs) {
                defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                this.$refs.svg.appendChild(defs);
            }

            const gradientId = `gradient_${connectionUUID}`;
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

            if (startNodeId === endNodeId) {
                return false;
            }

            if (startFlowType !== endFlowType) {
                return false;
            }

            const valid = (startDir === 'outlet' && endDir === 'inlet') ||
                (startDir === 'inlet' && endDir === 'outlet');
            return valid;
        },

        _scheduleConnectionUpdates(nodeId, nodeElement = null, animationDuration = 300) {
            this._updateConnectionsForNode(nodeId);

            if (!nodeElement && nodeId) {
                nodeElement = document.getElementById(nodeId);
            }

            if (nodeElement && nodeElement._animationTimers) {
                nodeElement._animationTimers.forEach(timer => clearTimeout(timer));
                nodeElement._animationTimers = [];
            }

            const updateCount = Math.max(3, Math.min(8, Math.ceil(animationDuration / 50)));
            const interval = animationDuration / updateCount;

            for (let i = 1; i <= updateCount; i++) {
                const delay = interval * i;
                const timer = setTimeout(() => {
                    this._updateConnectionsForNode(nodeId);
                }, delay);

                if (nodeElement) {
                    if (!nodeElement._animationTimers) {
                        nodeElement._animationTimers = [];
                    }
                    nodeElement._animationTimers.push(timer);
                }
            }
        },

        _connectionExists(outputNodeId, outletPinId, inputNodeId, inletPinId) {
            const connectionUUID = this._buildconnectionUUID(outputNodeId, outletPinId, inputNodeId, inletPinId);
            return this.connectionPaths.has(connectionUUID);
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
    width: 8000px;
    height: 8000px;
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
    width: 8000px;
    height: 8000px;
    pointer-events: auto;
    z-index: 1;
}

.node-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 8000px;
    height: 8000px;
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

/* Connection state styles - UIEdge visual feedback */
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