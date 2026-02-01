# Interactive Interpreter with Frame Loop - Investigation & Proposal

## Overview

This document investigates the feasibility of implementing an interactive interpreter within the `UndoRedoTestAppWithCanvasManager` that runs in a loop with:
- Start/Stop buttons for user control
- BEGIN_PLAY trigger on start
- Periodic TICK triggers at a configurable framerate
- SHUTDOWN trigger on stop

## Current Architecture Analysis

### 1. Interpreter System

**Location**: `src/haywire/core/execution/interpreter.py`

**Current Behavior**:
- Interpreter is event-driven, not loop-based
- Events are dispatched explicitly via `dispatch_system_event()` or `dispatch_external_event()`
- Execution model: "dispatch → execute → complete"
- No built-in loop mechanism

**Key Methods**:
```python
interpreter.load_graph(graph)                              # Assembly
interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)  # One-shot trigger
interpreter.dispatch_system_event(SystemEventType.TICK)        # One-shot trigger
interpreter.wait_all(timeout)                              # Wait for completion
interpreter.shutdown()                                     # Cleanup
```

### 2. Flow Scheduler & Threading

**Location**: `src/haywire/core/execution/scheduler.py`

**Architecture**:
- **One scheduler per Flow** (not per graph)
- **Each scheduler has its own execution thread** (`_execution_loop`)
- **Thread lifecycle**:
  - Created when first trigger is enqueued
  - Runs until trigger queue is empty
  - **Thread exits automatically when no more work**
  
**Key Implementation Details**:
```python
def _execution_loop(self):
    """Main execution loop (runs in separate thread)."""
    # Call startup() on all nodes ONCE
    self._call_startup()
    
    while not self.should_stop:
        # Wait for next trigger (timeout 0.5s)
        trigger = self.trigger_queue.get(timeout=0.5)
        
        # Execute flow
        self._execute_flow(trigger)
        
        # Mark done
        self.trigger_queue.task_done()
        
        # If queue empty and not stopped, break
        if self.trigger_queue.empty() and not self.should_stop:
            break  # ← Thread exits here!
    
    # Call shutdown() on all nodes ONCE
    self._call_shutdown()
```

**Critical Finding**: The scheduler's execution thread is **NOT persistent**. It exits when the queue is empty, which means:
- ❌ Can't keep thread alive for periodic ticks
- ❌ Thread restarts on each new trigger (startup/shutdown called each time)
- ✅ Good for one-shot event handling
- ❌ Bad for continuous frame loops

### 3. Event System

**Location**: `src/haywire/core/execution/event_source.py`

**Available System Events**:
```python
class SystemEventType(Enum):
    BEGIN_PLAY = "begin_play"
    TICK = "tick"
    SHUTDOWN = "shutdown"
    PAUSE = "pause"
    RESUME = "resume"
```

**Event Nodes**:
- `BeginPlayNode`: Listens for BEGIN_PLAY, triggers once
- `TickNode`: Listens for TICK, triggers on each tick
  - Has `interval` config (default 0.016s = 60fps)
  - Receives `delta_time` from trigger payload
- **No ShutdownNode exists yet** (would need to be created)

## Feasibility Analysis

### ✅ **YES, it's possible** with modifications

The system has all the foundational pieces, but requires architectural changes to support a persistent loop.

## Required Changes

### 1. **Application-Level Loop Manager** (NEW)

Create a new component that manages the frame loop at the application level:

**Location**: `src/haywire/ui/editor/interpreter_loop_manager.py`

