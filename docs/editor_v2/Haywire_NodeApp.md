# Haywire Editor - Refined Architecture Overview

## Architecture Components

The Haywire Editor follows a clean 5-layer architecture with strict separation of concerns, event-driven communication, and multi-session support:

```
┌─────────────────────────────────────────────────────────────┐
│                    HaywireApplication                       │
│              (Bootstrap & Coordination)                     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      EditorUI                               │
│              (Layout & Visual Components)                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   HaywireEditor                             │
│              (Core Business Logic)                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   SessionManager                            │
│              (Multi-Client Coordination)                    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     GraphCanvas                             │
│              (Visual & Interactions)                        │
└─────────────────────────────────────────────────────────────┘
```

## 1. **HaywireEditor** (Core Business Logic)
**Single Responsibility**: Pure graph operations and business rules as the single source of truth

**Key Features:**
- **Single Source of Truth**: One HaywireEditor manages the authoritative graph state
- **UI-agnostic**: Can work with any frontend or headlessly
- **Undo/Redo Integration**: All operations create history actions
- **Validation**: Business rule enforcement for connections
- **Pure Business Logic**: No UI concerns or session management

**Core Methods:**
- `create_node(node_type, x, y)` - Create new node with validation
- `delete_node(node_id)` - Remove node and all connections
- `move_node(node_id, x, y)` - Update node position
- `create_connection(start_node, start_port, end_node, end_port)` - Create validated connection
- `delete_connection(connection_id)` - Remove connection
- `select_nodes(node_ids, multi_select)` - Update selection state
- `undo()` / `redo()` - History management
- `get_graph_state()` - Return complete graph state for synchronization

## 2. **SessionManager** (Multi-Client Coordination)
**Single Responsibility**: Managing multiple browser sessions and coordinating shared editor state

**Key Features:**
- **Session Registry**: Tracks active GraphCanvas instances across browser sessions
- **Event Coordination**: Routes events from GraphCanvas to HaywireEditor and back
- **State Broadcasting**: Synchronizes changes across all connected sessions
- **Session-Specific State**: Manages per-session UI modes and preferences
- **Pure Event-Driven**: No direct business logic, only coordination

**Core Methods:**
- `register_canvas(session_id, canvas_instance)` - Register new session
- `unregister_canvas(session_id)` - Clean up disconnected session
- `handle_canvas_event(session_id, event_data)` - Route events to HaywireEditor
- `broadcast_graph_change(change_type, change_data)` - Sync all sessions
- `set_session_mode(session_id, mode)` - Manage session-specific UI state
- `get_session_state(session_id)` - Return session UI state

**Session-Specific State Management:**
- **UI Modes**: creation_mode, tool_selection, interaction_mode
- **User Preferences**: grid_snap, auto_save, theme_preferences
- **Canvas Metadata**: active_sessions, session_timestamps

## 3. **GraphCanvas** (Pure Visual Component)
**Single Responsibility**: Visual representation and user interaction capture

**Key Features:**
- **NiceGUI Hybrid**: Python wrapper around Vue.js component for optimal UX
- **Pure Event Emission**: No business logic, only visual interactions and events
- **Context Menu Integration**: Right-click context menus for discoverability
- **Visual State Only**: Zoom, pan, selection highlighting, drag feedback
- **Real-time Interactions**: Smooth drag operations and visual feedback

**Event Emissions (to SessionManager):**
- `nodePositionChanged(node_id, x, y)` - User dragged node
- `connectionRequested(start_node, start_port, end_node, end_port)` - User connected pins
- `nodeCreationRequested(node_type, x, y)` - Context menu node creation
- `nodeSelectionChanged(node_ids, multi_select)` - User selection
- `nodeDeletionRequested(node_ids)` - Delete key or context menu
- `undoRequested()` / `redoRequested()` - Keyboard shortcuts

**Visual State Management:**
- **Zoom/Pan**: Canvas viewport transformation
- **Selection Highlighting**: Visual feedback for selected elements
- **Drag Feedback**: Real-time visual updates during interactions
- **Connection Previews**: Visual feedback during connection creation

**Context Menu System:**
- **Canvas Context**: Available node types for creation
- **Node Context**: Duplicate, delete, inspect, connect actions
- **Connection Context**: Delete, inspect, trace data flow

