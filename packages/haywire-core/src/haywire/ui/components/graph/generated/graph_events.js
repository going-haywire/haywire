// Auto-generated from Python event definitions
// DO NOT EDIT MANUALLY - Run `python ./scripts/generate_vue_events.py` to update

// Event type constants - Make available globally
window.GraphEvents = {
  UserInteractions: {
    USER_DRAG_START: 'userDragStart', // User started dragging nodes
    USER_DRAG_UPDATE: 'userDragUpdate', // User is dragging nodes
    USER_DRAG_END: 'userDragEnd', // User finished dragging nodes
    USER_RESIZE_END: 'userResizeEnd', // User finished resizing a node via the gadget
    NODE_MEASURED: 'nodeMeasured', // A node's host slot was measured by the ResizeObserver (auto-axis write-back)
    NODE_CREATE_REQUEST: 'nodeCreateRequest', // Request to create node from context menu
    SPLIT_EDGE_WITH_REROUTE: 'splitEdgeWithReroute', // Split a data edge and insert a reroute node from the edge context menu
    DISSOLVE_REROUTE: 'dissolveReroute', // Dissolve a reroute node and bridge its connections
    EDGE_CREATED: 'edgeCreated', // New connection created
    EDGE_CLICKED: 'edgeClicked', // Connection clicked
    ELEMENT_REDRAW: 'elementRedraw', // redraw selected element
    ELEMENT_RESET: 'elementReset', // reset selected element
    ELEMENT_REVALIDATE: 'elementRevalidate', // revalidate selected element
    SELECTION_CHANGED: 'selectionChanged', // Selection state changed
    SELECTION_BOUNDS: 'selectionBounds', // Selection screen bounding box (toolbar anchor)
    SELECTION_BOUNDS_HIDE: 'selectionBoundsHide', // Hide the floating toolbar (gesture in progress)
    USER_REMOVE: 'userRemove', // User wants to remove elements
    USER_COPY_SELECTED: 'userCopySelected', // Copy selected elements to clipboard
    CONTEXT_MENU_CANVAS: 'contextMenuCanvas', // Canvas context menu triggered
    CONTEXT_MENU_EDGE: 'contextMenuEdge', // Connection context menu triggered
    CONTEXT_MENU_SELECTED: 'contextMenuSelected', // Context menu triggered on selected elements
    CONTEXT_MENU_CUSTOM: 'contextMenuCustom', // Custom-scope context menu triggered via data-hw-custom-menu-focus-id attribute
    CONTEXT_MENU_PORT: 'contextMenuPort', // Port context menu triggered via data-hw-port-menu-focus-id attribute
    USER_PASTE_CLIPBOARD: 'userPasteClipboard', // Paste clipboard contents
  },
  
  SyncCommands: {
    TOOLBAR_ACTION: 'toolbarAction', // Floating-toolbar button clicked
    SYNC_NODE_ADDITION: 'syncNodeAddition', // Sync node addition to UI
    SYNC_NODE_REMOVAL: 'syncNodeRemoval', // Sync node removal from UI
    SYNC_NODE_POSITION: 'syncNodePosition', // Sync node position to UI
    SYNC_EDGE_ADDITION: 'syncEdgeAddition', // Sync connection addition/update to UI with visual properties
    SYNC_EDGE_REMOVAL: 'syncEdgeRemoval', // Sync connection removal from UI
    SYNC_SELECTIONS: 'syncSelections', // Sync selection state to UI
    SYNC_CANVAS_CLEAR: 'syncCanvasClear', // Clear entire canvas
    SYNC_ALL_EDGES: 'syncAllEdges', // Sync all connections to UI
    SYNC_NODE_REDRAW: 'syncNodeRedraw', // Node DOM was rebuilt — re-attach observer and redraw edges
    SYNC_EDGES_UPDATE: 'syncEdgesUpdate', // Update connections for node
    SYNC_EDGE_RECONNECT: 'syncEdgeReconnect', // Remove an edge and start a new connection drag from the anchor pin
    SYNC_EDGE_CONNECT_RESUME: 'syncEdgeConnectResume', // Resume a paused pending connection drag (context menu dismissed without action)
    SYNC_EDGE_CONNECT_CANCEL: 'syncEdgeConnectCancel', // Cancel an in-progress connection drag (e.g. after auto-wire committed the edge)
    SYNC_REQUEST_CLIPBOARD_PASTE: 'syncRequestClipboardPaste', // Ask Vue to read the OS clipboard and emit a paste
  }
};

