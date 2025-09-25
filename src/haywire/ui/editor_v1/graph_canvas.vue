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
                mouseDownEvent: null
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
                                this.updateConnectionsForNode(nodeId);
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
                this.updateConnectionsForNode(nodeId);
            }
        },

        _syncConnectionAddition(data) {
            const { connectionId, outputNodeId, outletPinId, inputNodeId, inletPinId, isValid } = data;
            
            if (this.connectionPaths.has(connectionId)) {
                if (path.dataset.isValid === String(isValid)) {
                    return;
                } else {
                    this._removeConnectionVisual(connectionId);
                }
            }

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
            const success = this._removeConnectionVisual(connectionId);
            
            if (success) {
                console.log('🔗 Vue ✅ Connection removed via sync:', connectionId);
            } else {
                console.error('🔗 Vue ❌ Failed to remove connection via sync:', connectionId);
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
                currentConnections.forEach(connectionId => {
                    if (!newConnections.has(connectionId)) {
                        this._updateConnectionVisualSelection(connectionId, false);
                    }
                });
                
                // Find connections to select (in new but not in current)
                newConnections.forEach(connectionId => {
                    if (!currentConnections.has(connectionId)) {
                        this._updateConnectionVisualSelection(connectionId, true);
                    }
                });
                // Update internal state to match new selection
                this.selectionState.selectedConnections = newConnections;
            }
            
            console.log(`🔄 Synced selections: ${(nodes || []).length} nodes, ${(connections || []).length} connections`);
        },

        _syncCanvasClear() {
            this.connectionPaths.forEach((path, pathId) => {
                path.remove();
                const hitArea = document.getElementById(pathId + '_hitarea');
                if (hitArea) hitArea.remove();
                const gradient = document.getElementById(`gradient_${pathId}`);
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
            this.addNodeObserver(nodeId);
        },

        _syncNodeObserverRemove(data) {
            const { nodeId } = data;
            this.removeNodeObserver(nodeId);
        },

        _syncConnectionsUpdate(data) {
            const { nodeId } = data;
            this.updateConnectionsForNode(nodeId);
        },

        _setSelectionState(selectedNodes, selectedConnections) {
            this.clearSelection();
            selectedNodes.forEach(nodeId => this.selectElement('node', nodeId, true));
            selectedConnections.forEach(connectionId => this.selectElement('connection', connectionId, true));
        },

        // =============================================================================
        // UNIFIED EVENT HANDLERS
        // =============================================================================

        handleMouseDown(e) {
            if (e.button === 2) return; // Skip right-click
            
            const clickTime = Date.now();
            this.selectionState.lastClickTime = clickTime;

            // Check for connection pin first
            const pin = e.target.closest('.connection-pin');
            if (pin) {
                this._startConnectionDrag(e, pin);
                return;
            }

            // Check for interactive widgets
            if (this._isInteractiveWidgetElement(e.target)) {
                console.log('Click on interactive widget element - skipping drag');
                return;
            }

            // Check for elements that can be dragged
            const draggableElement = this._findDraggableElement(e.target);
            if (draggableElement) {
                this._startUnifiedDrag(e, draggableElement);
                return;
            }

            // Start box selection on empty canvas
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
            const connectionElement = target.closest('path[data-connection-id]');
            if (connectionElement) {
                return {
                    type: 'connection',
                    id: connectionElement.getAttribute('data-connection-id'),
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
                        this.updateConnectionsForNode(element.id);
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
                    this.deselectElement(elementType, elementId);
                } else {
                    this.selectElement(elementType, elementId, true);
                }
            } else {
                // Clear other selections and select this element
                this.clearSelection();
                this.selectElement(elementType, elementId, false);
            }

            // Emit unified selection change event
            this._emitSelectionChanged();
        },

        selectElement(elementType, elementId, multiSelect = false) {
            if (!multiSelect) {
                this.clearSelection();
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

        deselectElement(elementType, elementId) {
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

        clearSelection() {
            const previouslySelectedNodes = Array.from(this.selectionState.selectedNodes);

            this.selectionState.selectedNodes.forEach(nodeId => {
                this._updateNodeVisualSelection(nodeId, false);
            });

            this.selectionState.selectedConnections.forEach(connectionId => {
                this._updateConnectionVisualSelection(connectionId, false);
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
                this.clearSelection();
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
                
                intersectingConnections.forEach(connectionId => {
                    this.selectionState.selectedConnections.add(connectionId);
                    this._updateConnectionVisualSelection(connectionId, true);
                });
            } else {
                this.selectionState.selectedNodes.forEach(nodeId => {
                    if (!intersectingNodes.includes(nodeId)) {
                        this._updateNodeVisualSelection(nodeId, false);
                    }
                });
                
                this.selectionState.selectedConnections.forEach(connectionId => {
                    if (!intersectingConnections.includes(connectionId)) {
                        this._updateConnectionVisualSelection(connectionId, false);
                    }
                });

                this.selectionState.selectedNodes.clear();
                this.selectionState.selectedConnections.clear();
                
                intersectingNodes.forEach(nodeId => {
                    this.selectionState.selectedNodes.add(nodeId);
                    this._updateNodeVisualSelection(nodeId, true);
                });
                
                intersectingConnections.forEach(connectionId => {
                    this.selectionState.selectedConnections.add(connectionId);
                    this._updateConnectionVisualSelection(connectionId, true);
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
            
            this.connectionPaths.forEach((pathElement, connectionId) => {
                try {
                    const pathBBox = pathElement.getBBox();
                    const pathRect = {
                        left: pathBBox.x,
                        top: pathBBox.y,
                        right: pathBBox.x + pathBBox.width,
                        bottom: pathBBox.y + pathBBox.height
                    };

                    if (this._rectanglesIntersect(rect, pathRect)) {
                        intersectingConnections.push(connectionId);
                    }
                } catch (e) {
                    console.warn('Error getting path bounding box for selection:', e);
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
            let connectionId = null;

            if (target.tagName === 'path') {
                connectionId = target.getAttribute('data-connection-id') || target.id;
                connectionElement = target;
            } else {
                const svgElement = target.closest('svg');
                if (svgElement) {
                    const paths = svgElement.querySelectorAll('path[data-connection-id]');
                    const clickPoint = { x: clientX, y: clientY };

                    for (const path of paths) {
                        if (this.isPointNearPath(path, clickPoint)) {
                            connectionElement = path;
                            connectionId = path.getAttribute('data-connection-id') || path.id;
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
            } else if (connectionElement && connectionId) {
                const isConnectionSelected = this.selectionState.selectedConnections.has(connectionId);
                const hasMultipleSelected = this.selectionState.selectedNodes.size > 0 || this.selectionState.selectedConnections.size > 1;
                
                if (isConnectionSelected && hasMultipleSelected) {
                    this.emitCanvasEvent(EventCreators.createContextMenuSelected(
                        clientX, clientY, canvasCoords.x, canvasCoords.y,
                        Array.from(this.selectionState.selectedNodes),
                        Array.from(this.selectionState.selectedConnections)
                    ));
                } else {
                    this.emitCanvasEvent(EventCreators.createContextMenuConnection(
                        clientX, clientY, canvasCoords.x, canvasCoords.y, connectionId
                    ));
                }
            } else {
                this.emitCanvasEvent(EventCreators.createContextMenuCanvas(
                    clientX, clientY, canvasCoords.x, canvasCoords.y
                ));
            }
        },

        isPointNearPath(pathElement, point) {
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

        // Unified removal method for delete key / context menu
        removeSelectedElements() {
            const elementsToRemove = this._getSelectedElementsForRemoval();
            
            if (elementsToRemove.length > 0) {
                this.emitCanvasEvent(EventCreators.createUserRemove(elementsToRemove));
            }
        },

        _getSelectedElementsForRemoval() {
            const elements = [];
            
            // Add selected nodes
            this.selectionState.selectedNodes.forEach(nodeId => {
                elements.push({ type: 'node', id: nodeId });
            });
            
            // Add selected connections
            this.selectionState.selectedConnections.forEach(connectionId => {
                elements.push({ type: 'connection', id: connectionId });
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
            const offsetDir = pin.dataset.pinDir === 'inlet' ? -1 : 1;
            const pinColor = pin.dataset.pinColor || '#000000';

            this.connectionState.tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const initialPath = this._createBezierPath(startPos, startPos, offsetDir);

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
            const offsetDir = this.connectionState.startPin.dataset.pinDir === 'inlet' ? -1 : 1;

            const pathData = this._createBezierPath(startPos, mousePos, offsetDir);
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
            const offsetDir = this.connectionState.startPin.dataset.pinDir === 'inlet' ? -1 : 1;

            const suggestionPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const pathData = this._createBezierPath(startPos, endPos, offsetDir);

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

        _createConnectionVisual(outputNodeId, outletPinId, inputNodeId, inletPinId, pathId, isValid, logPrefix = '', connectionData = null) {
            const startPinId = this._buildOutletPinId(outputNodeId, outletPinId);
            const endPinId = this._buildInletPinId(inputNodeId, inletPinId);

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
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.dataset.isValid = isValid.toString();
            path.setAttribute('id', pathId);
            path.setAttribute('data-connection-id', pathId); 
            if (isValid) {
                path.setAttribute('stroke', startPin.dataset.pinColor); 
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

            const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            hitArea.setAttribute('id', pathId + '_hitarea');
            hitArea.setAttribute('data-connection-id', pathId);
            hitArea.setAttribute('stroke', 'transparent');
            hitArea.setAttribute('stroke-width', '10');
            hitArea.setAttribute('fill', 'none');
            hitArea.style.pointerEvents = 'stroke';
            hitArea.style.cursor = 'pointer';

            this.$refs.svg.appendChild(path);
            this.$refs.svg.appendChild(hitArea);
            this.connectionPaths.set(pathId, path);

            const clickHandler = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.emitCanvasEvent(EventCreators.createConnectionClicked(pathId));
            };

            path.addEventListener('click', clickHandler);
            hitArea.addEventListener('click', clickHandler);

            this.$nextTick(() => {
                this.updateConnectionPath(path);
            });

            return { success: true, pathElement: path };
        },

        _removeConnectionVisual(connectionId) {
            const path = this.connectionPaths.get(connectionId);

            if (path) {
                path.remove();

                const hitArea = document.getElementById(connectionId + '_hitarea');
                if (hitArea) {
                    hitArea.remove();
                }

                const gradient = document.getElementById(`gradient_${connectionId}`);
                if (gradient) {
                    gradient.remove();
                }

                this.connectionPaths.delete(connectionId);
                return true;
            } else {
                return false;
            }
        },

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

            const offsetDir = startPin.dataset.pinDir === 'inlet' ? -1 : 1;
            const pathData = this._createBezierPath(startPos, endPos, offsetDir);

            pathElement.setAttribute('d', pathData);
            const hitArea = document.getElementById(pathId + '_hitarea');
            if (hitArea) {
                hitArea.setAttribute('d', pathData);
            }

            const isValid = pathElement.dataset.isValid === 'true';
            let startColor = pathElement.dataset.startColor || '#000000';
            let endColor = pathElement.dataset.endColor || '#000000';

            const stroke = this._createBezierStroke(startPos, endPos, startColor, endColor, pathId);
            pathElement.setAttribute('stroke', stroke);
        },

        updateConnectionsForNode(nodeId) {
            if (!nodeId) return;
            this.connectionPaths.forEach((path, pathId) => {
                if (pathId.includes(nodeId)) {
                    this.updateConnectionPath(path);
                }
            });
        },

        addNodeObserver(nodeId) {
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

        removeNodeObserver(nodeId) {
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

        _updateConnectionVisualSelection(pathId, selected) {
            const pathElement = this.connectionPaths.get(pathId);
            if (pathElement) {
                if (selected) {
                    pathElement.classList.add('connection-selected');
                    pathElement.style.strokeWidth = '3';
                } else {
                    pathElement.classList.remove('connection-selected');
                    pathElement.style.strokeWidth = '2';
                }
            }
        },

        // =============================================================================
        // UTILITY & HELPER METHODS
        // =============================================================================

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
            const isFormElement = element.matches('input, textarea, select, button, [contenteditable]') ||
                element.closest('input, textarea, select, button, [contenteditable]');

            const isQuasarElement = element.closest('.q-field, .q-btn, .q-checkbox, .q-radio, .q-toggle, .q-slider, .q-knob, .q-select') ||
                element.closest('[role="button"], [role="checkbox"], [role="radio"], [role="slider"]');

            const isWidgetContainer = element.closest('.widget-container');
            const isMarkedInteractive = element.closest('[data-interactive="true"], .interactive, .clickable');
            const isDragHandle = element.closest('.drag-handle');
            
            if (isDragHandle) {
                return false;
            }

            return isFormElement || isQuasarElement || isWidgetContainer || isMarkedInteractive;
        },

        _parseConnectionId(connectionId) {
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
                outletPinFullId: `${parts[1]}__${parts[2]}__${parts[3]}`,
                inletPinFullId: `${parts[4]}__${parts[5]}__${parts[6]}`
            };
        },

        _buildConnectionId(outputNodeId, outletPinId, inputNodeId, inletPinId) {
            const outletPin = this._buildOutletPinId(outputNodeId, outletPinId);
            const inletPin = this._buildInletPinId(inputNodeId, inletPinId);
            return `connection__${outletPin}__${inletPin}`;
        },

        _buildOutletPinId(nodeId, pinId) {
            return `outlet__${nodeId}__${pinId}`;
        },

        _buildInletPinId(nodeId, pinId) {
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

        _createBezierPath(start, end, offsetDir) {
            const controlOffset = Math.abs(end.x - start.x) * 0.5 * offsetDir;
            return `M ${start.x} ${start.y} C ${start.x + controlOffset} ${start.y}, ${end.x - controlOffset} ${end.y}, ${end.x} ${end.y}`;
        },

        _createBezierStroke(startPos, endPos, startColor, endColor, pathId) {
            if (!endColor || !pathId) {
                return startColor || '#ff0000';
            }

            let defs = this.$refs.defs;
            if (!defs) {
                defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                this.$refs.svg.appendChild(defs);
            }

            const gradientId = `gradient_${pathId}`;
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
            this.updateConnectionsForNode(nodeId);

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
                    this.updateConnectionsForNode(nodeId);
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
            const connectionId = this._buildConnectionId(outputNodeId, outletPinId, inputNodeId, inletPinId);
            return this.connectionPaths.has(connectionId);
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

.connection-pin.connection-compatible {
    box-shadow: 0 0 8px rgba(76, 175, 80, 0.6) !important;
    border-color: rgba(76, 175, 80, 0.8) !important;
    transform: scale(1.2) !important;
    z-index: 10001 !important;
    opacity: 0.8 !important;
}

.connection-selected {
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
}

path.connection-selected {
    filter: drop-shadow(0 0 12px rgba(74, 144, 226, 0.6)) drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3)) !important;
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