## 4. **EditorUI** (UI Layout & Component Orchestration)
**Single Responsibility**: Creating and managing application layout and UI components

**Key Features:**
- **Layout Management**: Responsive UI with panels and controls
- **Component Orchestration**: Coordinates all UI components
- **Statistics Display**: Shows graph metrics and operation counts
- **Tool Panels**: Node creation tools, property editors, debug panels
- **Session-Aware**: Creates appropriate UI for each browser session

**Core Methods:**
- `create_main_page()` - Build complete application layout
- `create_header()` - Main controls and application title
- `create_tool_panels()` - Left/right panels with tools and information
- `create_status_displays()` - Statistics, history, selection info
- `update_displays()` - Refresh all UI displays with current state
- `handle_ui_events()` - Process UI control interactions

**UI Components:**
- **Header**: Undo/redo, clear, save/load controls
- **Left Panel**: Node creation tools, mode controls, debug tools
- **Right Panel**: Statistics, history, selection details, property editors
- **Status Bar**: Current mode, zoom level, selection count

## 5. **HaywireApplication** (Bootstrap & Lifecycle)
**Single Responsibility**: Application setup, service initialization, and lifecycle management

**Key Features:**
- **Service Bootstrap**: Initialize and wire all application services
- **Dependency Injection**: Configure and provide shared services
- **Lifecycle Management**: Startup, shutdown, error recovery
- **Configuration**: Load and apply application settings

**Core Methods:**
- `initialize()` - Set up all services and dependencies
- `create_editor()` - Initialize core HaywireEditor instance
- `setup_session_manager()` - Configure multi-session support
- `run()` - Start the NiceGUI application
- `cleanup()` - Graceful shutdown and resource cleanup

## Event Flow Architecture

### User Interaction Flow
```
User Action → GraphCanvas (visual interaction)
          → emits event → SessionManager (coordination)
          → calls method → HaywireEditor (business logic)
          → returns result → SessionManager (broadcasting)
          → syncs state → All GraphCanvas instances (visual update)
```

### State Change Flow
```
HaywireEditor (authoritative state change)
          → notifies → SessionManager (change detection)
          → broadcasts → All Active GraphCanvas instances
          → update visuals → User sees synchronized changes
```

## Updated Use Cases

### 1. **User Creates Node via Context Menu**
```
User → Right-Click Canvas → GraphCanvas (show context menu)
     → User Selects Node Type → GraphCanvas (emit nodeCreationRequested)
     → SessionManager (route event) → HaywireEditor (create node + history)
     → SessionManager (broadcast change) → All GraphCanvas (sync visual state)
     → Node appears in all sessions
```

### 2. **User Moves Node**
```
User → Drag Node → GraphCanvas (real-time visual feedback)
     → Mouse Up → GraphCanvas (emit nodePositionChanged)
     → SessionManager (route event) → HaywireEditor (update position + undo action)
     → SessionManager (broadcast change) → All GraphCanvas (sync node position)
     → Position synchronized across all sessions
```

### 3. **User Creates Connection**
```
User → Drag Pin to Pin → GraphCanvas (visual feedback during drag)
     → Drop → GraphCanvas (emit connectionRequested)
     → SessionManager (route event) → HaywireEditor (validate + create connection)
     → SessionManager (broadcast change) → All GraphCanvas (add connection visual)
     → Connection appears in all sessions
```

### 4. **Undo Operation**
```
User → Ctrl+Z → GraphCanvas (emit undoRequested)
     → SessionManager (route event) → HaywireEditor (undo + restore state)
     → SessionManager (broadcast change) → All GraphCanvas (sync complete state)
     → All sessions show undone state
```

### 5. **User Selects Multiple Nodes**
```
User → Ctrl+Click Nodes → GraphCanvas (visual selection feedback)
     → Selection Complete → GraphCanvas (emit selectionChanged)
     → SessionManager (route event) → HaywireEditor (update selection state)
     → SessionManager (broadcast change) → All GraphCanvas (sync selection visuals)
     → Selection state synchronized across sessions
```

### 6. **User Deletes Node via Context Menu**
```
User → Right-Click Node → GraphCanvas (show node context menu)
     → User Clicks Delete → GraphCanvas (emit nodeDeletionRequested)
     → SessionManager (route event) → HaywireEditor (remove node + connections + history)
     → SessionManager (broadcast change) → All GraphCanvas (remove visuals)
     → Node and connections disappear from all sessions
```

