# Haywire Editor - Comprehensive Architecture Overview

## Architecture Components

The Haywire Editor follows a clean 5-layer architecture with proper separation of concerns, multi-session support, and event-driven communication:

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
│                   SessionManager                            │
│              (Multi-Client Coordination)                    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     GraphCanvas                             │
│              (Visual & Interactions)                        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   HaywireEditor                             │
│              (Core Business Logic)                          │
└─────────────────────────────────────────────────────────────┘
```

## 1. **HaywireEditor** (Core Business Logic)
**Single Responsibility**: Pure graph operations and business rules

```python
class HaywireEditor:
    """Core editor managing graph state and operations."""
    
    def __init__(self, graph: HaywireGraph, node_factory, history_manager):
        self.graph = graph
        self.node_factory = node_factory
        self.history_manager = history_manager
    
    # Node Operations
    def create_node(self, node_type: str, position: Tuple[float, float]) -> BaseNode
    def delete_node(self, node_id: str) -> bool
    def move_node(self, node_id: str, position: Tuple[float, float]) -> bool
    
    # Connection Operations  
    def create_connection(self, from_node_id: str, from_port: str, to_node_id: str, to_port: str) -> Edge
    def delete_connection(self, edge: Edge) -> bool
    def validate_connection(self, from_node_id: str, from_port: str, to_node_id: str, to_port: str) -> bool
    
    # Selection Operations
    def select_nodes(self, node_ids: List[str], multi_select: bool = False)
    def select_connections(self, connection_ids: List[str], multi_select: bool = False) 
    def clear_selection()
    def delete_selected()
    
    # History Operations
    def undo() -> bool
    def redo() -> bool
    
    # Context Menu Operations
    def duplicate_node(self, node_id: str, offset: Tuple[float, float] = (50, 50)) -> BaseNode
    def get_node_info(self, node_id: str) -> dict
    def get_connection_info(self, connection_id: str) -> dict
```

**Key Features:**
- **Editor as Single Source of Truth**: One HaywireEditor manages all operations
- **UI-agnostic**: Can work with any frontend or headlessly
- **Undo/Redo Integration**: All operations create history actions
- **Validation**: Business rule enforcement for connections
- **Context Operations**: Support for context menu actions

## 2. **GraphCanvas** (Unified Visual Component)
**Single Responsibility**: Visual representation and direct user interactions

```python
class GraphCanvas(ui.element, component='graph_canvas.vue'):
    """Unified graph canvas with integrated Python/Vue functionality."""
    
    def __init__(self, editor: HaywireEditor, node_render_factory, zoom_container, **callbacks):
        super().__init__()
        self.editor = editor
        self.node_render_factory = node_render_factory
        self.zoom_container = zoom_container
        
        # Visual state (single source of truth)
        self.node_visuals: Dict[str, Dict] = {}
        self.connection_visuals: Dict[str, str] = {}
        
        # Vue event handlers (direct)
        self.on('nodePositionChanged', self._handle_node_moved)
        self.on('connectionCreated', self._handle_connection_created)
        self.on('connectionRemoved', self._handle_connection_removed)
        self.on('selectionChanged', self._handle_selection_changed)
        self.on('contextMenuCanvas', self._handle_context_menu_canvas)
        self.on('contextMenuNode', self._handle_context_menu_node)
        self.on('contextMenuConnection', self._handle_context_menu_connection)
    
    # Visual Management
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float])
    def remove_node_visual(self, node_id: str)
    def add_connection_visual(self, edge: Edge)
    def remove_connection_visual(self, connection_id: str)
    
    # Context Menu Integration
    def show_context_menu(self, menu_type: str, x: float, y: float, target_data: dict)
    def _handle_context_menu_canvas(self, screen_x, screen_y, canvas_x, canvas_y)
    def _handle_context_menu_node(self, node_id: str, x: float, y: float)
    def _handle_context_menu_connection(self, connection_id: str, x: float, y: float)
