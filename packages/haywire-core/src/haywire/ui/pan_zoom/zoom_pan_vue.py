from nicegui import ui, events
from typing import TYPE_CHECKING, Optional, Callable
import uuid
import time

from haywire.ui.pan_zoom.settings import EditorPanZoomSettings
from haywire.ui.minimap.settings import MinimapSettings

if TYPE_CHECKING:
    from haywire.ui.minimap.mini_map_vue import MinimapCanvas


class ZoomPanContainer(ui.element, component="zoom_pan_container.vue"):
    """
    A Vue-based zoom and pan container for NiceGUI.

    Features:
    - Mouse wheel zoom in/out
    - Click and drag to pan
    - Trackpad pinch to zoom, two-finger swipe to pan
    - Zoom to fit functionality
    - Configurable via EditorPanZoomSettings (live-updates on setting change)
    - Event callbacks for zoom/pan changes
    """

    def __init__(
        self,
        initial_zoom: float = 1.0,
        on_zoom_change: Optional[Callable[[float], None]] = None,
        on_pan_change: Optional[Callable[[float, float], None]] = None,
        **kwargs,
    ) -> None:
        """
        Initialize the ZoomPanContainer.

        Args:
            initial_zoom: Initial zoom level (default: 1.0)
            on_zoom_change: Callback fired when zoom changes
            on_pan_change: Callback fired when pan position changes
        """
        self._pz_settings = EditorPanZoomSettings()
        self._mm_settings = MinimapSettings()

        # Generate unique ID for this container
        self.container_id = f"zoom-pan-{uuid.uuid4().hex[:8]}"

        # Store callbacks
        self.on_zoom_change = on_zoom_change
        self.on_pan_change = on_pan_change

        # Minimap instance — created in _setup_container after DOM is ready
        self.minimap: Optional["MinimapCanvas"] = None

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

        # Set initial Vue component props from settings
        self._props["container-id"] = self.container_id
        self._props["initial-zoom"] = initial_zoom
        self._apply_settings_props()

        # Set up Python event handlers
        self.on("transform-changed", self._handle_transform_changed)

        # Subscribe to settings changes — fires via _on_global_change in Settings base
        self._pz_settings.subscribe(self._on_setting_changed)
        self._mm_settings.subscribe(self._on_minimap_setting_changed)

    def _apply_settings_props(self) -> None:
        """Push current settings values to Vue props."""
        pz = self._pz_settings
        self._props["min-zoom"] = pz.min_zoom
        self._props["max-zoom"] = pz.max_zoom
        self._props["zoom-sensitivity"] = pz.zoom_sensitivity
        self._props["pan-sensitivity"] = pz.pan_sensitivity

    def _on_setting_changed(self, name: str, value, old) -> None:
        """Propagate a pan/zoom settings change to the Vue component immediately."""
        prop_map = {
            "min_zoom": "min-zoom",
            "max_zoom": "max-zoom",
            "zoom_sensitivity": "zoom-sensitivity",
            "pan_sensitivity": "pan-sensitivity",
        }
        if name in prop_map:
            self._props[prop_map[name]] = value
            self.update()

    def _on_minimap_setting_changed(self, name: str, value, _old) -> None:
        """Propagate a minimap settings change to the MinimapCanvas instance."""
        if self.minimap is None:
            return
        if name == "enabled":
            self.minimap.set_enabled(value)
        elif name == "position":
            self.minimap.set_position(value)
        elif name == "width":
            self.minimap.set_width(value)

    def _setup_container(self) -> None:
        """Setup the basic container structure."""
        from haywire.ui.minimap.mini_map_vue import MinimapCanvas

        self.classes("zoom-pan-container")
        self.style("position: relative; overflow: hidden; width: 100%; height: 100%;")
        # Set the unique ID
        self.props(f'id="{self.container_id}"')

        # Create the content container that will be transformed
        with self:
            self.content_container = ui.element("div").classes("zoom-pan-content")
            self.content_container.style(
                "position: absolute; "
                "transform-origin: 0 0; "
                "transition: transform 0.2s ease-out; "
                "width: max-content; "
                "height: max-content; "
                "min-width: 100%; "
                "min-height: 100%;"
            )

        # Minimap is placed as a sibling of ZoomPanContainer in the parent context
        # (not inside the slot which feeds into .zoom-pan-content and gets transformed).
        mm = self._mm_settings
        self.minimap = MinimapCanvas(
            zoom_container=self,
            width=mm.width,
            position=mm.position,
            visible=mm.enabled,
        )

    def _handle_transform_changed(self, e: events.GenericEventArguments) -> None:
        """Handle zoom change events from Vue component."""
        try:
            self.pan_x = e.args["panX"]
            self.pan_y = e.args["panY"]
            self.current_zoom = e.args["zoom"]
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
                "fps": fps,
                "total_updates": self.update_count,
                "time_since_last_update": time_since_last_update,
                "current_zoom": self.current_zoom,
                "pan_x": self.pan_x,
                "pan_y": self.pan_y,
            }
        except Exception:
            return {
                "fps": 0,
                "total_updates": 0,
                "time_since_last_update": 0,
                "current_zoom": self.current_zoom,
                "pan_x": self.pan_x,
                "pan_y": self.pan_y,
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
        self.run_method("$el._zoomPanControls.zoomIn")

    def zoom_out(self) -> None:
        """Zoom out programmatically."""
        self.run_method("$el._zoomPanControls.zoomOut")

    def reset_view(self) -> None:
        """Reset zoom and pan to initial values."""
        self.run_method("$el._zoomPanControls.reset")

    def fit_to_content(self) -> None:
        """Automatically fit the content to the container."""
        self.run_method("$el._zoomPanControls.fitToContent")

    def set_zoom(
        self, zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None
    ) -> None:
        """Set zoom level programmatically."""
        if center_x is not None and center_y is not None:
            self.run_method("$el._zoomPanControls.setZoom", zoom, center_x, center_y)
        else:
            self.run_method("$el._zoomPanControls.setZoom", zoom)

    def set_pan(self, x: float, y: float) -> None:
        """Set pan position programmatically."""
        self.run_method("$el._zoomPanControls.setPan", x, y)

    def center_on(self, content_x: float, content_y: float) -> None:
        """Pan so that the given content-space point is centered in the viewport."""
        ui.run_javascript(f"""
            const el = document.getElementById('{self.container_id}');
            if (el && el._zoomPanControls) {{
                const rect = el.getBoundingClientRect();
                const zoom = el._zoomPanControls.getZoom();
                el._zoomPanControls.setPan(
                    rect.width  / 2 - {content_x} * zoom,
                    rect.height / 2 - {content_y} * zoom
                );
            }}
        """)

    def __enter__(self):
        """Context manager entry - enter the content container if it exists, otherwise self."""
        if hasattr(self, "content_container") and self.content_container:
            return self.content_container.__enter__()
        else:
            return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit."""
        if hasattr(self, "content_container") and self.content_container:
            return self.content_container.__exit__(exc_type, exc_value, traceback)
        else:
            return super().__exit__(exc_type, exc_value, traceback)


def create_zoom_pan_controls(container: ZoomPanContainer) -> None:
    """Create standard zoom/pan control buttons."""
    with ui.element("div").classes("zoom-pan-controls"):
        ui.button("+", on_click=container.zoom_in).props("round dense").classes("text-xs")
        ui.button("−", on_click=container.zoom_out).props("round dense").classes("text-xs")
        ui.button("⌂", on_click=container.reset_view).props("round dense").classes("text-xs")
        ui.button("⛶", on_click=container.fit_to_content).props("round dense").classes("text-xs")


def create_zoom_pan_info(container: ZoomPanContainer) -> ui.label:
    """Create info display with comprehensive performance metrics
    for current zoom and pan values."""
    info_label = ui.label().classes("zoom-pan-info")

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
                zoom = metrics["current_zoom"]
            if pan_x is None:
                pan_x = metrics["pan_x"]
            if pan_y is None:
                pan_y = metrics["pan_y"]

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
                f"Zoom: {zoom:.2f} ({zoom_class}) | "
                f"Pan: ({pan_x:.0f}, {pan_y:.0f}) | "
                f"Container FPS: {metrics['fps']} | "
                f"Info FPS: {info_fps} | "
                f"Updates: {metrics['total_updates']} | "
                f"Uptime: {uptime:.1f}s"
            )

            # Add performance warnings if needed
            if metrics["fps"] > 60:
                info_text += " | ⚡ High Performance"
            elif metrics["fps"] < 10 and metrics["fps"] > 0:
                info_text += " | ⚠️ Low Performance"
            elif metrics["time_since_last_update"] > 1.0:
                info_text += " | 💤 Idle"

            info_label.set_text(info_text)
            info_label.update()
        except Exception as e:
            # Fallback display on error
            error_text = f"Error: {str(e)[:50]}..." if len(str(e)) > 50 else f"Error: {str(e)}"
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