## Key Architecture Benefits

### 1. **Clean Separation of Concerns**
- **GraphCanvas**: Pure visual representation with no business logic
- **SessionManager**: Pure coordination with no UI or business concerns
- **HaywireEditor**: Pure business logic with no UI dependencies
- **EditorUI**: Pure layout and component management
- **HaywireApplication**: Pure service setup and lifecycle

### 2. **Event-Driven Communication**
- **Loose Coupling**: Components only know about events, not each other
- **Testability**: Each layer can be tested independently
- **Extensibility**: Easy to add logging, metrics, or new features
- **Debugging**: Clear event trail for troubleshooting

### 3. **Multi-Session Scalability**
- **Shared State**: Single authoritative graph state
- **Independent UI**: Each session has its own visual state
- **Efficient Sync**: Only changed data is broadcast
- **Session Isolation**: UI problems in one session don't affect others

### 4. **Maintainability**
- **Single Responsibility**: Each component has one clear purpose
- **Predictable Flow**: Events always flow up, state changes flow down
- **Clear Boundaries**: No cross-cutting concerns or mixed responsibilities
- **Easy Testing**: Pure functions and clear interfaces throughout

### 5. **User Experience**
- **Real-time Collaboration**: Changes visible instantly across sessions
- **Smooth Interactions**: Visual feedback handled separately from business logic
- **Context-Aware UI**: Right-click menus provide discoverable actions
- **Reliable Undo/Redo**: Complete history management with proper grouping

## Implementation Guidelines by Layer

### 1. **HaywireEditor Implementation**

**Source Code Inspiration:**
- `UndoRedoTestAppWithCanvasManager.on_connection_created_for_specific_session()` → Core connection creation logic
- `UndoRedoTestAppWithCanvasManager.on_node_moved_for_specific_session()` → Node positioning business logic
- `UndoRedoTestAppWithCanvasManager.undo_action()` / `redo_action()` → History management patterns
- `UndoRedoTestAppWithCanvasManager.on_context_create_node_for_session()` → Node creation workflows

**Key Divergences:**
- **Remove all session handling** - HaywireEditor should be session-agnostic
- **Remove UI concerns** - No direct UI updates or display management
- **Pure business logic only** - Focus on graph operations and validation
- **Synchronous operations** - No async UI callbacks or timer-based updates
- **Single graph instance** - No per-session state management

**Implementation Focus:**
- Extract pure graph manipulation logic from session-specific methods
- Consolidate undo/redo actions from scattered implementations
- Create clean validation methods for connections and node operations
- Implement delta change notifications for SessionManager

### 2. **SessionManager Implementation**

**Source Code Inspiration:**
- `UndoRedoTestAppWithCanvasManager.get_session_data()` / `create_session_data()` → Session lifecycle patterns
- `UndoRedoTestAppWithCanvasManager.sync_all_sessions()` → Multi-session synchronization approach
- Session management patterns from `sessions` dictionary handling
- Event coordination patterns from session-specific event handlers

**Key Divergences:**
- **Pure event routing** - No direct business logic execution
- **Delta broadcasting** - Send specific changes, not complete state syncs
- **Remove UI management** - No direct UI container or display updates
- **Stateless coordination** - Only route events and coordinate sessions

**Implementation Focus:**
- Create event routing system between GraphCanvas and HaywireEditor
- Implement delta change broadcasting to multiple GraphCanvas instances
- Manage session registry and cleanup for disconnected clients
- Handle session-specific UI state (modes, preferences) separately from business state

### 3. **GraphCanvas Implementation**

**Source Code Inspiration:**
- `GraphCanvasManager` class structure → Visual representation patterns
- `GraphCanvasVue` component → Vue.js integration approach
- `graph_canvas.vue` → User interaction handling and event system
- Connection and node visual management from existing canvas implementations

**Key Divergences:**
- **Pure event emission** - Remove all direct business logic calls
- **No graph state ownership** - Only visual state (zoom, pan, selection highlighting)
- **Context menu integration** - Keep context menus but emit events instead of direct actions
- **Remove synchronization logic** - No `sync_with_graph()` or similar state management

**Implementation Focus:**
- Preserve the NiceGUI + Vue.js hybrid architecture
- Convert all business logic calls to semantic event emissions
- Maintain smooth visual interactions and real-time feedback
- Keep context menu UI but route all actions through events

