from nicegui import ui, events
from typing import Optional, Callable
import uuid
import time


class ZoomPanContainer(ui.element, component='zoom_pan_container.vue'):
    """
    A Vue-based zoom and pan container for NiceGUI.
    
    Features:
    - Mouse wheel zoom in/out
    - Click and drag to pan
    - Keyboard shortcuts (+ and - for zoom)
    - Zoom to fit functionality
    - Configurable zoom limits
    - Smooth animations
    - Event callbacks for zoom/pan changes
    """
    
    def __init__(
        self,
        min_zoom: float = 0.1,
        max_zoom: float = 5.0,
        initial_zoom: float = 1.0,
        zoom_sensitivity: float = 0.1,
        pan_sensitivity: float = 1.0,
        smooth_zoom: bool = True,
        enable_keyboard: bool = True,
        on_zoom_change: Optional[Callable[[float], None]] = None,
        on_pan_change: Optional[Callable[[float, float], None]] = None,
        **kwargs
    ) -> None:
        """
        Initialize the ZoomPanContainer.
        
        Args:
            min_zoom: Minimum zoom level (default: 0.1)
            max_zoom: Maximum zoom level (default: 5.0)
            initial_zoom: Initial zoom level (default: 1.0)
            zoom_sensitivity: How sensitive zoom operations are (default: 0.1)
            pan_sensitivity: How sensitive pan operations are (default: 1.0)
            smooth_zoom: Whether to use smooth zoom animations (default: True)
            enable_keyboard: Enable keyboard shortcuts (default: True)
            on_zoom_change: Callback for zoom changes
            on_pan_change: Callback for pan changes
        """
        # Generate unique ID for this container
        self.container_id = f'zoom-pan-{uuid.uuid4().hex[:8]}'
        
        # Store configuration for Python-side access
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_sensitivity = zoom_sensitivity
        self.pan_sensitivity = pan_sensitivity
        self.smooth_zoom = smooth_zoom
        self.enable_keyboard = enable_keyboard
        
        # Store callbacks
        self.on_zoom_change = on_zoom_change
        self.on_pan_change = on_pan_change
        
        # Current state tracking
        self.current_zoom = initial_zoom
        self.pan_x = 0.0
        self.pan_y = 0.0
        
        # Performance tracking
        self.update_times = []
        self.update_count = 0
        self.last_update_time = time.time()
        
        super().__init__(**kwargs)
        
        # Setup the container structure
        self._setup_container()
        
        # Set Vue component props
        self._props['container-id'] = self.container_id
        self._props['min-zoom'] = min_zoom
        self._props['max-zoom'] = max_zoom
        self._props['initial-zoom'] = initial_zoom
        self._props['zoom-sensitivity'] = zoom_sensitivity
        self._props['pan-sensitivity'] = pan_sensitivity
        self._props['smooth-zoom'] = smooth_zoom
        self._props['enable-keyboard'] = enable_keyboard
        
        # Set up Python event handlers
        self.on('transform-changed', self._handle_transform_changed)
    
    def _setup_container(self) -> None:
        """Setup the basic container structure."""
        self.classes('zoom-pan-container')
        self.style('position: relative; overflow: hidden; width: 100%; height: 100%;')
        # Set the unique ID
        self.props(f'id="{self.container_id}"')
        
        # Create the content container that will be transformed
        with self:
            self.content_container = ui.element('div').classes('zoom-pan-content')
            self.content_container.style(
                'position: absolute; '
                'transform-origin: 0 0; '
                'transition: transform 0.2s ease-out; '
                'width: max-content; '
                'height: max-content; '
                'min-width: 100%; '
                'min-height: 100%;'
            )
    
    def  _handle_transform_changed(self, e: events.GenericEventArguments) -> None:
        """Handle zoom change events from Vue component."""
        try:
            self.pan_x = e.args['panX']
            self.pan_y = e.args['panY']
            self.current_zoom = e.args['zoom']
            self._update_performance_metrics()
            if self.on_zoom_change:
                self.on_zoom_change(self.current_zoom)
            if self.on_pan_change:
                self.on_pan_change(self.pan_x, self.pan_y)
        except Exception:
            pass
       
    def _update_performance_metrics(self) -> None:
        """Update performance tracking metrics."""
        try:
            current_time = time.time()
            self.update_count += 1
            self.last_update_time = current_time
            
            # Track update times for FPS calculation
            self.update_times.append(current_time)
            # Keep only updates from the last second
            cutoff_time = current_time - 1.0
            self.update_times = [t for t in self.update_times if t > cutoff_time]
        except Exception:
            pass
    
    def get_performance_metrics(self) -> dict:
        """Get current performance metrics."""
        try:
            current_time = time.time()
            # Clean old entries
            cutoff_time = current_time - 1.0
            self.update_times = [t for t in self.update_times if t > cutoff_time]
            
            fps = len(self.update_times)
            time_since_last_update = current_time - self.last_update_time
            
            return {
                'fps': fps,
                'total_updates': self.update_count,
                'time_since_last_update': time_since_last_update,
                'current_zoom': self.current_zoom,
                'pan_x': self.pan_x,
                'pan_y': self.pan_y
            }
        except Exception:
            return {
                'fps': 0,
                'total_updates': 0,
                'time_since_last_update': 0,
                'current_zoom': self.current_zoom,
                'pan_x': self.pan_x,
                'pan_y': self.pan_y
            }
    
    def get_zoom_class_name(self) -> str:
        """Get the zoom class name for current zoom level."""
        if self.current_zoom <= 0.5:
            return "Low"
        elif self.current_zoom <= 1.0:
            return "Medium"
        elif self.current_zoom <= 2.0:
            return "High"
        else:
            return "Very High"
    
    def reset_performance_metrics(self) -> None:
        """Reset all performance tracking metrics."""
        try:
            self.update_times.clear()
            self.update_count = 0
            self.last_update_time = time.time()
        except Exception:
            pass
    
    def get_performance_summary(self) -> str:
        """Get a formatted string summary of performance metrics."""
        try:
            metrics = self.get_performance_metrics()
            zoom_class = self.get_zoom_class_name()
            
            summary = (
                f"Performance Summary:\n"
                f"  Zoom: {metrics['current_zoom']:.2f} ({zoom_class})\n"
                f"  Pan: ({metrics['pan_x']:.0f}, {metrics['pan_y']:.0f})\n"
                f"  FPS: {metrics['fps']}\n"
                f"  Total Updates: {metrics['total_updates']}\n"
                f"  Time Since Last Update: {metrics['time_since_last_update']:.2f}s"
            )
            return summary
        except Exception as e:
            return f"Error generating performance summary: {str(e)}"
    
    def zoom_in(self) -> None:
        """Zoom in programmatically."""
        self.run_method('$el._zoomPanControls.zoomIn')
    
    def zoom_out(self) -> None:
        """Zoom out programmatically."""
        self.run_method('$el._zoomPanControls.zoomOut')
    
    def reset_view(self) -> None:
        """Reset zoom and pan to initial values."""
        self.run_method('$el._zoomPanControls.reset')
    
    def fit_to_content(self) -> None:
        """Automatically fit the content to the container."""
        self.run_method('$el._zoomPanControls.fitToContent')
    
    def set_zoom(self, zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None) -> None:
        """Set zoom level programmatically."""
        if center_x is not None and center_y is not None:
            self.run_method('$el._zoomPanControls.setZoom', zoom, center_x, center_y)
        else:
            self.run_method('$el._zoomPanControls.setZoom', zoom)
    
    def set_pan(self, x: float, y: float) -> None:
        """Set pan position programmatically."""
        self.run_method('$el._zoomPanControls.setPan', x, y)
    
    def __enter__(self):
        """Context manager entry - enter the content container if it exists, otherwise self."""
        if hasattr(self, 'content_container') and self.content_container:
            return self.content_container.__enter__()
        else:
            return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit."""
        if hasattr(self, 'content_container') and self.content_container:
            return self.content_container.__exit__(exc_type, exc_value, traceback)
        else:
            return super().__exit__(exc_type, exc_value, traceback)


def create_zoom_pan_controls(container: ZoomPanContainer) -> None:
    """Create standard zoom/pan control buttons."""
    with ui.element('div').classes('zoom-pan-controls'):
        ui.button('+', on_click=container.zoom_in).props('round dense').classes('text-xs')
        ui.button('−', on_click=container.zoom_out).props('round dense').classes('text-xs')
        ui.button('⌂', on_click=container.reset_view).props('round dense').classes('text-xs')
        ui.button('⛶', on_click=container.fit_to_content).props('round dense').classes('text-xs')


def create_zoom_pan_info(container: ZoomPanContainer) -> ui.label:
    """Create info display with comprehensive performance metrics for current zoom and pan values."""
    info_label = ui.label().classes('zoom-pan-info')
    
    # Additional performance tracking for the info display
    info_update_times = []
    info_update_count = [0]
    start_time = time.time()
    
    def update_info(zoom=None, pan_x=None, pan_y=None):
        try:
            current_time = time.time()
            info_update_count[0] += 1
            
            # Get comprehensive metrics from container
            metrics = container.get_performance_metrics()
            
            # Use provided values or fall back to container state
            if zoom is None:
                zoom = metrics['current_zoom']
            if pan_x is None:
                pan_x = metrics['pan_x']
            if pan_y is None:
                pan_y = metrics['pan_y']
            
            zoom_class = container.get_zoom_class_name()
            
            # Calculate info display FPS (separate from container FPS)
            info_update_times.append(current_time)
            cutoff_time = current_time - 1.0
            info_update_times[:] = [t for t in info_update_times if t > cutoff_time]
            info_fps = len(info_update_times)
            
            # Calculate uptime
            uptime = current_time - start_time
            
            # Create comprehensive info text
            info_text = (
                f'Zoom: {zoom:.2f} ({zoom_class}) | '
                f'Pan: ({pan_x:.0f}, {pan_y:.0f}) | '
                f'Container FPS: {metrics["fps"]} | '
                f'Info FPS: {info_fps} | '
                f'Updates: {metrics["total_updates"]} | '
                f'Uptime: {uptime:.1f}s'
            )
            
            # Add performance warnings if needed
            if metrics['fps'] > 60:
                info_text += ' | ⚡ High Performance'
            elif metrics['fps'] < 10 and metrics['fps'] > 0:
                info_text += ' | ⚠️ Low Performance'
            elif metrics['time_since_last_update'] > 1.0:
                info_text += ' | 💤 Idle'
            
            info_label.set_text(info_text)
            info_label.update()
        except Exception as e:
            # Fallback display on error
            error_text = f'Error: {str(e)[:50]}...' if len(str(e)) > 50 else f'Error: {str(e)}'
            info_label.set_text(error_text)
            info_label.update()
    
    # Store original callbacks
    original_zoom_callback = container.on_zoom_change
    original_pan_callback = container.on_pan_change
    
    def zoom_callback(zoom):
        update_info(zoom=zoom)
        if original_zoom_callback:
            original_zoom_callback(zoom)
    
    def pan_callback(x, y):
        update_info(pan_x=x, pan_y=y)
        if original_pan_callback:
            original_pan_callback(x, y)
    
    # Replace the container's callbacks
    container.on_zoom_change = zoom_callback
    container.on_pan_change = pan_callback
    
    # Initial update with a small delay to ensure container is ready
    ui.timer(0.1, lambda: update_info(), once=True)
    
    return info_label


def main():
    @ui.page('/')
    def main_page():
        ui.label('NiceGUI Vue Zoom/Pan Container Demo').classes('text-2xl font-bold mb-4')
        
        def on_zoom_change(zoom):
            pass
        
        def on_pan_change(x, y):
            pass
        
        # Main layout with left panel and zoom container
        with ui.row().classes('w-full gap-4').style('height: 80vh;'):
            # Right side with zoom container (create first so we can reference it)
            with ui.card().classes('flex-grow').style('height: 100%; display: flex; flex-direction: column;'):
                ui.label('Zoomable Content Area').classes('text-lg mb-2 flex-shrink-0')
                
                # Create the zoom/pan container
                zoom_container = ZoomPanContainer(
                    min_zoom=0.1,
                    max_zoom=3.0,
                    initial_zoom=1.0,
                    on_zoom_change=on_zoom_change,
                    on_pan_change=on_pan_change
                ).classes('w-full flex-grow border-2 border-gray-300').style('height: 100%;')
                
                # Add content to the container
                with zoom_container:
                    with ui.grid(columns=50).classes('gap-6 p-8'):
                        for i in range(500):
                            with ui.card().classes('w-32 h-32 bg-blue-100 flex flex-col items-center justify-center zoomable-card'):
                                ui.label(f'Item {i+1}').classes('text-center text-sm mb-2')
                                ui.button('Click', on_click=lambda i=i: ui.notify(f'Clicked item {i+1}')).classes('text-xs')
                
                # Add controls
                create_zoom_pan_controls(zoom_container)
                create_zoom_pan_info(zoom_container)
            
            # Left panel with controls and documentation
            with ui.card().classes('w-80 flex-shrink-0').style('height: 100%; display: flex; flex-direction: column;'):
                ui.label('Controls & Info').classes('text-xl font-bold mb-4')
                
                # Additional demo controls
                with ui.column().classes('gap-2 mb-6'):
                    ui.label('Demo Controls').classes('text-lg font-semibold mb-2')
                    ui.button('Zoom to 2x', on_click=lambda: zoom_container.set_zoom(2.0)).classes('w-full')
                    ui.button('Pan to (100, 50)', on_click=lambda: zoom_container.set_pan(100, 50)).classes('w-full')
                    ui.button('Reset View', on_click=zoom_container.reset_view).classes('w-full')
                    ui.button('Fit Content', on_click=zoom_container.fit_to_content).classes('w-full')
                    
                    # Performance controls
                    ui.separator()
                    ui.label('Performance').classes('text-md font-semibold mb-2')
                    ui.button('Show Performance Summary', 
                             on_click=lambda: ui.notify(zoom_container.get_performance_summary(), 
                                                       type='info', timeout=10000)).classes('w-full')
                    ui.button('Reset Performance Metrics', 
                             on_click=lambda: (zoom_container.reset_performance_metrics(), 
                                             ui.notify('Performance metrics reset', type='positive'))).classes('w-full')
                
                # Controls documentation
                with ui.column().classes('flex-grow'):
                    ui.label('Keyboard & Mouse Controls').classes('text-lg font-semibold mb-2')
                    ui.markdown('''
                        **Mouse Controls:**
                        - **Mouse wheel**: Zoom in/out
                        - **Click and drag**: Pan around

                        **Keyboard Shortcuts:**
                        - **+ key**: Zoom in
                        - **- key**: Zoom out  
                        - **0 key**: Reset view

                        **Button Controls:**
                        - Use the control buttons for programmatic control
                        - Corner buttons: +/- zoom, home, fit content
                    ''').classes('text-sm')
    
    ui.run()


# Example usage and demo
if __name__ in {'__main__', '__mp_main__'}:
    main()