```

**Key Features:**
- **Hybrid Architecture**: Python wrapper around Vue.js component
- **Real-time Interactions**: Smooth drag operations, connection creation
- **Context Menu System**: Integrated right-click context menus
- **Selection Management**: Multi-select with visual feedback
- **Event Delegation**: Clean separation between UI and business logic

## 3. **SessionManager** (Multi-Client Support)
**Single Responsibility**: Managing multiple browser sessions with shared editor

```python
class SessionManager:
    """Manages multiple browser sessions with shared editor state."""
    
    def __init__(self, editor: HaywireEditor):
        self.editor = editor  # Shared across all sessions
        self.sessions: Dict[str, SessionData] = {}
        self.active_canvases: Dict[str, GraphCanvas] = {}
    
    # Session Lifecycle
    def get_or_create_session(self, client_id: str) -> SessionData
    def cleanup_session(self, client_id: str)
    
    # Cross-Session Synchronization
    def broadcast_editor_change(self, change_type: str, **data):
        """Notify all active sessions of editor changes."""
        for client_id, canvas in self.active_canvases.items():
            try:
                if change_type == 'node_added':
                    canvas.add_node_visual(data['node'], data['position'])
                elif change_type == 'node_removed':
                    canvas.remove_node_visual(data['node_id'])
                elif change_type == 'connection_added':
                    canvas.add_connection_visual(data['edge'])
                elif change_type == 'selection_changed':
                    canvas.highlight_selected(data['nodes'], data['connections'])
                elif change_type == 'context_action':
                    # Context menu actions are broadcast to all sessions
                    canvas.refresh_all_visuals()
            except RuntimeError:
                self.mark_for_cleanup(client_id)
    
    # Context Menu Session Handling
    def handle_context_action(self, client_id: str, action_type: str, **params):
        """Handle context menu actions that affect shared state."""
        if action_type == 'create_node':
            node = self.editor.create_node(params['node_type'], (params['x'], params['y']))
            self.broadcast_editor_change('node_added', node=node, position=(params['x'], params['y']))
        
        elif action_type == 'delete_node':
            success = self.editor.delete_node(params['node_id'])
            if success:
                self.broadcast_editor_change('node_removed', node_id=params['node_id'])
        
        elif action_type == 'duplicate_node':
            new_node = self.editor.duplicate_node(params['node_id'], params.get('offset', (50, 50)))
            self.broadcast_editor_change('node_added', node=new_node, position=new_node.position)
        
        elif action_type == 'delete_connection':
            success = self.editor.delete_connection_by_id(params['connection_id'])
            if success:
                self.broadcast_editor_change('connection_removed', connection_id=params['connection_id'])
