// Auto-generated from Python event definitions
// DO NOT EDIT MANUALLY - Run `python generate_vue_events.py` to update

// Event type constants - Make available globally
window.GraphEvents = {
  UserInteractions: {
    USER_DRAG_START: 'userDragStart', // User started dragging nodes
    USER_DRAG_UPDATE: 'userDragUpdate', // User is dragging nodes
    USER_DRAG_END: 'userDragEnd', // User finished dragging nodes
    USER_REMOVE: 'userRemove', // User wants to remove elements
    NODE_CREATE_REQUEST: 'nodeCreateRequest', // Request to create node from context menu
    EDGE_CREATED: 'edgeCreated', // New edge created
    EDGE_CLICKED: 'edgeClicked', // Edge clicked
    SELECTION_CHANGED: 'selectionChanged', // Selection state changed
    CONTEXT_MENU_CANVAS: 'contextMenuCanvas', // Canvas context menu triggered
    CONTEXT_MENU_NODE: 'contextMenuNode', // Node context menu triggered
    CONTEXT_MENU_EDGE: 'contextMenuEdge', // Edge context menu triggered
    CONTEXT_MENU_SELECTED: 'contextMenuSelected', // Context menu triggered on selected elements
    USER_COPY_SELECTED: 'userCopySelected', // Copy selected elements to clipboard
    USER_PASTE_CLIPBOARD: 'userPasteClipboard', // Paste clipboard contents
  },
  
  SyncCommands: {
    SYNC_NODE_ADDITION: 'syncNodeAddition', // Sync node addition to UI
    SYNC_NODE_REMOVAL: 'syncNodeRemoval', // Sync node removal from UI
    SYNC_NODE_POSITION: 'syncNodePosition', // Sync node position to UI
    SYNC_EDGE_ADDITION: 'syncEdgeAddition', // Sync edge addition/update to UI with visual properties
    SYNC_EDGE_REMOVAL: 'syncEdgeRemoval', // Sync edge removal from UI
    SYNC_SELECTIONS: 'syncSelections', // Sync selection state to UI
    SYNC_CANVAS_CLEAR: 'syncCanvasClear', // Clear entire canvas
    SYNC_ALL_EDGES: 'syncAllEdges', // Sync all edges to UI
    SYNC_NODE_OBSERVER_ADD: 'syncNodeObserverAdd', // Add node observer
    SYNC_NODE_OBSERVER_REMOVE: 'syncNodeObserverRemove', // Remove node observer
    SYNC_EDGES_UPDATE: 'syncEdgesUpdate', // Update edges for node
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

  createUserDragUpdate(nodes, deltaX, deltaY, sessionId = 'default') {
    return {
      event_type: 'userDragUpdate',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, deltaX, deltaY },
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

  createUserRemove(nodes, edges, sessionId = 'default') {
    return {
      event_type: 'userRemove',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodes, edges },
      requires_broadcast: true
    };
  },

  createNodeCreateRequest(registryKey, position, sessionId = 'default') {
    return {
      event_type: 'nodeCreateRequest',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { registryKey, position },
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

  createSelectionChanged(selectedNodes, selectedEdges, sessionId = 'default') {
    return {
      event_type: 'selectionChanged',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { selectedNodes, selectedEdges },
      requires_broadcast: true
    };
  },

  createContextMenuCanvas(screenX, screenY, canvasX, canvasY, sessionId = 'default') {
    return {
      event_type: 'contextMenuCanvas',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY },
      requires_broadcast: true
    };
  },

  createContextMenuNode(screenX, screenY, canvasX, canvasY, nodeId, sessionId = 'default') {
    return {
      event_type: 'contextMenuNode',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, nodeId },
      requires_broadcast: true
    };
  },

  createContextMenuEdge(screenX, screenY, canvasX, canvasY, edge_id, sessionId = 'default') {
    return {
      event_type: 'contextMenuEdge',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, edge_id },
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

  createUserCopySelected(selectedNodes, selectedEdges, sessionId = 'default') {
    return {
      event_type: 'userCopySelected',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { selectedNodes, selectedEdges },
      requires_broadcast: true
    };
  },

  createUserPasteClipboard(canvasX, canvasY, sessionId = 'default') {
    return {
      event_type: 'userPasteClipboard',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { canvasX, canvasY },
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
    const requiredFields = ["nodes", "deltaX", "deltaY"];
    return requiredFields.every(field => field in data);
  },

  validateUserDragEnd(data) {
    const requiredFields = ["nodes"];
    return requiredFields.every(field => field in data);
  },

  validateUserRemove(data) {
    const requiredFields = ["nodes", "connections"];
    return requiredFields.every(field => field in data);
  },

  validateNodeCreateRequest(data) {
    const requiredFields = ["registryKey", "position"];
    return requiredFields.every(field => field in data);
  },

  validateEdgeCreated(data) {
    const requiredFields = ["outputNodeId", "outletPinId", "inputNodeId", "inletPinId"];
    return requiredFields.every(field => field in data);
  },

  validateEdgeClicked(data) {
    const requiredFields = ["edge_id"];
    return requiredFields.every(field => field in data);
  },

  validateSelectionChanged(data) {
    const requiredFields = ["selectedNodes", "selectedEdges"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuCanvas(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuNode(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "nodeId"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuEdge(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "edge_id"];
    return requiredFields.every(field => field in data);
  },

  validateContextMenuSelected(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "selectedNodes", "selectedEdges"];
    return requiredFields.every(field => field in data);
  },

  validateUserCopySelected(data) {
    const requiredFields = ["selectedNodes", "selectedEdges"];
    return requiredFields.every(field => field in data);
  },

  validateUserPasteClipboard(data) {
    const requiredFields = ["canvasX", "canvasY"];
    return requiredFields.every(field => field in data);
  }
};