### 4. **EditorUI Implementation**

**Source Code Inspiration:**
- `UndoRedoTestAppWithCanvasManager.create_ui()` → Overall layout structure
- `UndoRedoTestAppWithCanvasManager.create_header()` / `create_left_panel()` / `create_right_panel()` → Panel organization
- UI update methods like `update_displays_for_session()` → Display refresh patterns
- Statistics and information display patterns

**Key Divergences:**
- **Remove business logic** - No direct graph operations or undo/redo execution
- **Remove session management** - Focus on UI layout, not session coordination
- **Event-driven updates** - React to state changes via events, not direct polling
- **Component orchestration only** - Coordinate UI components, don't manage their internal state

**Implementation Focus:**
- Extract UI creation and layout management from current application class
- Create display update patterns that respond to graph state changes
- Organize tool panels and information displays cleanly
- Handle UI control events (buttons, menus) by routing to appropriate layers

### 5. **HaywireApplication Implementation**

**Source Code Inspiration:**
- `UndoRedoTestAppWithCanvasManager.__init__()` → Service initialization patterns
- `UndoRedoTestAppWithCanvasManager.setup_library_system()` → Dependency injection setup
- `UndoRedoTestAppWithCanvasManager.run()` → Application lifecycle management
- DI system configuration from library service setup

**Key Divergences:**
- **Pure bootstrap responsibility** - No UI creation or business logic
- **Service wiring only** - Configure dependencies but don't manage ongoing operations
- **Clean separation** - Initialize each layer independently with clear interfaces
- **Lifecycle management** - Handle startup/shutdown without operational concerns

**Implementation Focus:**
- Extract service initialization from current mixed-responsibility class
- Create clean dependency injection for all layers
- Implement proper startup/shutdown lifecycle
- Configure inter-layer communication patterns without managing the communication itself

### General Migration Principles

**What to Preserve:**
- NiceGUI + Vue.js integration patterns from GraphCanvas components
- Undo/redo action system and history management approach
- Multi-session coordination concepts from current session handling
- Context menu integration and user interaction patterns

**What to Eliminate:**
- Mixed responsibilities and cross-cutting concerns in current classes
- Direct business logic calls from UI components
- Session-specific business logic handling
- Synchronous state polling and manual display updates

**New Patterns to Implement:**
- Pure event-driven communication between all layers
- Delta-based state synchronization for multi-session support
- Clean separation between visual state and business state
- Semantic event names that describe user intent, not implementation details

## Event-Driven Communication Protocol

### Event Structure

Each event follows a consistent format for predictable communication:

```python
@dataclass
class GraphEvent:
    event_type: str           # Semantic event name (camelCase)
    source_session_id: str    # Which session originated the event
    timestamp: float          # When the event occurred
    data: Dict[str, Any]      # Event-specific payload
    requires_broadcast: bool  # Whether to sync to other sessions
```

### Event Type Definitions

Event types are defined separately in JavaScript and Python for optimal IDE support, with verification to ensure synchronization.

**JavaScript Definition (graph_canvas_events.js):**
```javascript
export const GraphEvents = {

/*
    IMPORTANT: Keep in sync with graph_events.py
    When adding/removing/changing events:
    1. Update both files simultaneously
    2. Run sync verification script: python verify_events_sync.py
    3. Update tests that use these events
*/

  // User interactions (Vue → Python)
  USER_INTERACTIONS: {
    NODE_CREATION_REQUESTED: 'nodeCreationRequested',
    NODE_POSITION_CHANGED: 'nodePositionChanged',
    CONNECTION_REQUESTED: 'connectionRequested',
    UNDO_REQUESTED: 'undoRequested',
    REDO_REQUESTED: 'redoRequested',
    NODE_SELECTION_CHANGED: 'nodeSelectionChanged',
    NODE_DELETION_REQUESTED: 'nodeDeletionRequested'
  },
  
  // Sync commands (Python → Vue)
  SYNC_COMMANDS: {
    SYNC_NODE_ADDITION: 'syncNodeAddition',
    SYNC_NODE_REMOVAL: 'syncNodeRemoval', 
    SYNC_NODE_POSITION: 'syncNodePosition',
    SYNC_CONNECTION_ADDITION: 'syncConnectionAddition',
    SYNC_CONNECTION_REMOVAL: 'syncConnectionRemoval',
    SYNC_SELECTION_STATE: 'syncSelectionState'
  }
}
```