```

**Key Features:**
- **Shared State**: Single editor instance across all browser sessions
- **Independent UI State**: Each session has its own view/zoom settings
- **Broadcast System**: Efficient delta updates to all connected clients
- **Context Menu Coordination**: Context actions affect all sessions simultaneously

## 4. **EditorUI** (UI Layout & Components)
**Single Responsibility**: Creating and managing UI layout and controls

```python
class EditorUI:
    """Handles UI layout, panels, and visual components."""
    
    def __init__(self, session_manager: SessionManager, node_registry):
        self.session_manager = session_manager
        self.node_registry = node_registry
        self.editor = session_manager.editor
    
    def create_main_page(self):
        """Create the main page layout."""
        @ui.page('/', title="Haywire Editor")
        def main_page():
            session_data, client_id = self.session_manager.get_or_create_session()
            
            self.create_header(session_data, client_id)
            
            with ui.row().classes('w-full flex-grow gap-4 p-4'):
                self.create_left_panel(session_data, client_id)
                self.create_main_editor_panel(session_data, client_id)
                self.create_right_panel(session_data, client_id)
    
    def create_main_editor_panel(self, session_data, client_id):
        """Create the main editor panel with canvas."""
        with ui.card().classes('flex-grow'):
            # Create canvas with context menu integration
            canvas = GraphCanvas(
                editor=self.editor,
                node_render_factory=self.node_render_factory,
                zoom_container=zoom_container,
                on_context_canvas=lambda e: self._handle_context_canvas(client_id, e),
                on_context_node=lambda e: self._handle_context_node(client_id, e),
                on_context_connection=lambda e: self._handle_context_connection(client_id, e)
            )
            
            # Register canvas with session manager
            self.session_manager.register_canvas(client_id, canvas)
    
    # Context Menu Event Handlers
    def _handle_context_canvas(self, client_id: str, event_data: dict):
        """Handle canvas context menu."""
        self.session_manager.handle_context_action(
            client_id, 'show_canvas_context',
            x=event_data['canvasX'], 
            y=event_data['canvasY'],
            available_nodes=self.node_registry.list_names()
        )
    
    def _handle_context_node(self, client_id: str, event_data: dict):
        """Handle node context menu."""
        self.session_manager.handle_context_action(
            client_id, 'show_node_context',
            node_id=event_data['nodeId'],
            x=event_data['x'],
            y=event_data['y']
        )
    
    def _handle_context_connection(self, client_id: str, event_data: dict):
        """Handle connection context menu."""
        self.session_manager.handle_context_action(
            client_id, 'show_connection_context',
            connection_id=event_data['connectionId'],
            x=event_data['x'],
            y=event_data['y']
        )
```

**Key Features:**
- **Layout Management**: Responsive UI with left/center/right panels
- **Context Menu Integration**: Wires context events to business logic
- **Session-Aware**: Each browser session gets its own UI instance
- **Component Orchestration**: Coordinates all UI components

## 5. **HaywireApplication** (Top-Level Coordinator)
**Single Responsibility**: Application bootstrap, service setup, and lifecycle management

```python
class HaywireApplication:
    """Main application coordinator - setup, initialization, and lifecycle."""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        
        # Initialize in order
        self._setup_services()
        self._setup_core_components()
        self._setup_ui()
    
    def _setup_core_components(self):
        """Initialize core business components."""
        # Create shared graph
        graph = HaywireGraph("main_graph", "Main Editor Graph")
        
        # Create core editor
        self.editor = HaywireEditor(
            graph=graph,
            node_factory=self.services['node_factory'],
            history_manager=self.services['history_manager']
        )
        
        # Create session manager
        self.session_manager = SessionManager(self.editor)
    
    def _setup_ui(self):
        """Initialize UI system."""
        self.ui = EditorUI(
            session_manager=self.session_manager,
            node_registry=self.services['node_registry']
        )
    
    def run(self, port: int = 8082, **ui_kwargs):
        """Run the application."""
        # Setup hot-reload callbacks
        self.library_service.on_hot_reload = self._handle_hot_reload
        
        # Create UI
        self.ui.create_main_page()
        
        # Run NiceGUI
        ui.run(port=port, show=True, title="Haywire Editor", **ui_kwargs)
```

## Updated Use Cases with Context Menu Functionality

### 1. **User Adds a Node**

#### **New Context Menu Method:**
```
User → Right-Click Canvas → GraphCanvas._handle_context_menu_canvas()
     → ContextMenu.show_canvas_menu() → Display available nodes
     → User Selects Node Type → ContextMenu.emit('create_node')
     → SessionManager.handle_context_action('create_node')
     → HaywireEditor.create_node() → AddNodeAction → History
     → SessionManager.broadcast_editor_change('node_added')
     → All GraphCanvas.add_node_visual()
