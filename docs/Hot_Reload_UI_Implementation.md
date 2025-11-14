# Hot Reload UI Implementation

## Overview

This document describes the implementation of hot reload support for node visuals in the Haywire graph canvas. The solution enhances `UINode` to directly subscribe to both `NodeWrapper` and `NodeRenderFactory` callbacks, enabling automatic re-rendering when:
- Node classes are hot-reloaded (NodeWrapper)
- Renderer classes are hot-reloaded (NodeRenderFactory)

## Architecture Decision

### Considered Approach: UINodeWrapper
Initially considered creating a `UINodeWrapper` class to mirror the `NodeWrapper` pattern, which would:
- Hold a reference to the NiceGUI container
- Listen to NodeWrapper callbacks
- Manage visual lifecycle

### Chosen Approach: Enhanced UINode ✅
Instead, we enhanced the existing `UINode` class because:

1. **UINode already manages visual lifecycle** - it's the perfect place for hot reload
2. **Avoids unnecessary wrapper layer** - simpler architecture
3. **Direct correspondence**: `NodeWrapper` ↔ `UINode` ↔ Visual Container
4. **Leverages existing `rerender()` method** - designed for this use case
5. **Better encapsulation** - hot reload becomes an internal UINode concern

## Implementation Details

### 1. Enhanced UINode (`src/haywire/ui/ui_node.py`)

#### Key Changes

**Added NodeWrapper and Renderer Tracking:**
```python
def __init__(self, haywire_node: BaseNode, factory: NodeRenderFactory, component, 
             node_wrapper: Optional['NodeWrapper'] = None):
    # ... existing code ...
    self.node_wrapper = node_wrapper
    self._current_renderer_name: Optional[str] = None  # Track renderer for hot reload
    
    # Subscribe to wrapper changes for node hot reload
    if self.node_wrapper:
        self.node_wrapper.add_change_callback(self._on_wrapper_changed)
    
    # Subscribe to factory renderer changes for renderer hot reload
    self.factory.add_customer_callback(self._on_renderer_changed)
```

**Node Hot Reload Callback Handler:**
```python
def _on_wrapper_changed(self, wrapper: 'NodeWrapper', change_type: str):
    """
    Handle NodeWrapper change notifications for hot reload support.
    
    Handles:
    - migration_completed: Node class hot-reloaded → update reference & re-render
    - initialized_with_error: Initialization failed → show error state
    - migration_failed_error_node_created: Hot reload failed → show error node
    - initialized/deserialized: Node ready → ensure UI in sync
    """
```

**Renderer Hot Reload Callback Handler:**
```python
def _on_renderer_changed(self, registry_key: str, affected_class_names: list, library_identity):
    """Handle renderer hot reload notifications from NodeRenderFactory."""
    # Check if our renderer is affected
    if self._current_renderer_name:
        renderer_class = self.factory.renderers_registry.get_renderer_class(self._current_renderer_name)
        if renderer_class.__name__ in affected_class_names:
            self.rerender()  # Re-render with updated renderer
            ui.notify(f"Renderer for node {self.haywire_node.node_id} hot-reloaded", type='positive')
```

**Thread-Safe UI Updates:**
The callback may be invoked from background threads (file watcher), so we use NiceGUI's client context:

```python
if self.container_slot and hasattr(self.container_slot, 'client'):
    with self.container_slot.client:
        update_ui()
```

**Enhanced Cleanup:**
```python
def destroy(self):
    # Unsubscribe from wrapper changes
    if self.node_wrapper:
        self.node_wrapper.remove_change_callback(self._on_wrapper_changed)
        self.node_wrapper = None
    
    # Unsubscribe from factory renderer changes
    self.factory.remove_customer_callback(self._on_renderer_changed)
    
    # ... existing cleanup ...
```

### 2. Enhanced NodeRenderFactory (`src/haywire/ui/node_render_factory.py`)

**Added Customer Callback System:**
```python
def __init__(self, renderers_registry: RendererRegistry, widget_registry: WidgetRegistry):
    # ... existing code ...
    
    # Customer callbacks for hot reload notifications
    self._customer_callbacks: List[Callable[[str, List[str], LibraryIdentity], None]] = []

def add_customer_callback(self, callback):
    """Register a customer callback for renderer hot reload notifications."""
    if callback not in self._customer_callbacks:
        self._customer_callbacks.append(callback)

def remove_customer_callback(self, callback):
    """Unregister a customer callback."""
    if callback in self._customer_callbacks:
        self._customer_callbacks.remove(callback)

def _notify_customers(self, registry_key, affected_class_names, library_identity):
    """Notify all registered customers about renderer changes."""
    for callback in self._customer_callbacks[:]:
        callback(registry_key, affected_class_names, library_identity)
```

**Enhanced Renderer Reload Handler:**
```python
def _on_renderer_reloaded(self, registry_key, affected_class_names, library_identity):
    # Clear cache for affected renderer classes
    for class_name in affected_class_names:
        if class_name in self._renderer_cache:
            del self._renderer_cache[class_name]
    
    # Notify customers (UINodes) about the renderer reload
    self._notify_customers(registry_key, affected_class_names, library_identity)
```

### 3. Simplified GraphCanvasManager (`src/haywire/ui/editor_v1/graph_canvas_manager.py`)

#### Key Changes:

**Pass Wrapper to UINode:**
```python
def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
    # Get the wrapper for this node to enable hot reload support
    wrapper = self.graph.get_node_wrapper(node_id)
    if not wrapper:
        print(f"⚠️ Warning: No wrapper found for node {node_id}, hot reload won't work")
    
    # Create UINode with wrapper reference for hot reload support
    ui_node = UINode(node, self.node_render_factory, container, wrapper)
```

**Removed Redundant Code:**
- Removed `_pending_notifications` queue
- Removed `_on_wrapper_changed()` method
- Removed `_process_pending_notifications()` method
- Removed notification processing timer
- Simplified `_setup_wrapper_callbacks()` to a no-op

UINode now handles all hot reload visual updates internally.

## Data Flow

### Hot Reload Sequence

```
1. File System Change
   ↓
2. File Watcher (background thread)
   ↓
3. Library System detects change
   ↓
4. NodeFactory.handle_hot_reload()
   ↓
5. NodeWrapper detects class change
   ↓
6. NodeWrapper._migrate_to_new_class()
   ↓
7. NodeWrapper._notify_change("migration_completed")
   ↓
8. UINode._on_wrapper_changed() [may be background thread]
   ↓
9. UINode uses client context for thread safety
   ↓
10. UINode.rerender() [updates visual with new node class]
   ↓
11. ui.notify() shows user feedback
```

### Key Components

- **NodeWrapper**: Core lifecycle manager (detects hot reload)
- **UINode**: Visual lifecycle manager (renders updated UI)
- **GraphCanvasManager**: Canvas coordinator (creates UINode with wrapper)
- **NiceGUI Client Context**: Thread-safe UI updates

## Benefits

1. **Elegant Architecture**: UINode naturally extends its existing responsibility
2. **Thread-Safe**: Uses NiceGUI's client context for background thread callbacks
3. **Automatic Updates**: Nodes re-render immediately on hot reload
4. **Clean Separation**: Hot reload is internal to UINode, not GraphCanvasManager's concern
5. **Less Code**: Removed ~80 lines of notification queue management
6. **Better Encapsulation**: Each UINode manages its own hot reload lifecycle

## Thread Safety

### The Challenge
`NodeWrapper` callbacks are invoked from background threads (file watcher), but NiceGUI UI updates must run in the UI thread.

### The Solution
```python
# UINode._on_wrapper_changed()
if self.container_slot and hasattr(self.container_slot, 'client'):
    with self.container_slot.client:
        update_ui()  # Safe: runs in client's UI thread
```

NiceGUI's client context manager ensures UI updates are queued and executed in the correct thread.

## Usage Example

```python
# GraphCanvasManager.add_node_visual()
wrapper = self.graph.get_node_wrapper(node_id)
ui_node = UINode(node, factory, container, wrapper)  # ← wrapper enables hot reload
ui_node.render()

# Later, when file changes...
# UINode automatically:
# 1. Detects wrapper callback
# 2. Updates self.haywire_node reference
# 3. Calls self.rerender()
# 4. Shows notification to user
```

## Testing Hot Reload

1. Start the playground app:
   ```bash
   cd playground
   python app_graph_canvas.py
   ```

2. Add a node to the canvas from the test library

3. Edit the node's Python file (e.g., `libraries/haybale-example/haybale_example/nodes/processor.py`)

4. Save the file

5. Observe:
   - Console shows hot reload detection
   - UINode re-renders automatically
   - Notification appears: "Node {id} hot-reloaded"
   - Visual updates with new node definition

## Future Enhancements

### Potential Improvements:
1. **Diff-based updates**: Only re-render changed pins/widgets
2. **Smoother transitions**: Fade/slide animations during re-render
3. **Error recovery**: More graceful handling of migration failures
4. **State preservation**: Maintain widget values across hot reload
5. **Batch updates**: Group multiple rapid hot reloads

### Alternative Approaches:
- **Queue in UINode**: Each UINode could have its own notification queue
- **Global UI thread timer**: Central timer processes all UINode updates
- **AsyncIO integration**: Use async/await for hot reload notifications

## Backward Compatibility

The implementation is **fully backward compatible**:
- `node_wrapper` parameter is optional in `UINode.__init__()`
- Existing code without wrapper still works (no hot reload support)
- No changes required to existing node implementations
- GraphCanvasManager automatically passes wrapper when available

## Related Documentation

- [Hot Reload Callback System](Hot_Reload_Callback/README.md)
- [Library System Developer Guide](library/Library_System_Developer_Guide.md)
- [Undo/Redo System](Undo:Redo_System.md)

## Summary

This implementation provides elegant hot reload support for both node classes and renderer classes by enhancing `UINode` to subscribe directly to both `NodeWrapper` and `NodeRenderFactory` callbacks. The approach is architecturally sound, thread-safe, and requires minimal code changes while providing automatic visual updates when:

1. **Node classes are hot-reloaded**: UINode detects wrapper changes and updates the node instance
2. **Renderer classes are hot-reloaded**: UINode detects factory changes and re-renders if using the affected renderer

Key architectural decisions:
- UINode is the natural home for visual hot reload logic
- Reuses existing `rerender()` method for both types of hot reload
- Maintains clean separation: NodeWrapper (core) ↔ UINode (visual) ↔ NodeRenderFactory (rendering)
- Thread-safe using NiceGUI's client context
- Customer callback pattern consistent across the system (registries → factory → UINode)