**Python Definition (graph_events.py):**
```python
class GraphEvents:
    """
    Event type definitions for graph canvas communication.
    
    IMPORTANT: Keep in sync with graph_canvas_events.js
    When adding/removing/changing events:
    1. Update both files simultaneously
    2. Run sync verification script: python verify_events_sync.py
    3. Update tests that use these events
    """
    
    class UserInteractions:
        """Events from Vue component to Python (user actions)"""
        NODE_CREATION_REQUESTED = 'nodeCreationRequested'
        NODE_POSITION_CHANGED = 'nodePositionChanged'
        CONNECTION_REQUESTED = 'connectionRequested'
        UNDO_REQUESTED = 'undoRequested'
        REDO_REQUESTED = 'redoRequested'
        NODE_SELECTION_CHANGED = 'nodeSelectionChanged'
        NODE_DELETION_REQUESTED = 'nodeDeletionRequested'
    
    class StateChanges:
        """Events from HaywireEditor to SessionManager (state changes)"""
        NODE_ADDED = 'nodeAdded'
        NODE_REMOVED = 'nodeRemoved'
        NODE_MOVED = 'nodeMoved'
        CONNECTION_ADDED = 'connectionAdded'
        CONNECTION_REMOVED = 'connectionRemoved'
        SELECTION_UPDATED = 'selectionUpdated'
        HISTORY_CHANGED = 'historyChanged'
    
    class SyncCommands:
        """Events from SessionManager to Vue component (sync updates)"""
        SYNC_NODE_ADDITION = 'syncNodeAddition'
        SYNC_NODE_REMOVAL = 'syncNodeRemoval'
        SYNC_NODE_POSITION = 'syncNodePosition'
        SYNC_CONNECTION_ADDITION = 'syncConnectionAddition'
        SYNC_CONNECTION_REMOVAL = 'syncConnectionRemoval'
        SYNC_SELECTION_STATE = 'syncSelectionState'
```

### Usage Examples

**In Vue Component (graph_canvas.vue):**
```javascript
import { GraphEvents } from './graph_canvas_events.js'

export default {
  methods: {
    handleNodeDragEnd(nodeId, x, y, positionChanged) {
      if (positionChanged) {
        this.$emit(GraphEvents.USER_INTERACTIONS.NODE_POSITION_CHANGED, {
          nodeId, x, y, timestamp: Date.now()
        })
      }
    },
    
    applySyncEvent(eventType, eventData) {
      if (eventType === GraphEvents.SYNC_COMMANDS.SYNC_NODE_ADDITION) {
        this.addNodeVisual(eventData)
      }
    }
  }
}
```

**In Python Classes:**
```python
from graph_events import GraphEvents

class SessionManager:
    def handle_canvas_event(self, event):
        if event.event_type == GraphEvents.UserInteractions.NODE_CREATION_REQUESTED:
            # Handle node creation
            pass
        elif event.event_type == GraphEvents.UserInteractions.UNDO_REQUESTED:
            # Handle undo
            pass
```

### Communication Patterns

**Upward Flow (User Interactions)**:
```python
# In GraphCanvas
def handle_user_action(self, action_type, action_data):
    event = GraphEvent(
        event_type=action_type,
        source_session_id=self.session_id,
        timestamp=time.time(),
        data=action_data,
        requires_broadcast=True
    )
    self.emit_to_session_manager(event)

# In SessionManager  
def handle_canvas_event(self, event: GraphEvent):
    # Route to business logic
    result = self.haywire_editor.process_event(event)
    
    # If successful, broadcast to other sessions
    if result.success and event.requires_broadcast:
        self.broadcast_change(result.change_event)
```

**Downward Flow (State Synchronization)**:
```python
# In SessionManager
def broadcast_change(self, change_event: GraphEvent):
    for session_id, canvas in self.active_canvases.items():
        # Don't send back to originating session
        if session_id != change_event.source_session_id:
            sync_event = self.convert_to_sync_event(change_event)
            canvas.apply_sync_event(sync_event)

# In GraphCanvas
def apply_sync_event(self, sync_event: GraphEvent):
    if sync_event.event_type == GraphEvents.SyncCommands.SYNC_NODE_ADDITION:
        self.add_node_visual(sync_event.data)
    elif sync_event.event_type == GraphEvents.SyncCommands.SYNC_NODE_POSITION:
        self.update_node_position(sync_event.data)
    # ... etc
```

