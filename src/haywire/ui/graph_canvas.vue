<template>
  <div 
    :id="containerId"
    ref="container"
    class="graph-canvas"
    :class="{ 
      dragging: connectionState.isDragging,
    }"
    tabindex="0"
    @click="handleCanvasClick"
  >
    <!-- SVG layer for connections -->
    <svg 
      id="connection-svg"
      ref="svg"
      class="connection-svg"
      :style="svgTransform"
    >
      <defs ref="defs">
        <!-- Dynamic gradients will be added here -->
      </defs>
      <!-- Dynamic paths will be added here -->
    </svg>
    
    <!-- Node container slot -->
    <div 
      id="node-container"
      ref="nodeContainer"
      class="node-container"
      :style="nodeContainerTransform"
    >
      <!-- Debug info to verify component is working -->
      <div class="debug-info" v-if="!connectionState.hasNodes">
        Canvas Ready - ID: {{ containerId }}
      </div>
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GraphCanvas',
  
  props: {
    containerId: { type: String, required: true },
    connections: { type: Array, default: () => [] }  // Add connections prop
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
        dragThreshold: 5 // pixels - minimum movement to consider it a drag
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
  },  computed: {
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
  
  mounted() {
    console.log('GraphCanvas Vue component mounted with container ID:', this.containerId);
    console.log('Container element:', this.$el);
    console.log('Container dimensions:', this.$el.offsetWidth, 'x', this.$el.offsetHeight);
    console.log('🔗 Vue initial connections prop:', this.connections);
    
    // Initialize component
    this._setupEventListeners();
    this._setupObservers();
    this._setupZoomPanListener();
    
    // Process initial connections if any exist
    if (this.connections && this.connections.length > 0) {
      console.log('🔗 Vue processing initial connections on mount:', this.connections.length);
      // Use nextTick to ensure DOM is ready
      this.$nextTick(() => {
        this._updateConnectionsFromPropsDelayed(this.connections, []);
      });
    }
    
    // Expose API to parent/Python
    this.$el._graphCanvasControls = {
      addConnectionVisual: this.addConnectionVisual,
      removeConnectionVisual: this.removeConnectionVisual,
      updateConnectionPath: this.updateConnectionPath,
      updateAllConnections: this.updateAllConnections,
      updateConnectionsForNode: this.updateConnectionsForNode,
      addNodeObserver: this.addNodeObserver,
      removeNodeObserver: this.removeNodeObserver,
      getPinPosition: this.getPinPosition,
      transformScreenToSVG: this.transformScreenToSVG,
      getZoomState: () => this.zoomState,
      // Selection API
      selectNode: this.selectNode,
      deselectNode: this.deselectNode,
      selectConnection: this.selectConnection,
      deselectConnection: this.deselectConnection,
      clearSelection: this.clearSelection,
      getSelection: this.getSelection,
      setSelection: this.setSelection
    };
  },

  updated() {
    console.log('🔗 Vue component updated, connections prop now:', this.connections);
  },

  beforeDestroy() {
    this._cleanupEventListeners();
    this._cleanupObservers();
    this._cleanupZoomPanListener();
  },
  
  // Note: No watcher for zoomState needed - zoom/pan is handled by CSS transforms
  // in the zoom container, so SVG paths don't need to be recalculated on zoom/pan changes
  
  watch: {
    // Watch for changes in connections prop and update visuals
    connections: {
      handler(newConnections, oldConnections) {
        console.log('🔗 Vue connections prop changed:', { newConnections, oldConnections });
        this._updateConnectionsFromProps(newConnections, oldConnections || []);
      },
      deep: true
    }
  },
  
  methods: {
    // Connection ID Utilities
    parseConnectionId(connectionId) {
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

    // Debug method to list available pin elements
    _debugListPinElements() {
      const pinElements = Array.from(document.querySelectorAll('[id*="__"]')).filter(el => 
        el.id.startsWith('outlet__') || el.id.startsWith('inlet__')
      );
      return pinElements.map(el => ({ id: el.id, exists: true }));
    },

    // Event Listeners Setup
    _setupEventListeners() {
      // Mouse events for connection creation
      document.body.addEventListener('mousedown', this.handleMouseDown, true);
      document.body.addEventListener('mousemove', this.handleMouseMove, true);
      document.body.addEventListener('mouseup', this.handleMouseUp, true);
    },
    
    // Canvas Click Handler
    handleCanvasClick(event) {
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
        
        // Emit click event to Python with proper coordinates
        const rect = this.$el.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        
        this.$emit('click', {
          offsetX: offsetX,
          offsetY: offsetY,
          clientX: event.clientX,
          clientY: event.clientY
        });
      }
    },
    
    _cleanupEventListeners() {
      document.body.removeEventListener('mousedown', this.handleMouseDown, true);
      document.body.removeEventListener('mousemove', this.handleMouseMove, true);
      document.body.removeEventListener('mouseup', this.handleMouseUp, true);
    },

    // Update connection visuals based on props changes
    _updateConnectionsFromProps(newConnections, oldConnections) {
      console.log('🔗 Vue updating connections from props:', { new: newConnections.length, old: oldConnections.length });
      
      // Add a small delay to ensure DOM elements are ready
      this.$nextTick(() => {
        this._updateConnectionsFromPropsDelayed(newConnections, oldConnections);
      });
    },
    
    _updateConnectionsFromPropsDelayed(newConnections, oldConnections) {
      console.log('🔗 Vue updating connections from props (delayed):', { new: newConnections.length, old: oldConnections.length });
      
      // Convert arrays to Maps for easier comparison
      const oldConnectionMap = new Map(oldConnections.map(c => [c.id, c]));
      const newConnectionMap = new Map(newConnections.map(c => [c.id, c]));
      
      // Remove connections that are no longer in the new list
      for (const [connectionId, connectionData] of oldConnectionMap) {
        if (!newConnectionMap.has(connectionId)) {
          console.log('🔗 Vue removing connection from props:', connectionId);
          this._removeConnectionVisualInternal(connectionId);
        }
      }
      
      // Add connections that are new in the list
      for (const [connectionId, connectionData] of newConnectionMap) {
        if (!oldConnectionMap.has(connectionId)) {
          console.log('🔗 Vue adding connection from props:', connectionId);
          this._addConnectionVisualInternal(connectionData);
        }
      }
    },

    // Shared internal method for creating connection visuals
    _createConnectionVisual(outputNodeId, outletPinId, inputNodeId, inletPinId, pathId, logPrefix = '') {
      // Generate pin IDs in the expected format
      const startPinId = `outlet__${outputNodeId}__${outletPinId}`;
      const endPinId = `inlet__${inputNodeId}__${inletPinId}`;
      
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
        
        // List all available pins for debugging
        const allPins = document.querySelectorAll('.connection-pin');
        console.log('Available pins:', Array.from(allPins).map(p => p.id));
        
        return { success: false, pathElement: null };
      }
      
      // Check if path already exists
      if (this.connectionPaths.has(pathId)) {
        console.log(`🔗 Vue${logPrefix} connection already exists:`, pathId);
        return { success: false, pathElement: null };
      }
      
      // Create SVG path element
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('id', pathId);
      path.setAttribute('stroke', '#4A90E2'); // Default blue, will be updated by updateConnectionPath
      path.setAttribute('stroke-width', '2');
      path.setAttribute('fill', 'none');
      path.style.pointerEvents = 'stroke';
      path.style.cursor = 'pointer';
      
      this.$refs.svg.appendChild(path);
      this.connectionPaths.set(pathId, path);
      
      console.log(`🔗 Vue${logPrefix} created path element:`, pathId);
      
      // Update path after a brief delay to ensure nodes are rendered
      this.$nextTick(() => {
        this.updateConnectionPath(path);
      });
      
      return { success: true, pathElement: path };
    },

    // Internal method to add connection visual (used by props watcher)
    _addConnectionVisualInternal(connectionData) {
      const { id, outputNodeId, outletPinId, inputNodeId, inletPinId } = connectionData;
      
      const result = this._createConnectionVisual(
        outputNodeId, 
        outletPinId, 
        inputNodeId, 
        inletPinId, 
        id, // Use the connection ID directly as path ID (Format 2)
        ' (internal)' // Log prefix
      );
      
      if (result.success) {
        // Add click handler for connection selection (only for persistent connections)
        const path = result.pathElement;
        const pathId = id;
        
        console.log('🔗 Adding click event listener to internal path:', pathId, path);
        console.log('🔗 Internal path element details:', { 
          tagName: path.tagName,
          id: path.id,
          parentElement: path.parentElement?.tagName,
          style: path.style.pointerEvents,
          computedPointerEvents: window.getComputedStyle(path).pointerEvents
        });
        
        path.addEventListener('click', (e) => {
          console.log('🔗 Connection path clicked (internal)!', pathId);
          e.preventDefault();
          e.stopPropagation();
          this._handleConnectionSelection(e, pathId);
          this.$emit('connection-clicked', { pathId, connectionData });
        });
        
        console.log('🔗 Internal event listener added to path:', pathId);
      }
      
      return result.success;
    },

    // Internal method to remove connection visual (used by props watcher)
    _removeConnectionVisualInternal(connectionId) {
      // Use the connection ID (Format 2) to find the path
      const path = this.connectionPaths.get(connectionId);
      
      if (path) {
        path.remove();
        this.connectionPaths.delete(connectionId);
        console.log('🔗 Vue (internal) removed path element:', connectionId);
        return true;
      } else {
        console.log('🔗 Vue (internal) path not found for removal:', connectionId);
        return false;
      }
    },

    // Zoom/Pan Event Listener Setup
    _setupZoomPanListener() {
      // Listen for zoom/pan state changes from the zoom container
      this.handleZoomPanUpdate = (event) => {
        const { zoom, panX, panY, containerId, isDragging } = event.detail;
        
        // Update our local zoom state
        this.zoomState = { zoom, panX, panY, isDragging };
        
        console.log('🔍 GraphCanvas received zoom/pan update:', this.zoomState);
        
        // Update all connections when zoom/pan changes
        // Note: This is throttled in the zoom container, so we don't need additional throttling
        this.updateAllConnections();
      };
      
      document.addEventListener('zoom-pan-state', this.handleZoomPanUpdate);
    },

    _cleanupZoomPanListener() {
      if (this.handleZoomPanUpdate) {
        document.removeEventListener('zoom-pan-state', this.handleZoomPanUpdate);
        this.handleZoomPanUpdate = null;
      }
    },
    
    // Observer Setup
    _setupObservers() {
      // Mutation observer for node position changes
      this.mutationObserver = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
          if (mutation.attributeName === 'style') {
            const nodeElement = mutation.target;
            const nodeId = nodeElement.dataset.nodeId;
            
            // Only process style changes on node containers, not on children
            if (nodeId && nodeElement.hasAttribute('data-node-id')) {
                /*
                console.log(`🔍 Style mutation detected on node ${nodeId}:`, {
                    oldValue: mutation.oldValue,
                    currentStyle: nodeElement.style.cssText,
                    isDragging: this.connectionState.isDragging,
                    hasLeftTop: nodeElement.style.left || nodeElement.style.top
                });
                */

              // Only process if the style change actually includes position properties
              const styleText = nodeElement.style.cssText;
              if (styleText.includes('left:') || styleText.includes('top:')) {
                this.updateConnectionsForNode(nodeId);
                this._emitNodePositionChanged(nodeElement, nodeId);
              } else {
                //console.log(`🚫 Skipping style mutation for ${nodeId} - no position changes detected`);
              }
            }
          }
        });
      });
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
    
    // Connection Drag Handlers
    handleMouseDown(e) {
      // Store click time for distinguishing clicks from drags
      const clickTime = Date.now();
      this.selectionState.lastClickTime = clickTime;
      
      // Check for connection pin first
      const pin = e.target.closest('.connection-pin');
      if (pin) {
        this._startConnectionDrag(e, pin);
        return;
      }
      
      // Check for node dragging/selection - look for node container
      const nodeElement = e.target.closest('[data-node-id]');
      if (nodeElement && !e.target.closest('.connection-pin')) {
        const nodeId = nodeElement.dataset.nodeId;
        if (nodeId) {
          // Handle selection on mouse down (before potential drag)
          this._handleNodeSelection(e, nodeId);
          this._startNodeDrag(e, nodeElement);
          return;
        }
      }
    },

    _startConnectionDrag(e, pin) {
      e.preventDefault();
      e.stopPropagation();
      
      this.connectionState.isDragging = true;
      this.connectionState.startPin = pin;
      
      const startPos = this.getPinPosition(pin);
      const offsetDir = pin.dataset.pinDir === 'inlet' ? -1 : 1;
      const pinColor = pin.dataset.pinColor || '#000000';
      
      // Create temporary path
      this.connectionState.tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const initialPath = this.createBezierPath(startPos, startPos, offsetDir);
      
      this.connectionState.tempPath.setAttribute('d', initialPath);
      this.connectionState.tempPath.setAttribute('stroke', pinColor);
      this.connectionState.tempPath.setAttribute('stroke-width', '4');
      this.connectionState.tempPath.setAttribute('fill', 'none');
      this.connectionState.tempPath.setAttribute('stroke-dasharray', '8,4');
      this.connectionState.tempPath.style.pointerEvents = 'none';
      
      this.$refs.svg.appendChild(this.connectionState.tempPath);
      
      // Visual feedback on start pin
      pin.style.boxShadow = '0 0 15px #4A90E2';
      pin.style.transform = 'scale(1.8)';
      pin.style.zIndex = '10003';
    },

    _startNodeDrag(e, nodeElement) {
      e.preventDefault();
      e.stopPropagation();
      
      console.log('Preparing node drag for:', nodeElement.dataset.nodeId);
      
      this.nodeDragState.isDragging = true;
      this.nodeDragState.draggedNode = nodeElement;
      this.nodeDragState.startMousePos = { x: e.clientX, y: e.clientY };
      this.nodeDragState.hasActuallyMoved = false;
      
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

    _handleConnectionDragMove(e) {
      const startPos = this.getPinPosition(this.connectionState.startPin);
      const mousePos = this.transformScreenToSVG(e.clientX, e.clientY);
      const offsetDir = this.connectionState.startPin.dataset.pinDir === 'inlet' ? -1 : 1;
      
      const pathData = this.createBezierPath(startPos, mousePos, offsetDir);
      this.connectionState.tempPath.setAttribute('d', pathData);
      
      // Highlight valid drop targets
      const targetPin = e.target.closest('.connection-pin');
      document.querySelectorAll('.connection-pin').forEach(pin => {
        pin.classList.remove('connection-valid', 'connection-invalid');
        if (pin !== this.connectionState.startPin) {
          if (targetPin === pin) {
            if (this.isValidConnection(this.connectionState.startPin, pin)) {
              pin.classList.add('connection-valid');
            } else {
              pin.classList.add('connection-invalid');
            }
          }
        }
      });
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
        
        // Emit drag start event to add fence for undo grouping
        this.$emit('node-drag-start', {
          nodeId: nodeId
        });
        
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
      if (endPin && this.isValidConnection(this.connectionState.startPin, endPin)) {
        let startData = this.connectionState.startPin.dataset;
        let endData = endPin.dataset;
        
        // Maintain outlet->inlet convention
        if (endPin.dataset.pinDir === 'outlet') {
          endData = this.connectionState.startPin.dataset;
          startData = endPin.dataset;
        }
        
        // Emit connection created event
        this.$emit('connection-created', {
          startNodeId: startData.nodeId,
          startPort: startData.pinId,
          endNodeId: endData.nodeId,
          endPort: endData.pinId
        });
      }
      
      // Reset state
      this.connectionState.isDragging = false;
      this.connectionState.startPin = null;
      this.connectionState.lastDragEndTime = Date.now(); // Track when drag ended
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
          // Emit position change event to Python
          this.$emit('node-position-changed', {
            nodeId: nodeId,
            x: finalX,
            y: finalY
          });
          
          console.log(`Node ${nodeId} drag ended with position change: (${startX}, ${startY}) -> (${finalX}, ${finalY})`);
        } else {
          console.log(`Node ${nodeId} drag ended with no position change: (${finalX}, ${finalY})`);
        }
        
        // Emit drag end event to close fence for undo grouping
        this.$emit('node-drag-end', {
          nodeId: nodeId,
          positionChanged: positionChanged
        });
      } else {
        // This was just a click, not a drag - handle as selection
        console.log(`Node ${nodeId} was clicked (not dragged)`);
        
        // The selection was already handled in handleMouseDown/_handleNodeSelection
        // No need to emit drag events
      }
      
      // Reset drag state
      this.nodeDragState.isDragging = false;
      this.nodeDragState.draggedNode = null;
      this.nodeDragState.startMousePos = { x: 0, y: 0 };
      this.nodeDragState.startNodePos = { x: 0, y: 0 };
      this.nodeDragState.dragOffset = { x: 0, y: 0 };
      this.nodeDragState.hasActuallyMoved = false;
    },
    
    // Connection Management Methods
    addConnectionVisual(edgeData) {
      console.log('🔗 Vue addConnectionVisual called with:', edgeData);
      const { outputNodeId, outletPinId, inputNodeId, inletPinId } = edgeData;
      
      // Generate path ID using the descriptive format
      const startPinId = `outlet__${outputNodeId}__${outletPinId}`;
      const endPinId = `inlet__${inputNodeId}__${inletPinId}`;
      const pathId = `connection__${startPinId}__${endPinId}`;
      
      console.log('🔗 Vue generated pin IDs:', { startPinId, endPinId, pathId });
      
      const result = this._createConnectionVisual(
        outputNodeId, 
        outletPinId, 
        inputNodeId, 
        inletPinId, 
        pathId,
        '' // No log prefix for public API
      );
      
      if (!result.success) {
        console.error('🔗 Vue connection creation failed');
        return null;
      }
      
      // Add click handler for connection selection (only for persistent connections)
      const path = result.pathElement;
      
      console.log('🔗 Adding click event listener to path:', pathId, path);
      console.log('🔗 Path element details:', { 
        tagName: path.tagName,
        id: path.id,
        parentElement: path.parentElement?.tagName,
        style: path.style.pointerEvents,
        computedPointerEvents: window.getComputedStyle(path).pointerEvents
      });
      
      path.addEventListener('click', (e) => {
        console.log('🔗 Connection path clicked!', pathId);
        console.log('🔗 Path click event details:', { 
          target: e.target, 
          currentTarget: e.currentTarget,
          pathId: pathId,
          bubbles: e.bubbles,
          preventDefault: e.defaultPrevented 
        });
        e.preventDefault();
        e.stopPropagation();
        this._handleConnectionSelection(e, pathId);
        this.$emit('connection-clicked', { pathId, edgeData });
      });
      
      console.log('🔗 Event listener added to path:', pathId);
      
      // Additional logging and testing for public API
      console.log('🔗 SVG element exists:', !!this.$refs.svg);
      console.log('🔗 Path element exists:', !!path);
      console.log('🔗 Path pointer events:', path.style.pointerEvents);
      console.log('🔗 Path cursor:', path.style.cursor);
      
      // Add a test to see if the path element is properly in the DOM
      setTimeout(() => {
        const foundPath = document.getElementById(pathId);
        console.log('🔗 Path found in DOM after timeout:', !!foundPath);
        if (foundPath) {
          console.log('🔗 Path bounding box:', foundPath.getBBox());
        }
      }, 500);
      
      // Update path with additional delay for public API (maintains existing behavior)
      this.$nextTick(() => {
        setTimeout(() => {
          console.log('🔗 Vue updating connection path...');
          this.updateConnectionPath(path);
        }, 100);
      });
      
      return pathId;
    },
    
    removeConnectionVisual(pathId) {
      const path = this.connectionPaths.get(pathId);
      if (path) {
        path.remove();
        this.connectionPaths.delete(pathId);
        
        // Also remove any associated gradient
        const gradientId = `gradient_${pathId}`;
        const gradient = document.getElementById(gradientId);
        if (gradient) {
          gradient.remove();
        }
        
        return true;
      }
      return false;
    },
    
    updateConnectionPath(pathElement) {
      if (!pathElement || !pathElement.id) return;
      
      const pathId = pathElement.id;
      const connectionInfo = this.parseConnectionId(pathId);
      
      if (!connectionInfo) {
        console.error(`Failed to parse connection ID: ${pathId}`);
        pathElement.remove();
        this.connectionPaths.delete(pathId);
        return;
      }
      
      const startPin = document.getElementById(connectionInfo.outletPinFullId);
      const endPin = document.getElementById(connectionInfo.inletPinFullId);
      
      if (!startPin || !endPin) {
        pathElement.remove();
        this.connectionPaths.delete(pathId);
        return;
      }
      
      const startPos = this.getPinPosition(startPin);
      const endPos = this.getPinPosition(endPin);
      
      const controlOffset = Math.abs(endPos.x - startPos.x) * 0.5;
      const pathData = `M ${startPos.x} ${startPos.y} C ${startPos.x + controlOffset} ${startPos.y}, ${endPos.x - controlOffset} ${endPos.y}, ${endPos.x} ${endPos.y}`;
      
      pathElement.setAttribute('d', pathData);
      
      // Update stroke with gradient
      const stroke = this.createBezierStroke(startPos, endPos, startPin.dataset.pinColor, endPin.dataset.pinColor, pathId);
      pathElement.setAttribute('stroke', stroke);
      
      // Set consistent stroke width
      pathElement.setAttribute('stroke-width', '2');
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
    
    // Node Observer Management
    addNodeObserver(nodeId) {
      if (!this.mutationObserver || !nodeId) return;
      
      // Function to attempt adding the observer
      const attemptAddObserver = (retryCount = 0) => {
        const nodeElement = document.getElementById(nodeId);
        if (nodeElement) {
          console.log(`[GraphCanvas] Adding observer for node ${nodeId}`, nodeElement);
          
          this.mutationObserver.observe(nodeElement, {
            attributes: true,
            childList: true,
            subtree: true,
            attributeFilter: ['style', 'class']
          });
          
          // Setup hover observers for LOD animations
          this._setupHoverObserver(nodeElement);
        } else if (retryCount < 3) {
          // Retry after a short delay (up to 3 times)
          console.log(`[GraphCanvas] Node element with ID ${nodeId} not found, retrying... (${retryCount + 1}/3)`);
          setTimeout(() => attemptAddObserver(retryCount + 1), 100);
        } else {
          console.warn(`[GraphCanvas] Node element with ID ${nodeId} not found after 3 retries`);
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
    
    _setupHoverObserver(nodeElement) {
      const lodElement = nodeElement.querySelector('.zoom-pan-lod0');
      if (!lodElement) return;
      
      const nodeId = nodeElement.getAttribute('data-node-id');
      if (!nodeId) return;
      
      const scheduleConnectionUpdates = () => {
        // Immediate update
        this.updateConnectionsForNode(nodeId);
        
        // Clear any existing animation timers
        if (nodeElement._animationTimers) {
          nodeElement._animationTimers.forEach(timer => clearTimeout(timer));
        }
        nodeElement._animationTimers = [];
        
        // Schedule additional updates during animations
        for (let i = 1; i <= 5; i++) {
          const delay = (200 / 5) * i; // 40ms intervals
          const timer = setTimeout(() => {
            this.updateConnectionsForNode(nodeId);
          }, delay);
          nodeElement._animationTimers.push(timer);
        }
      };
      
      lodElement.addEventListener('mouseenter', scheduleConnectionUpdates);
      lodElement.addEventListener('mouseleave', scheduleConnectionUpdates);
    },
    
    // Utility Methods
    getPinPosition(pinElement) {
      if (!pinElement) return { x: 0, y: 0 };
      
      const pinRect = pinElement.getBoundingClientRect();
      const position = this.transformScreenToSVG(
        pinRect.left + pinRect.width / 2,
        pinRect.top + pinRect.height / 2
      );
      
      return position;
    },
    
    transformScreenToSVG(clientX, clientY) {
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
    
    createBezierPath(start, end, offsetDir) {
      const controlOffset = Math.abs(end.x - start.x) * 0.5 * offsetDir;
      return `M ${start.x} ${start.y} C ${start.x + controlOffset} ${start.y}, ${end.x - controlOffset} ${end.y}, ${end.x} ${end.y}`;
    },
    
    createBezierStroke(startPos, endPos, startColor, endColor, pathId) {
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
    
    isValidConnection(startPin, endPin) {
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
        
        console.log(`🔍 Node position debug for ${nodeId}:`, {
          stylePosition: { left: styleLeft, top: styleTop },
          calculatedPosition: { x: relativeX, y: relativeY },
          rectLeft: rect.left,
          rectTop: rect.top,
          containerLeft: containerRect.left,
          containerTop: containerRect.top
        });
        
        // Use the style position directly instead of calculated position
        // as it's more reliable for absolute positioned elements
        this.$emit('node-position-changed', {
          nodeId,
          x: styleLeft,
          y: styleTop
        });
      }, 100);
    },

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
      
      // Emit selection change to Python
      this.$emit('selection-changed', {
        selectedNodes: Array.from(this.selectionState.selectedNodes),
        selectedConnections: Array.from(this.selectionState.selectedConnections)
      });
    },

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
      
      // Emit selection change to Python
      this.$emit('selection-changed', {
        selectedNodes: Array.from(this.selectionState.selectedNodes),
        selectedConnections: Array.from(this.selectionState.selectedConnections)
      });
    },

    selectNode(nodeId, multiSelect = false) {
      if (!multiSelect) {
        this.clearSelection();
      }
      
      this.selectionState.selectedNodes.add(nodeId);
      this._updateNodeVisualSelection(nodeId, true);
      
      console.log(`🎯 Selected node: ${nodeId}`);
    },

    deselectNode(nodeId) {
      this.selectionState.selectedNodes.delete(nodeId);
      this._updateNodeVisualSelection(nodeId, false);
      
      console.log(`🎯 Deselected node: ${nodeId}`);
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

    clearSelection() {
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
      console.log('🎨 _updateConnectionVisualSelection called:', { pathId, selected });
      const pathElement = this.connectionPaths.get(pathId);
      console.log('🎨 Found path element:', !!pathElement, pathElement?.id);
      if (pathElement) {
        if (selected) {
          pathElement.classList.add('connection-selected');
          pathElement.style.strokeWidth = '4';
          pathElement.style.stroke = '#FF6B35';
          console.log('🎨 Applied selection styles to path:', pathId);
        } else {
          pathElement.classList.remove('connection-selected');
          pathElement.style.strokeWidth = '2';
          pathElement.style.stroke = '#4A90E2';
          console.log('🎨 Removed selection styles from path:', pathId);
        }
      } else {
        console.warn('🎨 Path element not found in connectionPaths map for pathId:', pathId);
        console.log('🎨 Available paths:', Array.from(this.connectionPaths.keys()));
      }
    }
  }
}
</script>

<style scoped>
.graph-canvas {
  position: relative;
  width: 8000px;
  height: 8000px;
  overflow: visible; /* Allow content to extend beyond bounds */
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
  z-index: 10; /* Above nodes to ensure path clicks work */
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
  z-index: 2; /* In front of canvas background */
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
  transform: translateZ(0); /* Force hardware acceleration */
}

[data-node-id]:active {
  cursor: grabbing;
}

/* Node selection styles */
[data-node-id].node-selected {
  outline: 3px solid #FF6B35 !important;
  outline-offset: 2px !important;
  box-shadow: 0 0 20px rgba(255, 107, 53, 0.3) !important;
}

[data-node-id].node-selected:hover {
  outline: 3px solid #FF6B35 !important;
  outline-offset: 2px !important;
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

/* Connection selection styles */
.connection-selected {
  stroke: #FF6B35 !important;
  stroke-width: 4 !important;
  filter: drop-shadow(0 0 8px rgba(255, 107, 53, 0.5)) !important;
}

path.connection-selected {
  stroke: #FF6B35 !important;
  stroke-width: 4 !important;
  filter: drop-shadow(0 0 8px rgba(255, 107, 53, 0.5)) !important;
}
</style>
