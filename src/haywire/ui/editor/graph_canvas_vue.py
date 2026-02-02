"""
GraphCanvasVue - Vue-based graph canvas component for NiceGUI

This component provides a clean Python wrapper around a Vue component that handles
all client-side graph canvas interactions with the enhanced event system.

"""

from typing import Optional, Callable
from pathlib import Path

from nicegui import ui
from nicegui.dependencies import register_library

from .event_definitions import BaseGraphEvent, GRAPH_EVENT_REGISTRY

# Register the auto-generated library
script_dir = Path(__file__).parent
library_path = script_dir / "generated" / "graph_events.js"

if library_path.exists():
    try:
        my_library = register_library(library_path, max_time=library_path.stat().st_mtime)
    except Exception as e:
        print(f"❌ Failed to register library: {e}")
else:
    print(f"❌ Library not found at: {library_path}")


class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with ONLY unified event handling."""
    
    def __init__(self, 
                 on_canvas_event: Optional[Callable[[BaseGraphEvent], None]] = None,
                 zoom_container=None,
                 canvas_width: int = 8000, 
                 canvas_height: int = 8000):
        super().__init__()
        self.libraries.append(my_library)
        
        self._on_canvas_event = on_canvas_event
        self.zoom_container = zoom_container
        
        # Props for Vue component
        self._props['containerId'] = f"graph-canvas-{id(self)}"
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        self._props['data-graph_canvas'] = True
        
        # Register single unified event handler
        self.on('canvasEvent', self._handle_canvas_event)
    
    def _handle_canvas_event(self, event_data):
        """Unified canvas event handler - routes to GraphCanvasManager"""
        if self._on_canvas_event and hasattr(event_data, 'args'):
            event = event_data.args
            event_type = event.get('event_type')
            
            # Log for debugging
            print(f"🔄 Vue→Python Event: {event_type} | Data: {event.get('data', {})}")
            
            # Create event instance from registry
            if event_type in GRAPH_EVENT_REGISTRY:
                event_class = GRAPH_EVENT_REGISTRY[event_type]
                try:
                    event_instance = event_class.from_dict(event)
                    self._on_canvas_event(event_instance)
                except Exception as e:
                    print(f"Error creating event instance for {event_type}: {e}")
            else:
                print(f"Unknown event type: {event_type}")
    
    def emit_sync_event(self, event: BaseGraphEvent):
        """
        Send sync event to Vue component - THE ONLY COMMUNICATION METHOD
        """
        # Don't send events if component is being cleaned up
        if getattr(self, '_is_cleanup', False):
            return
            
        event_dict = event.to_dict()
        event_type = event_dict.get('event_type')
        data = event_dict.get('data', {})
        
        print(f"🔄 Python→Vue Event: {event_type} | Data: {data}")
        
        # Send to Vue component via handleSyncEvent - the ONLY run_method call
        self.run_method('handleSyncEvent', event_dict)
        
    def cleanup(self):
        """Cleanup resources and references."""
        self._is_cleanup = True
        self._on_canvas_event = None
        self.zoom_container = None