```python
class InterpreterLoopManager:
    """
    Manages continuous execution loop for interactive interpreter.
    
    Responsibilities:
    - Maintain persistent loop thread
    - Dispatch TICK events at configured framerate
    - Handle START/STOP lifecycle
    - Track performance metrics (FPS, frame time)
    """
    
    def __init__(self, interpreter: Interpreter, target_fps: float = 60.0):
        self.interpreter = interpreter
        self.target_fps = target_fps
        self.target_frame_time = 1.0 / target_fps
        
        # Loop control
        self.is_running = False
        self.loop_thread = None
        self.should_stop = False
        
        # Performance tracking
        self.last_tick_time = 0.0
        self.actual_fps = 0.0
        self.frame_count = 0
    
    def start(self):
        """Start the execution loop."""
        if self.is_running:
            return
        
        self.should_stop = False
        self.is_running = True
        
        # Dispatch BEGIN_PLAY
        self.interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        
        # Start loop thread
        self.loop_thread = Thread(target=self._loop_worker, daemon=True)
        self.loop_thread.start()
    
    def stop(self):
        """Stop the execution loop."""
        if not self.is_running:
            return
        
        self.should_stop = True
        
        # Dispatch SHUTDOWN
        self.interpreter.dispatch_system_event(SystemEventType.SHUTDOWN)
        
        # Wait for loop thread to exit
        if self.loop_thread:
            self.loop_thread.join(timeout=2.0)
        
        self.is_running = False
    
    def _loop_worker(self):
        """Worker function that runs in separate thread."""
        import time
        
        self.last_tick_time = time.time()
        
        while not self.should_stop:
            frame_start = time.time()
            
            # Calculate delta time
            delta_time = frame_start - self.last_tick_time
            self.last_tick_time = frame_start
            
            # Dispatch TICK event with delta_time payload
            self.interpreter.dispatch_system_event(
                SystemEventType.TICK,
                payload={'delta_time': delta_time}
            )
            
            # Update performance metrics
            self.frame_count += 1
            
            # Sleep to maintain target framerate
            frame_elapsed = time.time() - frame_start
            sleep_time = max(0, self.target_frame_time - frame_elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Calculate actual FPS
            actual_frame_time = time.time() - frame_start
            if actual_frame_time > 0:
                self.actual_fps = 1.0 / actual_frame_time
    
    def set_target_fps(self, fps: float):
        """Update target framerate."""
        self.target_fps = fps
        self.target_frame_time = 1.0 / fps
    
    def get_stats(self) -> dict:
        """Get performance statistics."""
        return {
            'is_running': self.is_running,
            'target_fps': self.target_fps,
            'actual_fps': self.actual_fps,
            'frame_count': self.frame_count
        }
```

### 2. **FlowScheduler Modifications** (OPTIONAL BUT RECOMMENDED)

**Problem**: Current scheduler exits thread when queue is empty.

**Option A: Keep Current Behavior** (Recommended for now)
- No changes needed to scheduler
- Loop manager dispatches events fast enough that queue never empties
- Simpler, less risky

**Option B: Add Persistent Mode** (Future enhancement)
```python
class FlowScheduler:
    def __init__(self, ..., persistent_mode: bool = False):
        self.persistent_mode = persistent_mode
    
    def _execution_loop(self):
        self._call_startup()
        
        while not self.should_stop:
            try:
                trigger = self.trigger_queue.get(timeout=0.5)
                self._execute_flow(trigger)
                self.trigger_queue.task_done()
            except Empty:
                if self.persistent_mode:
                    continue  # Keep thread alive
                elif self.trigger_queue.empty():
                    break  # Exit as before
        
        self._call_shutdown()
```

**Recommendation**: Start with **Option A**, add Option B later if needed.

### 3. **Create ShutdownNode** (NEW)

Currently there's no node that listens for SHUTDOWN events.

**Location**: `libraries/haybale-core/haybale_core/nodes/shutdown.py`

```python
from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType

from ..types.specs import EXEC, FLOAT


@node(
    registry_id='shutdown',
    label='Shutdown',
    description='Triggered when execution is shutting down',
    menu='events/system',
    search_tags=['stop', 'end', 'cleanup', 'event'],
    node_type=NodeType.EVENT,
)
class ShutdownNode(BaseNode):
    """
    Triggered when execution is shutting down.
    
    Use this to perform cleanup operations before the interpreter stops.
    
    Outputs:
        exec: Control flow
        timestamp: Time when shutdown was triggered
    """
        
    def init(self):
        # Control output
        self.add(EXEC.as_outlet('exec', label='Execute'))
        
        # Data output
        self.add(FLOAT.as_outlet('timestamp', label='Shutdown Time'))
    
    def on_init(self):
        self.event_subscription = SystemEvent(SystemEventType.SHUTDOWN)
    
    def worker(self, context: ExecutionContext) -> str | None:
        import time
        
        self.out('timestamp', time.time())
        return 'exec'
```

### 4. **UI Integration in app_graph_canvas.py**

**Add to `UndoRedoTestAppWithCanvasManager`**:

