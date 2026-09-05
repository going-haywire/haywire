from nicegui import ui, events
from typing import Optional, Callable
import uuid
import logging

from haywire.ui.components.zoom.settings import EditorPanZoomSettings
from haywire.ui.components.minimap.minimap import MinimapCanvas
from haywire.ui.components.debug_overlay.debug_overlay import DebugOverlay

_log = logging.getLogger(__name__)


class ZoomPanContainer(ui.element, component="pan.vue"):
    """
    A Vue-based zoom and pan container for NiceGUI.

    Features:
    - Mouse wheel zoom in/out
    - Click and drag to pan
    - Trackpad pinch to zoom, two-finger swipe to pan
    - Zoom to fit functionality
    - Configurable via EditorPanZoomSettings (live-updates on setting change)

    The viewport is owned by the Vue side; Python holds only the last SETTLED
    value (``pan_x`` / ``pan_y`` / ``current_zoom``), refreshed once per
    gesture. Anything that wants the viewport live is client-side and should
    read the ``zoom-pan-state`` CustomEvent instead, as the minimap and the
    debug overlay do.
    """

    def __init__(
        self,
        initial_zoom: float = 1.0,
        **kwargs,
    ) -> None:
        """
        Initialize the ZoomPanContainer.

        Args:
            initial_zoom: Initial zoom level (default: 1.0)
        """
        self._pz_settings = EditorPanZoomSettings()

        # Generate unique ID for this container
        self.container_id = f"zoom-pan-{uuid.uuid4().hex[:8]}"

        # Called once when the Vue component first mounts (first transform-changed event).
        self._on_ready: Optional[Callable] = None

        # Minimap instance — created in _setup_container after DOM is ready
        self.minimap: Optional["MinimapCanvas"] = None

        # Debug/performance overlay — created in _setup_container after DOM is ready
        self.debug_overlay: Optional["DebugOverlay"] = None

        # Last SETTLED viewport, one update per gesture (see pan.vue's
        # _updateTransformDirect). Held so it can be read synchronously — a
        # client round-trip is not available on the paths that would want it
        # most, such as disconnect or shutdown.
        self.current_zoom = initial_zoom
        self.pan_x = 0.0
        self.pan_y = 0.0

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

    def _apply_settings_props(self) -> None:
        """Push current settings values to Vue props."""
        pz = self._pz_settings
        self._props["max-zoom"] = pz.max_zoom
        self._props["min-zoom"] = pz.min_zoom
        self._props["zoom-sensitivity"] = pz.zoom_sensitivity
        self._props["pan-sensitivity"] = pz.pan_sensitivity
        self._props["lod-enabled"] = pz.lod_enabled

    def _on_setting_changed(self, name: str, value, old) -> None:
        """Propagate a pan/zoom settings change to the Vue component immediately."""
        prop_map = {
            "max_zoom": "max-zoom",
            "min_zoom": "min-zoom",
            "zoom_sensitivity": "zoom-sensitivity",
            "pan_sensitivity": "pan-sensitivity",
            "lod_enabled": "lod-enabled",
        }
        if name in prop_map:
            self._props[prop_map[name]] = value
            self.update()

    def _setup_container(self) -> None:
        """Setup the basic container structure."""
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

        # Minimap is placed in the 'overlay' slot of ZoomPanContainer — a sibling of
        # .zoom-pan-content so it is not affected by the pan/zoom transform, but is
        # still a DOM child of the container div (required for position: absolute).
        with self.add_slot("overlay"):
            self.minimap = MinimapCanvas(zoom_container=self)
            self.debug_overlay = DebugOverlay(zoom_container=self)

    def _handle_transform_changed(self, e: events.GenericEventArguments) -> None:
        """Handle zoom change events from Vue component."""
        try:
            self.pan_x = e.args["panX"]
            self.pan_y = e.args["panY"]
            self.current_zoom = e.args["zoom"]
            if self._on_ready is not None:
                cb_name = self._on_ready.__name__ if hasattr(self._on_ready, "__name__") else self._on_ready
                _log.info(f"[ZoomPan] _on_ready firing, cb={cb_name}")
                cb = self._on_ready
                self._on_ready = None
                cb()
                _log.info("[ZoomPan] _on_ready cb returned")
        except Exception as ex:
            _log.warning(f"ZoomPanContainer._handle_transform_changed: {ex}")

    def set_canvas_size(self, width: int, height: int) -> None:
        """Push new canvas dimensions to the Vue zoom/pan container and minimap."""
        self._props["canvasWidth"] = width
        self._props["canvasHeight"] = height
        self.update()
        if self.minimap:
            self.minimap.set_canvas_size(width, height)

    def zoom_in(self) -> None:
        """Zoom in programmatically."""
        self.run_method("zoomIn")

    def zoom_out(self) -> None:
        """Zoom out programmatically."""
        self.run_method("zoomOut")

    def reset_view(self) -> None:
        """Reset zoom and pan to initial values."""
        self.run_method("resetView")

    def fit_to_content(self) -> None:
        """Automatically fit the content to the container."""
        self.run_method("fitToContent")

    def center_on_content(self) -> None:
        """Fit all content into view. Must be called after Vue component is mounted."""
        _log.info("[ZoomPan] center_on_content → run_method('fitToContent')")
        self.run_method("fitToContent")

    def set_zoom(
        self, zoom: float, center_x: Optional[float] = None, center_y: Optional[float] = None
    ) -> None:
        """Set zoom level programmatically."""
        if center_x is not None and center_y is not None:
            self.run_method("setZoom", zoom, center_x, center_y)
        else:
            self.run_method("setZoom", zoom)

    def set_pan(self, x: float, y: float) -> None:
        """Set pan position programmatically."""
        self.run_method("setPan", x, y)

    def center_on(self, content_x: float, content_y: float) -> None:
        """Pan so that the given content-space point is centered in the viewport.
        Must be called after the Vue component is mounted (_on_ready or later).
        """
        self.run_method("centerOn", content_x, content_y)

    def __enter__(self):
        """Context manager entry - enter the content container if it exists, otherwise self."""
        if hasattr(self, "content_container") and self.content_container:
            return self.content_container.__enter__()
        else:
            return super().__enter__()

    # Canonical context-manager signature; NiceGUI's Element.__exit__ uses *_.
    def __exit__(self, exc_type, exc_value, traceback):  # ty: ignore[invalid-method-override]
        """Context manager exit."""
        if hasattr(self, "content_container") and self.content_container:
            return self.content_container.__exit__(exc_type, exc_value, traceback)
        else:
            return super().__exit__(exc_type, exc_value, traceback)
