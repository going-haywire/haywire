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
    containerId: { type: String, required: true }
    // Note: zoomState prop removed - zoom/pan is handled by CSS transforms in parent container
  },
  
  data() {
    return {
      connectionState: {
        isDragging: false,
        startPin: null,
        tempPath: null,
        hasNodes: false
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
  },
  
  computed: {
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
    
    // Initialize component
    this._setupEventListeners();
    this._setupObservers();
    this._setupZoomPanListener();
    
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
      getZoomState: () => this.zoomState
    };
  },
  
  beforeDestroy() {
    this._cleanupEventListeners();
    this._cleanupObservers();
    this._cleanupZoomPanListener();
  },
  
  // Note: No watcher for zoomState needed - zoom/pan is handled by CSS transforms
  // in the zoom container, so SVG paths don't need to be recalculated on zoom/pan changes
  
  methods: {
    // Event Listeners Setup
    _setupEventListeners() {
      // Mouse events for connection creation
      document.body.addEventListener('mousedown', this.handleMouseDown, true);
      document.body.addEventListener('mousemove', this.handleMouseMove, true);
      document.body.addEventListener('mouseup', this.handleMouseUp, true);
    },
    
    // Canvas Click Handler
    handleCanvasClick(event) {
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
    },
    
    _cleanupEventListeners() {
      document.body.removeEventListener('mousedown', this.handleMouseDown, true);
      document.body.removeEventListener('mousemove', this.handleMouseMove, true);
      document.body.removeEventListener('mouseup', this.handleMouseUp, true);
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
            
            if (nodeId) {
              this.updateConnectionsForNode(nodeId);
              this._emitNodePositionChanged(nodeElement, nodeId);
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
      const pin = e.target.closest('.connection-pin');
      if (!pin) return;
      
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
    
    handleMouseMove(e) {
      if (!this.connectionState.isDragging || !this.connectionState.tempPath) return;
      
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
    
    handleMouseUp(e) {
      if (!this.connectionState.isDragging) return;
      
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
    },
    
    // Connection Management Methods
    addConnectionVisual(edgeData) {
      console.log('🔗 Vue addConnectionVisual called with:', edgeData);
      const { outputNodeId, outletPinId, inputNodeId, inletPinId } = edgeData;
      
      // Generate pin IDs in the expected format
      const startPinId = `outlet__${outputNodeId}__${outletPinId}`;
      const endPinId = `inlet__${inputNodeId}__${inletPinId}`;
      const pathId = `connection__${startPinId}__${endPinId}`;
      
      console.log('🔗 Vue generated pin IDs:', { startPinId, endPinId, pathId });
      
      // Check if pins exist
      const startPin = document.getElementById(startPinId);
      const endPin = document.getElementById(endPinId);
      console.log('🔗 Vue pin elements found:', { startPin: !!startPin, endPin: !!endPin });
      
      if (!startPin || !endPin) {
        console.error('🔗 Vue connection creation failed - pins not found');
        console.log('Looking for pins:', { startPinId, endPinId });
        // List all available pins for debugging
        const allPins = document.querySelectorAll('.connection-pin');
        console.log('Available pins:', Array.from(allPins).map(p => p.id));
        return null;
      }
      
      // Create SVG path element
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('id', pathId);
      path.setAttribute('stroke', '#4A90E2');
      path.setAttribute('stroke-width', '2');
      path.setAttribute('fill', 'none');
      path.style.pointerEvents = 'stroke';
      path.style.cursor = 'pointer';
      
      // Add click handler for connection removal
      path.addEventListener('click', () => {
        this.$emit('connection-clicked', { pathId, edgeData });
      });
      
      this.$refs.svg.appendChild(path);
      this.connectionPaths.set(pathId, path);
      
      console.log('🔗 Vue created path element:', pathId);
      
      // Update path after a brief delay to ensure nodes are rendered
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
      const parts = pathId.split('__');
      
      if (parts.length < 7) return;
      
      // Reconstruct pin IDs: connection__outlet__node_id__pin_id__inlet__node_id__pin_id
      const startPinId = `${parts[1]}__${parts[2]}__${parts[3]}`;
      const endPinId = `${parts[4]}__${parts[5]}__${parts[6]}`;
      
      const startPin = document.getElementById(startPinId);
      const endPin = document.getElementById(endPinId);
      
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
      
      console.log('Transforming screen to SVG:', { clientX, clientY, svgRect, zoomState: this.zoomState });

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
      // Debounce position change notifications
      clearTimeout(nodeElement._positionTimer);
      nodeElement._positionTimer = setTimeout(() => {
        const rect = nodeElement.getBoundingClientRect();
        const containerRect = this.$refs.nodeContainer.getBoundingClientRect();
        const relativeX = rect.left - containerRect.left;
        const relativeY = rect.top - containerRect.top;
        
        this.$emit('node-position-changed', {
          nodeId,
          x: relativeX,
          y: relativeY
        });
      }, 100);
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
  z-index: 1; /* Behind nodes */
}

.connection-svg path {
  pointer-events: stroke;
}

.node-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 8000px;
  height: 8000px;
  z-index: 2; /* In front of connections */
}

.graph-canvas.dragging {
  cursor: grabbing;
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
</style>