```python
class UndoRedoTestAppWithCanvasManager:
    def __init__(self):
        # ... existing code ...
        
        # Interpreter and loop manager (shared across sessions)
        self.interpreter = None
        self.loop_manager = None
    
    def setup_shared_services(self):
        # ... existing code ...
        
        # Create interpreter (not started yet)
        self.interpreter = Interpreter()
        
        # Create loop manager
        self.loop_manager = InterpreterLoopManager(
            interpreter=self.interpreter,
            target_fps=60.0
        )
    
    def create_header(self):
        """Create the application header with main controls."""
        with ui.header().classes('bg-blue-600 text-white px-4 py-2'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Enhanced Haywire Test App').classes('text-xl font-bold')
                
                with ui.row().classes('gap-2'):
                    # ... existing buttons ...
                    
                    ui.separator().props('vertical')
                    
                    # Interpreter controls
                    ui.button(
                        'Start Interpreter',
                        on_click=self.start_interpreter,
                        icon='play_arrow'
                    ).bind_enabled_from(
                        self.loop_manager,
                        'is_running',
                        backward=lambda x: not x
                    )
                    
                    ui.button(
                        'Stop Interpreter',
                        on_click=self.stop_interpreter,
                        icon='stop'
                    ).bind_enabled_from(
                        self.loop_manager,
                        'is_running'
                    )
                    
                    ui.number(
                        label='FPS',
                        value=60,
                        min=1,
                        max=120,
                        on_change=lambda e: self.set_target_fps(e.value)
                    ).classes('w-24')
    
    def start_interpreter(self):
        """Start the interpreter loop."""
        # Load current graph
        self.interpreter.load_graph(self.graph)
        
        # Start loop
        self.loop_manager.start()
        
        ui.notify("Interpreter started", type='positive')
    
    def stop_interpreter(self):
        """Stop the interpreter loop."""
        self.loop_manager.stop()
        
        # Wait for all flows to complete
        self.interpreter.wait_all(timeout=2.0)
        
        ui.notify("Interpreter stopped", type='info')
    
    def set_target_fps(self, fps: float):
        """Update target framerate."""
        self.loop_manager.set_target_fps(fps)
    
    def create_left_panel(self):
        """Create the left control panel with all information sections."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            # ... existing expansions ...
            
            # Interpreter Status (NEW)
            with ui.expansion(
                'Interpreter Status',
                icon='play_circle'
            ).classes('w-full'):
                with ui.column() as interpreter_container:
                    self.current_session['ui_containers'][
                        'interpreter_container'
                    ] = interpreter_container
                    self.update_interpreter_display()
    
    def update_interpreter_display(self):
        """Update interpreter status display."""
        if not hasattr(self, 'current_session'):
            return
        
        containers = self.current_session.get('ui_containers', {})
        if 'interpreter_container' not in containers:
            return
        
        container = containers['interpreter_container']
        container.clear()
        
        with container:
            if self.loop_manager:
                stats = self.loop_manager.get_stats()
                
                if stats['is_running']:
                    ui.label('✓ Running').classes('text-green-600 font-bold')
                else:
                    ui.label('○ Stopped').classes('text-gray-500')
                
                ui.label(
                    f'Target FPS: {stats["target_fps"]:.1f}'
                ).classes('text-sm')
                ui.label(
                    f'Actual FPS: {stats["actual_fps"]:.1f}'
                ).classes('text-sm')
                ui.label(
                    f'Frames: {stats["frame_count"]}'
                ).classes('text-sm')
            else:
                ui.label('Not initialized').classes('text-gray-500')
```

## Implementation Phases

### Phase 1: Core Loop Manager ✅ Ready to implement
1. Create `InterpreterLoopManager` class
2. Add Start/Stop methods
3. Implement frame loop with timing

### Phase 2: UI Integration ✅ Ready to implement
1. Add interpreter instance to app
2. Add Start/Stop buttons
3. Add FPS control
4. Add status display

### Phase 3: Shutdown Support ✅ Ready to implement
1. Create `ShutdownNode`
2. Test SHUTDOWN event dispatch
3. Verify cleanup behavior

### Phase 4: Testing & Refinement
1. Test with various framerates
2. Monitor performance
3. Add pause/resume functionality
4. Add step-by-step execution mode

## Potential Issues & Solutions

### Issue 1: Thread Safety with NiceGUI
**Problem**: NiceGUI requires UI updates to happen on the main/UI thread. The `InterpreterLoopManager` runs in a background thread, and attempting to update UI elements directly from that thread would violate NiceGUI's threading model, potentially causing:
- Race conditions on UI state
- UI elements becoming unresponsive
- Exceptions when accessing client contexts
- Unpredictable rendering behavior