// Event creators - Make available globally
window.EventCreators = {
  createUserDragStart(nodes, sessionId = 'default') {
    return {
      event_type: 'userDragStart',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes },
      requires_broadcast: true
    };
  },

  createUserDragUpdate(positions, sessionId = 'default') {
    return {
      event_type: 'userDragUpdate',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { positions },
      requires_broadcast: true
    };
  },

  createUserDragEnd(nodes, sessionId = 'default') {
    return {
      event_type: 'userDragEnd',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes },
      requires_broadcast: true
    };
  },

  createUserResizeEnd(nodeId, width, height, size_adapt, posX, posY, sessionId = 'default') {
    return {
      event_type: 'userResizeEnd',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId, width, height, size_adapt, posX, posY },
      requires_broadcast: true
    };
  },

  createNodeMeasured(nodeId, width, height, sessionId = 'default') {
    return {
      event_type: 'nodeMeasured',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId, width, height },
      requires_broadcast: true
    };
  },

  createNodeCreateRequest(registryKey, position, pending_connection, sessionId = 'default') {
    return {
      event_type: 'nodeCreateRequest',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { registryKey, position, pending_connection },
      requires_broadcast: true
    };
  },

  createSplitEdgeWithReroute(edge_id, position, sessionId = 'default') {
    return {
      event_type: 'splitEdgeWithReroute',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { edge_id, position },
      requires_broadcast: true
    };
  },

  createDissolveReroute(node_id, sessionId = 'default') {
    return {
      event_type: 'dissolveReroute',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { node_id },
      requires_broadcast: true
    };
  },

  createEdgeCreated(sourceNodeId, outletPinId, sinkNodeId, inletPinId, sessionId = 'default') {
    return {
      event_type: 'edgeCreated',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { sourceNodeId, outletPinId, sinkNodeId, inletPinId },
      requires_broadcast: true
    };
  },

  createEdgeClicked(edge_id, sessionId = 'default') {
    return {
      event_type: 'edgeClicked',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { edge_id },
      requires_broadcast: true
    };
  },

  createElementRedraw(nodes, edges, sessionId = 'default') {
    return {
      event_type: 'elementRedraw',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, edges },
      requires_broadcast: true
    };
  },

  createElementReset(nodes, edges, sessionId = 'default') {
    return {
      event_type: 'elementReset',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, edges },
      requires_broadcast: true
    };
  },

  createElementRevalidate(nodes, edges, sessionId = 'default') {
    return {
      event_type: 'elementRevalidate',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, edges },
      requires_broadcast: true
    };
  },

  createSelectionChanged(selectedNodes, selectedEdges, activeNodeId, activeEdgeId, sessionId = 'default') {
    return {
      event_type: 'selectionChanged',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { selectedNodes, selectedEdges, activeNodeId, activeEdgeId },
      requires_broadcast: true
    };
  },

  createSelectionBounds(left, top, right, bottom, sessionId = 'default') {
    return {
      event_type: 'selectionBounds',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { left, top, right, bottom },
      requires_broadcast: true
    };
  },

  createSelectionBoundsHide(sessionId = 'default') {
    return {
      event_type: 'selectionBoundsHide',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: {  },
      requires_broadcast: true
    };
  },

  createUserRemove(nodes, edges, sessionId = 'default') {
    return {
      event_type: 'userRemove',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, edges },
      requires_broadcast: true
    };
  },

  createUserCopySelected(selectedNodes, selectedEdges, sessionId = 'default') {
    return {
      event_type: 'userCopySelected',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { selectedNodes, selectedEdges },
      requires_broadcast: true
    };
  },

  createContextMenuCanvas(screenX, screenY, canvasX, canvasY, pendingPinId, pendingNodeId, pendingPinDir, pendingFlowType, pendingDataType, sessionId = 'default') {
    return {
      event_type: 'contextMenuCanvas',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, pendingPinId, pendingNodeId, pendingPinDir, pendingFlowType, pendingDataType },
      requires_broadcast: true
    };
  },

  createContextMenuEdge(screenX, screenY, canvasX, canvasY, edge_id, atSinkEnd, sessionId = 'default') {
    return {
      event_type: 'contextMenuEdge',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, edge_id, atSinkEnd },
      requires_broadcast: true
    };
  },

  createContextMenuSelected(screenX, screenY, canvasX, canvasY, selectedNodes, selectedEdges, sessionId = 'default') {
    return {
      event_type: 'contextMenuSelected',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, selectedNodes, selectedEdges },
      requires_broadcast: true
    };
  },

  createContextMenuCustom(screenX, screenY, canvasX, canvasY, nodeId, scope, sessionId = 'default') {
    return {
      event_type: 'contextMenuCustom',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, nodeId, scope },
      requires_broadcast: true
    };
  },

  createContextMenuPort(screenX, screenY, canvasX, canvasY, nodeId, portId, scope, sessionId = 'default') {
    return {
      event_type: 'contextMenuPort',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, nodeId, portId, scope },
      requires_broadcast: true
    };
  },

  createUserPasteClipboard(canvasX, canvasY, clipboardText, sessionId = 'default') {
    return {
      event_type: 'userPasteClipboard',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { canvasX, canvasY, clipboardText },
      requires_broadcast: true
    };
  }
};