```

**Key Improvements:**
- **Direct Action**: No mode switching required
- **Contextual**: Menu appears exactly where user wants to create
- **Discoverable**: Shows all available node types in one place

### 2. **User Creates a Connection Between Pins**
```
User → Drag from Pin → GraphCanvas._startConnectionDrag()
     → Mouse Move → GraphCanvas._handleConnectionDragMove() (visual feedback)
     → Drop on Target Pin → GraphCanvas._handleConnectionDragEnd()
     → Validate Connection → GraphCanvas._isValidConnection()
     → Emit 'connection-created' → SessionManager.handle_session_action()
     → HaywireEditor.create_connection() → AddEdgeAction → History
     → SessionManager.broadcast_editor_change('connection_added')
     → All GraphCanvas.add_connection_visual()
```

**Context Enhancement:**
- **Visual Feedback**: Valid/invalid targets highlighted during drag
- **Smart Validation**: Real-time connection validation
- **Gradient Colors**: Connections show data flow with color gradients

### 3. **User Moves a Node**
```
User → Mouse Down → GraphCanvas._startNodeDrag() (prepare drag)
     → Mouse Move → Check drag threshold → _handleNodeDragMove()
     → First Movement → Emit 'node-drag-start' → History.add_fence()
     → Continue Drag → Real-time position updates → Connection path updates
     → Mouse Up → GraphCanvas._handleNodeDragEnd()
     → Position Changed? → Emit 'node-position-changed'
     → HaywireEditor.move_node() → MoveNodeAction → History
     → Emit 'node-drag-end' → History.add_fence()
     → SessionManager.broadcast_editor_change('node_moved')
     → All GraphCanvas.update_node_position()
```

**Key Features:**
- **Drag Threshold**: Distinguishes clicks from drags (5px threshold)
- **Fence Grouping**: All drag movements grouped as single undo action
- **Real-time Updates**: Smooth connection updates during drag
- **Multi-Session Sync**: Drag visible across all connected browsers

### 4. **User Deletes Node with Connections**

#### **New Context Menu Method:**
```
User → Right-Click Node → GraphCanvas._handle_context_menu_node()
     → ContextMenu.show_node_menu() → Display node actions
     → User Clicks "Delete" → ContextMenu.emit('delete_node')
     → SessionManager.handle_context_action('delete_node')
     → HaywireEditor.delete_node() → RemoveNodeAction → History
     → SessionManager.broadcast_editor_change('node_removed')
     → All GraphCanvas.remove_node_visual()
```

**Additional Context Options:**
- **Duplicate Node**: Creates copy with 50px offset
- **Copy Properties**: Copies node configuration to clipboard
- **Inspect Node**: Shows detailed node information dialog
- **Select Connected**: Selects all nodes connected to this one

### 5. **User Selects a Node**
```
User → Click Node (no drag) → GraphCanvas._handleNodeDragEnd()
     → hasActuallyMoved = false → Handle as selection
     → GraphCanvas._handleNodeSelection() → Check multi-select (Ctrl/Cmd)
     → Multi-select? → Toggle selection : Clear + select single
     → Emit 'selection-changed' → SessionManager.handle_session_action()
     → HaywireEditor.select_nodes() → ChangeSelectionAction → History
     → SessionManager.broadcast_editor_change('selection_changed')
     → All GraphCanvas.highlight_selected()
```

**Selection Features:**
- **Multi-Select**: Ctrl/Cmd+Click for multiple selection
- **Visual Feedback**: Blue glow and shadow for selected nodes
- **Widget Fold/Unfold**: Selected nodes show expanded controls
- **Cross-Session**: Selection state shared across all browsers
- **Undo Support**: Selection changes are undoable actions

### 6. **User Selects/Deletes a Connection**

#### **Selection (Click):**
```
User → Click Connection Path → GraphCanvas._handleConnectionSelection()
     → Check multi-select → Update selection state
     → Emit 'selection-changed' → SessionManager.handle_session_action()
     → HaywireEditor.select_connections() → ChangeSelectionAction → History
     → SessionManager.broadcast_editor_change('selection_changed')
     → All GraphCanvas._updateConnectionVisualSelection()