**Why this matters**: The loop manager needs to update the FPS display, frame count, and running status, but these are UI elements that can't be safely updated from the background thread.

**Solution**: Use NiceGUI's `ui.timer()` to periodically poll the loop manager's state from the main thread:
```python
# In app startup - runs on main/UI thread
ui.timer(
    0.1,  # Update every 100ms
    lambda: self.update_interpreter_display(),
    active=True
)
```

This pattern is safe because:
- Timer callback runs on the main thread
- Loop manager's `get_stats()` is thread-safe (just reading attributes)
- UI updates happen from the proper thread context

### Issue 2: Graph Modifications During Execution
**Problem**: User edits graph while interpreter is running. If changes require reassembly (e.g., adding/removing nodes, changing connections), the running flows become invalid.

**Solution**: Monitor the graph's `ValidationManager` for changes that require reassembly. When detected, automatically stop the interpreter and notify the user to restart.

**Implementation**:

```python
class UndoRedoTestAppWithCanvasManager:
    def setup_shared_services(self):
        # ... existing code ...
        
        # Subscribe to graph validation changes
        self.graph.subscribe_to_validation(self._on_graph_validation_change)
    
    def _on_graph_validation_change(self, result: ValidationResult):
        """Handle graph validation changes."""
        # Check if interpreter is running
        if not self.loop_manager or not self.loop_manager.is_running:
            return
        
        # Check if changes require reassembly
        if result.change_reason and result.change_reason.requires_graph_reassembly:
            # Stop the interpreter
            self.stop_interpreter()
            
            # Notify user
            ui.notify(
                'Graph changed - interpreter stopped. '
                'Restart to execute modified graph.',
                type='warning',
                position='top',
                timeout=5000
            )
    
    def start_interpreter(self):
        """Start the interpreter loop."""
        # Validate graph first
        self.graph._validation.force_immediate_validation()
        
        if not self.graph._validation.is_valid:
            ui.notify(
                'Cannot start - graph has errors',
                type='negative'
            )
            return
        
        # Load current graph (triggers assembly)
        self.interpreter.load_graph(self.graph)
        
        # Start loop
        self.loop_manager.start()
        
        ui.notify("Interpreter started", type='positive')
    
    def stop_interpreter(self):
        """Stop the interpreter loop."""
        self.loop_manager.stop()
        
        # Wait for all flows to complete
        self.interpreter.wait_all(timeout=2.0)
        
        ui.notify("Interpreter stopped", type='info')
```

**Benefits of this approach**:
- ✅ User can freely edit the graph (no locking)
- ✅ Changes that don't require reassembly (e.g., changing widget values) work fine
- ✅ Destructive changes automatically stop execution
- ✅ State is transparent - user knows interpreter stopped and why
- ✅ Restart regenerates flows with updated graph structure
- ✅ Uses existing ValidationManager infrastructure

**Change reasons that trigger stop** (from `ChangeReason`):
- Adding/removing nodes
- Adding/removing edges
- Changing node types
- Any structural change requiring flow reassembly

### Issue 3: Performance with Many Ticks
**Problem**: Dispatching many TICK events may overwhelm the system.

**Solution**: Monitor queue depth, adjust framerate dynamically:
```python
def _loop_worker(self):
    while not self.should_stop:
        # Check if we're overwhelming the system
        if self._get_total_queue_depth() > 10:
            # Slow down
            time.sleep(0.1)
            continue
        
        # Normal tick dispatch
        self.interpreter.dispatch_system_event(...)
```

## Summary

### ✅ **Feasibility: YES**
The current architecture supports this with minimal changes.

### **Required Changes**:
1. **NEW**: `InterpreterLoopManager` (application-level loop)
2. **NEW**: `ShutdownNode` (event node)
3. **MODIFY**: `app_graph_canvas.py` (add UI controls)
4. **OPTIONAL**: FlowScheduler persistent mode (future enhancement)

### **No changes needed**:
- ✅ Interpreter (works as-is)
- ✅ FlowScheduler (current behavior sufficient)
- ✅ Event system (all events already defined)
- ✅ BeginPlayNode, TickNode (already exist)

### **Key Insight**:
The loop should be **external to the interpreter**, not internal to FlowScheduler. This keeps the architecture clean and separates concerns:
- **Interpreter**: Event-driven execution
- **LoopManager**: Continuous event generation
- **FlowScheduler**: Per-flow execution threading

This approach is **non-invasive** and maintains backward compatibility with existing code.