// Event validators - Make available globally  
window.EventValidators = {
  validateUserDragStart(data) {
    const requiredFields = ["nodes"];
    return requiredFields.every(field => field in data);
  },

  validateUserDragUpdate(data) {
    const requiredFields = ["positions"];
    return requiredFields.every(field => field in data);
  },

  validateUserDragEnd(data) {
    const requiredFields = ["nodes"];
    return requiredFields.every(field => field in data);
  },

  validateUserResizeEnd(data) {
    const requiredFields = ["nodeId", "width", "height", "size_adapt", "posX", "posY"];
    return requiredFields.every(field => field in data);
  },

  validateNodeMeasured(data) {
    const requiredFields = ["nodeId", "width", "height"];
    return requiredFields.every(field => field in data);
  },

  validateNodeCreateRequest(data) {
    const requiredFields = ["registryKey", "position", "pending_connection"];
    return requiredFields.every(field => field in data);
  },

  validateSplitEdgeWithReroute(data) {
    const requiredFields = ["edge_id", "position"];
    return requiredFields.every(field => field in data);
  },

  validateDissolveReroute(data) {
    const requiredFields = ["node_id"];
    return requiredFields.every(field => field in data);
  },

  validateEdgeCreated(data) {
    const requiredFields = ["sourceNodeId", "outletPinId", "sinkNodeId", "inletPinId"];
    return requiredFields.every(field => field in data);
  },

  validateEdgeClicked(data) {
    const requiredFields = ["edge_id"];
    return requiredFields.every(field => field in data);
  },

  validateElementRedraw(data) {
    const requiredFields = ["nodes", "edges"];
    return requiredFields.every(field => field in data);
  },

  validateElementReset(data) {
    const requiredFields = ["nodes", "edges"];
    return requiredFields.every(field => field in data);
  },

  validateElementRevalidate(data) {
    const requiredFields = ["nodes", "edges"];
    return requiredFields.every(field => field in data);
  },

  validateSelectionChanged(data) {
    const requiredFields = ["selectedNodes", "selectedEdges", "activeNodeId", "activeEdgeId"];
    return requiredFields.every(field => field in data);
  },

  validateSelectionBounds(data) {
    const requiredFields = ["left", "top", "right", "bottom"];
    return requiredFields.every(field => field in data);
  },

  validateSelectionBoundsHide(data) {
    const requiredFields = [];
    return requiredFields.every(field => field in data);
  },

  validateUserRemove(data) {
    const requiredFields = ["nodes", "edges"];
    return requiredFields.every(field => field in data);
  },

  validateUserCopySelected(data) {
    const requiredFields = ["selectedNodes", "selectedEdges"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuCanvas(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "pendingPinId", "pendingNodeId", "pendingPinDir", "pendingFlowType", "pendingDataType"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuEdge(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "edge_id", "atSinkEnd"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuSelected(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "selectedNodes", "selectedEdges"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuCustom(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "nodeId", "scope"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuPort(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "nodeId", "portId", "scope"];
    return requiredFields.every(field => field in data);
  },

  validateUserPasteClipboard(data) {
    const requiredFields = ["canvasX", "canvasY", "clipboardText"];
    return requiredFields.every(field => field in data);
  }
};