```

#### **Deletion via Context Menu:**
```
User → Right-Click Connection → GraphCanvas._handle_context_menu_connection()
     → ContextMenu.show_connection_menu() → Display connection actions
     → User Clicks "Delete Connection" → ContextMenu.emit('delete_connection')
     → SessionManager.handle_context_action('delete_connection')
     → HaywireEditor.delete_connection() → RemoveEdgeAction → History
     → SessionManager.broadcast_editor_change('connection_removed')
     → All GraphCanvas.remove_connection_visual()
```

**Connection Context Options:**
- **Delete Connection**: Removes the connection
- **Inspect Connection**: Shows connection details (data type, flow direction)
- **Trace Data Flow**: Highlights the data flow path
- **Connection Properties**: Shows advanced connection settings

## Context Menu System Architecture

### Context Menu Component Structure:
```python
class ContextMenu(ui.element, component='context_menu.vue'):
    """Unified context menu system."""
    
    def show_canvas_menu(self, x: float, y: float, canvas_x: float, canvas_y: float):
        """Show context menu for canvas (empty space)."""
        menu_items = [
            {'label': f'Create {node_type}', 'action': 'create_node', 'data': node_type}
            for node_type in self.available_nodes
        ]
        self.display_menu(x, y, menu_items)
    
    def show_node_menu(self, x: float, y: float, node_id: str):
        """Show context menu for node."""
        menu_items = [
            {'label': 'Duplicate Node', 'action': 'duplicate_node', 'data': node_id},
            {'label': 'Copy Properties', 'action': 'copy_node', 'data': node_id},
            {'label': 'Delete Node', 'action': 'delete_node', 'data': node_id, 'destructive': True},
            {'separator': True},
            {'label': 'Inspect Node', 'action': 'inspect_node', 'data': node_id},
            {'label': 'Select Connected', 'action': 'select_connected', 'data': node_id}
        ]
        self.display_menu(x, y, menu_items)
    
    def show_connection_menu(self, x: float, y: float, connection_id: str):
        """Show context menu for connection."""
        menu_items = [
            {'label': 'Delete Connection', 'action': 'delete_connection', 'data': connection_id, 'destructive': True},
            {'separator': True},
            {'label': 'Inspect Connection', 'action': 'inspect_connection', 'data': connection_id},
            {'label': 'Trace Data Flow', 'action': 'trace_flow', 'data': connection_id}
        ]
        self.display_menu(x, y, menu_items)
```

## Key Architecture Benefits

### 1. **Scalability**
- **Multi-Session**: Supports unlimited concurrent users
- **Session Independence**: Each user has independent view state
- **Efficient Broadcasting**: Only changed data is synchronized

### 2. **User Experience**
- **Intuitive Interactions**: Right-click context menus feel natural
- **Real-time Collaboration**: Changes visible instantly across all sessions
- **Smooth Performance**: JavaScript handles real-time interactions
- **Undo/Redo Support**: Every action is undoable, including selections

### 3. **Maintainability**
- **Single Responsibility**: Each class has one clear purpose
- **Clean Separation**: UI logic separate from business logic
- **Event-Driven**: Loose coupling through event system
- **Testable**: Each component can be tested independently

### 4. **Extensibility**
- **Plugin System**: Easy to add new node types
- **Context Actions**: Simple to add new context menu items
- **Custom Interactions**: Easy to add new user interactions
- **Multiple UIs**: Core editor can work with different frontends

### 5. **Robustness**
- **Error Handling**: Graceful handling of disconnected clients
- **State Recovery**: Automatic sync when clients reconnect
- **Validation**: Business rules enforced at editor level
- **History Management**: Comprehensive undo/redo with action grouping

This architecture provides a solid foundation for a professional node-based editor with excellent user experience, real-time collaboration, and maintainable code structure.