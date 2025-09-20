// Auto-generated from Python event definitions
// DO NOT EDIT MANUALLY - Run `python generate_vue_events.py` to update

// Event type constants
export const GraphEvents = {
  UserInteractions: {
    NODE_CREATED: 'nodeCreated', // New node created on canvas
    NODE_POSITION_CHANGED: 'nodePositionChanged', // Node position updated
    CONNECTION_CREATED: 'connectionCreated', // New connection created
    CONNECTION_REMOVED: 'connectionRemoved', // Connection removed
    CONNECTION_CLICKED: 'connectionClicked', // Connection clicked
    NODE_DRAG_START: 'nodeDragStart', // Node drag started
    NODE_DRAG_END: 'nodeDragEnd', // Node drag ended
    SELECTION_CHANGED: 'selectionChanged', // Selection state changed
    CONTEXT_MENU_CANVAS: 'contextMenuCanvas', // Canvas context menu triggered
    CONTEXT_MENU_NODE: 'contextMenuNode', // Node context menu triggered
    CONTEXT_MENU_CONNECTION: 'contextMenuConnection', // Connection context menu triggered
  },
  
  SyncCommands: {
    SYNC_NODE_ADDITION: 'syncNodeAddition', // Sync node addition to UI
    SYNC_NODE_REMOVAL: 'syncNodeRemoval', // Sync node removal from UI
    SYNC_NODE_POSITION: 'syncNodePosition', // Sync node position to UI
    SYNC_CONNECTION_ADDITION: 'syncConnectionAddition', // Sync connection addition to UI
    SYNC_CONNECTION_REMOVAL: 'syncConnectionRemoval', // Sync connection removal from UI
    SYNC_SELECTION_STATE: 'syncSelectionState', // Sync selection state to UI
    SYNC_CANVAS_CLEAR: 'syncCanvasClear', // Clear entire canvas
    SYNC_ALL_CONNECTIONS: 'syncAllConnections', // Sync all connections to UI
  }
};

// Event creators
export class EventCreators {

  static createNodeCreated(nodeId, position, sessionId = 'default') {
    return {
      event_type: 'nodeCreated',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId, position },
      requires_broadcast: true
    };
  }

  static createNodePositionChanged(nodeId, position, sessionId = 'default') {
    return {
      event_type: 'nodePositionChanged',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId, position },
      requires_broadcast: true
    };
  }

  static createConnectionCreated(outputNodeId, outletPinId, inputNodeId, inletPinId, sessionId = 'default') {
    return {
      event_type: 'connectionCreated',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { outputNodeId, outletPinId, inputNodeId, inletPinId },
      requires_broadcast: true
    };
  }

  static createConnectionRemoved(connectionId, sessionId = 'default') {
    return {
      event_type: 'connectionRemoved',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { connectionId },
      requires_broadcast: true
    };
  }

  static createConnectionClicked(connectionId, sessionId = 'default') {
    return {
      event_type: 'connectionClicked',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { connectionId },
      requires_broadcast: true
    };
  }

  static createNodeDragStart(nodeId, sessionId = 'default') {
    return {
      event_type: 'nodeDragStart',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId },
      requires_broadcast: true
    };
  }

  static createNodeDragEnd(nodeId, positionChanged, sessionId = 'default') {
    return {
      event_type: 'nodeDragEnd',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { nodeId, positionChanged },
      requires_broadcast: true
    };
  }

  static createSelectionChanged(selectedNodes, selectedConnections, sessionId = 'default') {
    return {
      event_type: 'selectionChanged',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { selectedNodes, selectedConnections },
      requires_broadcast: true
    };
  }

  static createContextMenuCanvas(screenX, screenY, canvasX, canvasY, sessionId = 'default') {
    return {
      event_type: 'contextMenuCanvas',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY },
      requires_broadcast: true
    };
  }

  static createContextMenuNode(screenX, screenY, canvasX, canvasY, nodeId, sessionId = 'default') {
    return {
      event_type: 'contextMenuNode',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, nodeId },
      requires_broadcast: true
    };
  }

  static createContextMenuConnection(screenX, screenY, canvasX, canvasY, connectionId, sessionId = 'default') {
    return {
      event_type: 'contextMenuConnection',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: { screenX, screenY, canvasX, canvasY, connectionId },
      requires_broadcast: true
    };
  }
}

// Event validators  
export class EventValidators {

  static validateNodeCreated(data) {
    const requiredFields = ["nodeId", "position"];
    return requiredFields.every(field => field in data);
  }

  static validateNodePositionChanged(data) {
    const requiredFields = ["nodeId", "position"];
    return requiredFields.every(field => field in data);
  }

  static validateConnectionCreated(data) {
    const requiredFields = ["outputNodeId", "outletPinId", "inputNodeId", "inletPinId"];
    return requiredFields.every(field => field in data);
  }

  static validateConnectionRemoved(data) {
    const requiredFields = ["connectionId"];
    return requiredFields.every(field => field in data);
  }

  static validateConnectionClicked(data) {
    const requiredFields = ["connectionId"];
    return requiredFields.every(field => field in data);
  }

  static validateNodeDragStart(data) {
    const requiredFields = ["nodeId"];
    return requiredFields.every(field => field in data);
  }

  static validateNodeDragEnd(data) {
    const requiredFields = ["nodeId", "positionChanged"];
    return requiredFields.every(field => field in data);
  }

  static validateSelectionChanged(data) {
    const requiredFields = ["selectedNodes", "selectedConnections"];
    return requiredFields.every(field => field in data);
  }

  static validateContextMenuCanvas(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY"];
    return requiredFields.every(field => field in data);
  }

  static validateContextMenuNode(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "nodeId"];
    return requiredFields.every(field => field in data);
  }

  static validateContextMenuConnection(data) {
    const requiredFields = ["screenX", "screenY", "canvasX", "canvasY", "connectionId"];
    return requiredFields.every(field => field in data);
  }
}