### Event Synchronization Verification

**Automated Sync Verification (verify_events_sync.py):**
```python
#!/usr/bin/env python3
"""
Verification script to ensure JavaScript and Python event definitions are in sync.
Run this script whenever you modify event definitions.
"""

import json
import re
from pathlib import Path

def extract_js_events(js_file_path):
    """Extract event definitions from JavaScript file"""
    with open(js_file_path) as f:
        content = f.read()
    
    pattern = r"(\w+):\s*['\"](\w+)['\"]"
    matches = re.findall(pattern, content)
    return {key: value for key, value in matches}

def extract_python_events(py_file_path):
    """Extract event definitions from Python file"""
    events = {}
    import sys
    sys.path.insert(0, str(py_file_path.parent))
    
    from graph_events import GraphEvents
    
    for class_name in ['UserInteractions', 'StateChanges', 'SyncCommands']:
        event_class = getattr(GraphEvents, class_name)
        for attr_name in dir(event_class):
            if not attr_name.startswith('_'):
                events[attr_name] = getattr(event_class, attr_name)
    
    return events

def verify_sync():
    """Verify that JavaScript and Python definitions are in sync"""
    project_root = Path(__file__).parent
    js_file = project_root / "graph_canvas_events.js" 
    py_file = project_root / "graph_events.py"
    
    try:
        js_events = extract_js_events(js_file)
        py_events = extract_python_events(py_file)
        
        js_only = set(js_events.values()) - set(py_events.values())
        py_only = set(py_events.values()) - set(js_events.values())
        
        if js_only or py_only:
            print("❌ Event definitions are NOT in sync!")
            if js_only:
                print(f"JavaScript only: {js_only}")
            if py_only:
                print(f"Python only: {py_only}")
            return False
        else:
            print("✅ Event definitions are in sync!")
            return True
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = verify_sync()
    sys.exit(0 if success else 1)
```

### Maintenance Guidelines

**Adding New Events:**
1. Add to both `graph_canvas_events.js` AND `graph_events.py`
2. Use identical string values in both files  
3. Run `python verify_events_sync.py` to verify sync
4. Update any affected tests

**Event Naming Convention:**
- Use camelCase for event strings (JavaScript-friendly)
- Use UPPER_SNAKE_CASE for Python constants
- Keep event names descriptive and action-oriented

**Pre-commit Verification:**
```bash
python verify_events_sync.py || exit 1
```

### Event Validation and Error Handling

**At SessionManager Level**:
```python
def validate_event(self, event: GraphEvent) -> bool:
    # Check event structure
    if not event.event_type or not event.source_session_id:
        return False
    
    # Validate session is still active
    if event.source_session_id not in self.active_sessions:
        return False
        
    # Event-specific validation
    return self.validate_event_data(event.event_type, event.data)
```

**Error Response Events**:
```python
# For failed operations
"operationFailed"          # data: {original_event, error_message, error_code}
"validationFailed"         # data: {field_name, validation_error}
```

### Protocol Benefits

**IDE Support**: Full autocomplete in both JavaScript and Python with separate, properly typed definitions.

**Type Safety**: Structured events with clear data contracts make the system predictable and debuggable.

**Sync Verification**: Automated checking ensures JavaScript and Python definitions remain synchronized.

**Extensibility**: New event types can be added without changing the core routing mechanism.

**Testing**: Each layer can be tested in isolation by mocking the event interface.

**Debugging**: Complete event trail provides clear audit log of all user actions and state changes.

**Race Condition Management**: The SessionManager serializes operations through the single HaywireEditor instance to maintain consistency when multiple sessions perform operations simultaneously.

### Implementation Considerations

**Event Ordering**: Critical operations should include sequence numbers to handle out-of-order delivery in complex scenarios.

**Session Recovery**: When a session reconnects, it should receive a complete state sync event to rebuild its visual representation.

**Performance**: High-frequency events (like mouse movements during drag) should be throttled at the GraphCanvas level to avoid overwhelming the system.

**Persistence**: Events can be logged for debugging, analytics, or implementing operation replay functionality.
